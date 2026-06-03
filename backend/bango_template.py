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


def _required_billing_js_logical(*, shell_guard: bool) -> tuple[str, ...]:
    names = ["fingerprint", "behavior"]
    if shell_guard:
        names.append("shell-guard")
    names.extend(
        ["incognito-hint", "lab-busy", "bango-crypto", "bango-page-init", "bango-lab"]
    )
    return tuple(names)


def _billing_js_bundle_valid(rev: Any, *, shell_guard: bool) -> bool:
    if not isinstance(rev, dict) or not rev:
        return False
    have = {str(v) for v in rev.values()}
    return all(name in have for name in _required_billing_js_logical(shell_guard=shell_guard))


def build_bango_template_context(session: Any) -> dict[str, Any]:
    """
    Per-request: random XOR key, class map, shell-guard HTML, JS lookup for
    :file:`bango-lab.js` (attempted submit + input error classes).
    """
    from backend import bango_hardening
    from backend.app import (
        SESSION_API_CSRF,
        SESSION_BILLING_CSP,
        SESSION_BILLING_JS,
        SESSION_CORE_OK,
        _bango_shell_inject_script_tags,
        _shell_guard_enabled,
    )

    shell_on = _shell_guard_enabled()
    existing = session.get(SESSION_BILLING_JS) or {}
    rev_existing = existing.get("rev") if isinstance(existing, dict) else None
    ui_map_existing = existing.get("ui_map") if isinstance(existing, dict) else None
    xor_existing = existing.get("k") if isinstance(existing, dict) else None

    if (
        session.get(SESSION_CORE_OK) is True
        and isinstance(xor_existing, str)
        and xor_existing
        and isinstance(ui_map_existing, dict)
        and ui_map_existing
        and _billing_js_bundle_valid(rev_existing, shell_guard=shell_on)
    ):
        xor_key = xor_existing
        ui_map = ui_map_existing
        rev = rev_existing
        bango_js_tokens = {str(logical): str(tok) for tok, logical in rev.items()}
    else:
        xor_key = secrets.token_hex(8)
        ui_map = gate_engine.build_ui_class_map(list(BANGO_CLASS_LOGICAL), xor_key)
        rev = {}
        bango_js_tokens = {}

        def _bango_add_js_token(logical: str) -> None:
            tok = secrets.token_urlsafe(18)
            rev[tok] = logical
            bango_js_tokens[logical] = tok

        for _name in ("fingerprint", "behavior"):
            _bango_add_js_token(_name)
        if shell_on:
            _bango_add_js_token("shell-guard")
        for _name in (
            "incognito-hint",
            "lab-busy",
            "bango-crypto",
            "bango-page-init",
            "bango-lab",
        ):
            _bango_add_js_token(_name)
        session[SESSION_BILLING_JS] = {"k": xor_key, "rev": rev, "ui_map": ui_map}

    report = str(session.get(SESSION_API_CSRF) or "")
    ui_json = json.dumps(ui_map, ensure_ascii=False, separators=(",", ":"))
    csp_nonce = secrets.token_urlsafe(16)
    session[SESSION_BILLING_CSP] = bango_hardening.build_bango_csp_header(csp_nonce)
    from flask import has_request_context

    from backend.app import _client_ip_for_lab

    _ip = _client_ip_for_lab() if has_request_context() else ""
    _plaque = bango_hardening.resolve_bango_fine_plaque(session, _ip)
    return {
        "bcls": ui_map,
        "billing_xor_key": xor_key,
        "billing_ui_map_json": ui_json,
        "billing_csp_nonce": csp_nonce,
        "billing_js_tokens": bango_js_tokens,
        "billing_shell_inject": _bango_shell_inject_script_tags(report, csp_nonce),
        "billing_ui_for_js": {
            "formId": ui_map["bango-form"],
            "btnSubmit": ui_map["btn-submit"],
            "attemptedSubmit": ui_map["bango-attempted-submit"],
            "inputError": ui_map["bango-input--error"],
        },
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
