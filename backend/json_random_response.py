"""
Educational lab: non-deterministic JSON shape (key order, whitespace) and optional
status-code pools for the same error class, to complicate static fingerprinting of API responses.

**Defensive concept:** *response homogeneity / evasion* — not a security boundary; clients use JSON.parse.
"""

from __future__ import annotations

import json
import random
from typing import Any

from flask import Response


def _shuffle_key_order(data: dict[str, Any]) -> dict[str, Any]:
    items = list(data.items())
    random.shuffle(items)
    return dict(items)


def _resolve_status(
    base_status: int, status_pool: str | None
) -> int:
    if status_pool == "bot":
        return random.choice((400, 403, 401))
    if status_pool == "rate":
        return random.choice((429, 503, 403))
    if status_pool == "session":
        return random.choice((403, 401))
    return base_status


def make_randomized_json_response(
    data: dict[str, Any],
    status: int = 200,
    *,
    status_pool: str | None = None,
) -> Response:
    """
    Shuffle top-level key order, randomly compact or pretty-print, optionally remap HTTP status
    (``status_pool``: ``"bot"`` | ``"rate"`` | ``"session"``) for the same logical error.
    """
    d = _shuffle_key_order(data)
    code = _resolve_status(status, status_pool)
    if random.random() < 0.5:
        body = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    else:
        ind = random.choice((1, 2, 3, 4))
        body = json.dumps(d, ensure_ascii=False, indent=ind)
    return Response(
        body,
        status=code,
        mimetype="application/json; charset=utf-8",
    )
