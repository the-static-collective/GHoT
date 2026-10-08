#!/usr/bin/env python3
"""UNHEARD CHOIR 006 hostile device-key compromise and custody matrix."""
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
from unheard_choir_collusion import make_anchor, signed_precommit, signed_measurement  # noqa: E402
from unheard_choir_counterfeit import (  # noqa: E402
    assess, verify_replay, make_pinset, sign_custody, sign_secondary,
    check_secondary, check_custody, validate_frames, map_secondary,
)


def parent_fixture():
    f = ROOT / "fixtures"
    sources = ("unheard-choir-002/observed-world.json", "unheard-choir-003/field.json",
               "unheard-choir-003/untrusted-catalog.json",
               "unheard-choir-003/owner-registry.json", "unheard-choir-003/reviewed-history.json")
    return parent_propose(*(json.loads((f / s).read_text(encoding="utf-8")) for s in sources))


class CounterfeitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory()
        folder = Path(cls.root.name)
        roles = ("owner", "source", "observer-east", "observer-west", "primary-instrument",
                 "primary-custodian", "secondary-instrument", "secondary-custodian", "attacker")
        cls.keys = {r: IdentityKey.load_or_create(folder / (r + ".pem")) for r in roles}
        cls.parent = parent_fixture()
        cls.roster = roster_for(cls.parent, cls.keys["owner"], {r: cls.keys[r] for r in ROLES})
        cls.anchor = make_anchor(cls.parent, cls.roster, cls.keys["primary-instrument"])

    @classmethod
    def tearDownClass(cls):
        cls.root.cleanup()

    def world(self, *, roots_a=None, roots_b=None, secondary=None,
              primary=None, claimed="PRESENT", claims=None, nonce="a" * 32):
        a = ["fixture-source-primary"] if roots_a is None else roots_a
        b = ["fixture-source-secondary"] if roots_b is None else roots_b
        frames_a = [1] * 8 if primary is None else primary
        frames_b = [0] * 8 if secondary is None else secondary
        challenge = make_challenge(self.parent, self.roster, self.keys["owner"],
                                   issued_at=1000, nonce=nonce)
        outcomes = [claimed] * 3 if claims is None else claims
        witnesses = [sign_statement(challenge, role, outcome, self.keys[role])
                     for role, outcome in zip(ROLES, outcomes)]
        pre = signed_precommit(self.parent, self.roster, self.anchor,
                               self.keys["primary-instrument"], samples=frames_a,
                               captured_at=900)
        measured_a = signed_measurement(challenge, pre, frames_a, self.keys["primary-instrument"])
        pins = make_pinset(
            self.parent, self.roster, challenge, self.anchor, self.keys["owner"],
            self.keys["primary-custodian"], self.keys["secondary-custodian"],
            self.keys["secondary-instrument"], primary_roots=a, secondary_roots=b)
        measured_b = sign_secondary(pins, challenge, frames_b, self.keys["secondary-instrument"])
        custody_a = sign_custody(pins, challenge, "primary", digest(measured_a),
                                 self.keys["primary-custodian"], declared_acquired_at=1000)
        custody_b = sign_custody(pins, challenge, "secondary", digest(measured_b),
                                 self.keys["secondary-custodian"], declared_acquired_at=1000)
        return [self.parent, self.roster, challenge, witnesses, self.anchor,
                pre, measured_a, pins, custody_a, custody_b, measured_b]

    def check(self, data, *, now=1001):
        return assess(*data, now=now)

    def test_counterfeit_primary_signer_true_key_still_held(self):
        values = self.world()
        report = self.check(values)
        self.assertEqual(report["005_disposition"], "REVIEW_MATCHES_SIMULATED_MEASUREMENT_NOT_ADMITTED")
        self.assertEqual(report["primary_simulated_outcome"], "PRESENT")
        self.assertEqual(report["secondary_simulated_outcome"], "EMPTY")
        self.assertEqual(report["decision"], "HOLD_COUNTERFEIT_OR_CALIBRATION_CONFLICT_UNRESOLVED")
        self.assertFalse(report["compromised_sensor_identified"])
        self.assertFalse(report["physical_truth_established"])
        self.assertFalse(report["independent_custody_proven"])

    def test_custody_claim_signatures_verify(self):
        data = self.world()
        report = self.check(data)
        self.assertTrue(report["signed_custody_claims_verified"])
        self.assertEqual(len(report["custody_claim_digests"]), 2)
        self.assertFalse(report["signed_receipts_are_physical_custody_proof"])
        self.assertFalse(report["external_execution"])
        self.assertEqual(report["effects"], [])

    def test_agreeing_multimodal_fixtures_never_admitted(self):
        values = self.world(secondary=[200, 180] + [0] * 6)
        report = self.check(values)
        self.assertEqual(report["secondary_simulated_outcome"], "PRESENT")
        self.assertEqual(report["decision"],
                         "REVIEW_DECLARED_DISTINCT_MODALITIES_CONCORDANT_NOT_ADMITTED")
        self.assertEqual(report["authority"], "NONE")
        self.assertFalse(report["native_relatte_signed_crossing"])

    def test_two_different_profiles_produce_different_results_from_same_frames(self):
        self.assertEqual(map_secondary([1] * 8), "EMPTY")
        self.assertEqual(map_secondary([128, 128] + [0] * 6), "PRESENT")
        self.assertEqual(map_secondary([255] + [0] * 7), "EMPTY")

    def test_nonbytes_and_inaccurate_lengths_rejected(self):
        for frames in ([], [0] * 9, [0] * 7 + [256], [0] * 7 + [True],
                       "eight", [-1] + [0] * 7, [1.0] + [0] * 7):
            with self.subTest(frames=frames), self.assertRaises(InvalidWorld):
                validate_frames(frames)

    def test_shared_dependency_root_forces_hold_even_when_modalities_agree(self):
        values = self.world(roots_a=["fixture-shared-bus"],
                            roots_b=["fixture-shared-bus"],
                            secondary=[200, 200] + [0] * 6)
        report = self.check(values)
        self.assertEqual(report["decision"], "HOLD_DECLARED_SHARED_DEPENDENCY")

    def test_two_modalities_do_not_establish_physical_independence(self):
        values = self.world(secondary=[200, 200] + [0] * 6)
        r = self.check(values)
        self.assertFalse(r["two_distinct_keys_are_physical_independence"])
        self.assertFalse(r["physical_truth_established"])

    def test_owner_must_be_pinned_to_sign_pinset(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            make_pinset(self.parent, self.roster, d[2], self.anchor, self.keys["attacker"],
                        self.keys["primary-custodian"], self.keys["secondary-custodian"],
                        self.keys["secondary-instrument"],
                        primary_roots=["fixture-a"], secondary_roots=["fixture-b"])

    def test_primary_sensor_cannot_be_its_custodian(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            make_pinset(self.parent, self.roster, d[2], self.anchor, self.keys["owner"],
                        self.keys["primary-instrument"], self.keys["secondary-custodian"],
                        self.keys["secondary-instrument"],
                        primary_roots=["fixture-a"], secondary_roots=["fixture-b"])

    def test_common_custodian_for_both_instruments_refused(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            make_pinset(self.parent, self.roster, d[2], self.anchor, self.keys["owner"],
                        self.keys["primary-custodian"], self.keys["primary-custodian"],
                        self.keys["secondary-instrument"],
                        primary_roots=["fixture-a"], secondary_roots=["fixture-b"])

    def test_secondary_sensor_reusing_claimant_key_rejected(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            make_pinset(self.parent, self.roster, d[2], self.anchor, self.keys["owner"],
                        self.keys["primary-custodian"], self.keys["secondary-custodian"],
                        self.keys["source"],
                        primary_roots=["fixture-a"], secondary_roots=["fixture-b"])

    def test_wrong_instrument_signing_key_refused(self):
        data = self.world()
        with self.assertRaises(InvalidWorld):
            sign_secondary(data[7], data[2], [0] * 8, self.keys["attacker"])

    def test_wrong_custodian_signing_key_refused(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            sign_custody(d[7], d[2], "primary", digest(d[6]),
                         self.keys["attacker"], declared_acquired_at=1000)

    def test_missing_secondary_evidence_holds(self):
        d = self.world()
        r = self.check(d[:7] + [None] * 4)
        self.assertEqual(r["decision"], "HOLD_NO_INDEPENDENT_CUSTODY_OR_SECONDARY_MODALITY")
        self.assertFalse(r["signed_custody_claims_verified"])

    def test_partial_custody_evidence_fails_closed(self):
        d = self.world()
        d[8] = None
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_stale_challenge_fails_closed(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            self.check(d, now=2000)

    def test_new_nonce_denies_replay_even_with_real_signatures(self):
        d = self.world()
        newer = make_challenge(self.parent, self.roster, self.keys["owner"],
                               issued_at=1000, nonce="b" * 32)
        d[2] = newer
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_custody_swap_between_instruments_refused(self):
        d = self.world()
        d[8], d[9] = d[9], d[8]
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_changed_measurement_without_updated_custody_refused(self):
        d = self.world()
        d[10] = sign_secondary(d[7], d[2], [200, 200] + [0] * 6,
                                self.keys["secondary-instrument"])
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_secondary_measurement_claim_can_not_launder_wrong_derived_outcome(self):
        d = self.world()
        d[10]["claimed_outcome"] = "PRESENT"
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_secondary_sensor_signs_mismatched_epoch_fails(self):
        d = self.world()
        d[10]["instrument_epoch"] = 999
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_previously_signed_primary_key_forgery_detected_on_mutation(self):
        d = self.world()
        d[6]["samples"][0] = 0
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_custody_signature_tampering_refused(self):
        d = self.world()
        d[8]["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_owner_signed_pinset_tamper_fails(self):
        d = self.world()
        d[7]["channels"]["secondary"]["dependency_roots"] = ["fixture-forged"]
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_custody_dependency_tamper_refused(self):
        d = self.world()
        d[9]["dependency_roots"] = ["fixture-fake"]
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_custody_cannot_claim_physical_receipt(self):
        d = self.world()
        d[8]["scope"] = "REAL_WORLD_CUSTODY_CONFIRMED"
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_unrecognized_secondary_calibration_profile_refused(self):
        d = self.world()
        d[7]["channels"]["secondary"]["modality"] = "CERTIFIED_SENSOR"
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_invalid_shared_dependency_syntax_refused(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            make_pinset(self.parent, self.roster, d[2], self.anchor, self.keys["owner"],
                        self.keys["primary-custodian"], self.keys["secondary-custodian"],
                        self.keys["secondary-instrument"],
                        primary_roots=["external-cloud"], secondary_roots=["fixture-secondary"])

    def test_duplicate_dependencies_refused(self):
        d = self.world()
        with self.assertRaises(InvalidWorld):
            make_pinset(self.parent, self.roster, d[2], self.anchor, self.keys["owner"],
                        self.keys["primary-custodian"], self.keys["secondary-custodian"],
                        self.keys["secondary-instrument"],
                        primary_roots=["fixture-x", "fixture-x"],
                        secondary_roots=["fixture-y"])

    def test_changed_challenge_epoch_refused(self):
        d = self.world()
        d[2]["owner_epoch"] += 1
        with self.assertRaises(InvalidWorld):
            self.check(d)

    def test_claimant_disagreement_retains_parent_hold(self):
        d = self.world(claims=["PRESENT", "EMPTY", "EMPTY"])
        r = self.check(d)
        self.assertEqual(r["decision"], "HOLD_PARENT005_EVIDENCE_OR_CLAIM")

    def test_real_signatures_do_not_grant_native_execution(self):
        r = self.check(self.world())
        self.assertFalse(r["native_relatte_signed_crossing"])
        self.assertFalse(r["independent_custody_proven"])
        self.assertFalse(r["physical_truth_established"])
        self.assertEqual(r["authority"], "NONE")
        self.assertEqual(r["effects"], [])

    def test_rehashed_forged_receipt_rejected_by_replay(self):
        d = self.world()
        r = self.check(d)
        r["physical_truth_established"] = True
        r["assessment_digest"] = digest({k: v for k, v in r.items() if k != "assessment_digest"})
        self.assertFalse(verify_replay(*d, r, now=1001))

    def test_cold_process_replay_without_private_keys(self):
        d = self.world()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            names = ("parent", "roster", "challenge", "statements", "primary_anchor",
                     "primary_precommit", "primary_measurement", "pinset", "primary_custody",
                     "secondary_custody", "secondary_measurement")
            flags = []
            for name, obj in zip(names, d):
                file = directory / (name + ".json")
                file.write_text(json.dumps(obj), encoding="utf-8")
                flags += ["--" + name.replace("_", "-"), str(file)]
            flags += ["--now", "1001"]
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_counterfeit.py")]
            seen = subprocess.run(cmd + ["assess"] + flags, capture_output=True, text=True)
            self.assertEqual(seen.returncode, 0, seen.stderr)
            self.assertEqual(json.loads(seen.stdout)["decision"],
                             "HOLD_COUNTERFEIT_OR_CALIBRATION_CONFLICT_UNRESOLVED")
            outpath = directory / "report.json"
            outpath.write_text(seen.stdout, encoding="utf-8")
            verified = subprocess.run(cmd + ["verify"] + flags +
                                      ["--receipt", str(outpath)], capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout), {"verified": True})

    def test_demo_compromised_key(self):
        r = subprocess.run([sys.executable, str(ROOT / "ghot" / "unheard_choir_counterfeit.py"),
                            "demo"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        result = json.loads(r.stdout)
        self.assertTrue(result["simulated_primary_compromised_key_used"])
        self.assertEqual(result["decision"],
                         "HOLD_COUNTERFEIT_OR_CALIBRATION_CONFLICT_UNRESOLVED")
        self.assertTrue(result["cold_replay_verified"])
        self.assertFalse(result["real_world_truth_proven"])
        self.assertFalse(result["external_execution"])


if __name__ == "__main__":
    unittest.main()
