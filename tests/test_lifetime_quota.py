"""Lifetime quota counts all gate decisions (allow + deny)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend import incident_store


class TestLifetimeQuotaUsed(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def test_allow_and_deny_both_count(self) -> None:
        incident_store.init_incident_db(self.root)
        ip = "198.51.100.7"
        incident_store.insert_incident(
            self.root,
            event_type="gate_decision",
            client_ip=ip,
            payload={"allowed": True, "reason": "ok", "risk": {}},
        )
        incident_store.insert_incident(
            self.root,
            event_type="gate_decision",
            client_ip=ip,
            payload={
                "allowed": False,
                "reason": "bad_csrf",
                "risk": {},
            },
        )
        self.assertEqual(incident_store.count_gate_lifetime_quota_used(self.root, ip), 2)
        self.assertEqual(incident_store.count_gate_allowed_lifetime(self.root, ip), 1)

    def test_any_deny_counts(self) -> None:
        incident_store.init_incident_db(self.root)
        ip = "198.51.100.8"
        incident_store.insert_incident(
            self.root,
            event_type="gate_decision",
            client_ip=ip,
            payload={"allowed": False, "reason": "bad_csrf", "risk": {}},
        )
        self.assertEqual(incident_store.count_gate_lifetime_quota_used(self.root, ip), 1)

    def test_mixed_denies_all_count(self) -> None:
        incident_store.init_incident_db(self.root)
        ip = "198.51.100.9"
        for reason in (
            "external_guard_unreachable",
            "external_guard_bad_payload",
            "external_guard_unclear",
            "risk_threshold",
            "bad_pow",
        ):
            incident_store.insert_incident(
                self.root,
                event_type="gate_decision",
                client_ip=ip,
                payload={"allowed": False, "reason": reason, "risk": {}},
            )
        self.assertEqual(incident_store.count_gate_lifetime_quota_used(self.root, ip), 5)


if __name__ == "__main__":
    unittest.main()
