"""``backend.lab_shield`` helpers: DOM noise filter, JSON shuffle."""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from backend import lab_shield
from markupsafe import Markup


class TestLabShield(unittest.TestCase):
    def test_dom_noise_filter_renders_spans(self) -> None:
        m = lab_shield.dom_noise_filter(2)
        self.assertIsInstance(m, Markup)
        s = str(m)
        self.assertEqual(s.count("<span"), 2)
        self.assertIn("data-z=", s)
        self.assertIn("data-v=", s)

    def test_shuffled_error_distinct_key_order_sometimes(self) -> None:
        body = {"a": 1, "b": 2, "c": 3}
        seen: set[tuple[str, ...]] = set()
        for _ in range(48):
            r = lab_shield._shuffled_error(body, 403)  # type: ignore[attr-defined]
            data = json.loads(r.get_data(as_text=True))
            seen.add(tuple(data.keys()))
        self.assertGreater(len(seen), 1, "shuffle should sometimes reorder key order in JSON")

    def test_ip_block_403(self) -> None:
        from backend.app import create_app

        app = create_app()
        with mock.patch.dict(os.environ, {"DEMO_IP_BLOCKLIST": "198.51.100.1"}, clear=False):
            c = app.test_client()
            r = c.get("/start", base_url="http://127.0.0.1:5000")
        self.assertNotEqual(r.status_code, 403)
        with mock.patch.dict(os.environ, {"DEMO_IP_BLOCKLIST": "127.0.0.1"}, clear=False):
            c = app.test_client()
            r = c.get("/start", base_url="http://127.0.0.1:5000")
        self.assertEqual(r.status_code, 403)
