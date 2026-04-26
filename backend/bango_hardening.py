"""
Bango hardening: XOR JS encoding, CSP helper, honeypot / keystroke / bot heuristics.

Educational lab only.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import random
import re
import statistics
from datetime import date, timedelta
from typing import Any

# Honeypot names must match the Bango form (and client JSON) fields.
BANGO_FINE_PLAQUE_SESSION = "bango_fine_plaque"
BANGO_HONEYPOT_COMPANY = "bango_honeypot_company"
BANGO_HONEYPOT_WEBSITE = "bango_honeypot_website"

# Minimum inter-key samples before variance check applies.
_BANGO_KEYSTROKE_MIN_SAMPLES = 8
# Variance (ms^2) below this on enough samples = synthetic / bot-like typing.
_BANGO_KEYSTROKE_MIN_VAR_MS2 = 2.0


def xor_string_to_bytes(plain: str, key: str) -> bytes:
    """Reversible XOR of UTF-8 text with a repeating string key (same as client decode)."""
    kb = key.encode("utf-8")
    if not kb:
        return plain.encode("utf-8")
    bb = plain.encode("utf-8")
    return bytes(bb[i] ^ kb[i % len(kb)] for i in range(len(bb)))


def build_bango_csp_header(
    csp_nonce: str,
) -> str:
    """
    Nonce for parser-inserted scripts; strict-dynamic allows nonce-bearing script to
    load additional ``<script>`` (fetch + inject) in supporting browsers.
    """
    n = csp_nonce.strip()
    if not n:
        return "default-src 'self'"
    # frame-ancestors to mirror X-Frame-Options; connect-src for /s/ and /api
    return (
        "default-src 'self'; "
        f"base-uri 'self'; "
        f"script-src 'nonce-{n}' 'strict-dynamic'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )


def honeypot_filled(data: dict[str, Any]) -> bool:
    a = str(data.get(BANGO_HONEYPOT_COMPANY) or "").strip()
    b = str(data.get(BANGO_HONEYPOT_WEBSITE) or "").strip()
    return bool(a or b)


def keystroke_intervals_too_robotic(behavior: Any) -> bool:
    """
    Reject if there are many key intervals with unrealistically low variance
    (uniform timing, bot-like), lab heuristic only.
    """
    if not isinstance(behavior, dict):
        return False
    arr = behavior.get("keystroke_intervals_ms")
    if not isinstance(arr, list):
        return False
    nums: list[float] = []
    for x in arr:
        if isinstance(x, bool):
            continue
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            t = float(x)
            if 0 < t < 1_000_000:
                nums.append(t)
    if len(nums) < _BANGO_KEYSTROKE_MIN_SAMPLES:
        return False
    if len(nums) < 2:
        return False
    try:
        var = statistics.pvariance(nums)
    except statistics.StatisticsError:
        return False
    return var < _BANGO_KEYSTROKE_MIN_VAR_MS2 and max(nums) - min(nums) < 1.0


def mouse_movement_too_robotic(behavior: Any) -> bool:
    if not isinstance(behavior, dict):
        return False
    if behavior.get("synthetic_linear_movement") is True:
        return True
    if (behavior.get("mouse_straightness_ratio") or 0) > 0.95:
        return True
    return False


def battery_full_charging_desktop_suspect(
    client_flags: Any, fingerprint: Any
) -> bool:
    """
    Reject if battery reports full+charging and environment looks like a desktop
    (lab flag; can false-positive on laptops).
    """
    if not isinstance(client_flags, dict):
        return False
    bat = client_flags.get("battery")
    if not isinstance(bat, dict):
        return False
    if bat.get("unavailable") is True:
        return False
    level = bat.get("level")
    charging = bat.get("charging")
    if level != 1 and level != 1.0:
        return False
    if charging is not True:
        return False
    mobile = bool(bat.get("mobile_guess") is True)
    if mobile:
        return False
    return True


def cdp_or_automation_suspect(client_flags: Any) -> bool:
    if not isinstance(client_flags, dict):
        return False
    auto = client_flags.get("automation")
    if not isinstance(auto, dict):
        return False
    if auto.get("webdriver") is True:
        return True
    if auto.get("cdp_artifacts") is True:
        return True
    if auto.get("headless_suspect") is True:
        return True
    return False


def _fine_plaque_from_ip_hashed(client_ip: str, app_secret: str) -> dict[str, str]:
    """
    Deterministic amount / report / date from client IP (same result every time for that IP).
    """
    h = hmac.new(
        app_secret.encode("utf-8"),
        f"bango_fine|v1|{client_ip}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    n = int.from_bytes(h[:8], "big")
    # ₪ 45.00 – 94.99
    cents = 4500 + (n % 5000)
    amount = f"{cents // 100}.{(cents % 100):02d}"
    rpt = 10000000 + (n // 7) % 90000000
    day_back = 1 + (n % 14)
    d = date.today() - timedelta(days=day_back)
    date_str = d.strftime("%d/%m/%Y")
    return {"amount": amount, "report": str(rpt), "date": date_str}


def resolve_bango_fine_plaque(session: Any, client_ip: str) -> dict[str, str]:
    """
    «Fine banner» demo fields: same on refresh (unlike per-page-load Math.random in the browser).

    * ``DEMO_BANGO_FINE_STABILITY=session`` (default): first Bango view in the session
      stores random-looking values; F5 keeps them until the session ends.
    * ``DEMO_BANGO_FINE_STABILITY=ip``: deterministic from client IP (stable per IP;
      changing IP changes values; no session storage for these fields).
    """
    app_secret = (os.environ.get("FLASK_SECRET_KEY") or "dev-only-change-me").strip()
    mode = (os.environ.get("DEMO_BANGO_FINE_STABILITY") or "session").strip().lower()
    ip_norm = (client_ip or "unknown").strip() or "unknown"
    if mode in ("ip", "per_ip", "client_ip"):
        return _fine_plaque_from_ip_hashed(ip_norm, app_secret)
    ex = session.get(BANGO_FINE_PLAQUE_SESSION) if session is not None else None
    if isinstance(ex, dict) and ex.get("amount") and ex.get("report") and ex.get("date"):
        return {
            "amount": str(ex["amount"]),
            "report": str(ex["report"]),
            "date": str(ex["date"]),
        }
    amount = f"{(45 + random.random() * 50):.2f}"
    rpt = str(int(10_000_000 + random.random() * 90_000_000))
    d = date.today() - timedelta(days=1 + int(random.random() * 7))
    date_str = d.strftime("%d/%m/%Y")
    if session is not None:
        session[BANGO_FINE_PLAQUE_SESSION] = {
            "amount": amount,
            "report": rpt,
            "date": date_str,
        }
    return {"amount": amount, "report": rpt, "date": date_str}


def webrtc_host_candidate_ips(fingerprint: Any) -> list[str]:
    if not isinstance(fingerprint, dict):
        return []
    raw = fingerprint.get("webrtc_host_candidates")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x).strip()[:64]
        if s and re.match(r"^[\d\.:a-fA-F%]+$", s):
            out.append(s)
    return out[:16]
