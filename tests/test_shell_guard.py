"""Shell guard injection and env toggles."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from backend import app as app_mod


class TestShellGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Avoid reading the repo .env in tests; rely on os.environ from patch.* below.
        cls._gkp = mock.patch("dotenv.get_key", return_value=None)
        cls._gkp.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._gkp.stop()
    def test_inject_inserts_url_when_enabled(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "DEMO_GATE_BLOCKED_REDIRECT_URL": "https://example.com/away",
                "GUARD_DEVTOOLS": "1",
            },
            clear=False,
        ):
            raw = "before__DEMO_BANGO_SHELL_INJECT__after"
            out = app_mod._bango_inject_shell_guard(raw, "csrf-for-bango")
        self.assertNotIn("__DEMO_BANGO_SHELL_INJECT__", out)
        self.assertIn("https://example.com/away", out)
        self.assertIn("shell-guard.js", out)
        self.assertIn('"enabled"', out)
        self.assertIn("true", out)
        self.assertIn("blockedUrl", out)
        self.assertIn("csrf-for-bango", out)
        self.assertIn("reportCsrf", out)

    def test_inject_strips_token_when_guard_off(self) -> None:
        with mock.patch.dict(os.environ, {"GUARD_DEVTOOLS": "0"}, clear=False):
            out = app_mod._bango_inject_shell_guard("__DEMO_BANGO_SHELL_INJECT__")
        self.assertEqual(out, "")

    def test_shell_guard_enabled(self) -> None:
        with mock.patch.dict(os.environ, {"DEMO_SHELL_GUARD": "off"}, clear=False):
            self.assertFalse(app_mod._shell_guard_enabled())
        with mock.patch.dict(
            os.environ,
            # Must override any GUARD_DEVTOOLS from process env (see _read order).
            {"GUARD_DEVTOOLS": "1", "DEMO_SHELL_GUARD": "1"},
            clear=False,
        ):
            self.assertTrue(app_mod._shell_guard_enabled())
        with mock.patch.dict(
            os.environ,
            {"GUARD_DEVTOOLS": "0", "DEMO_SHELL_GUARD": "1"},
            clear=False,
        ):
            self.assertFalse(app_mod._shell_guard_enabled(), "GUARD_DEVTOOLS should win over DEMO_SHELL_GUARD")
        with mock.patch.dict(
            os.environ,
            {"guard_devtools": "0", "GUARD_DEVTOOLS": "", "DEMO_SHELL_GUARD": "1"},
            clear=False,
        ):
            self.assertFalse(app_mod._shell_guard_enabled())

    def test_file_dotenv_takes_precedence_over_stale_process_env(self) -> None:
        with mock.patch.dict(
            os.environ, {"GUARD_DEVTOOLS": "1"}, clear=False
        ), mock.patch(
            "dotenv.get_key", return_value="0"
        ):
            self.assertFalse(
                app_mod._shell_guard_enabled(),
                "value from .env (get_key) should override os.environ for same key",
            )
