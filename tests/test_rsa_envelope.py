"""RSA+AES hybrid envelope (browser wire + Telegram PII)."""

from __future__ import annotations

import unittest

from backend import rsa_envelope


class TestRsaEnvelope(unittest.TestCase):
    def test_roundtrip_with_repo_keys(self) -> None:
        if not rsa_envelope.DEFAULT_PUBLIC_PEM.is_file():
            self.skipTest("no public.pem")
        if not rsa_envelope.DEFAULT_PRIVATE_PEM.is_file():
            self.skipTest("no private_demo.pem")
        payload = {
            "fname": "N",
            "lname": "M",
            "phone": "1",
            "email": "a@b.c",
            "personal_id": "i",
            "full_name": "N M",
            "cc": "4111111111111111",
            "exp": "11/33",
            "cvv": "233",
        }
        blob = rsa_envelope.encrypt_envelope_json(payload)
        self.assertIsNotNone(blob)
        assert blob is not None
        self.assertTrue(blob.startswith("1."))
        out = rsa_envelope.decrypt_envelope_string(blob)
        self.assertIsInstance(out, dict)
        assert isinstance(out, dict)
        self.assertEqual(out, payload)

    def test_decrypt_rejects_garbage(self) -> None:
        if not rsa_envelope.DEFAULT_PRIVATE_PEM.is_file():
            self.skipTest("no private_demo.pem")
        err = rsa_envelope.decrypt_envelope_string("nope")
        self.assertIsInstance(err, str)


if __name__ == "__main__":
    unittest.main()
