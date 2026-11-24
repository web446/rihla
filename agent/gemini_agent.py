"""The real AI travel agent with Google Gemini (free tier) + function calling.

It works exactly like claude_agent.py, with the same rules, the same 9 tools and
the same "summary -> Confirm" safety rule. Only the way we talk to the AI changes:
  1. We send Gemini the conversation, the system prompt and the 9 tool declarations.
  2. Gemini either answers with text (done) or asks to call tools ("function calls").
  3. OUR server runs each tool with run_tool() for the logged-in user and sends
     the results back as "function responses".
  4. Repeat until Gemini answers with text, at most MAX_TOOL_ROUNDS times.

Saving the history: every step is saved in the SAME block format as the Claude
agent ({"type": "text"}, {"type": "tool_use"}, {"type": "tool_result"}), so a chat
can continue even if the site is switched from one AI provider to the other.

The API key lives in .env on the server (AI_API_KEY) and is never sent to the browser.
"""
import base64
import json
import uuid

from flask import current_app
from google import genai
from google.genai import errors, types

# Both agents share the same rules and the same error type.
from agent.claude_agent import SYSTEM_PROMPT, AgentUnavailable
from agent.tools import TOOLS, result_to_json, run_tool

# Free-tier model. In our tests (November 2026) the bigger free models were often "overloaded"
# or took 30+ seconds, while flash-lite answered in a few seconds and used the tools well.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
MAX_TOOL_ROUNDS = 6
# Gemini 3 models attach a "thought signature" to their tool calls and expect it back.
# A tool call saved without one (e.g. written by Claude) is sent with this documented placeholder.
NO_SIGNATURE = b"skip_thought_signature_validator"
BLOCKED = {types.FinishReason.SAFETY, types.FinishReason.PROHIBITED_CONTENT, types.FinishReason.BLOCKLIST,
           types.FinishReason.SPII, types.FinishReason.RECITATION}


# ---------------------------------------------------------------------------
# Tool declarations: the same 9 tools as Claude, in a simpler schema
# ---------------------------------------------------------------------------
def _gemini_schema(input_schema):
    """Claude's strict schemas write optional values as "X or null" and list every field
    as required. For Gemini we keep plain types and only require the truly required ones."""
    properties, required = {}, []
    for name, prop in input_schema["properties"].items():
        if "anyOf" in prop:   # optional: keep the non-null type
            base = next(option for option in prop["anyOf"] if option.get("type") != "null")
            properties[name] = {**base, "description": prop["description"]}
        else:
            properties[name] = dict(prop)
            required.append(name)
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _declaration(tool):
    if not tool["input_schema"]["properties"]:   # list_my_bookings takes no arguments
        return types.FunctionDeclaration(name=tool["name"], description=tool["description"])
    return types.FunctionDeclaration(name=tool["name"], description=tool["description"],
                                     parameters_json_schema=_gemini_schema(tool["input_schema"]))


FUNCTIONS = [_declaration(tool) for tool in TOOLS]
TOOL_FIELDS = {tool["name"]: list(tool["input_schema"]["properties"]) for tool in TOOLS}


def clean_args(name, args):
    """Make Gemini's arguments look like Claude's: every field present (None when not given),
    and whole numbers as int (Gemini sends numbers like 12 as 12.0)."""
    def fix(value):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [fix(v) for v in value]
        if isinstance(value, dict):
            return {k: fix(v) for k, v in value.items()}
        return value
    args = fix(dict(args or {}))
    for field in TOOL_FIELDS.get(name, []):
        args.setdefault(field, None)
    return args


# ---------------------------------------------------------------------------
# History: saved blocks <-> Gemini "Content" objects
# ---------------------------------------------------------------------------
def _response_dict(text_json, is_error):
    """A tool result for Gemini must be a JSON object."""
    try:
        data = json.loads(text_json)
    except (TypeError, ValueError):
        data = text_json
    return {"error": data} if is_error else {"output": data}


def to_gemini(history):
    """Rebuild Gemini's contents from the saved blocks (thinking blocks from Claude are skipped)."""
    contents, tool_names = [], {}
    for message in history:
        blocks = message["content"]
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        parts = []
        for block in blocks:
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                parts.append(types.Part(text=block["text"]))
            elif kind == "tool_use":
                tool_names[block["id"]] = block["name"]
                signature = block.get("gemini_signature")
                parts.append(types.Part(
                    function_call=types.FunctionCall(name=block["name"], args=block["input"]),
                    thought_signature=base64.b64decode(signature) if signature else NO_SIGNATURE))
            elif kind == "tool_result":
                parts.append(types.Part(function_response=types.FunctionResponse(
                    name=tool_names.get(block["tool_use_id"], "unknown"),
                    response=_response_dict(block.get("content"), block.get("is_error")))))
        if not parts:
            continue
        role = "model" if message["role"] == "assistant" else "user"
        if contents and contents[-1].role == role:   # two messages in a row from the same side: merge
            contents[-1].parts.extend(parts)
        else:
            contents.append(types.Content(role=role, parts=parts))
    return contents


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------
def make_client():
    return genai.Client(api_key=current_app.config["AI_API_KEY"],
                        http_options=types.HttpOptions(timeout=60_000))   # milliseconds


def model_name():
    model = current_app.config["AI_MODEL"] or DEFAULT_MODEL
    return model if model.startswith("gemini") else DEFAULT_MODEL   # e.g. a Claude model left in .env


def _config(with_thinking=True):
    effort = current_app.config["AI_EFFORT"]
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=FUNCTIONS)],
        # WE run the tools ourselves (for the logged-in user), never the SDK.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=effort) if with_thinking and effort else None,
        max_output_tokens=16000,
    )


def _generate(client, contents):
    model = model_name()
    try:
        return client.models.generate_content(model=model, contents=contents, config=_config())
    except errors.ClientError as error:
        # Some models don't accept a thinking level: try once without it.
        if "thinking" not in str(error).lower():
            raise
        return client.models.generate_content(model=model, contents=contents, config=_config(False))
    except errors.ServerError:
        # 503 "high demand" / 504 timeout: free models are sometimes overloaded.
        # Try once with the default (lighter) model before giving up.
        if model == DEFAULT_MODEL:
            raise
        current_app.logger.warning("%s is overloaded, retrying with %s", model, DEFAULT_MODEL)
        return client.models.generate_content(model=DEFAULT_MODEL, contents=contents, config=_config())


def run_turn(messages, user, conversation_id, save):
    """Run the agent loop for one user message (same contract as claude_agent.run_turn).

    messages : the saved history (ending with the new user message). Appended to in place.
    save     : save(role, blocks, text, cards) stores each step in the database.
    Returns (final_text, cards).
    """
    client = make_client()
    contents = to_gemini(messages)
    cards = []
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = _generate(client, contents)
        except errors.APIError as error:   # bad key, free-tier limit reached, network, server error
            raise AgentUnavailable(f"{type(error).__name__} {getattr(error, 'code', '')}") from error

        candidate = response.candidates[0] if response.candidates else None
        parts = (candidate.content.parts or []) if candidate and candidate.content else []
        finish = candidate.finish_reason if candidate else None
        if not parts:
            if finish in BLOCKED or (response.prompt_feedback and response.prompt_feedback.block_reason):
                text = "Sorry, I can't help with that. I can plan trips, find flights, stays and guides, and manage bookings."
            else:
                text = "Sorry, I couldn't answer that. Could you ask again in another way?"
            save("assistant", None, text, cards)   # not added to the AI history
            return text, cards

        calls = [part for part in parts if part.function_call]
        text = "\n\n".join(part.text for part in parts if part.text and not part.thought).strip()
        if finish == types.FinishReason.MAX_TOKENS and calls:
            text = "Sorry, that answer got too long. Could you ask again in a simpler way?"
            save("assistant", None, text, cards)
            return text, cards

        # Keep Gemini's reply EXACTLY as received for the next request of this turn
        # (it carries the thought signatures), and save it as blocks.
        contents.append(candidate.content)
        blocks, ids = [], []
        for part in parts:
            if part.text and not part.thought:
                blocks.append({"type": "text", "text": part.text})
            elif part.function_call:
                block_id = "toolu_" + uuid.uuid4().hex[:24]
                ids.append(block_id)
                block = {"type": "tool_use", "id": block_id, "name": part.function_call.name,
                         "input": clean_args(part.function_call.name, part.function_call.args)}
                if part.thought_signature:
                    block["gemini_signature"] = base64.b64encode(part.thought_signature).decode()
                blocks.append(block)

        if not calls:
            if not text:
                text = "Sorry, I don't have an answer for that. Could you ask in another way?"
                blocks = [{"type": "text", "text": text}]
            messages.append({"role": "assistant", "content": blocks})
            save("assistant", blocks, text, cards)   # final answer: cards shown under it
            return text, cards

        messages.append({"role": "assistant", "content": blocks})
        save("assistant", blocks, "", None)   # in-between step, not shown in the chat
        # Run every requested tool and send ALL results back together.
        results, response_parts = [], []
        for part, block_id in zip(calls, ids):
            call = part.function_call
            args = clean_args(call.name, call.args)
            result = run_tool(call.name, args, user, conversation_id)
            cards.extend(result.cards)
            result_json = result_to_json(result)
            results.append({"type": "tool_result", "tool_use_id": block_id,
                            "content": result_json, "is_error": result.is_error})
            response_parts.append(types.Part(function_response=types.FunctionResponse(
                id=call.id, name=call.name, response=_response_dict(result_json, result.is_error))))
        contents.append(types.Content(role="user", parts=response_parts))
        messages.append({"role": "user", "content": results})
        save("tool", results, "", None)

    text = "That took me too many steps. Could you tell me a bit more precisely what you need?"
    save("assistant", None, text, cards)
    return text, cards
