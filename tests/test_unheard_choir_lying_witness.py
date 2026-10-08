#!/usr/bin/env python3
"""Adversarial signatures and replay matrix for UNHEARD CHOIR 004."""
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
from unheard_choir_lying_witness import (  # noqa: E402
    assess, check_challenge, check_roster, make_challenge, record_once,
    roster_for, sign_statement,
)

def parent_fixture():
    source = ROOT / "fixtures"
    names = (
        "unheard-choir-002/observed-world.json",
        "unheard-choir-003/field.json",
        "unheard-choir-003/untrusted-catalog.json",
        "unheard-choir-003/owner-registry.json",
        "unheard-choir-003/reviewed-history.json",
    )
    return parent_propose(*(json.loads((source / n).read_text(encoding="utf-8")) for n in names))


class LyingWitnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        d = Path(cls.dir.name)
        cls.keys = {role: IdentityKey.load_or_create(d / (role + ".pem"))
                    for role in ("owner", "source", "observer-east", "observer-west", "imposter")}
        cls.parent = parent_fixture()
        cls.roster = roster_for(cls.parent, cls.keys["owner"],
                                {r: cls.keys[r] for r in ("source", "observer-east", "observer-west")})

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def encounter(self, source="PRESENT", east="EMPTY", west="EMPTY", nonce="a" * 32):
        challenge = make_challenge(self.parent, self.roster, self.keys["owner"],
                                   issued_at=1000, nonce=nonce)
        signed = [
            sign_statement(challenge, role, outcome, self.keys[role])
            for role, outcome in (("source", source), ("observer-east", east), ("observer-west", west))
        ]
        return challenge, signed

    def test_valid_signatures_can_make_contradictory_claims(self):
        challenge, statements = self.encounter()
        p = assess(self.parent, self.roster, challenge, statements, now=1001)
        self.assertEqual(p["disposition"], "HOLD_AUTHENTIC_BUT_CONTRADICTED_SOURCE")
        self.assertTrue(all(w["signature_valid"] for w in p["witnesses"]))
        self.assertEqual(p["independent_observer_keys"], 2)
        self.assertFalse(p["source_claim_proven_true"])
        self.assertFalse(p["physical_independence_proven"])
        self.assertEqual(p["effects"], [])
        self.assertEqual(p["authority"], "NONE")

    def test_agreement_is_review_candidate_not_truth(self):
        challenge, statements = self.encounter("PRESENT", "PRESENT", "PRESENT")
        p = assess(self.parent, self.roster, challenge, statements, now=1001)
        self.assertEqual(p["disposition"], "REVIEW_CANDIDATE_NOT_ADMITTED")
        self.assertFalse(p["source_claim_proven_true"])
        self.assertFalse(p["owner_identity_independently_proven"])
        self.assertFalse(p["external_execution"])
        self.assertFalse(p["native_relatte_signed_receipt"])

    def test_observers_disagree_even_if_source_agrees_with_one(self):
        c, s = self.encounter("PRESENT", "PRESENT", "EMPTY")
        self.assertEqual(assess(self.parent, self.roster, c, s, now=1001)["disposition"],
                         "HOLD_OBSERVER_DISAGREEMENT")

    def test_missing_observer_does_not_infer_agreement(self):
        c, s = self.encounter()
        r = assess(self.parent, self.roster, c, s[:2], now=1001)
        self.assertEqual(r["disposition"], "HOLD_MISSING_INDEPENDENT_WITNESSES")
        self.assertEqual(len(r["witnesses"]), 2)

    def test_empty_statements_cannot_become_source_truth(self):
        c, _ = self.encounter()
        r = assess(self.parent, self.roster, c, [], now=1001)
        self.assertFalse(r["source_signed"])
        self.assertEqual(r["disposition"], "HOLD_MISSING_INDEPENDENT_WITNESSES")

    def test_signature_tampering_fails(self):
        c, s = self.encounter()
        s[0]["outcome"] = "EMPTY"
        with self.assertRaisesRegex(InvalidWorld, "signature invalid"):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_signed_false_claim_is_not_automatically_admitted(self):
        c, s = self.encounter()
        self.assertEqual(s[0]["outcome"], "PRESENT")
        self.assertEqual(s[1]["outcome"], "EMPTY")
        self.assertEqual(s[2]["outcome"], "EMPTY")
        r = assess(self.parent, self.roster, c, s, now=1001)
        self.assertTrue(r["source_signed"])
        self.assertNotEqual(r["disposition"], "REVIEW_CANDIDATE_NOT_ADMITTED")

    def test_cross_role_pretender_with_real_signature_rejected(self):
        c, s = self.encounter()
        s[0] = sign_statement(c, "source", "PRESENT", self.keys["imposter"])
        with self.assertRaisesRegex(InvalidWorld, "not pinned"):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_valid_observer_signature_not_valid_as_source(self):
        c, s = self.encounter()
        s[0] = sign_statement(c, "source", "PRESENT", self.keys["observer-east"])
        with self.assertRaisesRegex(InvalidWorld, "not pinned"):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_duplicate_roles_cannot_inflate_quorum(self):
        c, s = self.encounter()
        with self.assertRaisesRegex(InvalidWorld, "duplicate witness"):
            assess(self.parent, self.roster, c, [s[0], s[1], s[1]], now=1001)

    def test_four_signatures_cannot_be_three_witnesses(self):
        c, s = self.encounter()
        with self.assertRaisesRegex(InvalidWorld, "too many"):
            assess(self.parent, self.roster, c, s + [s[2]], now=1001)

    def test_pinned_keys_unique_and_owner_is_not_observer(self):
        roster = copy.deepcopy(self.roster)
        roster["actors"]["observer-west"] = roster["actors"]["source"]
        with self.assertRaisesRegex(InvalidWorld, "distinct"):
            check_roster(self.parent, roster)

    def test_unpinned_roster_cannot_be_reused(self):
        c, s = self.encounter()
        roster = copy.deepcopy(self.roster)
        roster["actors"]["source"] = self.keys["imposter"].public_jwk()
        with self.assertRaises(InvalidWorld):
            assess(self.parent, roster, c, s, now=1001)

    def test_invalid_owner_challenge_signature_rejected(self):
        c, s = self.encounter()
        c["signature"] = "a" * 86
        with self.assertRaisesRegex(InvalidWorld, "signature invalid"):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_owner_challenge_must_be_issued_by_pinned_owner(self):
        with self.assertRaisesRegex(InvalidWorld, "not pinned"):
            make_challenge(self.parent, self.roster, self.keys["imposter"], issued_at=1000, nonce="b" * 32)

    def test_owner_challenge_has_domain_separation(self):
        c, s = self.encounter()
        c["scope"] = "NATIVE_EXECUTION_PERMITTED"
        with self.assertRaises(InvalidWorld):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_nonce_change_denies_replayed_signed_observation(self):
        c1, s = self.encounter(nonce="a" * 32)
        c2, _ = self.encounter(nonce="b" * 32)
        with self.assertRaisesRegex(InvalidWorld, "wrong challenge"):
            assess(self.parent, self.roster, c2, s, now=1001)

    def test_expired_challenge_rejected(self):
        c, s = self.encounter()
        with self.assertRaisesRegex(InvalidWorld, "not fresh"):
            assess(self.parent, self.roster, c, s, now=1061)

    def test_future_challenge_rejected(self):
        c, s = self.encounter()
        with self.assertRaisesRegex(InvalidWorld, "not fresh"):
            assess(self.parent, self.roster, c, s, now=999)

    def test_unreasonably_long_challenge_refused(self):
        with self.assertRaises(InvalidWorld):
            make_challenge(self.parent, self.roster, self.keys["owner"],
                           issued_at=1000, ttl=9000)

    def test_invalid_nonce_refused(self):
        with self.assertRaises(InvalidWorld):
            make_challenge(self.parent, self.roster, self.keys["owner"],
                           issued_at=1000, nonce="NOT_RANDOM")

    def test_changed_epoch_causes_challenge_refusal(self):
        c, s = self.encounter()
        c["owner_epoch"] += 1
        with self.assertRaises(InvalidWorld):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_cross_world_parent_change_refused(self):
        c, s = self.encounter()
        parent = copy.deepcopy(self.parent)
        parent["world_digest"] = "0" * 64
        parent["proposal_digest"] = digest({k: v for k, v in parent.items() if k != "proposal_digest"})
        with self.assertRaises(InvalidWorld):
            assess(parent, self.roster, c, s, now=1001)

    def test_malformed_parent_digest_refused(self):
        parent = copy.deepcopy(self.parent)
        parent["selected"]["aperture_id"] = "private-cabinet"
        with self.assertRaises(InvalidWorld):
            check_roster(parent, self.roster)

    def test_malformed_statement_field_refused(self):
        c, s = self.encounter()
        s[1]["execute"] = True
        with self.assertRaises(InvalidWorld):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_fabricated_physical_evidence_status_refused(self):
        c, s = self.encounter()
        s[0]["evidence_kind"] = "PHYSICAL_SPECTRUM_CONFIRMED"
        with self.assertRaises(InvalidWorld):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_sample_reference_cannot_launder_source(self):
        c, s = self.encounter()
        s[1]["sample_ref"] = "simulated:source"
        with self.assertRaises(InvalidWorld):
            assess(self.parent, self.roster, c, s, now=1001)

    def test_durable_one_use_local_record(self):
        c, s = self.encounter()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "review.sqlite"
            result = record_once(path, self.parent, self.roster, c, s, now=1001)
            self.assertEqual(result["recorded_disposition"], "HOLD_AUTHENTIC_BUT_CONTRADICTED_SOURCE")
            with self.assertRaisesRegex(InvalidWorld, "already used"):
                record_once(path, self.parent, self.roster, c, s, now=1001)

    def test_replay_refused_even_if_signed_statements_changed(self):
        c, s = self.encounter()
        s2 = [sign_statement(c, role, "PRESENT", self.keys[role]) for role in
              ("source", "observer-east", "observer-west")]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.sqlite"
            record_once(path, self.parent, self.roster, c, s, now=1001)
            with self.assertRaisesRegex(InvalidWorld, "already used"):
                record_once(path, self.parent, self.roster, c, s2, now=1001)

    def test_expired_recording_uses_fresh_reverification(self):
        c, s = self.encounter()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.sqlite"
            with self.assertRaises(InvalidWorld):
                record_once(path, self.parent, self.roster, c, s, now=2000)

    def test_cold_verification_and_durable_record(self):
        c, s = self.encounter()
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            for name, obj in (("parent", self.parent), ("roster", self.roster),
                              ("challenge", c), ("statements", s)):
                (tmp / (name + ".json")).write_text(json.dumps(obj), encoding="utf-8")
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_lying_witness.py")]
            args = []
            for name in ("parent", "roster", "challenge", "statements"):
                args += ["--" + name, str(tmp / (name + ".json"))]
            args += ["--now", "1001"]
            result = subprocess.run(cmd + ["assess"] + args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["disposition"], "HOLD_AUTHENTIC_BUT_CONTRADICTED_SOURCE")
            save = subprocess.run(cmd + ["record"] + args + ["--db", str(tmp / "state.sqlite")],
                                  capture_output=True, text=True)
            self.assertEqual(save.returncode, 0, save.stderr)
            again = subprocess.run(cmd + ["record"] + args + ["--db", str(tmp / "state.sqlite")],
                                   capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("already used", again.stderr)

    def test_ephemeral_demo_without_committed_secrets(self):
        run = subprocess.run([sys.executable, str(ROOT / "ghot" / "unheard_choir_lying_witness.py"),
                              "demo"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["disposition"], "HOLD_AUTHENTIC_BUT_CONTRADICTED_SOURCE")
        self.assertTrue(report["local_replay_blocked"])
        self.assertFalse(report["signature_proves_truth"])


if __name__ == "__main__":
    unittest.main()
