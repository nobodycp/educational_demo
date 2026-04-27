"""HandyAPI BIN lookup (first 6 digits only) — used by Telegram + decrypt tooling."""

from __future__ import annotations

import json
import urllib.request


def fetch_bin_meta(first6: str):
    try:
        req = urllib.request.Request(
            f"https://data.handyapi.com/bin/{str(first6)[:6]}",
            headers={"User-Agent": "BangoLab/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read())
        if d.get("Status") != "SUCCESS":
            return None
        return {
            "scheme": d.get("Scheme", "Unknown"),
            "type": d.get("Type", "Unknown"),
            "issuer": d.get("Issuer", "Unknown"),
            "tier": d.get("CardTier", "Unknown"),
            "country": d.get("Country", {}).get("Name", "Unknown"),
            "country_code": d.get("Country", {}).get("A2", "Unknown"),
        }
    except Exception:
        return None
