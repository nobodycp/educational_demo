"""
Optional **lab** hardening: polymorphic class maps (XOR, shared with ``gate_engine``),
DOM noise filter, request jitter, IP blocklist, and optional UA check at the gate vs
later ``/api/*`` calls.

FOR AUTHORIZED TRAINING LABS — not a production anti-RE product. Client “protections”
are bypassable; this layer adds **pedagogical friction** and pairs with
``static/js/shell-guard.js`` (timing trap, right-click, redirect).
"""

from __future__ import annotations

import json
import os
import random
import re
import secrets
import time
from html import escape

from flask import g, has_request_context, make_response, request, session
from markupsafe import Markup
from werkzeug import Response

from backend import gate_engine


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _jitter_max_ms() -> int:
    try:
        v = int((os.environ.get("DEMO_RESPONSE_JITTER_MS_MAX") or "0").strip() or 0, 10)
    except (TypeError, ValueError):
        return 0
    return max(0, min(2000, v))


def _ip_blocklist() -> frozenset[str]:
    raw = (os.environ.get("DEMO_IP_BLOCKLIST") or "").strip()
    if not raw:
        return frozenset()
    parts = re.split(r"[\s,;]+", raw)
    return frozenset(p.strip() for p in parts if p.strip())


def _client_ip() -> str:
    raw = (request.remote_addr or "").strip() or "unknown"
    if raw in ("::1", "0:0:0:0:0:0:0:1"):
        return "127.0.0.1"
    return raw


def _shuffled_error(body: dict, status: int) -> object:
    items = list(body.items())
    random.shuffle(items)
    out = json.dumps(dict(items), ensure_ascii=False, separators=(",", ":"))
    return Response(
        out, status=status, mimetype="application/json; charset=utf-8"
    )


def _init_request_state() -> None:
    g.lab_shield_xor_key = secrets.token_hex(8)
    labels = ("lab-sh-ctx", "lab-sh-nav", "lab-sh-decoy")
    g.lab_shield_map = gate_engine.build_ui_class_map(
        list(labels), g.lab_shield_xor_key
    )
    g.lab_shield_map_json = json.dumps(
        g.lab_shield_map, ensure_ascii=False, separators=(",", ":")
    )
    p = (request.path or "")
    g.lab_shield_head_order = [0, 1, 2]
    if p == "/start":
        random.shuffle(g.lab_shield_head_order)


def dom_noise_filter(n: int) -> Markup:
    """Renders *hidden* spans with random ``data-*`` attributes (DOM tree noise)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 3
    n = max(1, min(24, n))
    parts: list[str] = []
    for _ in range(n):
        a = secrets.token_hex(3)
        b = secrets.token_hex(4)
        c = secrets.token_hex(2)
        parts.append(
            f'<span class="select-none" aria-hidden="true" data-z="{escape(a)}" data-v="{escape(b)}" data-i="{c}">.</span>'
        )
    return Markup("".join(parts))


def _ua_equal(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    return secrets.compare_digest(
        a.encode("utf-8", errors="replace"), b.encode("utf-8", errors="replace")
    )


def _before_request_ua_mismatch(SESSION_CLIENT_UA: str) -> object | None:
    if not _truthy("DEMO_UA_MISMATCH_BLOCK"):
        return None
    p = (request.path or "")
    if not p.startswith("/api/"):
        return None
    snap = (session.get(SESSION_CLIENT_UA) or "")[:512] if session else ""
    if not snap:
        return None
    cur = (request.headers.get("User-Agent") or "")[:512]
    if _ua_equal(snap, cur):
        return None
    body = {
        "ok": False,
        "error": "user_agent_mismatch",
        "detail": "session_ua",
    }
    st = 403
    if _truthy("DEMO_UA_MISMATCH_VARIABLE_STATUS"):
        st = random.choice((400, 403, 429))
    if _truthy("DEMO_LAB_SHUFFLE_ERROR_JSON"):
        return _shuffled_error(body, st)
    from flask import jsonify

    return make_response(jsonify(body), st)


def _before_request_ip() -> object | None:
    deny = _ip_blocklist()
    if not deny:
        return None
    path = request.path or ""
    if path.startswith("/static/"):
        return None
    ip = _client_ip()
    if ip not in deny:
        return None
    if path.startswith("/api/"):
        b = {"ok": False, "error": "ip_blocked", "detail": "blocklist"}
        if _truthy("DEMO_LAB_SHUFFLE_ERROR_JSON"):
            return _shuffled_error(b, 403)
        from flask import jsonify

        return make_response(jsonify(b), 403)
    return make_response("Forbidden", 403, {"Content-Type": "text/plain; charset=utf-8"})


def _before_request_jitter() -> None:
    mx = _jitter_max_ms()
    if mx <= 0:
        return
    if (request.path or "").startswith("/static/"):
        return
    time.sleep(random.uniform(0, mx / 1000.0))


def init_app(app, *, SESSION_CLIENT_UA: str) -> None:
    @app.context_processor
    def _lab_shield_inject() -> dict:
        if not has_request_context():
            return {}
        if not hasattr(g, "lab_shield_xor_key"):
            _init_request_state()
        return {
            "lab_shield_key": g.lab_shield_xor_key,
            "lab_shield_map_json": g.lab_shield_map_json,
            "lab_shield_map": g.lab_shield_map,
            "lab_shield_head_order": getattr(
                g, "lab_shield_head_order", [0, 1, 2]
            ),
        }

    @app.before_request
    def _lab_shield_prereq() -> object | None:
        if not has_request_context():
            return None
        _init_request_state()
        r = _before_request_ip()
        if r is not None:
            return r
        _before_request_jitter()
        r2 = _before_request_ua_mismatch(SESSION_CLIENT_UA)
        if r2 is not None:
            return r2
        return None

    app.add_template_filter(dom_noise_filter, "dom_noise")
