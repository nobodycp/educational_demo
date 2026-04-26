"""
Tests for ``DEMO_EXTERNAL_GUARD`` single-switch behaviour and ``step_external_guard``.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from backend import gate_engine


class _ResetDotenvPathMixin:
    """Tests rely on ``os.environ`` patches; disable hot-reload path so ``.env`` does not win."""

    def setUp(self) -> None:
        gate_engine.set_runtime_dotenv_path(None)

    def tearDown(self) -> None:
        gate_engine.set_runtime_dotenv_path(None)


class TestExternalGuardSwitch(_ResetDotenvPathMixin, unittest.TestCase):
    """``DEMO_EXTERNAL_GUARD`` must be exactly one of on/true/1/yes (case-insensitive)."""

    def _on_values(self) -> tuple[str, ...]:
        return ("on", "ON", "true", "True", "1", "yes", "YES")

    def _off_values(self) -> tuple[str, ...]:
        return ("", " ", "off", "false", "0", "no", "maybe", '"false"', "bad")

    def test_switch_on_values(self) -> None:
        for v in self._on_values():
            with patch.dict(os.environ, {"DEMO_EXTERNAL_GUARD": v}, clear=False):
                self.assertTrue(
                    gate_engine._external_guard_switch_on(),
                    msg=f"expected on for {v!r}",
                )

    def test_switch_off_values(self) -> None:
        for v in self._off_values():
            with patch.dict(os.environ, {"DEMO_EXTERNAL_GUARD": v}, clear=False):
                self.assertFalse(
                    gate_engine._external_guard_switch_on(),
                    msg=f"expected off for {v!r}",
                )

    def test_switch_unset_is_off(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEMO_EXTERNAL_GUARD", None)
            self.assertFalse(gate_engine._external_guard_switch_on())


class TestStepExternalGuard(_ResetDotenvPathMixin, unittest.TestCase):
    """HTTP is only used when switch on and URL + key are set."""

    _url = "http://127.0.0.1:9/tracker-does-not-exist"
    _key = "test-key"

    def _mock_cm(self, body: dict) -> MagicMock:
        inner = MagicMock()
        inner.read.return_value = json.dumps(body).encode("utf-8")
        cm = MagicMock()
        cm.__enter__.return_value = inner
        cm.__exit__.return_value = None
        return cm

    def test_off_skips_http_even_with_credentials(self) -> None:
        env = {
            "DEMO_EXTERNAL_GUARD": "off",
            "DEMO_EXTERNAL_GUARD_URL": self._url,
            "DEMO_EXTERNAL_GUARD_API_KEY": self._key,
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("backend.gate_engine.urllib.request.urlopen") as m_url:
                r = gate_engine.step_external_guard("203.0.113.1", "Mozilla/5.0")
                self.assertIsNone(r)
                m_url.assert_not_called()

    def test_on_missing_url_skips_http(self) -> None:
        env = {
            "DEMO_EXTERNAL_GUARD": "on",
            "DEMO_EXTERNAL_GUARD_URL": "",
            "DEMO_EXTERNAL_GUARD_API_KEY": self._key,
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("backend.gate_engine.urllib.request.urlopen") as m_url:
                self.assertIsNone(gate_engine.step_external_guard("203.0.113.2", "ua"))
                m_url.assert_not_called()

    def test_on_granted_returns_none(self) -> None:
        env = {
            "DEMO_EXTERNAL_GUARD": "on",
            "DEMO_EXTERNAL_GUARD_URL": self._url,
            "DEMO_EXTERNAL_GUARD_API_KEY": self._key,
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("backend.gate_engine.urllib.request.urlopen", return_value=self._mock_cm({"status": "access_granted"})) as m_url:
                r = gate_engine.step_external_guard("203.0.113.3", "ua")
                self.assertIsNone(r)
                m_url.assert_called_once()

    def test_on_denied_returns_decision(self) -> None:
        env = {
            "DEMO_EXTERNAL_GUARD": "on",
            "DEMO_EXTERNAL_GUARD_URL": self._url,
            "DEMO_EXTERNAL_GUARD_API_KEY": self._key,
        }
        with patch.dict(os.environ, env, clear=False):
            with patch(
                "backend.gate_engine.urllib.request.urlopen",
                return_value=self._mock_cm({"status": "access_denied", "reason": "test"}),
            ) as m_url:
                r = gate_engine.step_external_guard("203.0.113.4", "ua")
                self.assertIsNotNone(r)
                self.assertFalse(r.allowed)
                self.assertEqual(r.reason, "external_guard_denied")
                self.assertEqual(r.http_status, 403)
                self.assertEqual(r.risk.get("reason"), "test")
                self.assertEqual(r.risk.get("external_reason"), "test")
                m_url.assert_called_once()


if __name__ == "__main__":
    unittest.main()
