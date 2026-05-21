"""Tests for multi-theme runtime settings, steps extraction, and API flow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import theme_runtime
from backend.app import SESSION_API_CSRF, SESSION_CORE_OK, create_app


class TestThemeRuntimeCore(unittest.TestCase):
    def test_extract_steps_contract(self) -> None:
        html_ok = '<script>window.__STEPS__=["login","billing"];</script>'
        self.assertEqual(theme_runtime.extract_steps_from_html(html_ok), ["login", "billing"])
        with self.assertRaises(ValueError):
            theme_runtime.extract_steps_from_html("<html></html>")
        with self.assertRaises(ValueError):
            theme_runtime.extract_steps_from_html('<script>window.__STEPS__=["x","x"];</script>')


class TestThemeRuntimeApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cfg = root / "config"
        logs = root / "logs"
        themes = root / "themes"
        cls._patchers = [
            mock.patch.object(theme_runtime, "PROJECT_ROOT", root),
            mock.patch.object(theme_runtime, "CONFIG_DIR", cfg),
            mock.patch.object(theme_runtime, "LOGS_DIR", logs),
            mock.patch.object(theme_runtime, "THEMES_DIR", themes),
            mock.patch.object(theme_runtime, "SETTINGS_PATH", cfg / "settings.json"),
            mock.patch.object(theme_runtime, "REGISTRY_PATH", cfg / "theme_registry.json"),
            mock.patch.object(theme_runtime, "THEME_EVENTS_PATH", logs / "theme_events.jsonl"),
            mock.patch("dotenv.get_key", return_value=None),
        ]
        for p in cls._patchers:
            p.start()
        theme_runtime.ensure_theme_runtime_bootstrap()
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls) -> None:
        for p in reversed(cls._patchers):
            p.stop()
        cls._tmp.cleanup()

    def _authed_client(self):
        c = self.app.test_client()
        with c.session_transaction() as sess:  # type: ignore[attr-defined]
            sess[SESSION_CORE_OK] = True
            sess[SESSION_API_CSRF] = "csrf-token-1"
        return c

    def test_freeze_active_theme_per_session(self) -> None:
        uploaded = theme_runtime.upsert_theme_from_upload(
            name="modern",
            index_html=b'<html><head><script>window.__STEPS__=["one"];</script></head><body>x</body></html>',
            texts_json=json.dumps({"title": "Modern"}).encode("utf-8"),
            assets=[],
        )
        self.assertEqual(uploaded["name"], "modern")
        theme_runtime.set_active_theme("modern")

        c1 = self._authed_client()
        r1 = c1.get("/api/theme/runtime")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.get_json()["theme"], "modern")

        theme_runtime.set_active_theme("default")
        r2 = c1.get("/api/theme/runtime")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.get_json()["theme"], "modern", "theme should be frozen in same session")

        c2 = self._authed_client()
        r3 = c2.get("/api/theme/runtime")
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.get_json()["theme"], "default", "new session gets new active theme")

    def test_verification_global_and_override(self) -> None:
        st = theme_runtime.load_settings()
        st["verification"] = {
            "enabled": True,
            "title": "V",
            "prompt": "P",
            "expected_code": "7788",
        }
        theme_runtime.save_settings(st)

        c = self._authed_client()
        r_bad = c.post(
            "/api/theme/verify",
            json={"code": "1111"},
            headers={"X-CSRF-Token": "csrf-token-1", "Content-Type": "application/json"},
        )
        self.assertEqual(r_bad.status_code, 400)

        r_ok = c.post(
            "/api/theme/verify",
            json={"code": "7788"},
            headers={"X-CSRF-Token": "csrf-token-1", "Content-Type": "application/json"},
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertTrue(r_ok.get_json()["ok"])

        reg = theme_runtime.load_registry()
        reg["themes"]["default"]["verification_override_enabled"] = False
        theme_runtime.save_registry(reg)
        self.assertFalse(theme_runtime.verification_enabled_for_theme("default"))

    def test_theme_step_api_validates_declared_steps(self) -> None:
        c = self._authed_client()
        ok = c.post(
            "/api/theme/step",
            json={"step": "profile", "payload": {"x": 1}},
            headers={"X-CSRF-Token": "csrf-token-1", "Content-Type": "application/json"},
        )
        self.assertEqual(ok.status_code, 200)
        bad = c.post(
            "/api/theme/step",
            json={"step": "not_declared"},
            headers={"X-CSRF-Token": "csrf-token-1", "Content-Type": "application/json"},
        )
        self.assertEqual(bad.status_code, 400)

