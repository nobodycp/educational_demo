"""Tests for admin .env read/write helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend import admin_env


class TestAdminEnv(unittest.TestCase):
    def test_write_atomic_updates_and_masks_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env_path = Path(td) / ".env"
            env_path.write_text(
                "FLASK_SECRET_KEY=abc123\nSTRICT_ORIGIN=\nTELEGRAM_CHAT_ID=10\n",
                encoding="utf-8",
            )
            saved = admin_env.write_env_values_atomic(
                env_path,
                {
                    "FLASK_SECRET_KEY": "new-secret-789",
                    "STRICT_ORIGIN": "1",
                },
            )
            self.assertEqual(saved, ["FLASK_SECRET_KEY", "STRICT_ORIGIN"])
            values = admin_env.read_env_values(env_path)
            self.assertEqual(values["STRICT_ORIGIN"], "1")
            self.assertEqual(values["FLASK_SECRET_KEY"], "new-secret-789")
            masked = admin_env.masked_value("FLASK_SECRET_KEY", values["FLASK_SECRET_KEY"])
            self.assertNotEqual(masked, values["FLASK_SECRET_KEY"])

    def test_write_rejects_non_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env_path = Path(td) / ".env"
            env_path.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                admin_env.write_env_values_atomic(env_path, {"NOT_ALLOWED_KEY": "x"})

    def test_merged_read_and_fallback_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            primary = root / ".env"
            override = root / "data" / "admin_runtime.env"
            primary.write_text("ACTIVE_THEME=default\n", encoding="utf-8")
            saved_keys, target = admin_env.write_env_values_with_fallback(
                primary, override, {"ACTIVE_THEME": "post_pyment"}
            )
            self.assertEqual(saved_keys, ["ACTIVE_THEME"])
            self.assertEqual(target, primary)
            merged = admin_env.read_env_values_merged(primary, override, keys={"ACTIVE_THEME"})
            self.assertEqual(merged["ACTIVE_THEME"], "post_pyment")

            primary.unlink()
            saved_keys2, target2 = admin_env.write_env_values_with_fallback(
                primary, override, {"ACTIVE_THEME": "post_pyment"}
            )
            self.assertEqual(saved_keys2, ["ACTIVE_THEME"])
            self.assertEqual(target2, override)
            merged2 = admin_env.read_env_values_merged(primary, override, keys={"ACTIVE_THEME"})
            self.assertEqual(merged2["ACTIVE_THEME"], "post_pyment")

