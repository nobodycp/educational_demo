"""Telegram Bango registration message formatting."""

from __future__ import annotations

import html
import os
import unittest
from unittest import mock

from backend import rsa_envelope, telegram_notify


class TestTelegramEnvHelpers(unittest.TestCase):
    def test_strip_bom_and_quotes(self) -> None:
        self.assertEqual(
            telegram_notify._strip_env_value('\ufeff"123456:abc-def"'),
            "123456:abc-def",
        )

    def test_coerce_chat_id_int(self) -> None:
        self.assertEqual(telegram_notify._coerce_chat_id_for_api(" 987654321 "), 987654321)
        self.assertEqual(telegram_notify._coerce_chat_id_for_api("-1001234567890"), -1001234567890)
        self.assertEqual(telegram_notify._coerce_chat_id_for_api("@mychannel"), "@mychannel")


def _sample_reg(**extra):
    base = {
        "fname": "a",
        "lname": "b",
        "email": "e@e.co",
        "phone": "1",
        "personal_id": "id",
        "full_name": "Full Name",
        "card_number": "1111******2222",
        "card_exp": "01/30",
        "cvv_len": "3",
    }
    base.update(extra)
    return base


@mock.patch.dict(os.environ, {"DEMO_TELEGRAM_PII_PLAINTEXT": "1"}, clear=False)
class TestTelegramFormatPlaintext(unittest.TestCase):
    def test_registration_escapes_html_in_fields(self) -> None:
        reg = _sample_reg(fname="<b>x</b>", card_number="<b>4111</b>******2222")
        msg = telegram_notify.format_demo_registration_message(reg, client_ip="127.0.0.1")
        self.assertNotIn("<b>x</b>", msg)
        self.assertIn(html.escape("<b>x</b>"), msg)
        self.assertNotIn("<b>4111</b>", msg)
        self.assertIn(html.escape("<b>4111</b>"), msg)

    def test_long_fingerprint_truncated(self) -> None:
        reg = _sample_reg(fingerprint_signals={"k": "x" * 2000})
        msg = telegram_notify.format_demo_registration_message(reg, client_ip="1.1.1.1")
        self.assertLess(len(msg), 5000)
        self.assertIn("…", msg)


class TestTelegramFormat(unittest.TestCase):
    def test_default_pii_is_encrypted_no_plain_name(self) -> None:
        if not rsa_envelope.DEFAULT_PUBLIC_PEM.is_file():
            self.skipTest("no public.pem")
        with mock.patch.dict(os.environ, {"DEMO_TELEGRAM_PII_PLAINTEXT": "0"}, clear=False):
            msg = telegram_notify.format_demo_registration_message(
                _sample_reg(fname="Secret"), client_ip="127.0.0.1"
            )
        self.assertIn("🔐", msg)
        self.assertNotIn("Secret", msg)
        self.assertIn("1.", msg)

    def test_registration_bango_heading(self) -> None:
        msg = telegram_notify.format_demo_registration_message(
            _sample_reg(),
            client_ip="1.1.1.1",
        )
        self.assertIn("bango", msg.lower())

    def test_registration_includes_redirect_line_when_set(self) -> None:
        msg = telegram_notify.format_demo_registration_message(
            _sample_reg(),
            client_ip="127.0.0.1",
            done_redirect_url="https://example.com/x",
        )
        self.assertIn("example.com", msg)

    @mock.patch.dict(os.environ, {"DEMO_TELEGRAM_PII_PLAINTEXT": "1"}, clear=False)
    def test_plaintext_telegram_shows_label_lines(self) -> None:
        msg = telegram_notify.format_demo_registration_message(_sample_reg(), client_ip="1.1.1.1")
        self.assertIn("First name", msg)


if __name__ == "__main__":
    unittest.main()
