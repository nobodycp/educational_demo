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

