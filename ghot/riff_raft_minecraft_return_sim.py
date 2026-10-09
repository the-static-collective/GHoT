#!/usr/bin/env python3
"""Hostile tests for read-only external reLATTE -> GHoT return boundary."""
from __future__ import annotations
import json
import unittest
from copy import deepcopy
from pathlib import Path

from riff_raft_minecraft_return import (
    BUNDLE, CORE, DONOR, EXPECTED, ReturnHold, STAGES,
    _states, receive, sha,
)


class ReturnTests(unittest.TestCase):
    def test_contract_constants(self):
        self.assertEqual(DONOR, "a63624f1be6a533f5ab927b1e4e8b1a629f1ba53")
        self.assertEqual(CORE, "c0e4d2c59481e0fb2a4bf4bb294f373907fd2b76")
        self.assertEqual(len(STAGES), 9)
        self.assertEqual(EXPECTED["broken"], [True] * 3 + [False] * 6)

    def test_empty_and_missing_signatures_refuse(self):
        for item in (None, {}, [], {"schema": BUNDLE}):
            with self.assertRaises((ReturnHold, TypeError, KeyError)):
                receive(item)

    def test_unsigned_forged_success_refuses(self):
        packet = {
            "schema": "ghot.riff-raft-minecraft-return/v0",
            "comparison": {"distinct_instances": True},
            "recommended_gHot_disposition": "HOLD",
        }
        forged = {
            "schema": BUNDLE,
            "packet_json": json.dumps(packet),
            "crossing": {"crossing_id": "faux"},
            "receipt": {"kind": "R3_HOLD"},
            "world_evidence": {"A": {}, "B": {}},
        }
        with self.assertRaisesRegex(ReturnHold, "CROSSING_SIGNATURE_INVALID"):
            receive(forged)

    def test_witness_stage_order_required(self):
        good = [{"cue": cue, "lit": i < 3} for i, cue in enumerate(STAGES)]
        self.assertEqual(_states(good, "broken"), EXPECTED["broken"])
        bad = deepcopy(good)
        bad[2]["cue"] = "fake"
        with self.assertRaisesRegex(ReturnHold, "broken_ORDER"):
            _states(bad, "broken")

    def test_expanded_or_nonboolean_trace_refused(self):
        base = [{"cue": cue, "lit": False} for cue in STAGES]
        with self.assertRaisesRegex(ReturnHold, "before_LENGTH"):
            _states(base[:-1], "before")
        base[0]["lit"] = 1
        with self.assertRaisesRegex(ReturnHold, "before_NOT_BOOLEAN"):
            _states(base, "before")

    def test_payload_digest_is_byte_strict(self):
        left = b'{"comparison":true}'
        right = b'{"comparison": true}'
        self.assertNotEqual(sha(left), sha(right))

    def test_existing_relatte_signed_fixture_is_not_valid_return(self):
        root = Path(__file__).resolve().parents[1] / "fixtures"
        crossing = json.loads((root / "relatte-genesis-signed-crossing.json").read_text())
        receipt = json.loads((root / "relatte-genesis-signed-receipt.json").read_text())
        unrelated = {
            "schema": BUNDLE, "packet_json": "{}",
            "crossing": crossing, "receipt": receipt,
            "world_evidence": {"A": {}, "B": {}},
        }
        with self.assertRaises(ReturnHold):
            receive(unrelated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
