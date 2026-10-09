#!/usr/bin/env python3
"""Deterministic hostile tests for UNFINISHED BUSINESS 001."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from unfinished_business import discover, decide, validate

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "unfinished-business-001.json"


def base():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def by_id(result, subject):
    return next(c for c in result["cases"] if c["subject_id"] == subject)


class UnfinishedCaseTests(unittest.TestCase):
    def test_first_real_source_case(self):
        r = discover(base())
        case = by_id(r, "ghot.intent-assignment-crossing")
        self.assertEqual(case["status"], "CANDIDATE")
        self.assertEqual(case["matched"][0]["candidates"][0]["provider_id"], "relatte.portable-receipts")
        self.assertFalse(case["execution_authorized"])
        self.assertEqual(case["matched"][0]["candidates"][0]["source_verification"], "NOT_PERFORMED")

    def test_obstacle_and_source_only(self):
        r = discover(base())
        self.assertEqual(by_id(r, "cannon.owner-selected-histories")["status"], "OBSTACLE")
        self.assertEqual(by_id(r, "cannon.owner-selected-histories")["unmet"], ["crossrepo.inventory-index"])
        self.assertEqual(by_id(r, "relatte.portable-receipts")["status"], "SOURCE_ONLY")

    def test_deterministic_order_and_permutation(self):
        a = base()
        b = base()
        b["items"].reverse()
        self.assertEqual(discover(a), discover(b))
        self.assertEqual(discover(a), discover(a))

    def test_explicit_relation_respects_dial(self):
        a = base()
        a["items"][0]["needs"] = ["receipt.attested"]
        a["relations"] = [{
            "id": "human-hypothesis-001", "from": "receipt.boundary",
            "to": "receipt.attested", "proposed_by": "fixture-author",
            "basis": "hypothesis only, not tested interoperability",
        }]
        self.assertEqual(by_id(discover(a, 1), "ghot.intent-assignment-crossing")["status"], "OBSTACLE")
        at_two = by_id(discover(a, 2), "ghot.intent-assignment-crossing")
        self.assertEqual(at_two["status"], "CANDIDATE")
        self.assertEqual(at_two["matched"][0]["candidates"][0]["declared_relation_ids"], ["human-hypothesis-001"])

    def test_released_provider_cannot_be_used(self):
        a = base()
        a["items"][1]["state"] = "RELEASED"
        r = discover(a)
        self.assertEqual(by_id(r, "relatte.portable-receipts")["status"], "RELEASED")
        self.assertEqual(by_id(r, "ghot.intent-assignment-crossing")["status"], "OBSTACLE")

    def test_held_provider_cannot_be_used(self):
        a = base()
        a["items"][1]["state"] = "HELD"
        r = discover(a)
        self.assertEqual(by_id(r, "relatte.portable-receipts")["status"], "HOLD")
        self.assertEqual(by_id(r, "ghot.intent-assignment-crossing")["status"], "OBSTACLE")

    def test_released_subject_no_matching(self):
        a = base()
        a["items"][0]["state"] = "RELEASED"
        case = by_id(discover(a), "ghot.intent-assignment-crossing")
        self.assertEqual(case["status"], "RELEASED")
        self.assertFalse(case["matched"])

    def test_reject_bad_commit(self):
        a = base()
        a["items"][0]["source"]["commit"] = "main"
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_ADDRESS"):
            discover(a)

    def test_reject_escaping_path(self):
        a = base()
        a["items"][0]["source"]["path"] = "../secrets"
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_ADDRESS"):
            discover(a)

    def test_reject_duplicate_identity(self):
        a = base()
        a["items"][1]["id"] = a["items"][0]["id"]
        with self.assertRaises(ValueError):
            validate(a)

    def test_reject_invalid_dials_and_capabilities(self):
        for dial in [0, 12, True]:
            with self.assertRaises(ValueError):
                discover(base(), dial)
        a = base()
        a["items"][0]["offers"] = ["__import__('os').system('id')"]
        with self.assertRaises(ValueError):
            discover(a)

    def test_decision_receipt_is_not_execution(self):
        result = discover(base())
        case = by_id(result, "ghot.intent-assignment-crossing")
        receipt = decide(result, case["case_id"], "ACCEPT_FOR_REVIEW", "explicit-human-test")
        self.assertEqual(receipt["semantic_effect"], "decision-receipt-only")
        self.assertFalse(receipt["executed"])
        self.assertFalse(receipt["signed"])
        self.assertEqual(receipt, decide(result, case["case_id"], "ACCEPT_FOR_REVIEW", "explicit-human-test"))

    def test_obstacle_cannot_be_accepted(self):
        result = discover(base())
        case = by_id(result, "cannon.owner-selected-histories")
        with self.assertRaises(ValueError):
            decide(result, case["case_id"], "ACCEPT_FOR_REVIEW", "tester")
        self.assertEqual(decide(result, case["case_id"], "HOLD", "tester")["decision"], "HOLD")

    def test_tamper_detection(self):
        result = discover(base())
        case_id = by_id(result, "ghot.intent-assignment-crossing")["case_id"]
        altered = copy.deepcopy(result)
        altered["cases"][0]["unmet"] = ["invented"]
        with self.assertRaises(ValueError):
            decide(altered, case_id, "RELEASED", "tester")
        with self.assertRaises(ValueError):
            decide(result, "forged-case-id", "RELEASED", "tester")

    def test_no_overwrite_of_decision_witness(self):
        result = discover(base())
        case_id = by_id(result, "ghot.intent-assignment-crossing")["case_id"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "decision.json"
            command = [
                sys.executable, str(Path(__file__).with_name("unfinished_business.py")),
                "decide", str(FIXTURE), "--case-id", case_id, "--decision", "HOLD",
                "--selection-source", "explicit-test", "--out", str(out),
            ]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            before = out.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(out.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
