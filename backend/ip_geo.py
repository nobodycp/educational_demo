"""
Optional public-IP geolocation (external API) for lab logs / Telegram — **educational only**.

Uses ipapi.co JSON over HTTPS (no API key, low daily cap). Skips non-global addresses
(``127.0.0.1``, RFC1918, etc.) so we do not call the service for loopback.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 3.0


def is_public_routable_ip(ip: str) -> bool:
    """True only for addresses suitable for a public-geo lookup."""
    s = (ip or "").strip()
    if not s:
        return False
    try:
        return ipaddress.ip_address(s).is_global
    except ValueError:
        return False


def lookup_ip_public(ip: str, *, timeout: float = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    """
    Return structured geo/network fields, or a failure object with ``ok: False``.

    On success, keys: ``ok``, ``query``, ``isp``, ``country``, ``region``, ``city``,
    ``timezone`` (all string-safe for HTML escape).
    """
    q = (ip or "").strip() or "unknown"
    if not is_public_routable_ip(q):
        return {
            "ok": False,
            "query": q,
            "reason": "not_public",
            "isp": "—",
            "country": "—",
            "region": "",
            "city": "—",
            "timezone": "—",
        }

    url = f"https://ipapi.co/{q}/json/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EducationalDemo/1.0 (lab; local only)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        logger.info("ip_geo: request failed for %s: %s", q, e)
        return {
            "ok": False,
            "query": q,
            "reason": ("http_error: " + str(e))[:200],
            "isp": "—",
            "country": "—",
            "region": "",
            "city": "—",
            "timezone": "—",
        }

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {
            "ok": False,
            "query": q,
            "reason": "invalid_json",
            "isp": "—",
            "country": "—",
            "region": "",
            "city": "—",
            "timezone": "—",
        }

    if not isinstance(data, dict):
        return {
            "ok": False,
            "query": q,
            "reason": "bad_shape",
            "isp": "—",
            "country": "—",
            "region": "",
            "city": "—",
            "timezone": "—",
        }

    if data.get("error"):
        return {
            "ok": False,
            "query": q,
            "reason": str(data.get("reason") or data.get("message") or "error")[:200],
            "isp": "—",
            "country": "—",
            "region": "",
            "city": "—",
            "timezone": "—",
        }

    org = str(data.get("org") or "").strip()
    if not org:
        asn = str(data.get("asn") or "").strip()
        if asn:
            org = f"ASN {asn}"
    if not org:
        org = "—"

    country = str(
        data.get("country_name")
        or data.get("country")
        or data.get("country_code")
        or "—"
    )
    city = str(data.get("city") or "—")
    region = str(data.get("region") or data.get("region_code") or "").strip()
    tz = str(data.get("timezone") or "—")
    return {
        "ok": True,
        "query": str(data.get("ip") or q),
        "isp": org,
        "country": country,
        "region": region,
        "city": city,
        "timezone": tz,
    }
