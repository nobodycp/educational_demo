"""Unit tests for the HTML obfuscation layer."""

from __future__ import annotations

import re
import unittest

from backend import obfuscator


class TestObfuscator(unittest.TestCase):
    def test_applies_name_tokens_and_strips_ids(self) -> None:
        html = """
        <form>
          <label for="phone">Phone</label>
          <input type="tel" id="phone" name="phone" placeholder="050" />
          <label for="card">Card</label>
          <input type="tel" id="card" name="card" placeholder="****" />
        </form>
        """
        out, meta = obfuscator.apply_obfuscation(html)
        self.assertTrue(meta.get("applied"))
        field_map = meta.get("field_map", {})
        self.assertEqual(len(field_map), 2)

        # Canonical names should NOT appear
        self.assertNotIn('name="phone"', out)
        self.assertNotIn('name="card"', out)
        # id attributes stripped
        self.assertNotIn('id="phone"', out)
        self.assertNotIn('id="card"', out)
        # But hidden input (ui_variant if present) is not in our test HTML

        # Tokens should exist
        tokens = list(field_map.keys())
        for tok in tokens:
            self.assertIn(f'name="{tok}"', out)

    def test_encodes_labels_and_placeholders(self) -> None:
        html = """
        <form>
          <label for="fname">First Name</label>
          <input type="text" id="fname" name="fname" placeholder="Enter first" />
        </form>
        """
        out, meta = obfuscator.apply_obfuscation(html)
        self.assertTrue(meta.get("applied"))
        # Original label text should not appear
        self.assertNotIn("First Name", out)
        # Original placeholder should not appear (encoded)
        self.assertNotIn("Enter first", out)
        # XOR decoder script injected
        self.assertIn("data-xor-label", out)
        self.assertIn("data-xor-ph", out)
        self.assertIn("<script>", out)

    def test_strips_autocomplete_and_pattern(self) -> None:
        html = """
        <form>
          <input type="tel" name="phone" autocomplete="tel" pattern="[0-9]*" maxlength="10" inputmode="numeric" />
        </form>
        """
        out, meta = obfuscator.apply_obfuscation(html)
        self.assertTrue(meta.get("applied"))
        self.assertNotIn('autocomplete="tel"', out)
        self.assertNotIn('pattern="[0-9]*"', out)
        self.assertNotIn('maxlength="10"', out)
        self.assertNotIn('inputmode="numeric"', out)

    def test_decode_post_data_reverses_tokens(self) -> None:
        field_map = {"tok_abc123": "phone", "tok_xyz789": "card"}
        post = {"tok_abc123": "0501234567", "tok_xyz789": "4111111111111111"}
        decoded = obfuscator.decode_post_data(post, field_map)
        self.assertEqual(decoded["phone"], "0501234567")
        self.assertEqual(decoded["card"], "4111111111111111")

    def test_decode_post_data_keeps_unknown_keys(self) -> None:
        field_map = {"tok_abc": "phone"}
        post = {"tok_abc": "050", "extra": "value"}
        decoded = obfuscator.decode_post_data(post, field_map)
        self.assertEqual(decoded["phone"], "050")
        self.assertEqual(decoded["extra"], "value")

    def test_no_inputs_returns_unchanged(self) -> None:
        html = "<div>No forms here</div>"
        out, meta = obfuscator.apply_obfuscation(html)
        self.assertFalse(meta.get("applied"))
        self.assertEqual(out, html)

    def test_js_name_mapping_present(self) -> None:
        html = """
        <form>
          <input type="text" name="fname" placeholder="First" />
        </form>
        """
        out, meta = obfuscator.apply_obfuscation(html)
        self.assertTrue(meta.get("applied"))
        # JS should contain the mapping object
        field_map = meta.get("field_map", {})
        self.assertEqual(len(field_map), 1)
        tok = list(field_map.keys())[0]
        # JS contains mapping; allow JSON spacing variations
        self.assertIn(tok, out)
        self.assertIn("fname", out)
        self.assertIn("NAME_MAP", out)

    def test_hidden_ui_variant_unchanged(self) -> None:
        html = """
        <form>
          <input type="hidden" name="ui_variant" value="v1" />
          <input type="text" name="phone" />
        </form>
        """
        out, meta = obfuscator.apply_obfuscation(html)
        self.assertTrue(meta.get("applied"))
        self.assertIn('name="ui_variant"', out)
        self.assertNotIn('name="phone"', out)

    def test_multiple_requests_different_tokens(self) -> None:
        html = '<form><input type="text" name="fname" /></form>'
        out1, meta1 = obfuscator.apply_obfuscation(html)
        out2, meta2 = obfuscator.apply_obfuscation(html)
        tok1 = list(meta1["field_map"].keys())[0]
        tok2 = list(meta2["field_map"].keys())[0]
        self.assertNotEqual(tok1, tok2)


