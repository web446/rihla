"""JSON API for the chat window (called with fetch() from static/js/chat.js).

POST /api/chat                      {"conversation_id": 3 | null, "message": "..."}
POST /api/confirm/<proposal_id>     the Confirm button on a summary card
POST /api/decline/<proposal_id>     the "Not now" button
GET  /api/conversations             the user's past chats
GET  /api/conversations/<id>        the messages of one chat

All POSTs need the CSRF token in the "X-CSRF-Token" header (checked in security.py).
"""
from functools import wraps

from flask import Blueprint, g, jsonify, request

from agent import chat

agent_bp = Blueprint("agent", __name__, url_prefix="/api")


def traveler_json(view):
    """Like role_required("traveler"), but answers in JSON instead of redirecting."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return jsonify({"error": "Please log in to chat with the travel agent."}), 401
        if g.user.role != "traveler":
            return jsonify({"error": "The travel agent is for traveler accounts."}), 403
        try:
            return view(*args, **kwargs)
        except chat.ChatError as error:
            return jsonify({"error": str(error)}), error.status
    return wrapped


@agent_bp.route("/chat", methods=["POST"])
@traveler_json
def send_message():
    data = request.get_json(silent=True) or {}
    conversation_id = data.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, int):
        conversation_id = None
    return jsonify(chat.handle_message(g.user, conversation_id, data.get("message")))


@agent_bp.route("/confirm/<int:proposal_id>", methods=["POST"])
@traveler_json
def confirm(proposal_id):
    return jsonify(chat.confirm(g.user, proposal_id))


@agent_bp.route("/decline/<int:proposal_id>", methods=["POST"])
@traveler_json
def decline(proposal_id):
    return jsonify(chat.decline(g.user, proposal_id))


@agent_bp.route("/conversations")
@traveler_json
def conversations():
    return jsonify({"mode": chat.mode(), "conversations": chat.list_conversations(g.user)})


@agent_bp.route("/conversations/<int:conversation_id>")
@traveler_json
def conversation(conversation_id):
    conv = chat.get_conversation(g.user, conversation_id)
    if conv is None:
        return jsonify({"error": "Conversation not found."}), 404
    return jsonify({"conversation_id": conv.id, "mode": chat.mode(), "messages": chat.display_messages(conv)})
