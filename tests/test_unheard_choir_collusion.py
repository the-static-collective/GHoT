#!/usr/bin/env python3
"""Hostile independent-synthetic-evidence tests for UNHEARD CHOIR 005."""
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

from relatte_identity import IdentityKey  # noqa: E402
from unheard_choir import InvalidWorld, digest  # noqa: E402
from unheard_choir_false_aperture import propose as parent_propose  # noqa: E402
from unheard_choir_lying_witness import ROLES, make_challenge, roster_for, sign_statement  # noqa: E402
from unheard_choir_collusion import (  # noqa: E402
    assess, compute_outcome, make_anchor, signed_precommit, signed_measurement,
    verify_replay, validate_samples,
)


def parent_fixture():
    root = ROOT / "fixtures"
    names = (
        "unheard-choir-002/observed-world.json",
        "unheard-choir-003/field.json",
        "unheard-choir-003/untrusted-catalog.json",
        "unheard-choir-003/owner-registry.json",
        "unheard-choir-003/reviewed-history.json",
    )
    return parent_propose(*(json.loads((root / n).read_text(encoding="utf-8")) for n in names))


class CollusionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        cls.keys = {
            name: IdentityKey.load_or_create(folder / (name + ".pem"))
            for name in ("owner", "source", "observer-east", "observer-west", "instrument", "attacker")
        }
        cls.parent = parent_fixture()
        cls.roster = roster_for(cls.parent, cls.keys["owner"],
                                {role: cls.keys[role] for role in ROLES})
        cls.anchor = make_anchor(cls.parent, cls.roster, cls.keys["instrument"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setup_world(self, answers=None, samples=None, *,
                    issued_at=1000, captured_at=900, nonce="a" * 32):
        samples = [0] * 8 if samples is None else samples
        answers = ["PRESENT"] * 3 if answers is None else answers
        pre = signed_precommit(
            self.parent, self.roster, self.anchor, self.keys["instrument"],
            samples=samples, captured_at=captured_at)
        ch = make_challenge(self.parent, self.roster, self.keys["owner"],
                            issued_at=issued_at, nonce=nonce)
        witness = [sign_statement(ch, role, answer, self.keys[role])
                   for role, answer in zip(ROLES, answers)]
        measured = signed_measurement(ch, pre, samples, self.keys["instrument"])
        return ch, witness, pre, measured

    def evaluate(self, ch, witness, pre=None, measured=None, *,
                 anchor=None, now=1001):
        if anchor is None and pre is not None:
            anchor = self.anchor
        return assess(self.parent, self.roster, ch, witness,
                      anchor, pre, measured, now=now)

    def test_three_signed_lies_do_not_override_simulated_raw_samples(self):
        ch, signs, pre, samples = self.setup_world()
        result = self.evaluate(ch, signs, pre, samples)
        self.assertEqual(result["claimant_consensus"], "PRESENT")
        self.assertEqual(result["recomputed_simulation_outcome"], "EMPTY")
        self.assertEqual(result["disposition"],
                         "HOLD_COLLUDING_CLAIMS_CONFLICT_WITH_SIMULATED_MEASUREMENT")
        self.assertEqual(result["004_disposition"], "REVIEW_CANDIDATE_NOT_ADMITTED")
        self.assertEqual(result["effects"], [])
        self.assertFalse(result["independent_truth_established"])

    def test_valid_claimant_signatures_without_instrument_remain_held(self):
        ch, signs, _, _ = self.setup_world()
        r = self.evaluate(ch, signs)
        self.assertEqual(r["disposition"], "HOLD_NO_PRECOMMITTED_DISTINCT_MEASUREMENT")
        self.assertEqual(r["measurement_evidence"], "MISSING")
        self.assertIsNone(r["recomputed_simulation_outcome"])

    def test_matching_simulated_independent_outcome_is_review_not_truth(self):
        ch, signs, pre, measured = self.setup_world(samples=[0, 0, 1, 0, 0, 0, 0, 0])
        r = self.evaluate(ch, signs, pre, measured)
        self.assertEqual(r["recomputed_simulation_outcome"], "PRESENT")
        self.assertEqual(r["disposition"], "REVIEW_MATCHES_SIMULATED_MEASUREMENT_NOT_ADMITTED")
        self.assertFalse(r["physical_sensor_independence_established"])
        self.assertFalse(r["native_relatte_admission"])
        self.assertFalse(r["external_execution"])

    def test_all_empty_signed_and_empty_samples_review_only(self):
        ch, signs, pre, measured = self.setup_world(answers=["EMPTY"] * 3)
        r = self.evaluate(ch, signs, pre, measured)
        self.assertEqual(r["disposition"], "REVIEW_MATCHES_SIMULATED_MEASUREMENT_NOT_ADMITTED")
        self.assertFalse(r["independent_truth_established"])

    def test_conflicting_claimants_stay_held_regardless_of_measurement(self):
        ch, signs, pre, measured = self.setup_world(answers=["PRESENT", "EMPTY", "EMPTY"])
        r = self.evaluate(ch, signs, pre, measured)
        self.assertEqual(r["disposition"], "HOLD_004_WITNESS_DISAGREEMENT_OR_MISSING")

    def test_observer_disagreement_stays_held(self):
        ch, signs, pre, measured = self.setup_world(answers=["PRESENT", "PRESENT", "EMPTY"])
        r = self.evaluate(ch, signs, pre, measured)
        self.assertEqual(r["disposition"], "HOLD_004_WITNESS_DISAGREEMENT_OR_MISSING")

    def test_partial_witness_set_stays_held(self):
        ch, signs, pre, measured = self.setup_world()
        r = self.evaluate(ch, signs[:2], pre, measured)
        self.assertEqual(r["disposition"], "HOLD_004_WITNESS_DISAGREEMENT_OR_MISSING")

    def test_no_witnesses_still_not_admitted(self):
        ch, _, pre, measured = self.setup_world()
        r = self.evaluate(ch, [], pre, measured)
        self.assertEqual(r["disposition"], "HOLD_004_WITNESS_DISAGREEMENT_OR_MISSING")

    def test_invalid_raw_fixture_shape_fails(self):
        for invalid in ([0], [0] * 9, [True] + [0] * 7, [-1] + [0] * 7,
                        [256] + [0] * 7, "00000000"):
            with self.subTest(invalid=invalid), self.assertRaises(InvalidWorld):
                validate_samples(invalid)

    def test_declared_deterministic_calibration_is_not_semantics(self):
        self.assertEqual(compute_outcome([0] * 8), "EMPTY")
        self.assertEqual(compute_outcome([0, 0, 255, 0, 0, 0, 0, 0]), "PRESENT")

    def test_tampered_signer_outcome_caught_by_004(self):
        ch, signs, pre, measured = self.setup_world()
        signs[0]["outcome"] = "EMPTY"
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_attacker_signs_claim_with_unpinned_key(self):
        ch, signs, pre, measured = self.setup_world()
        signs[0] = sign_statement(ch, "source", "PRESENT", self.keys["attacker"])
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_reusing_claims_on_new_nonce_fails(self):
        ch, signs, pre, measured = self.setup_world(nonce="a" * 32)
        different = make_challenge(self.parent, self.roster, self.keys["owner"],
                                   issued_at=1000, nonce="b" * 32)
        with self.assertRaises(InvalidWorld):
            self.evaluate(different, signs, pre, measured)

    def test_stale_challenge_refuses_even_signed_fixture(self):
        ch, signs, pre, measured = self.setup_world()
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured, now=2000)

    def test_future_challenge_refuses(self):
        ch, signs, pre, measured = self.setup_world()
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured, now=999)

    def test_unsupported_physical_sensor_claim_fails(self):
        ch, signs, pre, measured = self.setup_world()
        measured["measurement_scope"] = "VERIFIED_REAL_HARDWARE"
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_signer_key_reuse_from_colluding_trio_rejected(self):
        with self.assertRaises(InvalidWorld):
            make_anchor(self.parent, self.roster, self.keys["source"])

    def test_owner_as_instrument_key_rejected(self):
        with self.assertRaises(InvalidWorld):
            make_anchor(self.parent, self.roster, self.keys["owner"])

    def test_fake_pinned_instrument_key_rejected(self):
        ch, signs, pre, measured = self.setup_world()
        anchor = copy.deepcopy(self.anchor)
        anchor["instrument_public_key"] = self.keys["attacker"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured, anchor=anchor)

    def test_fake_instrument_signature_rejected(self):
        ch, signs, pre, measured = self.setup_world()
        measured["signature"] = "abc"
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_fake_precommit_signature_rejected(self):
        ch, signs, pre, measured = self.setup_world()
        pre["signature"] = "abc"
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_precommit_postdated_after_challenge_refused(self):
        ch, signs, pre, measured = self.setup_world(captured_at=1100)
        with self.assertRaisesRegex(InvalidWorld, "precede"):
            self.evaluate(ch, signs, pre, measured)

    def test_tampered_precommit_cut_refused(self):
        ch, signs, pre, measured = self.setup_world()
        pre["source_world_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_tampered_epoch_refused(self):
        ch, signs, pre, measured = self.setup_world()
        pre["instrument_epoch"] = 100
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_stale_source_cut_roster_refused(self):
        ch, signs, pre, measured = self.setup_world()
        new_parent = copy.deepcopy(self.parent)
        new_parent["world_digest"] = "0" * 64
        new_parent["proposal_digest"] = digest({
            k: v for k, v in new_parent.items() if k != "proposal_digest"})
        with self.assertRaises(InvalidWorld):
            assess(new_parent, self.roster, ch, signs, self.anchor, pre, measured, now=1001)

    def test_mismatched_raw_bytes_refused_even_correct_signature_of_old(self):
        ch, signs, pre, measured = self.setup_world()
        measured["samples"][0] = 1
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_raw_bytes_rehashed_without_resigning_fails(self):
        ch, signs, pre, measured = self.setup_world()
        measured["samples"][0] = 1
        measured["sample_digest"] = digest(measured["samples"])
        measured["derived_outcome"] = "PRESENT"
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_tampered_derived_outcome_refused(self):
        ch, signs, pre, measured = self.setup_world()
        measured["derived_outcome"] = "PRESENT"
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_measurement_from_other_challenge_refused(self):
        ch, signs, pre, measured = self.setup_world()
        newer = make_challenge(self.parent, self.roster, self.keys["owner"],
                               issued_at=1000, nonce="b" * 32)
        measured["challenge_digest"] = digest(newer)
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_precommit_missing_does_not_accidentally_accept_measurement(self):
        ch, signs, pre, measured = self.setup_world()
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, None, measured, anchor=self.anchor)

    def test_anchor_without_measurement_is_not_usable(self):
        ch, signs, pre, measured = self.setup_world()
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, None)

    def test_precommit_does_not_claim_external_sensor(self):
        ch, signs, pre, measured = self.setup_world()
        pre["data_scope"] = "PHYSICAL_TRUSTED"
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, pre, measured)

    def test_raw_samples_from_other_precommit_cannot_be_laundered(self):
        ch, signs, pre, measured = self.setup_world()
        new_commit = signed_precommit(
            self.parent, self.roster, self.anchor, self.keys["instrument"],
            samples=[0, 0, 3, 0, 0, 0, 0, 0], captured_at=900)
        with self.assertRaises(InvalidWorld):
            self.evaluate(ch, signs, new_commit, measured)

    def test_attestation_receipt_recomputed_digest_forgery_fails(self):
        ch, signs, pre, measured = self.setup_world()
        r = self.evaluate(ch, signs, pre, measured)
        r["independent_truth_established"] = True
        r["assessment_digest"] = digest({
            k: v for k, v in r.items() if k != "assessment_digest"})
        self.assertFalse(verify_replay(self.parent, self.roster, ch, signs,
            self.anchor, pre, measured, r, now=1001))

    def test_valid_cold_replay_read_only(self):
        ch, signs, pre, measured = self.setup_world()
        report = self.evaluate(ch, signs, pre, measured)
        self.assertTrue(verify_replay(self.parent, self.roster, ch, signs,
                        self.anchor, pre, measured, report, now=1001))
        self.assertEqual(report, self.evaluate(ch, signs, pre, measured))

    def test_attacker_supplies_new_trust_anchor_can_fake_agreement(self):
        # A *separate* fixture-author-provisioned key/anchor can consistently
        # claim positive sample bytes. This is the deliberate trust-root limit:
        # key distinctness alone is not true independent observation.
        ch, signs, _, _ = self.setup_world()
        bogus = make_anchor(self.parent, self.roster, self.keys["attacker"])
        samples = [1] * 8
        pre = signed_precommit(self.parent, self.roster, bogus, self.keys["attacker"],
                               samples=samples, captured_at=900)
        measurement = signed_measurement(ch, pre, samples, self.keys["attacker"])
        r = self.evaluate(ch, signs, pre, measurement, anchor=bogus)
        self.assertEqual(r["disposition"], "REVIEW_MATCHES_SIMULATED_MEASUREMENT_NOT_ADMITTED")
        self.assertFalse(r["independent_truth_established"])

    def test_cli_cross_process_evaluation_without_private_keys(self):
        ch, signs, pre, measured = self.setup_world()
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            for name, obj in (("parent", self.parent), ("roster", self.roster),
                              ("challenge", ch), ("statements", signs),
                              ("anchor", self.anchor), ("precommit", pre),
                              ("measurement", measured)):
                (temp / (name + ".json")).write_text(json.dumps(obj), encoding="utf-8")
            common = []
            for name in ("parent", "roster", "challenge", "statements", "anchor", "precommit", "measurement"):
                common += ["--" + name, str(temp / (name + ".json"))]
            common += ["--now", "1001"]
            cli = [sys.executable, str(ROOT / "ghot" / "unheard_choir_collusion.py")]
            assessed = subprocess.run(cli + ["assess"] + common,
                                      capture_output=True, text=True)
            self.assertEqual(assessed.returncode, 0, assessed.stderr)
            output = json.loads(assessed.stdout)
            self.assertEqual(output["disposition"],
                             "HOLD_COLLUDING_CLAIMS_CONFLICT_WITH_SIMULATED_MEASUREMENT")
            (temp / "receipt.json").write_text(assessed.stdout, encoding="utf-8")
            verified = subprocess.run(cli + ["verify"] + common + [
                "--receipt", str(temp / "receipt.json")],
                capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout), {"verified": True})

    def test_demo_signed_colluding_lie_refused(self):
        r = subprocess.run([sys.executable, str(ROOT / "ghot" / "unheard_choir_collusion.py"),
                            "demo"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual(report["signed_cryptographic_objects"], 6)
        self.assertEqual(report["disposition"],
                         "HOLD_COLLUDING_CLAIMS_CONFLICT_WITH_SIMULATED_MEASUREMENT")
        self.assertTrue(report["cold_replay_verified"])
        self.assertFalse(report["new_source_real_world_truth_proven"])


if __name__ == "__main__":
    unittest.main()
