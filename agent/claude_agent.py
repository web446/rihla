"""The real AI travel agent: Claude + tool calling (the "agent loop").

How one turn works:
  1. We send Claude the conversation, a system prompt and the 9 tool schemas.
  2. Claude either answers with text (done) or asks to use tools (stop_reason
     "tool_use") with arguments, e.g. search_flights(to_country="Italy").
  3. OUR server runs each tool with run_tool() for the logged-in user, and
     sends the results back as "tool_result" blocks.
  4. Repeat until Claude answers with text, at most MAX_TOOL_ROUNDS times.

Claude never touches the database itself: it can only ask for our tools, and
the booking tool only PREPARES a proposal that the user must confirm.

The API key lives in .env on the server (AI_API_KEY) and is never sent to the browser.
"""
import anthropic
from flask import current_app

from agent.tools import TOOLS, result_to_json, run_tool

MAX_TOOL_ROUNDS = 6
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Frozen for every conversation (it is part of what Claude's earlier reasoning
# is tied to, so it must not change between requests). Today's date is
# therefore sent inside each user message instead of here.
SYSTEM_PROMPT = """You are Rihla, the friendly AI travel agent of the Rihla travel website.
Rihla sells round-trip flights from Beirut, hotels and apartments, and approved local guides in a few countries.
Rihla's travelers hold Lebanese passports, and every destination can be entered without arranging a visa in advance (some under conditions).

Rules:
- Use ONLY information returned by your tools. Never invent countries, flights, prices, hotels, guides, dates or availability. If the tools don't have something, say so.
- Entry rules (visa, maximum stay, conditions) come ONLY from the tools' entry fields. Mention conditions clearly (e.g. Egypt is visa-free only in some cases, Georgia requires health insurance) and remind the traveler that rules can change.
- Prices are in US dollars. Flights only depart from Beirut.
- When the traveler hasn't chosen a destination, call search_countries. Before proposing a flight, stay or guide, look it up with the search tools and use the ids they return.
- The results of search tools are shown to the traveler as cards automatically, so summarize briefly instead of repeating every detail.
- To book or cancel, call create_booking or cancel_booking. These only PREPARE a summary: the traveler must click Confirm (or type "confirm"). Never say a trip is booked or cancelled until you see a confirmation message in the conversation.
- Before preparing a booking, make sure the traveler agreed on the items, the number of seats and the nights.
- Ask a short question when something important is missing (month, budget, number of travelers).
- Keep answers short and warm: 1-4 sentences, plain text, no tables."""


class AgentUnavailable(Exception):
    """The AI couldn't answer (no key, bad key, network...). The caller falls back to demo mode."""


def make_client():
    return anthropic.Anthropic(api_key=current_app.config["AI_API_KEY"], timeout=60.0, max_retries=2)


def _without_gemini_fields(messages):
    """Turns written by the Gemini agent keep Gemini's "thought signature" in an extra
    "gemini_signature" field of their tool_use blocks. Claude doesn't know that field,
    so it is left out here. Claude's own blocks never have it, so they are sent unchanged."""
    cleaned = []
    for message in messages:
        content = message["content"]
        if isinstance(content, list) and any("gemini_signature" in b for b in content):
            content = [{k: v for k, v in b.items() if k != "gemini_signature"} for b in content]
        cleaned.append({**message, "content": content})
    return cleaned


def _create(client, messages):
    cfg = current_app.config
    model = cfg["AI_MODEL"] if cfg["AI_MODEL"].startswith("claude") else "claude-opus-5-5"
    return client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=_without_gemini_fields(messages),
        output_config={"effort": cfg["AI_EFFORT"]},
        # If Claude's safety filter declines a request, Anthropic re-runs it on a
        # fallback model inside the same call instead of failing.
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )


def _strip_thinking(messages):
    """Recovery only: remove thinking blocks from the history (text and tool calls stay)."""
    cleaned = []
    for message in messages:
        content = message["content"]
        if isinstance(content, list):
            content = [b for b in content if b.get("type") not in ("thinking", "redacted_thinking")]
        cleaned.append({**message, "content": content})
    return cleaned


def run_turn(messages, user, conversation_id, save):
    """Run the agent loop for one user message.

    messages : the full API history (ending with the new user message). Appended to in place.
    save     : save(role, api_content, text, cards) stores each step in the database.
    Returns (final_text, cards).
    """
    client = make_client()
    cards = []
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            try:
                response = _create(client, messages)
            except anthropic.BadRequestError as error:
                # Safety net: if the API says an old thinking block no longer matches the
                # conversation, retry once without thinking blocks (see README).
                if "thinking" not in str(error):
                    raise
                response = _create(client, _strip_thinking(messages))
        except anthropic.APIError as error:   # bad key, rate limit, network, server error
            raise AgentUnavailable(type(error).__name__) from error

        if response.stop_reason == "refusal":
            # Not added to the API history (an unfinished turn), only shown to the user.
            text = "Sorry, I can't help with that. I can plan trips, find flights, stays and guides, and manage bookings."
            save("assistant", None, text, cards)
            return text, cards

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text = "\n\n".join(b.text for b in response.content if b.type == "text").strip()

        if response.stop_reason == "max_tokens" and tool_uses:
            # The tool call may be cut off: never run it.
            text = "Sorry, that answer got too long. Could you ask again in a simpler way?"
            save("assistant", None, text, cards)
            return text, cards

        # Save Claude's reply EXACTLY as received (thinking + text + tool_use blocks).
        assistant_content = [block.to_dict() for block in response.content]
        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason != "tool_use" or not tool_uses:
            save("assistant", assistant_content, text, cards)   # final answer: cards shown under it
            return text, cards

        # In-between steps ("Let me look...") are kept for the API but not shown in the chat.
        save("assistant", assistant_content, "", None)
        # Run every requested tool and send ALL results back in ONE user message.
        results = []
        for block in tool_uses:
            result = run_tool(block.name, block.input, user, conversation_id)
            cards.extend(result.cards)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": result_to_json(result), "is_error": result.is_error})
        messages.append({"role": "user", "content": results})
        save("tool", results, "", None)

    text = "That took me too many steps. Could you tell me a bit more precisely what you need?"
    save("assistant", None, text, cards)
    return text, cards
