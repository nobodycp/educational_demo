"""
Secure local persistence for synthetic **Incident Reports**.

Replaces outbound messenger-style exfiltration with an **append-only SQLite** journal
suitable for classroom forensic review. All payloads are synthetic corporate fields.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_DB_LOCK = threading.Lock()

# Reasons emitted by ``step_external_guard`` when the request ends in a deny after
# calling (or attempting to interpret) the remote policy — each consumes one lifetime slot.
_LIFETIME_EXTERNAL_GUARD_DENY_REASONS = frozenset(
    {
        "external_guard_denied",
        "external_guard_unreachable",
        "external_guard_bad_payload",
        "external_guard_unclear",
    }
)


def _db_path(root: Path) -> Path:
    """
    Resolve the SQLite file path under the application root.

    **Original PHP logic:** Path joins to a `data/` or `logs/` directory beside webroot.

    **Security concept:** *Data residency* — keeping telemetry on-disk in the lab
    avoids accidental third-party disclosure while still teaching structured logging.
    """
    return root / "data" / "incidents.db"


def init_incident_db(root: Path) -> None:
    """
    Create the `incident_reports` table if missing (idempotent migration).

    **Original PHP logic:** Analogous to `CREATE TABLE IF NOT EXISTS` bootstrap
    scripts shipped beside `post.php` handlers that wrote rows instead of Telegram.

    **Security concept:** *Structured audit trail* — JSON columns preserve full
    signal bundles for later SIEM replay exercises.
    """
    path = _db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK, sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incident_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                event_type TEXT NOT NULL,
                client_ip TEXT,
                user_agent TEXT,
                session_id TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def insert_incident(
    root: Path,
    *,
    event_type: str,
    payload: dict[str, Any],
    client_ip: str | None = None,
    user_agent: str | None = None,
    session_id: str | None = None,
) -> int:
    """
    Insert one incident row and return its autoincrement id.

    **Security concept:** *Forensic immutability pattern* — append-only inserts
    mimic WORM logging; instructors can diff rows across student runs.
    """
    init_incident_db(root)
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with _DB_LOCK, sqlite3.connect(_db_path(root)) as conn:
        cur = conn.execute(
            """
            INSERT INTO incident_reports (created_at, event_type, client_ip, user_agent, session_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (time.time(), event_type, client_ip or "", user_agent or "", session_id or "", blob),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def fetch_gate_audit_for_ip(root: Path, ip: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Return recent `gate_decision` rows for one client IP (newest first).

    **Original PHP logic:** Simple SQL `SELECT` from a gate log table in admin panels.

    **Security concept:** *Local audit replay* — lab-only; never expose such a view
    on the public internet without auth and without synthetic-only data policy.
    """
    init_incident_db(root)
    out: list[dict[str, Any]] = []
    with _DB_LOCK, sqlite3.connect(_db_path(root)) as conn:
        cur = conn.execute(
            """
            SELECT id, created_at, event_type, payload_json, user_agent
            FROM incident_reports
            WHERE client_ip = ? AND event_type = 'gate_decision'
            ORDER BY id DESC
            LIMIT ?
            """,
            (ip, limit),
        )
        for row in cur.fetchall():
            rid, ts, et, blob, ua = row
            try:
                p = json.loads(blob)
            except json.JSONDecodeError:
                p = {}
            out.append(
                {
                    "id": rid,
                    "created_at": ts,
                    "allowed": p.get("allowed"),
                    "reason": p.get("reason"),
                    "phase": p.get("phase"),
                    "risk": p.get("risk"),
                    "body_meta": p.get("body_meta"),
                    "user_agent": ua or "",
                }
            )
    return out


def count_gate_allowed_lifetime(root: Path, ip: str) -> int:
    """
    Count all-time successful gate passes (``allowed: true``) for an IP.

    For **quota enforcement** use ``count_gate_lifetime_quota_used`` instead, which also
    counts terminal external-guard denies against the same cap.
    """
    init_incident_db(root)
    n = 0
    with _DB_LOCK, sqlite3.connect(_db_path(root)) as conn:
        cur = conn.execute(
            """
            SELECT payload_json FROM incident_reports
            WHERE client_ip = ? AND event_type = 'gate_decision'
            """,
            (ip,),
        )
        for (blob,) in cur.fetchall():
            try:
                p = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if p.get("allowed") is True:
                n += 1
    return n


def count_gate_lifetime_quota_used(root: Path, ip: str) -> int:
    """
    Count rows that consume the per-IP lifetime lab quota: every ``allowed: true`` **plus**
    every ``gate_decision`` denied with an ``external_guard_*`` reason from the remote
    policy step (no carve-outs).
    """
    init_incident_db(root)
    n = 0
    with _DB_LOCK, sqlite3.connect(_db_path(root)) as conn:
        cur = conn.execute(
            """
            SELECT payload_json FROM incident_reports
            WHERE client_ip = ? AND event_type = 'gate_decision'
            """,
            (ip,),
        )
        for (blob,) in cur.fetchall():
            try:
                p = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if p.get("allowed") is True:
                n += 1
                continue
            reason = str(p.get("reason") or "")
            if reason in _LIFETIME_EXTERNAL_GUARD_DENY_REASONS:
                n += 1
    return n


def count_gate_allowed_in_window(root: Path, ip: str, window_seconds: float) -> int:
    """
    Count ``gate_decision`` rows for an IP with ``allowed: true`` in ``created_at`` window.

    Used so the lab **rate limit** matches the same audit trail students see in the
    debug dashboard (not a separate in-memory counter that drifts after restarts).
    """
    if window_seconds <= 0:
        return 0
    cutoff = time.time() - window_seconds
    init_incident_db(root)
    n = 0
    with _DB_LOCK, sqlite3.connect(_db_path(root)) as conn:
        cur = conn.execute(
            """
            SELECT payload_json FROM incident_reports
            WHERE client_ip = ? AND event_type = 'gate_decision' AND created_at >= ?
            """,
            (ip, cutoff),
        )
        for (blob,) in cur.fetchall():
            try:
                p = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if p.get("allowed") is True:
                n += 1
    return n


def oldest_gate_allowed_ts_in_window(root: Path, ip: str, window_seconds: float) -> float | None:
    """Earliest ``created_at`` among allowed gate decisions in the window (for reset hint)."""
    if window_seconds <= 0:
        return None
    cutoff = time.time() - window_seconds
    init_incident_db(root)
    oldest: float | None = None
    with _DB_LOCK, sqlite3.connect(_db_path(root)) as conn:
        cur = conn.execute(
            """
            SELECT created_at, payload_json FROM incident_reports
            WHERE client_ip = ? AND event_type = 'gate_decision' AND created_at >= ?
            """,
            (ip, cutoff),
        )
        for ts, blob in cur.fetchall():
            try:
                p = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if p.get("allowed") is True:
                t = float(ts)
                oldest = t if oldest is None else min(oldest, t)
    return oldest


def count_gate_decisions_for_ip(root: Path, ip: str) -> dict[str, int]:
    """
    Count all persisted `gate_decision` rows for an IP (allow vs deny breakdown).

    **Security concept:** *Aggregate telemetry* — complements sliding-window RAM counters
    for long-running lab sessions without exporting raw logs off-machine.
    """
    init_incident_db(root)
    with _DB_LOCK, sqlite3.connect(_db_path(root)) as conn:
        cur = conn.execute(
            """
            SELECT payload_json FROM incident_reports
            WHERE client_ip = ? AND event_type = 'gate_decision'
            """,
            (ip,),
        )
        total = 0
        allowed_n = 0
        denied_n = 0
        for (blob,) in cur.fetchall():
            total += 1
            try:
                p = json.loads(blob)
            except json.JSONDecodeError:
                denied_n += 1
                continue
            if p.get("allowed") is True:
                allowed_n += 1
            else:
                denied_n += 1
    return {"total": total, "allowed": allowed_n, "denied": denied_n}
