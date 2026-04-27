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

    def test_expired(self) -> None:
        self.assertIsNone(app_module._normalize_card_expiry("11/11"))

    def test_invalid_month_zero(self) -> None:
        self.assertIsNone(app_module._normalize_card_expiry("00/30"))

    def test_too_far_future(self) -> None:
        # 2050-12 is beyond today + 15 years for any "today" in 2016–2026+.
        self.assertIsNone(app_module._normalize_card_expiry("12/50"))

    def test_card_expiry_error_codes(self) -> None:
        c, e = app_module._card_expiry_result("11/11")
        self.assertIsNone(c)
        self.assertEqual(e, "expired_card")
        c, e = app_module._card_expiry_result("00/30")
        self.assertIsNone(c)
        self.assertEqual(e, "bad_expiry")
        c, e = app_module._card_expiry_result("12/50")
        self.assertIsNone(c)
        self.assertEqual(e, "bad_expiry")
        c, e = app_module._card_expiry_result("1/2")
        self.assertIsNone(c)
        self.assertEqual(e, "bad_exp_format")
        c, e = app_module._card_expiry_result("01/30")
        self.assertIsNotNone(c)
        self.assertIsNone(e)


if __name__ == "__main__":
    unittest.main()
