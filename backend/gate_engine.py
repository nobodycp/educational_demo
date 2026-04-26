"""
Strict port of **gate / processor** responsibilities (`sys/gate/engine.php`, `proc.php`).

This module implements the **nine-step validation pipeline** used in advanced kits:

1. **Lifetime IP quota** — lab blocks an IP forever after ``N`` successful gate passes (SQLite).
2. **Rate limiting** — in-memory sliding window per IP (burst control).
3. **Host blacklisting** — reject disallowed `Host` headers (virtual-host abuse).
4. **User-Agent blacklisting** — block obvious automation signatures.
5. **Incognito / private-mode hints** — consume client-reported `signals` (no magic).
6. **Risk scoring** — composite score from signals + lists + timing heuristics.
7. **API handshake** — session-bound CSRF, proof-of-work, and handshake nonce.
8. **HMAC request signing** — `HMAC-SHA256(secret, ts + "|" + canonical_json)` over the body.
9. **External policy (optional)** — when ``DEMO_EXTERNAL_GUARD`` is ``on`` (see code), POST IP + UA
   to ``DEMO_EXTERNAL_GUARD_URL``; ``access_denied`` in JSON becomes the final deny.
   With ``set_runtime_dotenv_path``, guard URL / key / switch are read from ``.env`` on each request.

**XOR obfuscation** helpers mirror kits that XOR-encode CSS class names or DOM markers
to evade naive static string scanners ("evasion techniques" — taught defensively only).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from backend import incident_store

_RUNTIME_DOTENV_PATH: Path | None = None


def set_runtime_dotenv_path(path: Path | None) -> None:
    """
    When set (Flask ``create_app`` passes ``ROOT / ".env"``), external-guard keys are
    re-read from that file on **every** gate decision so instructors can toggle
    ``DEMO_EXTERNAL_GUARD`` / URL / key without restarting the dev server.
    """
    global _RUNTIME_DOTENV_PATH
    _RUNTIME_DOTENV_PATH = path


def _live_env(key: str, default: str = "") -> str:
    """
    Prefer the current on-disk ``.env`` (if ``set_runtime_dotenv_path`` was called)
    over ``os.environ`` for that key.
    """
    if _RUNTIME_DOTENV_PATH is not None and _RUNTIME_DOTENV_PATH.is_file():
        from dotenv import get_key

        v = get_key(_RUNTIME_DOTENV_PATH, key)
        if v is not None:
            return v
    return os.environ.get(key, default)


@dataclass(frozen=True)
class GateDecision:
    """
    Outcome object returned by the gate pipeline.

    **Security concept:** *Explicit allow/deny with reason codes* — the same
    pattern WAFs and bot managers use for policy traceability.
    """

    allowed: bool
    http_status: int
    reason: str
    risk: dict[str, Any]


def xor_obfuscate_utf8(plain: str, key: str) -> str:
    """
    XOR-obfuscate a UTF-8 string with a repeating key, then **base64url**-encode.

    **Original PHP logic:** `str_split` + `^` key cycling + `base64_encode` bundles
    shipped to the browser for class-name or selector rehydration.

    **Security concept:** *String obfuscation is not encryption* — it defeats
    grep-based IOC extraction but provides **zero confidentiality** against
    anyone who sees the key in HTML/JS (a common student misconception).
    """
    p = plain.encode("utf-8", errors="strict")
    k = key.encode("utf-8", errors="strict")
    if not k:
        raise ValueError("xor key must be non-empty")
    out = bytes(p[i] ^ k[i % len(k)] for i in range(len(p)))
    return base64.urlsafe_b64encode(out).decode("ascii").rstrip("=")


def xor_deobfuscate_utf8(blob: str, key: str) -> str:
    """
    Reverse `xor_obfuscate_utf8` (XOR is self-inverse under the same key).

    **Security concept:** *Symmetric obfuscation* — identical to PHP `base64_decode`
    followed by the same XOR loop used client-side to rebuild DOM class lists.
    """
    pad = "=" * (-len(blob) % 4)
    raw = base64.urlsafe_b64decode((blob + pad).encode("ascii"))
    k = key.encode("utf-8", errors="strict")
    if not k:
        raise ValueError("xor key must be non-empty")
    out = bytes(raw[i] ^ k[i % len(k)] for i in range(len(raw)))
    return out.decode("utf-8", errors="strict")


def build_ui_class_map(labels: list[str], xor_key: str) -> dict[str, str]:
    """
    Produce a mapping `{logical_name: obfuscated_blob}` for UI class tokens.

    **Original PHP logic:** Server emits a JSON dictionary; JS replaces placeholders
    after XOR decode so static HTML never contains raw class strings.

    **Security concept:** *Evasion vs detection trade-off* — defenders fingerprint
    DOM structure; attackers rotate encodings. Labs study both sides.
    """
    return {name: xor_obfuscate_utf8(name, xor_key) for name in labels}


def _truthy_env(name: str) -> bool:
    """
    Return True when an environment flag is set to common affirmative strings.

    **Original PHP logic:** `in_array(strtolower(getenv('FLAG')), ['1','true'])` style
    toggles used across `engine.php` to enable optional strict branches.

    **Security concept:** *Operational kill-switches* — runtime flags let operators
    tighten defenses during an attack without redeploying code.
    """
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _truthy_live(name: str) -> bool:
    """Like ``_truthy_env`` but prefers on-disk ``.env`` when hot-reload path is set."""
    return (_live_env(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _rate_window_seconds() -> int:
    """
    Read configured sliding window for per-IP rate limiting (default 60s).

    **Original PHP logic:** `RATE_WINDOW` constants beside Redis/memcached TTL knobs.

    **Security concept:** *Time-windowed quotas* — bounds memory for hit counters
    while still smoothing bursts inside the window.
    """
    try:
        return int(os.environ.get("DEMO_RATE_WINDOW_SEC", "60"))
    except ValueError:
        return 60


def lifetime_gate_max() -> int:
    """
    Max **lifetime quota slots** per IP for the lab (default 10), then **permanent** deny.

    Each slot is one successful gate pass **or** one external-guard terminal deny
    recorded in SQLite (see ``incident_store.count_gate_lifetime_quota_used``).

    **Security concept:** *Fixed quota / burn-after-N* — models one-shot invite links or
    kiosk sessions; clearing ``incidents.db`` resets the lab counter.
    """
    try:
        return int(os.environ.get("DEMO_GATE_LIFETIME_MAX_ALLOWS_PER_IP", "10"))
    except ValueError:
        return 10


def _rate_max_hits() -> int:
    """
    Read configured max in-memory ``POST /p`` attempts per sliding window (default 600).

    **Original PHP logic:** `MAX_HITS` paired with `RATE_WINDOW` in gate configs.

    **Security concept:** *Threshold tuning* — trade-off between false positives for
    NAT users and protection against parallel scripted requests.
    """
    try:
        return int(os.environ.get("DEMO_RATE_MAX", "600"))
    except ValueError:
        return 600


def rate_limit_snapshot(ip: str, hits_store: dict[str, list[float]]) -> dict[str, Any]:
    """
    Read-only view of the in-memory sliding-window rate limit (same rule as step 2).
    """
    window = _rate_window_seconds()
    max_hits = _rate_max_hits()
    now = time.time()
    hits = hits_store.get(ip, [])
    pruned = [t for t in hits if now - t < window]
    oldest = min(pruned) if pruned else None
    return {
        "ip": ip,
        "window_seconds": window,
        "max_hits_per_window": max_hits,
        "post_attempts_in_current_window": len(pruned),
        "would_block_next_post": len(pruned) >= max_hits,
        "oldest_hit_epoch": oldest,
        "window_resets_epoch_approx": (oldest + window) if oldest is not None else None,
        "rate_source": "memory",
    }


def step_lifetime_ip_quota(ip: str, sql_root: Path | None) -> GateDecision | None:
    """
    **Pipeline step 1 — Lifetime gate quota per IP (SQLite).**

    After ``DEMO_GATE_LIFETIME_MAX_ALLOWS_PER_IP`` **consumed slots** for this IP, every
    further ``POST /p`` is rejected with ``lifetime_ip_cap`` (HTTP 403) until the lab
    database is reset or the limit is increased. A slot is one successful pass **or**
    one terminal deny from the external guard (``external_guard_*`` reasons in the
    audit row).

    **Security concept:** *Non-replenishing quota* — unlike sliding windows, models
    “this kiosk may enroll ten visitors total.”
    """
    if sql_root is None:
        return None
    cap = lifetime_gate_max()
    if cap <= 0:
        return None
    n = incident_store.count_gate_lifetime_quota_used(sql_root, ip)
    if n >= cap:
        return GateDecision(
            False,
            403,
            "lifetime_ip_cap",
            {"score": 100, "decision": "deny", "lifetime_used": n, "lifetime_cap": cap},
        )
    return None


def step_rate_limiting(
    ip: str,
    hits_store: dict[str, list[float]],
) -> GateDecision | None:
    """
    **Pipeline step 2 — Rate limiting (in-memory sliding window).**

    **Original PHP logic:** In-memory or Redis counters keyed by `REMOTE_ADDR`.

    **Security concept:** *Cost asymmetry mitigation* — cheap checks before PoW/HMAC.
    """
    now = time.time()
    window = _rate_window_seconds()
    max_hits = _rate_max_hits()
    hits = hits_store.setdefault(ip, [])
    hits[:] = [t for t in hits if now - t < window]
    if len(hits) >= max_hits:
        return GateDecision(False, 429, "rate_limit", {"score": 100, "decision": "deny"})
    hits.append(now)
    return None


def _host_blacklist() -> set[str]:
    """
    Parse `DEMO_HOST_BLACKLIST` as comma-separated lowercase hostnames.

    **Security concept:** *Virtual-host allow/deny* — kits sometimes block hosting
    provider default domains to reduce automated sandbox hits.
    """
    raw = os.environ.get("DEMO_HOST_BLACKLIST", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def step_host_blacklisting(host_header: str | None) -> GateDecision | None:
    """
    **Pipeline step 2 — Host header blacklist.**

    **Original PHP logic:** `$_SERVER['HTTP_HOST']` compared to deny lists / regex.

    **Security concept:** *HTTP host header attacks* — mismatched hosts can poison
    caches or hit unintended vhosts; explicit deny rules model CDN/WAF lists.
    """
    host = (host_header or "").strip().lower()
    if not host:
        return GateDecision(False, 400, "missing_host", {"score": 80, "decision": "deny"})
    bl = _host_blacklist()
    if bl and host in bl:
        return GateDecision(False, 403, "host_blacklisted", {"score": 100, "decision": "deny"})
    return None


def _ua_blacklist_substrings() -> list[str]:
    """
    Parse `DEMO_UA_BLACKLIST` as comma-separated case-insensitive substrings.

    **Security concept:** *Automation fingerprinting* — naive bots advertise
    library User-Agent strings; deny rules are brittle but cheap.
    """
    raw = os.environ.get("DEMO_UA_BLACKLIST", "")
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def step_ua_blacklisting(user_agent: str | None) -> GateDecision | None:
    """
    **Pipeline step 3 — User-Agent blacklist.**

    **Original PHP logic:** `stripos($_SERVER['HTTP_USER_AGENT'], 'curl')` style gates.

    **Security concept:** *Signal stacking* — UA alone is spoofable; combined with
    PoW/HMAC it raises attacker cost (defenders still must not trust UA).
    """
    ua = (user_agent or "").lower()
    for needle in _ua_blacklist_substrings():
        if needle and needle in ua:
            return GateDecision(False, 403, "ua_blacklisted", {"score": 95, "decision": "deny"})
    return None


def _incognito_hint_from_body(
    client_flags: Mapping[str, Any] | None,
    fingerprint_signals: Mapping[str, Any] | None,
) -> bool:
    """True when the browser reported a private-mode hint (client-side heuristics only)."""
    if isinstance(client_flags, dict) and bool(client_flags.get("incognito")):
        return True
    if isinstance(fingerprint_signals, dict) and bool(
        fingerprint_signals.get("incognito_storage_hint")
    ):
        return True
    return False


def step_incognito_detection(
    client_flags: Mapping[str, Any] | None,
    fingerprint_signals: Mapping[str, Any] | None = None,
) -> GateDecision | None:
    """
    **Pipeline step 4 — Incognito / private-mode *hint* ingestion.**

    **Original PHP logic:** Kits often read JS `navigator.webdriver`, storage quota,
    or `chrome.runtime` heuristics sent as JSON flags; server **cannot** prove
    incognito without client cooperation.

    **Security concept:** *Client-supplied context is untrusted* — we **score** rather
    than hard-block unless ``DEMO_INCOGNITO_BLOCK`` is on (instructor-only strict mode).
    Uses ``_truthy_live`` so toggles follow the same hot-reloaded ``.env`` as the
    external guard when configured.
    """
    if not _incognito_hint_from_body(client_flags, fingerprint_signals):
        return None
    if _truthy_live("DEMO_INCOGNITO_BLOCK"):
        return GateDecision(False, 403, "incognito_blocked", {"score": 70, "decision": "deny"})
    return None


def _score_from_signals(signals: Mapping[str, Any] | None) -> int:
    """
    Derive partial risk points from fingerprint/behavior signal dictionaries.

    **Security concept:** *Behavioral biometrics as risk signals* — anomalies add
    points; legitimate users may still pass under threshold.
    """
    if not signals:
        return 15
    score = 0
    if signals.get("webdriver") is True:
        score += 40
    if signals.get("languages_empty") is True:
        score += 10
    if int(signals.get("plugin_count") or 0) == 0:
        score += 5
    if signals.get("devtools_timing_anomaly") is True:
        score += 25
    if signals.get("debugger_tripped") is True:
        score += 20
    tz = str(signals.get("timezone") or "")
    if not tz:
        score += 10
    return min(100, score)


def step_risk_scoring(
    client_flags: Mapping[str, Any] | None,
    fingerprint_signals: Mapping[str, Any] | None,
    behavior_signals: Mapping[str, Any] | None,
) -> tuple[GateDecision | None, dict[str, Any]]:
    """
    **Pipeline step 5 — Composite risk scoring.**

    **Original PHP logic:** Weighted sums of bot hints + timing checks + TLS/JA3
    placeholders; kits clamp to `[0,100]` then branch on thresholds.

    **Security concept:** *Risk-based access control* — continuous authentication
    ideas ported to a single gate decision for pedagogy.
    """
    base = 0
    if _incognito_hint_from_body(client_flags, fingerprint_signals):
        base += 12
    fp_score = _score_from_signals(fingerprint_signals)
    bh_score = _score_from_signals(behavior_signals)
    total = min(100, base + fp_score // 2 + bh_score // 2)
    risk = {"score": total, "decision": "review" if total >= 60 else "allow"}
    try:
        threshold = int(os.environ.get("DEMO_RISK_BLOCK_THRESHOLD", "100"))
    except ValueError:
        threshold = 100
    if total >= threshold:
        return GateDecision(False, 403, "risk_threshold", risk), risk
    return None, risk


def step_api_handshake(
    *,
    session_csrf_expected: str | None,
    body_csrf: str | None,
    handshake_expected: str | None,
    body_handshake: str | None,
    pow_id: str | None,
    pow_zeros: int,
    pow_nonce: Any,
    verify_pow_fn,
) -> GateDecision | None:
    """
    **Pipeline step 6 — API handshake (CSRF + PoW + nonce).**

    **Original PHP logic:** Session token validation combined with server-issued
    challenge IDs (`pow_id`) and client-returned `pow_nonce`.

    **Security concept:** *Request Integrity Protection* — binds the POST to a prior
    GET (`/start`) and forces a client puzzle expensive for dumb bots.
    """
    if not _truthy_env("DEMO_GATE_CSRF_DISABLED"):
        exp = (session_csrf_expected or "").strip()
        got = (body_csrf or "").strip()
        if not exp or not got or not hmac.compare_digest(exp, got):
            return GateDecision(False, 400, "bad_csrf", {"score": 90, "decision": "deny"})

    if not _truthy_env("DEMO_HANDSHAKE_DISABLED"):
        hexp = (handshake_expected or "").strip()
        hgot = (body_handshake or "").strip()
        if not hexp or not hgot or not hmac.compare_digest(hexp, hgot):
            return GateDecision(False, 400, "bad_handshake", {"score": 85, "decision": "deny"})

    if pow_zeros > 0:
        pid = (pow_id or "").strip()
        if len(pid) < 8:
            return GateDecision(False, 400, "missing_pow_challenge", {"score": 50, "decision": "deny"})
        nonce = str(pow_nonce if pow_nonce is not None else "")
        if not verify_pow_fn(pid, nonce, pow_zeros):
            return GateDecision(False, 400, "bad_pow", {"score": 60, "decision": "deny"})
    return None


def step_hmac_request_signing(
    *,
    secret: str,
    body: Mapping[str, Any],
    ts: Any,
    sig: Any,
    skew_sec: int = 120,
) -> GateDecision | None:
    """
    **Pipeline step 7 — HMAC request signing.**

    **Original PHP logic:** `hash_hmac('sha256', $ts.'|'.$canonical_json, $secret)`
    compared in constant time to client `sig`.

    **Security concept:** *Message authentication* — proves payload integrity +
    freshness window when the secret is **not** public (labs may intentionally
    violate this by embedding secrets client-side to teach why it fails).
    """
    if not secret:
        return None
    if ts is None or sig is None:
        return GateDecision(False, 400, "missing_sig", {"score": 80, "decision": "deny"})
    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        return GateDecision(False, 400, "bad_ts", {"score": 70, "decision": "deny"})
    if abs(int(time.time()) - ts_int) > skew_sec:
        return GateDecision(False, 400, "stale_ts", {"score": 65, "decision": "deny"})
    body_for_sig = {k: v for k, v in body.items() if k not in ("ts", "sig")}
    canonical = json.dumps(body_for_sig, sort_keys=True, separators=(",", ":"))
    msg = f"{ts_int}|{canonical}".encode("utf-8", errors="strict")
    expected = hmac.new(secret.encode("utf-8", errors="strict"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(sig)):
        return GateDecision(False, 400, "bad_sig", {"score": 95, "decision": "deny"})
    return None


def _external_guard_timeout_sec() -> float:
    try:
        return max(1.0, min(30.0, float((_live_env("DEMO_EXTERNAL_GUARD_TIMEOUT_SEC") or "5").strip() or "5")))
    except ValueError:
        return 5.0


def _external_guard_fail_open() -> bool:
    """
    When True (default), unreachable/ambiguous remote responses do not block the gate.
    Set ``DEMO_EXTERNAL_GUARD_FAIL_OPEN=false`` to deny on errors instead.
    """
    raw = (_live_env("DEMO_EXTERNAL_GUARD_FAIL_OPEN") or "true").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def _external_guard_env_token(raw: str | None) -> str:
    """Strip BOM and wrapping quotes from ``.env`` values."""
    return (raw or "").strip().strip("\ufeff\"'")


def _external_guard_switch_on() -> bool:
    """
    Single master switch: ``DEMO_EXTERNAL_GUARD``.

    **On** when value (case-insensitive) is one of: ``1``, ``true``, ``yes``, ``on``.
    **Off** when unset, empty, or anything else (``0``, ``false``, ``off``, …).
    """
    v = _external_guard_env_token(_live_env("DEMO_EXTERNAL_GUARD")).lower()
    return v in ("1", "true", "yes", "on")


def external_guard_runtime_status() -> dict[str, Any]:
    """
    Read-only snapshot for the gate debug dashboard (no secrets).

    ``guard_env_live`` matches what ``POST /p`` uses (live ``.env`` read when configured).
    """
    live_raw = _external_guard_env_token(_live_env("DEMO_EXTERNAL_GUARD"))
    url_set = bool((_live_env("DEMO_EXTERNAL_GUARD_URL") or "").strip())
    key_set = bool((_live_env("DEMO_EXTERNAL_GUARD_API_KEY") or "").strip())
    switch = _external_guard_switch_on()

    return {
        "guard_env_live": live_raw or "(empty)",
        "guard_env_raw": live_raw or "(empty)",
        "guard_state": "on" if switch else "off",
        "url_configured": url_set,
        "api_key_configured": key_set,
        "will_post_to_remote": bool(switch and url_set and key_set),
        "dotenv_hot_reload": bool(_RUNTIME_DOTENV_PATH and _RUNTIME_DOTENV_PATH.is_file()),
    }


def step_external_guard(client_ip: str, user_agent: str | None) -> GateDecision | None:
    """
    **Pipeline step 9 (optional) — remote policy after all local checks pass.**

    POST JSON ``{"ip": ..., "useragent": ...}`` with ``X-API-Key`` when
    ``DEMO_EXTERNAL_GUARD`` is on **and** URL + API key are set.

    **Security concept:** *Outsourced policy as final arbiter* — geo / reputation
    services return ``access_granted`` or ``access_denied``; only a clear deny
    blocks; transport failures follow ``DEMO_EXTERNAL_GUARD_FAIL_OPEN``.
    """
    if not _external_guard_switch_on():
        return None
    url = (_live_env("DEMO_EXTERNAL_GUARD_URL") or "").strip()
    api_key = (_live_env("DEMO_EXTERNAL_GUARD_API_KEY") or "").strip()
    if not url or not api_key:
        return None

    payload_obj = {"ip": client_ip, "useragent": (user_agent or "")[:2048]}
    payload = json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )
    timeout = _external_guard_timeout_sec()
    fail_open = _external_guard_fail_open()
    raw = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")[:8192]
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")[:8192]
        except Exception:
            raw = ""
    except (urllib.error.URLError, TimeoutError, OSError):
        if fail_open:
            return None
        return GateDecision(
            False,
            503,
            "external_guard_unreachable",
            {"score": 100, "decision": "deny", "external": "request_failed"},
        )

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        if fail_open:
            return None
        return GateDecision(
            False,
            503,
            "external_guard_bad_payload",
            {"score": 100, "decision": "deny", "external": "invalid_json"},
        )

    if not isinstance(data, dict):
        if fail_open:
            return None
        return GateDecision(
            False,
            503,
            "external_guard_bad_payload",
            {"score": 100, "decision": "deny", "external": "not_object"},
        )

    status = str(data.get("status") or "").strip().lower()
    if status == "access_denied":
        reason = str(data.get("reason") or "denied").strip()
        if len(reason) > 500:
            reason = reason[:500] + "..."
        return GateDecision(
            False,
            403,
            "external_guard_denied",
            {
                "score": 100,
                "decision": "deny",
                "external_status": "access_denied",
                "external_reason": reason,
                "reason": reason,
            },
        )
    if status == "access_granted":
        return None
    if fail_open:
        return None
    return GateDecision(
        False,
        503,
        "external_guard_unclear",
        {
            "score": 100,
            "decision": "deny",
            "external": "unexpected_status",
            "external_status": status or "(empty)",
        },
    )


def verify_pow_sha256_leading_hex(pow_id: str, nonce: str, zeros: int) -> bool:
    """
    Validate PoW: `SHA256(pow_id + nonce)` hex must start with `zeros` literal `'0'` chars.

    **Original PHP logic:** Same digest prefix check implemented in `engine.php`.

    **Security concept:** *Client puzzles* — shift CPU cost toward the browser for
    anonymous endpoints; not a CAPTCHA replacement.
    """
    if zeros <= 0:
        return True
    msg = f"{pow_id}{nonce}".encode("utf-8", errors="strict")
    hx = hashlib.sha256(msg).hexdigest()
    return hx.startswith("0" * zeros)


def process_gate_submission(
    *,
    client_ip: str,
    host_header: str | None,
    user_agent: str | None,
    body: dict[str, Any],
    gate_csrf: str | None,
    gate_pow_id: str | None,
    gate_pow_zeros: int,
    gate_handshake: str | None,
    rate_store: dict[str, list[float]],
    hmac_secret: str,
    quota_sql_root: Path | None = None,
) -> GateDecision:
    """
    **`proc.php` entrypoint** — run all local steps, then optional external guard, and return a decision.

    **Original PHP logic:** Central dispatcher that included `engine.php`, validated
    JSON, updated counters, and emitted JSON `{status, redirect, risk}`.

    **Security concept:** *Ordered defense in depth* — each layer short-circuits
    failures to keep later secrets and tokens unreachable to obvious bots.
    """
    r0 = step_lifetime_ip_quota(client_ip, quota_sql_root)
    if r0:
        return r0
    r1 = step_rate_limiting(client_ip, rate_store)
    if r1:
        return r1
    r2 = step_host_blacklisting(host_header)
    if r2:
        return r2
    r3 = step_ua_blacklisting(user_agent)
    if r3:
        return r3

    client_flags = body.get("client_flags") if isinstance(body.get("client_flags"), dict) else {}
    fp_sig = body.get("fingerprint_signals") if isinstance(body.get("fingerprint_signals"), dict) else {}
    r4 = step_incognito_detection(client_flags, fp_sig)
    if r4:
        return r4

    bh_sig = body.get("behavior_signals") if isinstance(body.get("behavior_signals"), dict) else {}
    r5, risk = step_risk_scoring(client_flags, fp_sig, bh_sig)
    if r5:
        return r5

    pow_zeros = int(gate_pow_zeros or 0)
    r6 = step_api_handshake(
        session_csrf_expected=gate_csrf,
        body_csrf=str(body.get("csrf") or "").strip() or None,
        handshake_expected=gate_handshake,
        body_handshake=str(body.get("handshake_nonce") or "").strip() or None,
        pow_id=str(gate_pow_id or "").strip() or None,
        pow_zeros=pow_zeros,
        pow_nonce=body.get("pow_nonce"),
        verify_pow_fn=verify_pow_sha256_leading_hex,
    )
    if r6:
        return r6

    r7 = step_hmac_request_signing(secret=hmac_secret, body=body, ts=body.get("ts"), sig=body.get("sig"))
    if r7:
        return r7

    fp_hash = str(body.get("fingerprint_hash") or "").strip()
    if len(fp_hash) < 8:
        return GateDecision(False, 400, "weak_client", {**risk, "decision": "deny"})

    r8 = step_external_guard(client_ip, user_agent)
    if r8:
        return GateDecision(
            r8.allowed,
            r8.http_status,
            r8.reason,
            {**risk, **r8.risk},
        )

    return GateDecision(True, 200, "ok", risk)
