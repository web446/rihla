"""Conversations: saving messages, rate limiting, choosing Claude or demo mode.

Every chat message is a row in chat_messages:
  role      user | assistant | tool
  content   the text shown in the chat window
  cards     JSON list of cards shown under it
  api_json  the exact blocks sent to / received from Claude (replayed to continue a chat)
"""
import json
import re
from datetime import date, datetime, timedelta

from flask import current_app

from extensions import db
from models import ChatConversation, ChatMessage

from agent import claude_agent, proposals
from agent.demo_agent import DemoAgent

CONFIRM_WORDS = re.compile(r"^\s*(yes[,!.]?\s*)?(confirm|confirmed|book it|go ahead)\s*[.!]*\s*$", re.IGNORECASE)
MAX_USER_MESSAGES_PER_CHAT = 60


class ChatError(Exception):
    """Shown to the user as-is. `status` is the HTTP status code (429 = too many messages)."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def mode():
    cfg = current_app.config
    return "claude" if cfg["AI_PROVIDER"] == "claude" and cfg["AI_API_KEY"] else "demo"


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
def get_conversation(user, conversation_id):
    """The user's own conversation, or None. Never someone else's."""
    if not conversation_id:
        return None
    conversation = db.session.get(ChatConversation, conversation_id)
    return conversation if conversation and conversation.user_id == user.id else None


def list_conversations(user):
    rows = db.session.execute(
        db.select(ChatConversation).where(ChatConversation.user_id == user.id)
        .order_by(ChatConversation.updated_at.desc()).limit(20)
    ).scalars().all()
    return [{"id": c.id, "title": c.title, "updated": c.updated_at.strftime("%d %b %H:%M")} for c in rows]


def display_messages(conversation):
    """What the chat window shows: user + assistant messages with text or cards."""
    out = []
    for m in conversation.messages:
        cards = json.loads(m.cards_json) if m.cards_json else []
        for card in cards:   # old summaries: show whether they were confirmed or are closed
            if card.get("type") == "summary":
                proposal = db.session.get(proposals.BookingProposal, card["proposal_id"])
                card["status"] = proposal.status if proposal else "expired"
        if m.role in ("user", "assistant") and (m.content or cards):
            out.append({"role": m.role, "text": m.content, "cards": cards})
    return out


def _save(conversation, role, api_content, text, cards):
    db.session.add(ChatMessage(
        conversation_id=conversation.id, role=role, content=text or "",
        cards_json=json.dumps(cards) if cards else None,
        api_json=json.dumps(api_content) if api_content is not None else None,
    ))
    conversation.updated_at = datetime.now()
    db.session.commit()


def _api_history(conversation):
    """Rebuild the Claude API messages from the saved rows, unchanged and in order."""
    history = []
    for m in conversation.messages:
        if m.api_json:
            history.append({"role": "assistant" if m.role == "assistant" else "user",
                            "content": json.loads(m.api_json)})
    return history


def _text_block(text):
    return [{"type": "text", "text": text}]


def _check_rate_limit(user):
    """Count this user's messages in the last hour, across all their chats."""
    limit = current_app.config["CHAT_LIMIT_PER_HOUR"]
    since = datetime.now() - timedelta(hours=1)
    sent = db.session.execute(
        db.select(db.func.count(ChatMessage.id)).join(ChatConversation)
        .where(ChatConversation.user_id == user.id, ChatMessage.role == "user", ChatMessage.created_at >= since)
    ).scalar()
    if sent >= limit:
        raise ChatError(f"You've reached the limit of {limit} messages per hour. Please try again a bit later.", 429)


# ---------------------------------------------------------------------------
# Handling a message
# ---------------------------------------------------------------------------
def handle_message(user, conversation_id, text):
    """Returns {"conversation_id", "mode", "messages": [new display messages]}."""
    text = (text or "").strip()
    if not text:
        raise ChatError("Please type a message.")
    if len(text) > 1000:
        raise ChatError("That message is too long (1000 characters max).")
    _check_rate_limit(user)

    conversation = get_conversation(user, conversation_id)
    if conversation is None:
        conversation = ChatConversation(user_id=user.id, title=text[:60])
        db.session.add(conversation)
        db.session.commit()
    elif sum(1 for m in conversation.messages if m.role == "user") >= MAX_USER_MESSAGES_PER_CHAT:
        raise ChatError("This chat is very long. Please start a new chat with the ＋ button.")

    # Typing "confirm" confirms the latest summary directly: no AI involved.
    pending = proposals.latest_pending(user, conversation.id)
    if pending and CONFIRM_WORDS.match(text):
        return confirm(user, pending.id, conversation, typed_text=text)

    # The date goes INSIDE the user message (the system prompt never changes).
    _save(conversation, "user", _text_block(f"[Today is {date.today():%A %d %B %Y}] {text}"), text, None)
    current_mode = mode()
    note = ""
    if current_mode == "claude":
        messages = _api_history(conversation)
        save = lambda role, api, t, cards: _save(conversation, role, api, t, cards)
        try:
            reply, cards = claude_agent.run_turn(messages, user, conversation.id, save)
            return _response(conversation, "claude", reply, cards)
        except claude_agent.AgentUnavailable as error:
            current_app.logger.warning("Claude unavailable (%s), using demo mode", error)
            current_mode, note = "demo", "⚠️ The AI service is unavailable right now, so I answered in demo mode. "

    reply, cards = DemoAgent(user, conversation.id).reply(text)
    reply = note + reply
    _save(conversation, "assistant", _text_block(reply), reply, cards)
    return _response(conversation, current_mode, reply, cards)


def confirm(user, proposal_id, conversation=None, typed_text="Confirm"):
    """The Confirm button (or typing "confirm"): books through services/booking.py."""
    proposal = db.session.get(proposals.BookingProposal, proposal_id)
    conversation = conversation or get_conversation(user, proposal.conversation_id if proposal else None)
    if conversation is None:
        raise ChatError("I couldn't find that booking summary.")
    _save(conversation, "user", _text_block(typed_text), typed_text, None)
    try:
        reply, cards = proposals.confirm(proposal_id, user)
    except proposals.ProposalError as error:
        reply, cards = str(error), []
    _save(conversation, "assistant", _text_block(reply), reply, cards)
    return _response(conversation, mode(), reply, cards, user_text=typed_text)


def decline(user, proposal_id):
    proposal = db.session.get(proposals.BookingProposal, proposal_id)
    conversation = get_conversation(user, proposal.conversation_id if proposal else None)
    if conversation is None:
        raise ChatError("I couldn't find that booking summary.")
    _save(conversation, "user", _text_block("Don't book this."), "Don't book this.", None)
    try:
        reply = proposals.decline(proposal_id, user)
    except proposals.ProposalError as error:
        reply = str(error)
    _save(conversation, "assistant", _text_block(reply), reply, None)
    return _response(conversation, mode(), reply, [], user_text="Don't book this.")


def _response(conversation, current_mode, reply, cards, user_text=None):
    messages = [{"role": "assistant", "text": reply, "cards": cards}]
    if user_text:
        messages.insert(0, {"role": "user", "text": user_text, "cards": []})
    return {"conversation_id": conversation.id, "mode": current_mode, "messages": messages}
