"""POST /api/demo/shell-guard-deny appends a gate_decision for debug audit."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from backend.app import SESSION_GATE_CSRF, create_app


class TestShellGuardDenyApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Same as test_shell_guard: do not use workspace .env for guard toggles.
        cls._gkp = mock.patch("dotenv.get_key", return_value=None)
        cls._gkp.start()
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls) -> None:
        cls._gkp.stop()

    def _env(self, **overrides: str) -> dict:
        m = {
            "GUARD_DEVTOOLS": "1",
            "DEMO_STRICT_ORIGIN": "",
        }
        m.update(overrides)
        return m

    def test_ok_with_gate_csrf(self) -> None:
        with mock.patch.dict(os.environ, self._env(), clear=False):
            client = self.app.test_client()
            tok = "a" * 32
            with client.session_transaction() as sess:  # type: ignore[attr-defined]
                sess[SESSION_GATE_CSRF] = tok
            r = client.post(
                "/api/demo/shell-guard-deny",
                json={"subreason": "devtools_timing"},
                headers={"X-CSRF-Token": tok, "Content-Type": "application/json"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json().get("ok"))

    def test_403_on_bad_csrf(self) -> None:
        with mock.patch.dict(os.environ, self._env(), clear=False):
            client = self.app.test_client()
            with client.session_transaction() as sess:  # type: ignore[attr-defined]
                sess[SESSION_GATE_CSRF] = "a" * 32
            r = client.post(
                "/api/demo/shell-guard-deny",
                json={},
                headers={"X-CSRF-Token": "b" * 32, "Content-Type": "application/json"},
            )
        self.assertEqual(r.status_code, 403)

    def test_404_when_guard_disabled(self) -> None:
        with mock.patch.dict(os.environ, self._env(GUARD_DEVTOOLS="0"), clear=False):
            client = self.app.test_client()
            tok = "a" * 32
            with client.session_transaction() as sess:  # type: ignore[attr-defined]
                sess[SESSION_GATE_CSRF] = tok
            r = client.post(
                "/api/demo/shell-guard-deny",
                json={},
                headers={"X-CSRF-Token": tok, "Content-Type": "application/json"},
            )
        self.assertEqual(r.status_code, 404)
