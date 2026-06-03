"""
WSGI entry for Gunicorn in Docker/production.
"""
from __future__ import annotations

from backend.app import app  # re-export the Flask app instance

__all__ = ["app"]
