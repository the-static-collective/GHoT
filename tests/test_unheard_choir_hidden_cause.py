#!/usr/bin/env python3
"""007 adversarial signed-graph tests: common causes and counterfeit provenance."""
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
from relatte_identity import IdentityKey  # noqa: E402
from unheard_choir_false_aperture import propose as propose_parent  # noqa: E402
from unheard_choir_lying_witness import ROLES, make_challenge, roster_for, sign_statement  # noqa: E402
from unheard_choir_collusion import make_anchor, signed_precommit, signed_measurement  # noqa: E402
from unheard_choir_counterfeit import make_pinset, sign_custody, sign_secondary  # noqa: E402
from unheard_choir_hidden_cause import (  # noqa: E402
    assess, attest, demo, dependency_trace, distinct, signed_manifest,
    verify_manifest, verify_attestations, verify_replay,
)

# 0 parent, 1 roster, 2 challenge, 3 witness, 4 anchor, 5 precommit,
# 6 primary, 7 pinset, 8 primary custody, 9 secondary custody,
# 10 secondary, 11 graph manifest, 12 graph attestations.
COMMON = {
    "fixture-primary": ["fixture-east"],
    "fixture-east": ["fixture-common"],
    "fixture-common": [],
    "fixture-west": ["fixture-common"],
    "fixture-secondary": ["fixture-west"],
}
DISJOINT = {
    "fixture-primary": ["fixture-east"],
    "fixture-east": ["fixture-root-a"],
    "fixture-root-a": [],
    "fixture-west": ["fixture-root-b"],
    "fixture-root-b": [],
    "fixture-secondary": ["fixture-west"],
}


def parent_fixture():
    f = ROOT / "fixtures"
    names = ("unheard-choir-002/observed-world.json", "unheard-choir-003/field.json",
             "unheard-choir-003/untrusted-catalog.json",
             "unheard-choir-003/owner-registry.json", "unheard-choir-003/reviewed-history.json")
    return propose_parent(*(json.loads((f / n).read_text(encoding="utf-8")) for n in names))


class GraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.keyroot = Path(cls.tmp.name)
        names = {"owner", "source", "observer-east", "observer-west",
                 "primary-sensor", "secondary-sensor", "primary-custodian", "secondary-custodian"}
        names.update(COMMON)
        names.update(DISJOINT)
        names.add("outsider")
        cls.keys = {name: IdentityKey.load_or_create(cls.keyroot / (name + ".pem"))
                    for name in sorted(names)}
        cls.parent = parent_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setup(self, graph=None, *, claim="PRESENT", second_present=True,
              nonce="a" * 32, primary_roots=None, secondary_roots=None):
        graph = COMMON if graph is None else graph
        keys = self.keys
        parent = self.parent
        roster = roster_for(parent, keys["owner"], {r: keys[r] for r in ROLES})
        challenge = make_challenge(parent, roster, keys["owner"], issued_at=1000, nonce=nonce)
        statements = [sign_statement(challenge, r, claim, keys[r]) for r in ROLES]
        anchor = make_anchor(parent, roster, keys["primary-sensor"])
        frames = [1] * 8
        commit = signed_precommit(parent, roster, anchor, keys["primary-sensor"],
                                  samples=frames, captured_at=900)
        primary = signed_measurement(challenge, commit, frames, keys["primary-sensor"])
        pins = make_pinset(parent, roster, challenge, anchor, keys["owner"],
                           keys["primary-custodian"], keys["secondary-custodian"],
                           keys["secondary-sensor"],
                           primary_roots=primary_roots or ["fixture-primary"],
                           secondary_roots=secondary_roots or ["fixture-secondary"])
        samples = ([200, 200] + [0] * 6) if second_present else [0] * 8
        secondary = sign_secondary(pins, challenge, samples, keys["secondary-sensor"])
        custody_a = sign_custody(pins, challenge, "primary", digest(primary),
                                 keys["primary-custodian"], declared_acquired_at=1000)
        custody_b = sign_custody(pins, challenge, "secondary", digest(secondary),
                                 keys["secondary-custodian"], declared_acquired_at=1000)
        entries = [
            {"node_id": n, "epoch": 1, "controller_public_key": keys[n].public_jwk(),
             "expected_parent_count": len(graph[n])}
            for n in sorted(graph)
        ]
        manifest = signed_manifest(parent, roster, challenge, pins, entries, keys["owner"])
        witness = [attest(manifest, challenge, entry, graph[entry["node_id"]],
                          keys[entry["node_id"]]) for entry in entries]
        return [parent, roster, challenge, statements, anchor, commit, primary, pins,
                custody_a, custody_b, secondary, manifest, witness]

    def decision(self, data):
        return assess(*data, now=1001)

    def test_disjoint_006_surfaces_hide_one_common_cause(self):
        w = self.setup()
        r = self.decision(w)
        self.assertEqual(r["006_decision"], "REVIEW_DECLARED_DISTINCT_MODALITIES_CONCORDANT_NOT_ADMITTED")
        self.assertEqual(r["decision"], "HOLD_ATTESTED_HIDDEN_COMMON_CAUSE")
        self.assertEqual(r["common_upstream_nodes"], ["fixture-common"])
        self.assertEqual(r["traced_upstream"]["primary"],
                         ["fixture-common", "fixture-east", "fixture-primary"])
        self.assertEqual(r["traced_upstream"]["secondary"],
                         ["fixture-common", "fixture-secondary", "fixture-west"])

    def test_p256_signatures_on_all_five_graph_nodes(self):
        r = self.decision(self.setup())
        self.assertEqual(r["signed_node_count"], 5)
        self.assertEqual(r["missing_signed_nodes"], [])
        self.assertFalse(r["physical_independence_proven"])
        self.assertFalse(r["hidden_unreported_common_cause_excluded"])

    def test_signed_disjoint_claims_only_review_not_truth(self):
        r = self.decision(self.setup(DISJOINT))
        self.assertEqual(r["decision"], "REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED")
        self.assertEqual(r["common_upstream_nodes"], [])
        self.assertFalse(r["declared_graph_exhausts_real_world"])
        self.assertFalse(r["signed_claim_is_truth"])

    def test_fully_signed_omission_cannot_be_detected_without_external_evidence(self):
        # A maliciously coordinated set of all 6 valid graph signers can
        # simply omit the actual common upstream from two fabricated roots.
        r = self.decision(self.setup(DISJOINT))
        self.assertTrue(len(r["traced_upstream"]["primary"]) > 0)
        self.assertFalse(r["hidden_unreported_common_cause_excluded"])
        self.assertEqual(r["decision"], "REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED")

    def test_missing_graph_holds_not_world_silence(self):
        w = self.setup()
        w[11] = w[12] = None
        r = self.decision(w)
        self.assertEqual(r["decision"], "HOLD_MISSING_SIGNED_GRAPH")
        self.assertFalse(r["declared_graph_exhausts_real_world"])

    def test_partial_graph_inputs_refused(self):
        w = self.setup()
        w[12] = None
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_missing_node_attestation_holds_even_if_apparently_leaf(self):
        w = self.setup()
        w[12] = w[12][:-1]
        r = self.decision(w)
        self.assertEqual(r["decision"], "HOLD_INCOMPLETE_SIGNED_PROVENANCE")
        self.assertEqual(len(r["missing_signed_nodes"]), 1)
        self.assertEqual(r["common_upstream_nodes"], [])

    def test_missing_shared_root_attestation_holds(self):
        w = self.setup()
        w[12] = [a for a in w[12] if a["node_id"] != "fixture-common"]
        r = self.decision(w)
        self.assertEqual(r["decision"], "HOLD_INCOMPLETE_SIGNED_PROVENANCE")

    def test_invalid_owner_graph_signature_refused(self):
        w = self.setup()
        w[11]["signature"] = "invalid"
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_changed_owner_graph_epoch_invalidates_signature(self):
        w = self.setup()
        w[11]["entries"][0]["epoch"] += 1
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_missing_manifest_entrypoint_refused(self):
        w = self.setup()
        w[11]["entries"] = [e for e in w[11]["entries"] if e["node_id"] != "fixture-primary"]
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_graph_controller_reuses_claimant_key_refused(self):
        w = self.setup()
        w[11]["entries"][0]["controller_public_key"] = self.keys["source"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_graph_controller_reuses_another_node_key_refused(self):
        w = self.setup()
        w[11]["entries"][1]["controller_public_key"] = w[11]["entries"][0]["controller_public_key"]
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_node_wrong_signer_rejected_before_signature(self):
        w = self.setup()
        entry = w[11]["entries"][0]
        with self.assertRaises(InvalidWorld):
            attest(w[11], w[2], entry, COMMON[entry["node_id"]], self.keys["outsider"])

    def test_node_signature_tamper_refused(self):
        w = self.setup()
        w[12][0]["signature"] = "bogus"
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_forged_extra_edge_refused(self):
        w = self.setup()
        w[12][0]["parents"].append("fixture-common")
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_duplicate_node_attestation_refused(self):
        w = self.setup()
        w[12][1] = copy.deepcopy(w[12][0])
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_attestation_to_unknown_node_refused(self):
        w = self.setup()
        x = w[12][0]
        if not x["parents"]:
            x = next(a for a in w[12] if a["parents"])
        x["parents"] = ["fixture-unlisted"]
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_cross_challenge_replay_refused(self):
        w = self.setup(nonce="a" * 32)
        later = self.setup(nonce="b" * 32)
        w[12] = later[12]
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_changed_source_custody_pinset_refuses(self):
        w = self.setup()
        w[7]["channels"]["primary"]["dependency_roots"] = ["fixture-fake"]
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_inherited_006_sensor_conflict_preserved(self):
        w = self.setup(second_present=False)
        r = self.decision(w)
        self.assertEqual(r["006_decision"], "HOLD_COUNTERFEIT_OR_CALIBRATION_CONFLICT_UNRESOLVED")
        self.assertEqual(r["decision"], "HOLD_ATTESTED_HIDDEN_COMMON_CAUSE")

    def test_disjoint_graph_does_not_override_006_hold(self):
        w = self.setup(DISJOINT, second_present=False)
        r = self.decision(w)
        self.assertEqual(r["decision"], "HOLD_006_PARENT_UNRESOLVED")

    def test_signed_cycle_is_refused_even_with_valid_signatures(self):
        graph = {"fixture-primary": ["fixture-east"], "fixture-east": ["fixture-primary"],
                 "fixture-secondary": []}
        w = self.setup(graph)
        with self.assertRaisesRegex(InvalidWorld, "cycle"):
            self.decision(w)

    def test_duplicated_node_identity_in_roster_refused(self):
        w = self.setup()
        w[11]["entries"].append(copy.deepcopy(w[11]["entries"][0]))
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_boolean_epoch_cannot_be_signer_incarnation(self):
        w = self.setup()
        w[11]["entries"][0]["epoch"] = True
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_false_physical_claim_in_signed_attestation_refused(self):
        w = self.setup()
        w[12][0]["physically_verified"] = True
        with self.assertRaises(InvalidWorld):
            self.decision(w)

    def test_nonexistent_dependency_node_signature_never_inferred(self):
        w = self.setup()
        w[12] = []
        r = self.decision(w)
        self.assertEqual(r["signed_node_count"], 0)
        self.assertEqual(r["decision"], "HOLD_INCOMPLETE_SIGNED_PROVENANCE")

    def test_receipt_rehashed_forgery_refused(self):
        w = self.setup()
        r = self.decision(w)
        r["physical_independence_proven"] = True
        r["receipt_digest"] = digest({k: v for k, v in r.items() if k != "receipt_digest"})
        self.assertFalse(verify_replay(*w, r, now=1001))

    def test_exact_signed_graph_cold_replay_passes(self):
        w = self.setup()
        r = self.decision(w)
        self.assertTrue(verify_replay(*w, r, now=1001))
        self.assertEqual(r, self.decision(w))
        self.assertEqual(r["effects"], [])
        self.assertEqual(r["authority"], "NONE")

    def test_cold_process_without_private_keys(self):
        w = self.setup()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fields = ("parent", "roster", "challenge", "statements", "primary_anchor",
                      "primary_precommit", "primary_measurement", "pinset",
                      "primary_custody", "secondary_custody", "secondary_measurement",
                      "manifest", "attestations")
            args = []
            for name, value in zip(fields, w):
                file = folder / (name + ".json")
                file.write_text(json.dumps(value), encoding="utf-8")
                args += ["--" + name.replace("_", "-"), str(file)]
            args += ["--now", "1001"]
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_hidden_cause.py")]
            run = subprocess.run(cmd + ["assess"] + args, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["decision"], "HOLD_ATTESTED_HIDDEN_COMMON_CAUSE")
            file = folder / "report.json"
            file.write_text(run.stdout, encoding="utf-8")
            verify = subprocess.run(cmd + ["verify"] + args + ["--receipt", str(file)],
                                    capture_output=True, text=True)
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertEqual(json.loads(verify.stdout), {"verified": True})

    def test_demo_trace(self):
        d = demo()
        self.assertEqual(d["006_decision"],
                         "REVIEW_DECLARED_DISTINCT_MODALITIES_CONCORDANT_NOT_ADMITTED")
        self.assertEqual(d["007_decision"], "HOLD_ATTESTED_HIDDEN_COMMON_CAUSE")
        self.assertEqual(d["common_upstream_nodes"], ["fixture-common"])
        self.assertTrue(d["cold_replay_verified"])
        self.assertFalse(d["physical_truth_proven"])
        self.assertFalse(d["external_execution"])


if __name__ == "__main__":
    unittest.main()
