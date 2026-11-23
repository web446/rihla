"""Business logic shared by the web pages AND the AI agent.

Routes (blueprints/) and AI tools (agent/) never change the database
directly for bookings: they call these functions, so the rules exist once.
"""
