"""Admin panel route tests and theme selector behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import app as app_mod


class TestAdminPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.env_path = root / ".env"
        cls.runtime_env_path = root / "data" / "admin_runtime.env"
        cls.theme_registry_path = root / "config" / "prebuilt_themes.json"
        cls.data_dir = root / "data"
        cls.theme_registry_path.parent.mkdir(parents=True, exist_ok=True)
        cls.data_dir.mkdir(parents=True, exist_ok=True)
        cls.theme_registry_path.write_text(
            """{
  "themes": {
    "default": {"label": "Default Bango", "template": "bango/index.html"},
    "post_pyment": {"label": "Post Payment", "template": "post_pyment/index.html"}
  }
}""",
            encoding="utf-8",
        )
        cls.env_path.write_text(
            "\n".join(
                [
                    "FLASK_SECRET_KEY=test-secret",
                    "ADMIN_PANEL_PASSWORD=adminpass",
                    "ADMIN_PANEL_ACCESS_MODE=open",
                    "ADMIN_PANEL_IP_WHITELIST=",
                    "ACTIVE_THEME=default",
                    "COOKIE_SECURE=",
                    "STRICT_ORIGIN=",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        cls.patches = [
            mock.patch.object(app_mod, "ENV_FILE_PATH", cls.env_path),
            mock.patch.object(app_mod, "ENV_RUNTIME_FILE_PATH", cls.runtime_env_path),
            mock.patch.object(app_mod, "THEME_REGISTRY_PATH", cls.theme_registry_path),
            mock.patch.object(app_mod, "DATA_DIR", cls.data_dir),
        ]
        for p in cls.patches:
            p.start()
        cls.app = app_mod.create_app()
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls) -> None:
        for p in reversed(cls.patches):
            p.stop()
        cls.tmp.cleanup()

    def test_admin_login_and_settings_save(self) -> None:
        c = self.app.test_client()
        r_login = c.post("/admin/login", data={"password": "adminpass"}, follow_redirects=True)
        self.assertEqual(r_login.status_code, 200)
        self.assertIn(b"Admin Settings Panel", r_login.data)

        r_save = c.post(
            "/admin/settings",
            data={
                "action": "save",
                "ACTIVE_THEME": "post_pyment",
                "TELEGRAM_CHAT_ID": "123456",
                "COOKIE_SECURE": "1",
            },
            follow_redirects=True,
        )
        self.assertEqual(r_save.status_code, 200)
        txt = self.env_path.read_text(encoding="utf-8")
        self.assertIn("ACTIVE_THEME=post_pyment", txt)
        self.assertIn("TELEGRAM_CHAT_ID=123456", txt)
        self.assertIn("COOKIE_SECURE=1", txt)

    def test_access_mode_restricted_blocks_non_whitelisted_ip(self) -> None:
        self.env_path.write_text(
            self.env_path.read_text(encoding="utf-8")
            .replace("ADMIN_PANEL_ACCESS_MODE=open", "ADMIN_PANEL_ACCESS_MODE=restricted")
            .replace("ADMIN_PANEL_IP_WHITELIST=", "ADMIN_PANEL_IP_WHITELIST=203.0.113.7"),
            encoding="utf-8",
        )
        c = self.app.test_client()
        r = c.get("/admin/login")
        self.assertEqual(r.status_code, 403)
        self.env_path.write_text(
            self.env_path.read_text(encoding="utf-8")
            .replace("ADMIN_PANEL_ACCESS_MODE=restricted", "ADMIN_PANEL_ACCESS_MODE=open")
            .replace("ADMIN_PANEL_IP_WHITELIST=203.0.113.7", "ADMIN_PANEL_IP_WHITELIST="),
            encoding="utf-8",
        )

    def test_theme_selection_reflected_in_bango_render(self) -> None:
        txt = self.env_path.read_text(encoding="utf-8")
        self.env_path.write_text(
            txt.replace("ACTIVE_THEME=default", "ACTIVE_THEME=post_pyment"),
            encoding="utf-8",
        )
        c = self.app.test_client()
        with c.session_transaction() as sess:  # type: ignore[attr-defined]
            sess[app_mod.SESSION_GATE] = True
            sess[app_mod.SESSION_CORE_OK] = True
            sess[app_mod.SESSION_APP_PATH] = "/a/b/bango"
        r = c.get("/a/b/bango")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"post_pyment", r.data)

    def test_register_validation_regression_phone_error(self) -> None:
        c = self.app.test_client()
        with c.session_transaction() as sess:  # type: ignore[attr-defined]
            sess[app_mod.SESSION_CORE_OK] = True
            sess[app_mod.SESSION_API_CSRF] = "csrf-token-x"
        payload = {
            "fname": "John",
            "lname": "Doe",
            "phone": "05012",
            "email": "john@example.com",
            "personal_id": "123456789",
            "full_name": "John Doe",
            "cc": "4242424242424242",
            "exp": "12/99",
            "cvv": "123",
        }
        r = c.post(
            "/api/demo/register",
            json=payload,
            headers={
                "X-CSRF-Token": "csrf-token-x",
                "Content-Type": "application/json",
                "Origin": "http://localhost",
            },
        )
        self.assertIn(r.status_code, {400, 401, 403, 422, 429})
        body = r.get_json()
        self.assertEqual(body.get("error_field"), "phone")

