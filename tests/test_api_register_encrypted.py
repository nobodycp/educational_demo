"""POST /api/demo/register with client-side encrypted PII (Python envelope same as bango-crypto)."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from backend.app import create_app
from backend.rsa_envelope import DEFAULT_PRIVATE_PEM, DEFAULT_PUBLIC_PEM, encrypt_envelope_json


class TestApiRegisterEncrypted(unittest.TestCase):
    def setUp(self) -> None:
        if not Path(DEFAULT_PUBLIC_PEM).is_file() or not Path(DEFAULT_PRIVATE_PEM).is_file():
            self.skipTest("RSA keys missing (run gen_keys.sh)")
        self._p_env = mock.patch.dict(
            os.environ,
            {"DEMO_RISK_BLOCK_THRESHOLD": "100", "DEMO_INCOGNITO_BLOCK": "0"},
            clear=False,
        )
        self._p_env.start()
        self.addCleanup(self._p_env.stop)
        self._blob = encrypt_envelope_json(
            {
                "fname": "A",
                "lname": "B",
                "phone": "1",
                "email": "a@b.c",
                "personal_id": "12",
                "full_name": "A B",
                "cc": "4111111111111111",
                "exp": "12/30",
                "cvv": "123",
            },
            public_key_path=DEFAULT_PUBLIC_PEM,
        )
        self.assertIsNotNone(self._blob)

    def test_encrypted_pii_200(self) -> None:
        app = create_app()
        c = app.test_client()
        with c.session_transaction() as sess:  # type: ignore[attr-defined]
            sess["core_verified"] = True
            sess["api_csrf"] = "testcsrf"
        r = c.post(
            "/api/demo/register",
            data=json.dumps(
                {
                    "encrypted_pii": self._blob,
                    "bango_honeypot_company": "",
                    "bango_honeypot_website": "",
                    "fingerprint_signals": {},
                    "behavior_signals": {},
                    "client_flags": {
                        "incognito": False,
                        "battery": {"unavailable": True},
                        "automation": {
                            "webdriver": False,
                            "cdp_artifacts": False,
                            "headless_suspect": False,
                        },
                    },
                }
            ),
            content_type="application/json",
            headers={"X-CSRF-Token": "testcsrf", "Origin": "http://127.0.0.1"},
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertTrue(d.get("ok"))


if __name__ == "__main__":
    unittest.main()
