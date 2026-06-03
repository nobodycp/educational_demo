from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_THEMES = {
    "default": {
        "label": "Default Bango",
        "template": "bango/index.html",
    },
    "post_pyment": {
        "label": "Post Payment",
        "template": "post_pyment/index.html",
    },
}


# Common misspellings / alternate names for theme ids in config/prebuilt_themes.json.
THEME_ALIASES: dict[str, str] = {
    "post_payment": "post_pyment",
    "post-payment": "post_pyment",
}


def resolve_theme_id(requested: str, themes: dict[str, dict[str, Any]]) -> str:
    key = (requested or "").strip()
    if not key:
        return ""
    if key in themes:
        return key
    alias = THEME_ALIASES.get(key.lower())
    if alias and alias in themes:
        return alias
    return key


def load_themes(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return dict(DEFAULT_THEMES)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_THEMES)
    themes = data.get("themes") if isinstance(data, dict) else None
    if not isinstance(themes, dict):
        return dict(DEFAULT_THEMES)
    out: dict[str, dict[str, Any]] = {}
    for key, value in themes.items():
        if not isinstance(value, dict):
            continue
        template_name = str(value.get("template") or "").strip()
        if not template_name:
            continue
        out[str(key)] = {
            "label": str(value.get("label") or key),
            "template": template_name,
        }
    return out or dict(DEFAULT_THEMES)

