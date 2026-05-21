from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = PROJECT_ROOT / "themes"
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"

SETTINGS_PATH = CONFIG_DIR / "settings.json"
REGISTRY_PATH = CONFIG_DIR / "theme_registry.json"
THEME_EVENTS_PATH = LOGS_DIR / "theme_events.jsonl"

DEFAULT_THEME_NAME = "default"
SESSION_THEME_KEY = "active_theme_frozen"

_THEME_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{2,64}$")
_STEPS_RE = re.compile(r"window\.__STEPS__\s*=\s*(\[[^\]]*\])", re.MULTILINE | re.DOTALL)


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _default_settings() -> dict[str, Any]:
    return {
        "active_theme": DEFAULT_THEME_NAME,
        "admin_password": "admin123",
        "verification": {
            "enabled": False,
            "title": "Verification",
            "prompt": "Enter verification code",
            "expected_code": "123456",
        },
    }


def _default_registry() -> dict[str, Any]:
    now = _utc_now_iso()
    return {
        "themes": {
            DEFAULT_THEME_NAME: {
                "name": DEFAULT_THEME_NAME,
                "display_name": "Default Theme",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
                "steps": ["profile", "card"],
                "verification_override_enabled": None,
            }
        }
    }


def _default_theme_index_html() -> str:
    source = PROJECT_ROOT / "frontend" / "static" / "bango.source.html"
    if source.is_file():
        html = source.read_text(encoding="utf-8")
    else:
        html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Default Theme</title></head>
<body><main><h1>Default Theme</h1><p>Theme bootstrap fallback page.</p></main></body></html>"""
    if "window.__STEPS__" not in html:
        marker = "</head>"
        inject = '<script>window.__STEPS__=["profile","card"];</script>'
        if marker in html:
            html = html.replace(marker, f"{inject}\n{marker}", 1)
        else:
            html = f"{inject}\n{html}"
    return html


def _default_theme_texts() -> dict[str, Any]:
    return {
        "name": "Default Theme",
        "cta_submit": "Submit",
        "verification_title": "Verification",
        "verification_prompt": "Enter verification code",
    }


def ensure_theme_runtime_bootstrap() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    THEMES_DIR.mkdir(parents=True, exist_ok=True)

    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.write_text(
            json.dumps(_default_settings(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.write_text(
            json.dumps(_default_registry(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if not THEME_EVENTS_PATH.exists():
        THEME_EVENTS_PATH.write_text("", encoding="utf-8")

    default_dir = THEMES_DIR / DEFAULT_THEME_NAME
    default_assets = default_dir / "assets"
    default_dir.mkdir(parents=True, exist_ok=True)
    default_assets.mkdir(parents=True, exist_ok=True)

    default_index = default_dir / "index.html"
    if not default_index.exists():
        default_index.write_text(_default_theme_index_html(), encoding="utf-8")
    default_texts = default_dir / "texts.json"
    if not default_texts.exists():
        default_texts.write_text(
            json.dumps(_default_theme_texts(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    _refresh_registry_for_theme(DEFAULT_THEME_NAME)


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(fallback)
    except Exception:
        return dict(fallback)


def load_settings() -> dict[str, Any]:
    return _read_json(SETTINGS_PATH, _default_settings())


def save_settings(data: dict[str, Any]) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_registry() -> dict[str, Any]:
    reg = _read_json(REGISTRY_PATH, _default_registry())
    if not isinstance(reg.get("themes"), dict):
        reg["themes"] = {}
    return reg


def save_registry(registry: dict[str, Any]) -> None:
    REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def append_theme_event(event: str, payload: dict[str, Any] | None = None) -> None:
    rec = {
        "ts": _utc_now_iso(),
        "event": event,
        "payload": payload or {},
    }
    with THEME_EVENTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def validate_theme_name(name: str) -> bool:
    return bool(_THEME_NAME_RE.match((name or "").strip()))


def extract_steps_from_html(html: str) -> list[str]:
    m = _STEPS_RE.search(html or "")
    if not m:
        raise ValueError("missing window.__STEPS__ declaration")
    try:
        arr = json.loads(m.group(1))
    except Exception as exc:  # pragma: no cover - explicit user-facing validation
        raise ValueError("invalid __STEPS__ JSON array") from exc
    if not isinstance(arr, list) or not arr:
        raise ValueError("__STEPS__ must be a non-empty array")
    out: list[str] = []
    seen: set[str] = set()
    for v in arr:
        s = str(v).strip()
        if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", s):
            raise ValueError(f"invalid step name: {s!r}")
        if s in seen:
            raise ValueError(f"duplicate step name: {s}")
        out.append(s)
        seen.add(s)
    return out


def list_themes() -> list[dict[str, Any]]:
    reg = load_registry()
    themes = reg.get("themes", {})
    out: list[dict[str, Any]] = []
    for name, meta in themes.items():
        if not isinstance(meta, dict):
            continue
        row = dict(meta)
        row["name"] = name
        out.append(row)
    out.sort(key=lambda x: str(x.get("name", "")))
    return out


def _refresh_registry_for_theme(name: str) -> None:
    theme_dir = THEMES_DIR / name
    idx = theme_dir / "index.html"
    txt = theme_dir / "texts.json"
    if not idx.exists() or not txt.exists():
        return
    html = idx.read_text(encoding="utf-8")
    steps = extract_steps_from_html(html)
    reg = load_registry()
    themes = reg.setdefault("themes", {})
    now = _utc_now_iso()
    old = themes.get(name, {}) if isinstance(themes.get(name), dict) else {}
    themes[name] = {
        "name": name,
        "display_name": str(old.get("display_name") or name.replace("_", " ").title()),
        "enabled": bool(old.get("enabled", True)),
        "created_at": old.get("created_at") or now,
        "updated_at": now,
        "steps": steps,
        "verification_override_enabled": old.get("verification_override_enabled", None),
    }
    save_registry(reg)


def get_active_theme_name(settings: dict[str, Any] | None = None) -> str:
    st = settings or load_settings()
    requested = str(st.get("active_theme") or DEFAULT_THEME_NAME).strip() or DEFAULT_THEME_NAME
    reg = load_registry()
    themes = reg.get("themes", {})
    if requested in themes:
        return requested
    if DEFAULT_THEME_NAME in themes:
        return DEFAULT_THEME_NAME
    return next(iter(themes.keys()), DEFAULT_THEME_NAME)


def freeze_theme_in_session(session_obj: dict[str, Any]) -> str:
    frozen = str(session_obj.get(SESSION_THEME_KEY) or "").strip()
    reg = load_registry()
    themes = reg.get("themes", {})
    if frozen and frozen in themes:
        return frozen
    active = get_active_theme_name()
    session_obj[SESSION_THEME_KEY] = active
    return active


def clear_frozen_theme_from_session(session_obj: dict[str, Any]) -> None:
    session_obj.pop(SESSION_THEME_KEY, None)


def get_theme_paths(name: str) -> dict[str, Path]:
    base = THEMES_DIR / name
    return {
        "base": base,
        "index": base / "index.html",
        "texts": base / "texts.json",
        "assets": base / "assets",
    }


def load_theme_runtime_bundle(name: str) -> dict[str, Any]:
    p = get_theme_paths(name)
    if not p["index"].is_file():
        raise FileNotFoundError(f"theme index missing: {name}")
    if not p["texts"].is_file():
        raise FileNotFoundError(f"theme texts missing: {name}")
    html = p["index"].read_text(encoding="utf-8")
    texts_data = json.loads(p["texts"].read_text(encoding="utf-8"))
    if not isinstance(texts_data, dict):
        raise ValueError("texts.json must be an object")
    steps = extract_steps_from_html(html)
    return {"name": name, "html": html, "texts": texts_data, "steps": steps}


def upsert_theme_from_upload(
    *,
    name: str,
    index_html: bytes,
    texts_json: bytes,
    assets: list[tuple[str, bytes]] | None = None,
) -> dict[str, Any]:
    nm = (name or "").strip()
    if not validate_theme_name(nm):
        raise ValueError("invalid theme name")
    if not index_html:
        raise ValueError("missing index.html")
    if not texts_json:
        raise ValueError("missing texts.json")
    html = index_html.decode("utf-8", errors="strict")
    steps = extract_steps_from_html(html)
    texts_obj = json.loads(texts_json.decode("utf-8", errors="strict"))
    if not isinstance(texts_obj, dict):
        raise ValueError("texts.json must be a JSON object")

    p = get_theme_paths(nm)
    p["base"].mkdir(parents=True, exist_ok=True)
    p["assets"].mkdir(parents=True, exist_ok=True)
    p["index"].write_text(html, encoding="utf-8")
    p["texts"].write_text(json.dumps(texts_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    for rel, blob in (assets or []):
        rel_clean = rel.strip().lstrip("/").replace("\\", "/")
        if not rel_clean or ".." in rel_clean.split("/"):
            continue
        target = p["assets"] / rel_clean
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)

    _refresh_registry_for_theme(nm)
    append_theme_event("theme_upload", {"name": nm, "steps": steps})
    return {"name": nm, "steps": steps}


def set_active_theme(name: str) -> str:
    reg = load_registry()
    if name not in reg.get("themes", {}):
        raise ValueError("theme not found")
    st = load_settings()
    st["active_theme"] = name
    save_settings(st)
    append_theme_event("theme_activate", {"name": name})
    return name


def verification_enabled_for_theme(name: str) -> bool:
    st = load_settings()
    global_enabled = bool((st.get("verification") or {}).get("enabled", False))
    reg = load_registry()
    meta = (reg.get("themes", {}) or {}).get(name, {})
    if isinstance(meta, dict):
        override = meta.get("verification_override_enabled", None)
        if isinstance(override, bool):
            return override
    return global_enabled


def verification_config_for_theme(name: str) -> dict[str, Any]:
    st = load_settings()
    ver = st.get("verification") or {}
    cfg = {
        "enabled": verification_enabled_for_theme(name),
        "title": str(ver.get("title") or "Verification"),
        "prompt": str(ver.get("prompt") or "Enter verification code"),
        "expected_code": str(ver.get("expected_code") or "123456"),
    }
    return cfg

