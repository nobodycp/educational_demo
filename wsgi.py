"""
WSGI entry for Gunicorn in Docker/production.
"""
from __future__ import annotations

from backend.app import app  # re-export the Flask app factory result

# ``create_app()`` is already called in backend.app
__all__ = ["app"]
