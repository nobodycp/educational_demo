"""Incognito hint + ``DEMO_INCOGNITO_BLOCK`` strict gate step."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend import gate_engine


class TestIncognitoGate(unittest.TestCase):
    def setUp(self) -> None:
        gate_engine.set_runtime_dotenv_path(None)

    def tearDown(self) -> None:
        gate_engine.set_runtime_dotenv_path(None)

    def test_block_on_client_flags(self) -> None:
        with patch.dict(os.environ, {"DEMO_INCOGNITO_BLOCK": "on"}, clear=False):
            r = gate_engine.step_incognito_detection({"incognito": True}, {})
            self.assertIsNotNone(r)
            self.assertEqual(r.reason, "incognito_blocked")

    def test_block_on_fingerprint_hint_only(self) -> None:
        with patch.dict(os.environ, {"DEMO_INCOGNITO_BLOCK": "on"}, clear=False):
            r = gate_engine.step_incognito_detection(
                {},
                {"incognito_storage_hint": True},
            )
            self.assertIsNotNone(r)
            self.assertEqual(r.reason, "incognito_blocked")

    def test_block_off_even_when_hint(self) -> None:
        with patch.dict(os.environ, {"DEMO_INCOGNITO_BLOCK": "off"}, clear=False):
            self.assertIsNone(
                gate_engine.step_incognito_detection({"incognito": True}, None)
            )

    def test_no_hint_returns_none(self) -> None:
        with patch.dict(os.environ, {"DEMO_INCOGNITO_BLOCK": "on"}, clear=False):
            self.assertIsNone(gate_engine.step_incognito_detection({}, {}))
            self.assertIsNone(gate_engine.step_incognito_detection(None, None))


if __name__ == "__main__":
    unittest.main()
