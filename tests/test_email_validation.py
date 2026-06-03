"""Strict email validation (known TLD / .co.il / ccTLD)."""

from __future__ import annotations

import unittest

from backend.app import _validate_email


class EmailValidationTests(unittest.TestCase):
    def test_rejects_fake_tld(self) -> None:
        self.assertEqual(_validate_email("aergaerg@argaewra.argaer"), "bad_email")

    def test_accepts_common_providers(self) -> None:
        self.assertIsNone(_validate_email("user@gmail.com"))
        self.assertIsNone(_validate_email("test@walla.co.il"))

    def test_rejects_missing_at(self) -> None:
        self.assertEqual(_validate_email("not-an-email"), "bad_email")


if __name__ == "__main__":
    unittest.main()
