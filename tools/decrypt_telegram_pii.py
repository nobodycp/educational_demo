#!/usr/bin/env python3
"""Decrypt a Bango PII wire envelope (line starting with ``1.``) — e.g. from Telegram, logs, or copy-paste."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.rsa_envelope import DEFAULT_PRIVATE_PEM, decrypt_envelope_string  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "blob",
        nargs="?",
        help="Envelope string (one line, starts with 1.)",
    )
    p.add_argument(
        "-k",
        "--private-key",
        type=Path,
        default=DEFAULT_PRIVATE_PEM,
        help=f"PEM path (default: {DEFAULT_PRIVATE_PEM})",
    )
    args = p.parse_args()
    raw = (args.blob or "").strip() or sys.stdin.read().strip()
    if not raw:
        print("Usage: decrypt_telegram_pii.py '1.xxx.xxx.xxx'  # or pipe", file=sys.stderr)
        return 2
    out = decrypt_envelope_string(raw, private_key_path=args.private_key)
    if isinstance(out, str):
        print(out, file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
