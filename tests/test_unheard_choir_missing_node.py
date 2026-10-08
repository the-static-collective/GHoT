#!/usr/bin/env python3
"""008 hostile matrix — externally pinned auditor vs owner-signed omissions."""
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
from unheard_choir_missing_node import (  # noqa: E402
    assess, build_fixture, check_commit, check_report, demo, make_commit,
    make_policy, make_report, verify_policy, verify_replay,
)

class MissingNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.origin, cls.keys = build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def data(self):
        return copy.deepcopy(self.origin)

    def check(self, data):
        return assess(*data, now=1001)

    def test_owner_signed_disjoint_graph_can_hide_common_node(self):
        o = self.check(self.data())
        self.assertEqual(o["007_decision"], "REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED")
        self.assertEqual(o["decision"], "HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH")
        self.assertEqual(o["shared_nodes_claimed_by_auditors"], ["fixture-hidden"])
        self.assertGreaterEqual(len(o["signed_graph_conflicts"]), 2)
        self.assertFalse(o["audit_claims_physically_verified"])
        self.assertFalse(o["undeclared_common_causes_excluded"])

    def test_three_layers_provenance_are_not_truth(self):
        r = self.check(self.data())
        self.assertTrue(r["external_root_pinned_in_local_fixture"])
        self.assertFalse(r["commit_timestamps_independently_proven"])
        self.assertFalse(r["external_execution"])
        self.assertEqual(r["authority"], "NONE")
        self.assertEqual(r["effects"], [])

    def test_matching_independently_signed_traces_are_review_only(self):
        traces = {
            "primary": ["fixture-primary", "fixture-east", "fixture-root-a"],
            "secondary": ["fixture-secondary", "fixture-west", "fixture-root-b"],
        }
        tmp, w, _ = build_fixture(traces=traces)
        try:
            r = self.check(w)
            self.assertEqual(r["decision"], "REVIEW_AUDIT_TRACES_MATCH_DECLARED_GRAPH_NOT_ADMITTED")
            self.assertEqual(r["signed_graph_conflicts"], [])
            self.assertEqual(r["shared_nodes_claimed_by_auditors"], [])
            self.assertFalse(r["audit_claims_physically_verified"])
        finally:
            tmp.cleanup()

    def test_no_outside_auditors_holds_not_accepts_disjointness(self):
        w = self.data()
        w[13:] = [None] * 4
        r = self.check(w)
        self.assertEqual(r["decision"], "HOLD_NO_INDEPENDENTLY_PINNED_AUDIT")

    def test_partial_external_audit_artifacts_refused(self):
        w = self.data()
        w[14] = None
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_missing_primary_auditor_report_holds(self):
        w = self.data()
        w[15] = [x for x in w[15] if x["channel"] != "primary"]
        r = self.check(w)
        self.assertEqual(r["decision"], "HOLD_MISSING_INDEPENDENT_AUDIT_CHANNEL")
        self.assertEqual(r["missing_audit_channels"], ["primary"])

    def test_missing_secondary_commit_holds(self):
        w = self.data()
        w[14] = [x for x in w[14] if x["channel"] != "secondary"]
        r = self.check(w)
        self.assertEqual(r["decision"], "HOLD_MISSING_INDEPENDENT_AUDIT_CHANNEL")
        self.assertEqual(r["missing_audit_channels"], ["secondary"])

    def test_duplicate_primary_report_refused(self):
        w = self.data()
        w[15][1] = copy.deepcopy(w[15][0])
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_duplicate_commit_refused(self):
        w = self.data()
        w[14].append(copy.deepcopy(w[14][0]))
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_external_audit_signature_mutation_refused(self):
        w = self.data()
        w[15][0]["signature"] = "notavalidsignature"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_external_root_not_self_authorizing(self):
        w = self.data()
        w[16] = self.keys["owner"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_owner_cannot_sign_external_policy(self):
        w = self.data()
        rogue = make_policy(w[0], w[2], w[7], self.keys["owner"], {
            "primary": self.keys["external-primary"],
            "secondary": self.keys["external-secondary"],
        })
        w[13] = rogue
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_graph_controller_cannot_be_auditor(self):
        w = self.data()
        w[13]["auditors"]["primary"] = self.keys["fixture-east"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_auditor_source_cannot_equal_custodian(self):
        w = self.data()
        w[13]["auditors"]["secondary"] = self.keys["primary-custodian"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_both_auditors_same_key_refused(self):
        w = self.data()
        w[13]["auditors"]["secondary"] = w[13]["auditors"]["primary"]
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_wrong_trust_root_signature_refused_even_valid_p256(self):
        w = self.data()
        w[16] = self.keys["external-primary"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_audit_policy_changed_epoch_requires_new_signature(self):
        w = self.data()
        w[13]["epoch"] += 1
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_policy_wrong_challenge_digest_refused(self):
        w = self.data()
        w[13]["challenge_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_commit_signed_for_wrong_channel_denied(self):
        w = self.data()
        w[14][0]["channel"] = "secondary"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_commit_digest_mutation_denied(self):
        w = self.data()
        w[14][0]["trace_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_commit_time_claim_cannot_be_after_challenge(self):
        w = self.data()
        w[14][0]["claimed_collected_at"] = 1000
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_temporal_claim_does_not_make_timestamps_independently_true(self):
        r = self.check(self.data())
        self.assertFalse(r["commit_timestamps_independently_proven"])

    def test_reveal_other_manifest_is_denied(self):
        w = self.data()
        w[15][0]["manifest_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_reveal_not_committed_is_denied(self):
        w = self.data()
        w[15][0]["trace"][2] = "fixture-fake"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_foreign_source_cut_parent_challenge_refused(self):
        w = self.data()
        w[0]["world_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_report_cannot_smuggle_native_execution(self):
        w = self.data()
        w[15][0]["native_execution"] = True
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_auditor_path_must_begin_with_declared_sensor_root(self):
        w = self.data()
        trace = ["fixture-missing", "fixture-hidden"]
        w[14][0] = make_commit(w[13], w[2], "primary", trace,
                                self.keys["external-primary"])
        w[15][0] = make_report(w[13], w[2], w[11], "primary", trace,
                                w[14][0], self.keys["external-primary"])
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_auditor_reported_path_cycle_refused(self):
        w = self.data()
        trace = ["fixture-primary", "fixture-east", "fixture-primary"]
        with self.assertRaises(InvalidWorld):
            make_commit(w[13], w[2], "primary", trace,
                        self.keys["external-primary"])

    def test_unknown_external_node_becomes_conflict_not_verified_world_fact(self):
        w = self.data()
        r = self.check(w)
        conflicts = {x["difference"] for x in r["signed_graph_conflicts"]}
        self.assertIn("UNDECLARED_EDGE", conflicts)
        self.assertIn("UNLISTED_NODE", conflicts)
        self.assertFalse(r["audit_claims_physically_verified"])

    def test_inherited_007_hold_cannot_be_cleared_by_consistent_audit(self):
        # Graph already contains signed common cause; 007 HOLD controls 008.
        shared = {
            "fixture-primary": ["fixture-east"],
            "fixture-east": ["fixture-common"],
            "fixture-common": [],
            "fixture-secondary": ["fixture-west"],
            "fixture-west": ["fixture-common"],
        }
        traces = {
            "primary": ["fixture-primary", "fixture-east", "fixture-common"],
            "secondary": ["fixture-secondary", "fixture-west", "fixture-common"],
        }
        tmp, w, _ = build_fixture(graph=shared, traces=traces)
        try:
            r = self.check(w)
            self.assertEqual(r["007_decision"], "HOLD_ATTESTED_HIDDEN_COMMON_CAUSE")
            self.assertEqual(r["decision"], "HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH")
        finally:
            tmp.cleanup()

    def test_different_manifest_with_old_reveal_fails(self):
        w = self.data()
        w[11]["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            self.check(w)

    def test_self_consistent_attacker_controlled_audit_root_still_not_world_proof(self):
        traces = {
            "primary": ["fixture-primary", "fixture-east", "fixture-root-a"],
            "secondary": ["fixture-secondary", "fixture-west", "fixture-root-b"],
        }
        tmp, w, _ = build_fixture(traces=traces)
        try:
            r = self.check(w)
            self.assertFalse(r["audit_claims_physically_verified"])
            self.assertFalse(r["undeclared_common_causes_excluded"])
            self.assertEqual(r["decision"], "REVIEW_AUDIT_TRACES_MATCH_DECLARED_GRAPH_NOT_ADMITTED")
        finally:
            tmp.cleanup()

    def test_one_rehashed_forged_receipt_cannot_cold_replay(self):
        w = self.data()
        r = self.check(w)
        r["audit_claims_physically_verified"] = True
        r["receipt_digest"] = digest({k: v for k, v in r.items() if k != "receipt_digest"})
        self.assertFalse(verify_replay(*w, r, now=1001))

    def test_cold_replay_valid_and_deterministic(self):
        w = self.data()
        r = self.check(w)
        self.assertTrue(verify_replay(*w, r, now=1001))
        self.assertEqual(r, self.check(w))

    def test_subprocess_readonly_replay_without_private_keys(self):
        w = self.data()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fields = ("parent", "roster", "challenge", "statements",
                      "primary_anchor", "primary_precommit", "primary_measurement",
                      "pinset", "primary_custody", "secondary_custody",
                      "secondary_measurement", "manifest", "attestations",
                      "audit_policy", "audit_commits", "audit_reports", "trusted_root")
            args = []
            for name, value in zip(fields, w):
                file = root / (name + ".json")
                file.write_text(json.dumps(value), encoding="utf-8")
                args += ["--" + name.replace("_", "-"), str(file)]
            args += ["--now", "1001"]
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_missing_node.py")]
            out = subprocess.run(cmd + ["assess"] + args, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["decision"],
                             "HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH")
            file = root / "receipt.json"
            file.write_text(out.stdout, encoding="utf-8")
            cold = subprocess.run(cmd + ["verify"] + args + ["--receipt", str(file)],
                                  capture_output=True, text=True)
            self.assertEqual(cold.returncode, 0, cold.stderr)
            self.assertEqual(json.loads(cold.stdout), {"verified": True})

    def test_demo_with_real_signed_external_auditor_reports(self):
        r = demo()
        self.assertEqual(r["007_decision"], "REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED")
        self.assertEqual(r["008_decision"], "HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH")
        self.assertEqual(r["auditor_claimed_hidden_node"], ["fixture-hidden"])
        self.assertTrue(r["cold_replay_verified"])
        self.assertFalse(r["physical_truth_proven"])


if __name__ == "__main__":
    unittest.main()
