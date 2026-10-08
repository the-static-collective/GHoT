#!/usr/bin/env python3
"""UNHEARD CHOIR 003 hostile vendor-catalogue and measured-novelty tests."""
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
from unheard_choir_false_aperture import (  # noqa: E402
    propose, simulate, verify, validate_inputs,
)

FIX = ROOT / "fixtures" / "unheard-choir-003"
BASE = ROOT / "fixtures" / "unheard-choir-002"
INPUTS = (
    BASE / "observed-world.json",
    FIX / "field.json",
    FIX / "untrusted-catalog.json",
    FIX / "owner-registry.json",
    FIX / "reviewed-history.json",
)
FUTURE = BASE / "hidden-oracle.json"


def data():
    return [json.loads(p.read_text(encoding="utf-8")) for p in INPUTS]


def oracle():
    return json.loads(FUTURE.read_text(encoding="utf-8"))


def accepted(history, registry):
    registry["accepted_history_digest"] = digest(history)


def run_fixture(items=None, expected=None, future=None):
    items = data() if items is None else items
    plan = propose(*items) if expected is None else expected
    o = oracle() if future is None else future
    return simulate(*items, plan, o, approved_id=plan["proposal_digest"],
                    approved_aperture=plan["selected"]["aperture_id"])


class FalseApertureTest(unittest.TestCase):
    def test_select_by_proven_simulated_novelty_not_vendor_claim(self):
        w, f, c, r, h = data()
        plan = propose(w, f, c, r, h)
        self.assertEqual(plan["selected"]["aperture_id"], "community-queue")
        self.assertEqual(plan["selected"]["historical_new_source_count"], 1)
        self.assertEqual(plan["selected"]["historical_trial_count"], 1)
        self.assertFalse(plan["vendor_gain_used_for_selection"])
        self.assertFalse(plan["archive_is_independently_authenticated"])
        self.assertFalse(plan["actual_information_utility_measured"])
        self.assertFalse(plan["future_oracle_read"])
        self.assertEqual(plan["effects"], [])

    def test_adversarial_rejections_are_audited(self):
        p = propose(*data())
        by_id = {c["claim_id"]: c for c in p["claim_witness"]}
        self.assertEqual(by_id["vendor-phantom-emergency"]["decision"], "UNDECLARED_APERTURE")
        self.assertEqual(by_id["vendor-private-cabinet"]["decision"], "OWNER_DID_NOT_ALLOW_PROPOSAL")
        self.assertEqual(by_id["vendor-radio-edge"]["decision"], "UNAFFORDABLE_INSTRUMENT")
        self.assertEqual(by_id["vendor-material-backlog"]["decision"], "NO_MEASURED_SIMULATED_NOVELTY")
        self.assertEqual(by_id["vendor-community-queue"]["decision"], "CANDIDATE_BY_ACCEPTED_SIMULATED_NOVELTY")

    def test_promises_can_be_arbitrarily_reordered_without_winning(self):
        items = data()
        claims = items[2]["claims"]
        claims[0]["advertised_gain"] = 1
        claims[2]["advertised_gain"] = 1000000
        claims[-2]["advertised_gain"] = 1000000
        claims.reverse()
        result = propose(*items)
        self.assertEqual(result["selected"]["aperture_id"], "community-queue")

    def test_empty_history_yields_hold_even_with_enormous_vendor_promise(self):
        items = data()
        items[4]["trials"] = []
        accepted(items[4], items[3])
        plan = propose(*items)
        self.assertIsNone(plan["selected"])
        self.assertEqual(plan["hold_reason"], "HOLD_NO_EVIDENCED_PERMITTED_INSTRUMENT")

    def test_owner_refusal_blocks_proposal_not_just_execution(self):
        items = data()
        entry = next(e for e in items[3]["entries"] if e["aperture_id"] == "community-queue")
        entry["owner_allows_proposal"] = False
        self.assertIsNone(propose(*items)["selected"])

    def test_owner_register_cannot_claim_external_permission(self):
        items = data()
        items[3]["scope"] = "GLOBAL_OPERATOR_GRANTED"
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_stale_source_rejected_against_register(self):
        items = data()
        items[0]["signals"][0]["salience"] = 0
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_unreviewed_history_mutation_does_not_promote(self):
        items = data()
        items[4]["trials"][0]["oracle"]["signal"]["salience"] = 11
        with self.assertRaisesRegex(InvalidWorld, "historical fixture changed"):
            propose(*items)

    def test_owner_accepted_but_stale_epoch_history_refuses(self):
        items = data()
        items[4]["trials"][0]["oracle"]["owner_epoch"] = 3
        accepted(items[4], items[3])
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_owner_accepted_but_corrupt_history_refuses(self):
        items = data()
        items[4]["trials"][0]["oracle"]["signal"]["evidence_status"] = "PHYSICAL_SIGNAL_PROVEN"
        accepted(items[4], items[3])
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_owner_registry_instrument_epoch_matches_current_field(self):
        items = data()
        items[3]["entries"][1]["owner_epoch"] += 1
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_withdrawn_instrument_does_not_execute_old_plan(self):
        items = data()
        plan = propose(*items)
        items[1]["apertures"][1]["available"] = False
        with self.assertRaises(InvalidWorld):
            run_fixture(items, expected=plan)

    def test_current_budget_withdrawal_prevents_stale_execution(self):
        items = data()
        plan = propose(*items)
        items[1]["exploration_budget"] = 0
        with self.assertRaises(InvalidWorld):
            run_fixture(items, expected=plan)

    def test_claimed_stale_epoch_is_denied(self):
        items = data()
        items[2]["claims"][2]["claimed_owner_epoch"] = 3
        self.assertIsNone(propose(*items)["selected"])
        p = propose(*items)
        self.assertEqual(next(x["decision"] for x in p["claim_witness"]
                              if x["claim_id"] == "vendor-community-queue"), "STALE_OWNER_EPOCH")

    def test_catalog_cannot_impersonate_source_verified_status(self):
        items = data()
        items[2]["claims"][0]["claim_status"] = "INDEPENDENTLY_VERIFIED"
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_duplicate_claim_ambiguity_quarantines_target(self):
        items = data()
        dup = copy.deepcopy(items[2]["claims"][2])
        dup["claim_id"] = "duplicate-community"
        items[2]["claims"].append(dup)
        self.assertIsNone(propose(*items)["selected"])
        p = propose(*items)
        self.assertEqual(2, sum(x["decision"] == "CONFLICTING_VENDOR_CLAIMS"
                                for x in p["claim_witness"]))

    def test_duplicate_claim_identity_fails(self):
        items = data()
        items[2]["claims"][0]["claim_id"] = items[2]["claims"][1]["claim_id"]
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_wrong_instrument_id_does_not_inherit_good_history(self):
        items = data()
        items[2]["claims"][2]["instrument_id"] = "different-inbox"
        self.assertIsNone(propose(*items)["selected"])

    def test_unsupported_history_trial_aperture_is_rejected(self):
        items = data()
        items[4]["trials"][0]["aperture_id"] = "phantom-emergency"
        accepted(items[4], items[3])
        with self.assertRaises(InvalidWorld):
            propose(*items)

    def test_empty_simulated_history_does_not_count_as_information_gain(self):
        p = propose(*data())
        m = next(x for x in p["claim_witness"] if x["claim_id"] == "vendor-material-backlog")
        self.assertEqual(m["historical_new_source_count"], 0)
        self.assertEqual(m["historical_trial_count"], 1)

    def test_fresh_approved_simulated_inspection_counts_new_source(self):
        items = data()
        plan = propose(*items)
        out = run_fixture(items, expected=plan)
        self.assertEqual(out["selected_aperture"], "community-queue")
        self.assertEqual(out["measured_novel_simulated_source_count"], 1)
        self.assertEqual(out["measured_novel_simulated_source_ids"], ["quiet-neighbor"])
        self.assertEqual(out["parent_002_receipt"]["exploration_budget_remaining"], 1)
        self.assertTrue(verify(*items, plan, oracle(), out,
            approved_id=plan["proposal_digest"], approved_aperture="community-queue"))
        self.assertFalse(out["advertised_gain_trusted"])
        self.assertFalse(out["novelty_is_human_benefit"])
        self.assertFalse(out["real_world_observed"])

    def test_empty_future_window_produces_zero_novelty(self):
        o = oracle()
        o["measurement_kind"] = "SIMULATED_EMPTY_WINDOW"
        o["signal"] = None
        out = run_fixture(future=o)
        self.assertEqual(out["measured_novel_simulated_source_count"], 0)
        self.assertEqual(out["parent_002_receipt"]["simulation_outcome"], "SIMULATED_EMPTY_WINDOW")

    def test_future_declared_no_consent_keeps_need_held(self):
        o = oracle()
        o["signal"]["consent_to_review"] = False
        out = run_fixture(future=o)
        self.assertEqual(out["measured_novel_simulated_source_count"], 0)
        self.assertEqual(out["parent_002_receipt"]["simulation_outcome"],
                         "HELD_UNREVIEWED_DECLARED_CONSENT")

    def test_no_approval_fails_closed(self):
        items = data()
        p = propose(*items)
        for ident, aperture in ((None, "community-queue"), (p["proposal_digest"], None),
                                ("bad", "community-queue"),
                                (p["proposal_digest"], "private-cabinet")):
            with self.subTest(ident=ident, aperture=aperture), self.assertRaises(InvalidWorld):
                simulate(*items, p, oracle(), approved_id=ident, approved_aperture=aperture)

    def test_forged_plan_and_rehashed_plan_fail(self):
        items = data()
        p = propose(*items)
        p["selected"]["instrument_id"] = "all-seeing-eye"
        p["proposal_digest"] = digest({k: v for k, v in p.items() if k != "proposal_digest"})
        with self.assertRaises(InvalidWorld):
            run_fixture(items, expected=p)

    def test_tampered_result_fails_even_with_rehashed_digest(self):
        items = data()
        p = propose(*items)
        out = run_fixture(items, expected=p)
        out["measured_novel_simulated_source_count"] = 900
        out["receipt_digest"] = digest({k: v for k, v in out.items() if k != "receipt_digest"})
        self.assertFalse(verify(*items, p, oracle(), out,
            approved_id=p["proposal_digest"], approved_aperture="community-queue"))

    def test_signal_group_laundering_refused_by_002(self):
        o = oracle()
        o["signal"]["kind"] = "radio"
        o["signal"]["cue"] = "repetition"
        o["signal"]["consent_to_review"] = False
        with self.assertRaises(InvalidWorld):
            run_fixture(future=o)

    def test_cli_does_not_read_future_without_exact_approval(self):
        items = data()
        p = propose(*items)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(p), encoding="utf-8")
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_false_aperture.py"),
                   "simulate"]
            for name, fpath in zip(("world", "field", "claims", "registry", "history"), INPUTS):
                cmd += ["--" + name, str(fpath)]
            cmd += ["--plan", str(path), "--oracle", str(Path(tmp) / "missing-oracle.json")]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("approval missing", run.stderr)
            self.assertNotIn("No such file", run.stderr)

    def test_cold_process_replay(self):
        items = data()
        p = propose(*items)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            proposal = path / "proposal.json"
            receipt = path / "receipt.json"
            flags = []
            for name, file_path in zip(("world", "field", "claims", "registry", "history"), INPUTS):
                flags.extend(["--" + name, str(file_path)])
            tool = [sys.executable, str(ROOT / "ghot" / "unheard_choir_false_aperture.py")]
            plan = subprocess.run(tool + ["plan"] + flags, capture_output=True, text=True)
            self.assertEqual(plan.returncode, 0, plan.stderr)
            self.assertEqual(json.loads(plan.stdout), p)
            proposal.write_text(plan.stdout, encoding="utf-8")
            extra = ["--plan", str(proposal), "--oracle", str(FUTURE),
                     "--approve-proposal", p["proposal_digest"],
                     "--approve-aperture", "community-queue"]
            executed = subprocess.run(tool + ["simulate"] + flags + extra,
                                      capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            receipt.write_text(executed.stdout, encoding="utf-8")
            verified = subprocess.run(tool + ["verify"] + flags + extra +
                                      ["--receipt", str(receipt)], capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout), {"verified": True})


if __name__ == "__main__":
    unittest.main()
