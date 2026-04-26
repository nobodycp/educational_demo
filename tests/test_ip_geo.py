"""Local-only behavior for ``ip_geo`` (no external call for loopback / private)."""

from __future__ import annotations

import unittest

from backend import ip_geo


class TestIpGeoLocal(unittest.TestCase):
    def test_loopback_not_public(self) -> None:
        self.assertFalse(ip_geo.is_public_routable_ip("127.0.0.1"))

    def test_lookup_skips_local(self) -> None:
        r = ip_geo.lookup_ip_public("127.0.0.1")
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("reason"), "not_public")


if __name__ == "__main__":
    unittest.main()
