"""Client IP resolution behind Cloudflare and other reverse proxies."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from backend.client_ip import resolve_client_ip


class ClientIpTests(unittest.TestCase):
    def _req(self, remote: str, headers: dict | None = None) -> MagicMock:
        req = MagicMock()
        req.remote_addr = remote
        req.headers = headers or {}
        return req

    def test_cloudflare_edge_uses_cf_connecting_ip(self) -> None:
        ip = resolve_client_ip(
            self._req(
                "172.70.108.18",
                {"CF-Connecting-IP": "203.0.113.42"},
            )
        )
        self.assertEqual(ip, "203.0.113.42")

    def test_private_peer_uses_cf_connecting_ip(self) -> None:
        ip = resolve_client_ip(
            self._req("10.0.0.5", {"CF-Connecting-IP": "198.51.100.7"})
        )
        self.assertEqual(ip, "198.51.100.7")

    def test_direct_public_peer_ignores_spoofed_headers(self) -> None:
        import os

        old = os.environ.pop("TRUST_PROXY", None)
        try:
            ip = resolve_client_ip(
                self._req(
                    "8.8.8.8",
                    {"CF-Connecting-IP": "1.2.3.4"},
                )
            )
            self.assertEqual(ip, "8.8.8.8")
        finally:
            if old is not None:
                os.environ["TRUST_PROXY"] = old

    def test_private_peer_falls_back_to_xff(self) -> None:
        ip = resolve_client_ip(
            self._req("127.0.0.1", {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"})
        )
        self.assertEqual(ip, "203.0.113.1")


if __name__ == "__main__":
    unittest.main()
