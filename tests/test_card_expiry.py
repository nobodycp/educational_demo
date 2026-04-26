"""Card expiry normalization used by ``/api/demo/register``."""

from __future__ import annotations

import unittest

from backend import app as app_module


class TestNormalizeCardExpiry(unittest.TestCase):
    def test_slash_form(self) -> None:
        self.assertEqual(app_module._normalize_card_expiry("01/30"), "01/30")

    def test_compact_form(self) -> None:
        self.assertEqual(app_module._normalize_card_expiry("0130"), "01/30")
        self.assertEqual(app_module._normalize_card_expiry(" 0130 "), "01/30")

    def test_invalid_month(self) -> None:
        self.assertIsNone(app_module._normalize_card_expiry("13/30"))

    def test_garbage(self) -> None:
        self.assertIsNone(app_module._normalize_card_expiry("abc"))
        self.assertIsNone(app_module._normalize_card_expiry(""))


if __name__ == "__main__":
    unittest.main()
