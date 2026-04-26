"""
Educational lab: optional X-JA3-Fingerprint blocking when nginx (or a proxy) injects
the OpenSSL/ja3 module hash. If the header is missing, all checks are skipped.
"""

from __future__ import annotations

# Plausible-looking hex JA3 “signatures” for lab blocklists (not real production IOCs).
BANNED_JA3_FINGERPRINTS: frozenset[str] = frozenset(
    {
        "6734f0e42605dc1a9e60f9a07f52e0e3",
        "19e295350fd94996329e2ed80f92efe7",
        "772bf468995f0e9112cba1653440e59e",
        "0ad85cbafc77127572d0bf34d870d11d",
        "51c64c77e1f1f4d58122be43e2497a42",
    }
)


def blocked_ja3_fingerprint_from_headers(headers) -> str | None:
    """
    Return the raw fingerprint string if it should be blocked, else None.
    Accepts a mapping-like object (e.g. Werkzeug headers).
    """
    for key in ("X-JA3-Fingerprint", "X-JA3", "X-JA3-Hash"):
        raw = (headers.get(key) or "").strip()
        if raw and raw in BANNED_JA3_FINGERPRINTS:
            return raw
    return None
