#!/usr/bin/env python3
"""009 hostile chronology, fork, witness identity and replay tests."""
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
from unheard_choir import InvalidWorld, digest  # noqa: E402
from unheard_choir_timestamp import (  # noqa: E402
    assess, append_entries, build_fixture_for_tests, demo, entry_head,
    make_checkpoint, make_policy, make_submission, signed_artifacts,
    verify_checkpoint, verify_entries, verify_replay,
)


class LyingTimestampTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.base, cls.keys = build_fixture_for_tests()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def world(self):
        return copy.deepcopy(self.base)

    def check(self, data):
        return assess(*data, now=1001)

    def test_signed_timestamps_claim_earlier_publication_than_log_records(self):
        r = self.check(self.world())
        self.assertEqual(r["008_decision"], "HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH")
        self.assertEqual(r["decision"], "HOLD_SIGNED_PUBLICATION_ORDER_CLAIM_CONTRADICTED")
        self.assertEqual(r["log_size"], 6)
        self.assertEqual(len(r["contradicted_publication_claims"]), 2)
        self.assertEqual(r["contradicted_publication_claims"][0]["claims_prior_to"], "owner-challenge")
        self.assertFalse(r["sample_captured_at_claim_verified"])

    def test_exactly_two_independent_cowitness_signatures(self):
        w = self.world()
        self.assertEqual(set(w[20][0]["witness_signatures"]), {"a", "b"})
        self.assertEqual(w[20][0]["size"], 6)
        self.assertTrue(w[20][0]["sequencer_signature"])
        verify_checkpoint(w[17], w[20][0])

    def test_two_valid_conflicting_cowitnessed_histories_force_hold(self):
        tmp, w, _ = build_fixture_for_tests(fork=True)
        try:
            r = self.check(w)
            self.assertEqual(r["decision"], "HOLD_MULTIPARTY_WITNESSED_LOG_FORK")
            self.assertEqual(r["forked_checkpoint_sizes"], [6])
            self.assertEqual(len(w[20]), 2)
            for checkpoint in w[20]:
                verify_checkpoint(w[17], checkpoint)
        finally:
            tmp.cleanup()

    def test_evidence_consistent_order_is_still_review_only(self):
        tmp, w, _ = build_fixture_for_tests(earlier_audit_matches=True,
                                             log_order_lie=False)
        try:
            r = self.check(w)
            self.assertEqual(r["008_decision"], "REVIEW_AUDIT_TRACES_MATCH_DECLARED_GRAPH_NOT_ADMITTED")
            self.assertEqual(r["decision"], "REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED")
            self.assertFalse(r["log_order_is_wall_clock_time"])
            self.assertFalse(r["external_execution"])
        finally:
            tmp.cleanup()

    def test_008_hold_never_cleared_by_matching_log(self):
        tmp, w, _ = build_fixture_for_tests(log_order_lie=False)
        try:
            r = self.check(w)
            self.assertEqual(r["decision"], "HOLD_INHERITED_008_EVIDENCE_CONTRADICTION")
        finally:
            tmp.cleanup()

    def test_missing_log_holds_and_never_infers_no_publications(self):
        w = self.world()
        w[17:] = [None] * 4
        r = self.check(w)
        self.assertEqual(r["decision"], "HOLD_NO_WITNESSED_TRANSPARENCY_LOG")
        self.assertFalse(r["sample_captured_at_claim_verified"])

    def test_partial_log_evidence_is_refused(self):
        w = self.world()
        w[19] = None
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_incomplete_event_coverage_holds(self):
        w = self.world()
        w[19] = w[19][:-1]
        w[20] = [make_checkpoint(w[17], len(w[19]), w[19][-1]["head"],
                                 self.keys["log-sequencer"],
                                 self.keys["log-witness-a"],
                                 self.keys["log-witness-b"])]
        r = self.check(w)
        self.assertEqual(r["decision"], "HOLD_INCOMPLETE_WITNESSED_LOG_COVERAGE")
        self.assertIn("audit-reveal-secondary", r["missing_publication_events"])

    def test_wrong_checkpoint_head_validly_signed_means_conflict_not_truth(self):
        w = self.world()
        cp = make_checkpoint(w[17], 6, "a" * 64,
                             self.keys["log-sequencer"],
                             self.keys["log-witness-a"], self.keys["log-witness-b"])
        w[20] = [cp]
        r = self.check(w)
        self.assertEqual(r["decision"], "HOLD_SIGNED_CHECKPOINT_INCONSISTENT_WITH_LOG")

    def test_wrong_checkpoint_signature_refused(self):
        w = self.world()
        w[20][0]["sequencer_signature"] = "invalid"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_witness_a_signature_tamper_refused(self):
        w = self.world()
        w[20][0]["witness_signatures"]["a"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_witness_b_signature_tamper_refused(self):
        w = self.world()
        w[20][0]["witness_signatures"]["b"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_missing_witness_signature_refused_not_degraded_quorum(self):
        w = self.world()
        del w[20][0]["witness_signatures"]["b"]
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_owner_reused_as_log_root_refused(self):
        w = self.world()
        w[18] = self.keys["owner"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_sensor_reused_as_log_witness_refused(self):
        w = self.world()
        w[17]["witnesses"]["a"] = self.keys["primary-sensor"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_same_p256_for_two_log_witness_roles_refused(self):
        w = self.world()
        w[17]["witnesses"]["a"] = w[17]["witnesses"]["b"]
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_wrong_log_root_signature_refused(self):
        w = self.world()
        w[17]["signature"] = "false"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_policy_source_cut_swapped_refused(self):
        w = self.world()
        w[17]["008_assessment_cut"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_policy_stale_epoch_refused(self):
        w = self.world()
        w[17]["epoch"] += 1
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_changed_submission_signature_fails(self):
        w = self.world()
        w[19][2]["submission"]["claimed_prior_to_in_this_log"] = None
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_fake_signed_artifact_digest_fails(self):
        w = self.world()
        w[19][2]["submission"]["artifact_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_changed_history_head_fails(self):
        w = self.world()
        w[19][3]["prev_head"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_missing_slot_does_not_shift_without_detection(self):
        w = self.world()
        del w[19][2]
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_swap_of_two_log_entries_is_refused(self):
        w = self.world()
        w[19][2], w[19][3] = w[19][3], w[19][2]
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_duplicate_event_fails_even_if_hash_chain_recomputed(self):
        w = self.world()
        submissions = [item["submission"] for item in w[19]]
        submissions[3] = submissions[2]
        w[19] = append_entries(submissions)
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_foreign_signature_does_not_authorize_source_event(self):
        w = self.world()
        actor = signed_artifacts(w[:17])
        with self.assertRaises(InvalidWorld):
            make_submission(actor, "audit-commit-primary", self.keys["owner"])

    def test_forged_new_event_rejected(self):
        w = self.world()
        w[19][1]["submission"]["event_id"] = "NOT_A_REAL_EVENT"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_witness_signed_checkpoint_requires_pinned_sequencer(self):
        w = self.world()
        with self.assertRaises(InvalidWorld):
            make_checkpoint(w[17], 6, w[19][-1]["head"],
                            self.keys["owner"],
                            self.keys["log-witness-a"], self.keys["log-witness-b"])

    def test_witness_signed_checkpoint_requires_both_pinned_witnesses(self):
        w = self.world()
        with self.assertRaises(InvalidWorld):
            make_checkpoint(w[17], 6, w[19][-1]["head"],
                            self.keys["log-sequencer"],
                            self.keys["owner"], self.keys["log-witness-b"])

    def test_colluding_log_signers_can_sign_two_histories_but_cannot_hide_both_seen(self):
        tmp, w, _ = build_fixture_for_tests(fork=True)
        try:
            r = self.check(w)
            self.assertTrue(r["forked_checkpoint_sizes"])
            self.assertFalse(r["external_witness_keys_are_independent_humans"])
        finally:
            tmp.cleanup()

    def test_source_claimed_capture_clock_not_falsified_by_later_log_append(self):
        r = self.check(self.world())
        self.assertEqual(len(r["contradicted_publication_claims"]), 2)
        self.assertFalse(r["sample_captured_at_claim_verified"])
        self.assertFalse(r["log_order_is_wall_clock_time"])

    def test_signed_complete_log_can_be_consistently_lied_about(self):
        tmp, w, _ = build_fixture_for_tests(earlier_audit_matches=True,
                                             log_order_lie=False)
        try:
            r = self.check(w)
            self.assertEqual(r["decision"], "REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED")
            self.assertFalse(r["physical_truth_proven"])
        finally:
            tmp.cleanup()

    def test_cold_replay_rejects_digest_recomputed_forgery(self):
        w = self.world()
        r = self.check(w)
        r["sample_captured_at_claim_verified"] = True
        r["receipt_digest"] = digest({k: v for k, v in r.items() if k != "receipt_digest"})
        self.assertFalse(verify_replay(*w, r, now=1001))

    def test_cold_replay_accepts_genuine_unsigned_review_receipt(self):
        w = self.world()
        r = self.check(w)
        self.assertTrue(verify_replay(*w, r, now=1001))
        self.assertEqual(r, self.check(w))
        self.assertEqual(r["effects"], [])

    def test_cold_process_has_no_private_keys(self):
        w = self.world()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            names = ("parent", "roster", "challenge", "statements",
                     "primary_anchor", "primary_precommit", "primary_measurement", "pinset",
                     "primary_custody", "secondary_custody", "secondary_measurement",
                     "manifest", "attestations", "audit_policy", "audit_commits",
                     "audit_reports", "trusted_root", "log_policy", "log_root",
                     "log_entries", "checkpoints")
            flags = []
            for name, value in zip(names, w):
                path = folder / (name + ".json")
                path.write_text(json.dumps(value), encoding="utf-8")
                flags.extend(("--" + name.replace("_", "-"), str(path)))
            flags.extend(("--now", "1001"))
            command = [sys.executable, str(ROOT / "ghot" / "unheard_choir_timestamp.py")]
            first = subprocess.run(command + ["assess"] + flags, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            result = json.loads(first.stdout)
            self.assertEqual(result["decision"], "HOLD_SIGNED_PUBLICATION_ORDER_CLAIM_CONTRADICTED")
            receipt = folder / "receipt.json"
            receipt.write_text(first.stdout, encoding="utf-8")
            replay = subprocess.run(command + ["verify"] + flags + [
                "--receipt", str(receipt)], capture_output=True, text=True)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(json.loads(replay.stdout), {"verified": True})

    def test_demo_timestamp_lied(self):
        report = demo()
        self.assertEqual(report["009_decision"], "HOLD_SIGNED_PUBLICATION_ORDER_CLAIM_CONTRADICTED")
        self.assertEqual(report["disputed_publication_claims"], 2)
        self.assertTrue(report["cold_replay_verified"])
        self.assertFalse(report["physically_proven_capture_time"])
        self.assertFalse(report["external_execution"])


if __name__ == "__main__":
    unittest.main()
