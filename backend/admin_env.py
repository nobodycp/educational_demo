from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

ENV_ALLOWLIST_GROUPS: dict[str, list[str]] = {
    "security": [
        "FLASK_SECRET_KEY",
        "HANDOFF_SECRET",
        "SESSION_SAMESITE",
        "COOKIE_SECURE",
        "STRICT_ORIGIN",
    ],
    "gate": [
        "POW_LEADING_ZEROS_HEX",
        "GATE_CSRF_DISABLED",
        "HANDSHAKE_DISABLED",
        "API_CSRF_DISABLED",
        "START_DEBUG_SECRET",
        "GATE_HMAC_SECRET",
        "GATE_BLOCKED_REDIRECT_URL",
        "INCOGNITO_BLOCK",
        "RISK_BLOCK_THRESHOLD",
        "EXTERNAL_GUARD",
        "EXTERNAL_GUARD_URL",
        "EXTERNAL_GUARD_API_KEY",
        "EXTERNAL_GUARD_TIMEOUT_SEC",
        "EXTERNAL_GUARD_FAIL_OPEN",
    ],
    "flow": [
        "BANGO_REG_LOADING_SECONDS",
        "BANGO_POST_REG_GLASS_SECONDS",
        "BANGO_DONE_REDIRECT_URL",
        "BANGO_DONE_REDIRECT_DELAY_SEC",
    ],
    "telegram": [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_THREAD_ID",
        "TELEGRAM_PII_PLAINTEXT",
    ],
    "admin": [
        "ADMIN_PANEL_PASSWORD",
        "ADMIN_PANEL_ACCESS_MODE",
        "ADMIN_PANEL_IP_WHITELIST",
        "ACTIVE_THEME",
    ],
}

SENSITIVE_KEYS: set[str] = {
    "FLASK_SECRET_KEY",
    "HANDOFF_SECRET",
    "GATE_HMAC_SECRET",
    "EXTERNAL_GUARD_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "ADMIN_PANEL_PASSWORD",
}


def all_allowlisted_keys() -> set[str]:
    out: set[str] = set()
    for keys in ENV_ALLOWLIST_GROUPS.values():
        out.update(keys)
    return out


def _strip_bom_quotes(v: str) -> str:
    return (v or "").strip().strip("\ufeff").strip("\"'")


def _parse_env_file(env_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = _strip_bom_quotes(v)
    return out


def read_env_values(env_path: Path, *, keys: set[str] | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    read_keys = keys or all_allowlisted_keys()
    file_values = _parse_env_file(env_path)
    for k in sorted(read_keys):
        if k in file_values:
            out[k] = file_values.get(k, "")
            continue
        out[k] = _strip_bom_quotes(os.environ.get(k, ""))
    return out


def _replace_or_append_lines(lines: list[str], updates: dict[str, str]) -> list[str]:
    remaining = dict(updates)
    out_lines: list[str] = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            out_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out_lines.append(f"{key}={remaining.pop(key)}")
        else:
            out_lines.append(line)
    if remaining:
        if out_lines and out_lines[-1].strip():
            out_lines.append("")
        out_lines.append("# --- Admin panel managed values ---")
        for k, v in remaining.items():
            out_lines.append(f"{k}={v}")
    return out_lines


def write_env_values_atomic(env_path: Path, updates: dict[str, str]) -> list[str]:
    allowed = all_allowlisted_keys()
    invalid = [k for k in updates if k not in allowed]
    if invalid:
        raise ValueError(f"unsupported keys: {', '.join(sorted(invalid))}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    raw_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    safe_updates = {k: (v or "").strip() for k, v in updates.items()}
    new_lines = _replace_or_append_lines(raw_lines, safe_updates)
    payload = "\n".join(new_lines) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False, dir=str(env_path.parent)
    ) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, env_path)
    return sorted(safe_updates.keys())


def masked_value(key: str, value: str) -> str:
    if key not in SENSITIVE_KEYS:
        return value
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def values_by_group(values: dict[str, str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for group, keys in ENV_ALLOWLIST_GROUPS.items():
        entries: dict[str, Any] = {}
        for key in keys:
            raw = values.get(key, "")
            entries[key] = {
                "value": raw,
                "masked": masked_value(key, raw),
                "sensitive": key in SENSITIVE_KEYS,
            }
        out[group] = entries
    return out


def append_admin_audit_log(data_dir: Path, *, event: str, payload: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "admin_audit.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": event, "payload": payload}, ensure_ascii=False) + "\n")

