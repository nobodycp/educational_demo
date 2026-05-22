"""Unit tests for safe CRO variant rendering."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend import cro_variants


class TestCroVariants(unittest.TestCase):
    def test_pick_variant_is_deterministic(self) -> None:
        variants = ["v1", "v2", "v3"]
        a1 = cro_variants.pick_variant("session-abc", variants)
        a2 = cro_variants.pick_variant("session-abc", variants)
        b1 = cro_variants.pick_variant("session-def", variants)
        self.assertEqual(a1, a2)
        self.assertIn(a1, variants)
        self.assertIn(b1, variants)

    def test_render_test_variant_safe_applies_expected_transformations(self) -> None:
        html = """
<form id="checkout-form">
  <label for="fname">Old first</label>
  <input type="text" id="fname" name="fname" placeholder="old ph" autocomplete="given-name" />
  <label for="phone">Old phone</label>
  <input type="tel" id="phone" name="phone" placeholder="old phone ph" autocomplete="tel" />
</form>
"""
        cfg = {
            "default_locale": "en",
            "variants": [
                {
                    "id": "v1",
                    "enabled": True,
                    "autocomplete_off": True,
                    "labels": {"fname": "First name", "phone": "Phone"},
                    "placeholders": {"fname": "Enter first", "phone": "050-000-0000"},
                    "visual_order": {"phone": 1, "fname": 2},
                }
            ],
        }
        out, meta = cro_variants.render_test_variant_safe(
            html, cfg, subject_key="subject-123"
        )
        self.assertTrue(meta.get("applied"))
        self.assertEqual(meta.get("variant_id"), "v1")
        self.assertIn('name="fname"', out)
        self.assertIn('name="phone"', out)
        self.assertIn('data-visual-order="2"', out)
        self.assertIn('data-visual-order="1"', out)
        self.assertIn('autocomplete="off"', out)
        self.assertIn("First name", out)
        self.assertIn("Phone", out)
        self.assertIn("Enter first", out)
        self.assertIn('name="ui_variant" value="v1"', out)

    def test_append_variant_event_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cro_variants.append_variant_event(
                root,
                event_type="exposure",
                payload={"variant_id": "v1", "path": "/x"},
            )
            p = root / "data" / "form_variant_events.jsonl"
            self.assertTrue(p.exists())
            line = p.read_text(encoding="utf-8").strip()
            obj = json.loads(line)
            self.assertEqual(obj["event_type"], "exposure")
            self.assertEqual(obj["payload"]["variant_id"], "v1")

