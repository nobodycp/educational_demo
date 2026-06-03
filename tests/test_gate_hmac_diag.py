"""HMAC gate step returns actionable subreason/hint for bad_sig and related failures."""

from __future__ import annotations

import json
import time
import unittest

from backend import gate_engine


class GateHmacDiagTests(unittest.TestCase):
    def test_bad_sig_includes_subreason_and_hint(self) -> None:
        body = {"note": "x", "csrf": "abc"}
        ts = int(time.time())
        r = gate_engine.step_hmac_request_signing(
            secret="test-secret",
            body={**body, "ts": ts, "sig": "0" * 64},
            ts=ts,
            sig="0" * 64,
        )
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.reason, "bad_sig")
        self.assertEqual(r.risk.get("subreason"), "digest_mismatch")
        self.assertIn("GATE_HMAC_SECRET", r.risk.get("hint", ""))
        self.assertTrue(r.risk.get("server_hmac_configured"))

    def test_hmac_disabled_client_signed(self) -> None:
        r = gate_engine.step_hmac_request_signing(
            secret="",
            body={"note": "x"},
            ts=int(time.time()),
            sig="deadbeef",
        )
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.reason, "hmac_disabled_client_signed")
        self.assertEqual(r.risk.get("subreason"), "server_hmac_off_client_sent_sig")
        self.assertIn("stale", r.risk.get("hint", "").lower())

    def test_missing_sig_when_secret_set(self) -> None:
        r = gate_engine.step_hmac_request_signing(
            secret="s",
            body={"note": "x"},
            ts=None,
            sig=None,
        )
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.reason, "missing_sig")
        self.assertEqual(r.risk.get("subreason"), "missing_ts_or_sig")

    def test_stale_ts_reports_skew(self) -> None:
        old_ts = int(time.time()) - 500
        r = gate_engine.step_hmac_request_signing(
            secret="s",
            body={"note": "x", "ts": old_ts, "sig": "a" * 64},
            ts=old_ts,
            sig="a" * 64,
            skew_sec=120,
        )
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.reason, "stale_ts")
        self.assertGreater(r.risk.get("ts_skew_sec", 0), 120)


if __name__ == "__main__":
    unittest.main()
