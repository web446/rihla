"""The AI travel agent.

tools.py       the 9 tools (functions on top of services/) + their JSON schemas
proposals.py   bookings/cancellations the agent PREPARES; only the user confirms them
claude_agent.py the Claude API tool loop (when AI_PROVIDER=claude and a key is set)
demo_agent.py  rule-based fallback that calls the same tools (no API key needed)
chat.py        saving conversations, rate limit, choosing the mode
"""
