"""
Lightweight User-Agent hints for lab dashboards (no external UA database).

**Security concept:** *Client self-reporting* — the UA string is trivially spoofed;
this module is for **teaching and logging**, not for strong security decisions.
"""

from __future__ import annotations

import re
from typing import Any


def parse_user_agent(ua: str | None) -> dict[str, Any]:
    """
    Extract coarse OS, browser, device class, and notable embeds (Electron, IDE shells).

    **Original PHP logic:** Kits often regex `$_SERVER['HTTP_USER_AGENT']` for
    `Mobile`, `Android`, `Trident`, etc.

    Returns keys: ``raw``, ``device_kind``, ``os_family``, ``os_version``,
    ``browser_family``, ``browser_version``, ``engine``, ``embeddings`` (list),
    ``is_mobile_hint``, ``is_tablet_hint``.
    """
    raw = (ua or "").strip()
    if not raw:
        return {
            "raw": "",
            "device_kind": "unknown",
            "os_family": "unknown",
            "os_version": "",
            "browser_family": "unknown",
            "browser_version": "",
            "engine": "",
            "embeddings": [],
            "is_mobile_hint": False,
            "is_tablet_hint": False,
        }

    s = raw
    low = s.lower()

    # --- OS from Mozilla platform token (first parentheses block is most reliable)
    os_family = "unknown"
    os_version = ""
    m = re.search(r"\(([^)]+)\)", s)
    platform = m.group(1) if m else ""

    device_guess = "unknown"

    if "iphone" in low:
        os_family = "iOS"
        device_guess = "mobile"
    elif "ipad" in low:
        os_family = "iOS"
        device_guess = "tablet"
    elif "android" in low:
        os_family = "Android"
        device_guess = "mobile" if "mobile" in low else "tablet" if "tablet" in low else "desktop"
    elif "mac os x" in low or "macintosh" in low:
        os_family = "macOS"
        device_guess = "desktop"
        mv = re.search(r"Mac OS X[_ ]([\d_]+)", s, re.I)
        if mv:
            os_version = mv.group(1).replace("_", ".")
    elif "windows nt" in low:
        os_family = "Windows"
        device_guess = "desktop"
        wv = re.search(r"Windows NT ([\d.]+)", s, re.I)
        if wv:
            os_version = wv.group(1)
    elif "linux" in low and "android" not in low:
        os_family = "Linux"
        device_guess = "desktop"
    else:
        device_guess = "unknown"

    is_mobile_hint = bool(re.search(r"\bMobile\b", s) or "iphone" in low)
    is_tablet_hint = "ipad" in low or "tablet" in low

    if device_guess == "unknown":
        if is_tablet_hint:
            device_kind = "tablet"
        elif is_mobile_hint:
            device_kind = "mobile"
        else:
            device_kind = "desktop"
    else:
        device_kind = device_guess

    # Electron / IDE wrappers often report as desktop Chrome
    embeddings: list[str] = []
    for label, pat in (
        ("Cursor", r"Cursor/([\d.]+)"),
        ("VS Code", r"VS Code/([\d.]+)"),
        ("Electron", r"Electron/([\d.]+)"),
        ("Slack", r"Slack_Ssr/([\d.]+)"),
    ):
        mm = re.search(pat, s, re.I)
        if mm:
            embeddings.append(f"{label} {mm.group(1)}")

    # --- Browser + version (prefer Chrome line if present; Edge; Firefox; Safari)
    browser_family = "unknown"
    browser_version = ""

    if re.search(r"\bEdg(?:e|A|iOS)?/([\d.]+)", s):
        mm = re.search(r"\bEdg(?:e|A|iOS)?/([\d.]+)", s)
        browser_family, browser_version = "Edge", mm.group(1) if mm else ""
    elif re.search(r"\bFirefox/([\d.]+)", s):
        mm = re.search(r"\bFirefox/([\d.]+)", s)
        browser_family, browser_version = "Firefox", mm.group(1)
    elif re.search(r"\bChrome/([\d.]+)", s) and "chromeframe" not in low:
        mm = re.search(r"\bChrome/([\d.]+)", s)
        browser_family, browser_version = "Chrome", mm.group(1)
        if "edg/" in low:
            mm2 = re.search(r"\bEdg/([\d.]+)", s, re.I)
            if mm2:
                browser_family, browser_version = "Edge", mm2.group(1)
    elif re.search(r"\bVersion/([\d.]+).*Safari/", s):
        mm = re.search(r"\bVersion/([\d.]+).*Safari/", s)
        browser_family, browser_version = "Safari", mm.group(1)
    elif "safari/" in low and "chrome/" not in low:
        mm = re.search(r"\bSafari/([\d.]+)", s)
        browser_family, browser_version = "Safari", mm.group(1) if mm else ""

    # Engine hint
    engine = ""
    if "applewebkit" in low:
        if "chrome/" in low or "chromium" in low:
            engine = "Blink (WebKit fork)"
        else:
            engine = "WebKit"
    elif "gecko/" in low:
        engine = "Gecko"

    if embeddings and browser_family == "Chrome":
        browser_family = "Chrome (embedded host)"

    return {
        "raw": raw[:500] + ("…" if len(raw) > 500 else ""),
        "raw_full_length": len(raw),
        "platform_token": platform[:200] + ("…" if len(platform) > 200 else ""),
        "device_kind": device_kind,
        "os_family": os_family,
        "os_version": os_version,
        "browser_family": browser_family,
        "browser_version": browser_version,
        "engine": engine,
        "embeddings": embeddings,
        "is_mobile_hint": is_mobile_hint,
        "is_tablet_hint": is_tablet_hint,
    }
