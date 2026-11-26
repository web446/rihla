"""Business logic shared by the web pages.

Routes (blueprints/) never change the database directly for bookings:
they call these functions, so the rules exist once.
"""
