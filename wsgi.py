"""
WSGI entry for Gunicorn (native install, no Docker).
"""
from __future__ import annotations

from backend.app import app  # re-export the Flask app instance

__all__ = ["app"]
