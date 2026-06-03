"""Billing JS session bundle validation."""

from __future__ import annotations

import unittest

from backend import bango_template


class BillingJsBundleTests(unittest.TestCase):
    def test_bundle_valid_without_shell_guard(self) -> None:
        rev = {
            "t1": "fingerprint",
            "t2": "behavior",
            "t3": "incognito-hint",
            "t4": "lab-busy",
            "t5": "bango-crypto",
            "t6": "bango-page-init",
            "t7": "bango-lab",
        }
        self.assertTrue(bango_template._billing_js_bundle_valid(rev, shell_guard=False))

    def test_bundle_invalid_when_missing_bango_lab(self) -> None:
        rev = {"t1": "fingerprint", "t2": "behavior"}
        self.assertFalse(bango_template._billing_js_bundle_valid(rev, shell_guard=False))


if __name__ == "__main__":
    unittest.main()
