#!/usr/bin/env python3
"""Hostile, no-network tests for THE UNHEARD CHOIR 001."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ghot"))
from unheard_choir import InvalidWorld, compare, run, validate, verify  # noqa: E402

FIXTURE = ROOT / "fixtures" / "unheard-choir-001" / "world.json"


def fresh():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class ChoirTest(unittest.TestCase):
    def test_twelve_source_counterfactual(self):
        reports = compare(fresh())
        self.assertEqual(len(reports["initial_loudest"]["witness"]), 11)
        self.assertEqual(len(reports["after_loudest"]["witness"]), 12)
        self.assertEqual(len(reports["after_protected"]["witness"]), 12)
        self.assertNotIn("quiet-neighbor", reports["after_loudest"]["selection_order"])
        self.assertIn("quiet-neighbor", reports["after_protected"]["selection_order"])
        self.assertEqual(reports["after_protected"]["next_question"]["source_signal_id"], "quiet-neighbor")
        self.assertTrue(verify(fresh(), reports["after_protected"]))
        self.assertTrue(verify(fresh(), reports["after_loudest"]))

    def test_budget_and_explicit_ignored_witness(self):
        world = fresh()
        for policy in ("loudest", "protected"):
            receipt = run(world, policy)
            self.assertLessEqual(receipt["attention_spent"], world["attention_units"])
            self.assertEqual(receipt["attention_spent"] + receipt["attention_unspent"], world["attention_units"])
            self.assertEqual(len(receipt["witness"]), len(world["signals"]))
            self.assertEqual(sum(w["disposition"] == "ATTENDED" for w in receipt["witness"]), len(receipt["questions"]))
            self.assertTrue(any(w["disposition"] == "OBSERVED_NOT_ATTENDED" for w in receipt["witness"]))
            self.assertEqual(receipt["coverage"]["unobserved_reality"], "UNKNOWN")

    def test_every_question_is_only_a_proposal(self):
        receipt = run(fresh(), "protected")
        self.assertEqual(receipt["effects"], [])
        self.assertEqual(receipt["authority"], "NONE")
        self.assertFalse(receipt["signed"])
        self.assertFalse(receipt["coverage"]["actual_rf_received"])
        self.assertFalse(receipt["coverage"]["actual_human_need_verified"])
        for question in receipt["questions"]:
            self.assertTrue(question["requires_fresh_owner_admission"])
            self.assertFalse(question["executed"])

    def test_reordered_sources_same_receipt(self):
        world = fresh()
        expected = run(world, "protected")
        world["signals"].reverse()
        actual = run(world, "protected")
        self.assertEqual(expected["selection_order"], actual["selection_order"])
        self.assertEqual(expected["questions"], actual["questions"])
        # The input digest changes because it binds the exact source sequence.
        self.assertNotEqual(expected["source_digest"], actual["source_digest"])
        self.assertTrue(verify(world, actual))

    def test_repeat_and_cold_replay(self):
        world = fresh()
        self.assertEqual(run(world, "protected"), run(copy.deepcopy(world), "protected"))
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "receipt.json"
            receipt.write_text(json.dumps(run(world, "protected")), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "ghot" / "unheard_choir.py"),
                 "verify", "--fixture", str(FIXTURE), "--receipt", str(receipt)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["verified"])

    def test_tampered_receipt_refused(self):
        receipt = run(fresh(), "protected")
        receipt["questions"][0]["executed"] = True
        self.assertFalse(verify(fresh(), receipt))
        receipt["receipt_digest"] = "0" * 64
        self.assertFalse(verify(fresh(), receipt))

    def test_source_mutation_refused_even_with_untouched_receipt(self):
        world = fresh()
        receipt = run(world, "protected")
        world["signals"][0]["salience"] = 0
        self.assertFalse(verify(world, receipt))

    def test_no_consent_no_review_even_if_loud(self):
        world = fresh()
        need = world["signals"][-1]
        need["salience"] = 11
        need["consent_to_review"] = False
        for policy in ("loudest", "protected"):
            receipt = run(world, policy)
            self.assertNotIn("quiet-neighbor", receipt["selection_order"])
            witness = next(w for w in receipt["witness"] if w["signal_id"] == "quiet-neighbor")
            self.assertEqual(witness["disposition"], "HELD_UNREVIEWED")
            self.assertEqual(witness["reason"], "CONSENT_NOT_GIVEN")

    def test_protected_policy_does_not_invent_need(self):
        world = fresh()
        world["signals"] = world["signals"][:-1]
        world["injected_signal_id"] = None
        self.assertEqual(run(world, "loudest")["selection_order"], run(world, "protected")["selection_order"])

    def test_need_too_expensive_to_attend(self):
        world = fresh()
        world["signals"][-1]["attention_cost"] = 8
        receipt = run(world, "protected")
        self.assertNotIn("quiet-neighbor", receipt["selection_order"])
        self.assertEqual(
            next(w["reason"] for w in receipt["witness"] if w["signal_id"] == "quiet-neighbor"),
            "COST_EXCEEDS_TOTAL_BUDGET",
        )

    def test_capacity_one_still_bounds_attendance(self):
        world = fresh()
        world["attention_units"] = 1
        selected = run(world, "protected")
        self.assertEqual(selected["selection_order"], ["quiet-neighbor"])
        self.assertEqual(selected["attention_spent"], 1)

    def test_duplicate_identity_fails(self):
        world = fresh()
        world["signals"][1]["signal_id"] = world["signals"][0]["signal_id"]
        with self.assertRaises(InvalidWorld):
            validate(world)

    def test_boolean_number_and_out_of_range_fail(self):
        for key, value in (
            ("attention_units", True), ("attention_units", 0),
            ("attention_units", 12), ("attention_units", 1.5),
        ):
            world = fresh()
            world[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(InvalidWorld):
                validate(world)
        for key, value in (("salience", True), ("attention_cost", 0), ("salience", 99)):
            world = fresh()
            world["signals"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(InvalidWorld):
                validate(world)

    def test_unhashable_source_classification_fails_closed(self):
        for field, bad in (("kind", ["human_need"]), ("cue", {"unmet_need": True})):
            world = fresh()
            world["signals"][-1][field] = bad
            with self.subTest(field=field), self.assertRaises(InvalidWorld):
                validate(world)

    def test_claimed_real_observation_fails_closed(self):
        world = fresh()
        world["signals"][0]["evidence_status"] = "PHYSICAL_RF_CONFIRMED"
        with self.assertRaises(InvalidWorld):
            validate(world)

    def test_unbound_source_ref_and_extra_fields_fail(self):
        for mutation in ("wrong-source", "extra-field"):
            world = fresh()
            if mutation == "wrong-source":
                world["signals"][0]["source_ref"] = "simulated:other"
            else:
                world["signals"][0]["commands"] = ["run-this"]
            with self.subTest(mutation=mutation), self.assertRaises(InvalidWorld):
                validate(world)

    def test_human_need_cannot_be_recast_as_radio(self):
        world = fresh()
        world["signals"][-1]["kind"] = "radio"
        with self.assertRaises(InvalidWorld):
            validate(world)

    def test_unknown_policy_fails(self):
        with self.assertRaises(InvalidWorld):
            run(fresh(), "execute-all")

    def test_no_pretense_of_real_ground_truth(self):
        receipt = run(fresh(), "protected")
        self.assertTrue(all(w["evidence_status"] == "SIMULATED_OBSERVED" for w in receipt["witness"]))
        self.assertNotIn("success", receipt)
        self.assertNotIn("utility", receipt)


if __name__ == "__main__":
    unittest.main()
