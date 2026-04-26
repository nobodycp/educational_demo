"""
Run the server from the project root:

    python app.py

Implementation lives in ``backend/``; browser assets live in ``frontend/``.
"""
from __future__ import annotations

import os

from backend.app import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
