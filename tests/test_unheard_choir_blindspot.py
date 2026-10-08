#!/usr/bin/env python3
"""Hostile source-cut, blind-spot, and probe tests for UNHEARD CHOIR 002."""
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
from unheard_choir import InvalidWorld  # noqa: E402
from unheard_choir_blindspot import (  # noqa: E402
    propose, simulate, validate_field, verify_simulation,
)

F = ROOT / "fixtures" / "unheard-choir-002"


def fixtures():
    return tuple(json.loads((F / fn).read_text(encoding="utf-8")) for fn in
                 ("observed-world.json", "field.json", "hidden-oracle.json"))


def execute(world=None, field=None, oracle=None, proposal=None, approve=True):
    w, f, o = fixtures()
    w = w if world is None else world
    f = f if field is None else field
    o = o if oracle is None else oracle
    p = propose(w, f) if proposal is None else proposal
    return simulate(w, f, p, o,
                    approve_proposal=p["proposal_digest"] if approve else None,
                    approve_aperture=p["selected"]["aperture_id"] if approve else None)


class BlindSpotTest(unittest.TestCase):
    def test_fresh_source_only_contains_eleven(self):
        world, field, oracle = fixtures()
        self.assertEqual(len(world["signals"]), 11)
        self.assertNotIn(oracle["signal"]["signal_id"],
                         [s["signal_id"] for s in world["signals"]])
        self.assertEqual(world["injected_signal_id"], None)
        validate_field(world, field)

    def test_proposal_does_not_read_hidden_fixture(self):
        world, field, oracle = fixtures()
        baseline = propose(world, field)
        altered = copy.deepcopy(oracle)
        altered["signal"]["salience"] = 11
        self.assertEqual(baseline, propose(world, field))
        self.assertFalse(baseline["oracle_read"])
        self.assertFalse(baseline["simulated_measurement_performed"])
        self.assertNotIn("quiet-neighbor", json.dumps(baseline))
        self.assertEqual(baseline["selected"]["aperture_id"], "community-queue")

    def test_declared_gap_is_not_evidence_of_a_signal(self):
        world, field, _ = fixtures()
        plan = propose(world, field)
        self.assertEqual(plan["source_observed_count"], 11)
        self.assertEqual(plan["known_unobserved_apertures"], 3)
        self.assertEqual(len(plan["aperture_witness"]), 3)
        self.assertIn("UNKNOWN", plan["epistemic_note"])
        self.assertFalse(plan["selected"]["execution_approved"])
        self.assertEqual(plan["effects"], [])

    def test_budget_and_cost_are_independent_of_source_attention(self):
        world, field, _ = fixtures()
        p = propose(world, field)
        self.assertEqual(world["attention_units"], 4)
        self.assertEqual(p["exploration_budget"], 2)
        self.assertEqual(p["selected"]["inspection_cost"], 1)
        self.assertTrue(all(x["decision"] != "INSTRUMENT_PROPOSED"
                            for x in p["aperture_witness"] if x["aperture_id"] == "radio-far-edge"))

    def test_approval_opens_one_simulated_aperture(self):
        w, f, o = fixtures()
        p = propose(w, f)
        r = execute(w, f, o, p)
        self.assertEqual(r["simulation_outcome"], "SIMULATED_OBSERVATION")
        self.assertEqual(r["synthetic_source_disclosed"]["signal_id"], "quiet-neighbor")
        self.assertEqual(len(r["source_attention_before"]["witness"]), 11)
        self.assertEqual(len(r["source_attention_after"]["witness"]), 12)
        self.assertIn("quiet-neighbor", r["source_attention_after"]["selection_order"])
        self.assertNotIn("quiet-neighbor", r["source_attention_before"]["selection_order"])
        self.assertEqual(r["exploration_budget_remaining"], 1)
        self.assertTrue(verify_simulation(w, f, p, o, r,
            approve_proposal=p["proposal_digest"], approve_aperture="community-queue"))

    def test_completely_unsigned_and_no_real_effect(self):
        r = execute()
        self.assertEqual(r["authority"], "NONE")
        self.assertEqual(r["effects"], [])
        self.assertFalse(r["external_execution"])
        self.assertFalse(r["real_world_observed"])
        self.assertFalse(r["signed"])
        self.assertFalse(r["human_need_independently_verified"])
        self.assertTrue(r["simulated_read_only_probe_performed"])

    def test_missing_approval_refuses_before_oracle(self):
        w, f, o = fixtures()
        p = propose(w, f)
        with self.assertRaisesRegex(InvalidWorld, "approval missing"):
            simulate(w, f, p, o, approve_proposal=None,
                     approve_aperture="community-queue")
        with self.assertRaisesRegex(InvalidWorld, "aperture test approval missing"):
            simulate(w, f, p, o, approve_proposal=p["proposal_digest"],
                     approve_aperture=None)

    def test_wrong_approval_refuses(self):
        w, f, o = fixtures()
        p = propose(w, f)
        with self.assertRaises(InvalidWorld):
            simulate(w, f, p, o, approve_proposal="0" * 64,
                     approve_aperture="community-queue")
        with self.assertRaises(InvalidWorld):
            simulate(w, f, p, o, approve_proposal=p["proposal_digest"],
                     approve_aperture="radio-far-edge")

    def test_stale_or_forged_plan_refused(self):
        w, f, o = fixtures()
        p = propose(w, f)
        altered = copy.deepcopy(p)
        altered["selected"]["instrument_id"] = "fake-instrument"
        with self.assertRaises(InvalidWorld):
            execute(w, f, o, altered)

    def test_digest_recompute_does_not_launder_forged_selection(self):
        from unheard_choir import digest
        w, f, o = fixtures()
        p = propose(w, f)
        p["selected"]["aperture_id"] = "radio-far-edge"
        p["proposal_digest"] = digest({k: v for k, v in p.items() if k != "proposal_digest"})
        with self.assertRaises(InvalidWorld):
            execute(w, f, o, p)

    def test_changed_source_cut_refuses(self):
        w, f, o = fixtures()
        p = propose(w, f)
        w["signals"][0]["salience"] = 1
        with self.assertRaises(InvalidWorld):
            execute(w, f, o, p)

    def test_changed_instrument_owner_epoch_refuses(self):
        w, f, o = fixtures()
        p = propose(w, f)
        f["apertures"][1]["owner_epoch"] += 1
        with self.assertRaises(InvalidWorld):
            execute(w, f, o, p)

    def test_withdrawn_capability_refuses_stale_plan(self):
        w, f, o = fixtures()
        p = propose(w, f)
        f["apertures"][1]["available"] = False
        with self.assertRaises(InvalidWorld):
            execute(w, f, o, p)

    def test_budget_withdrawal_refuses_stale_plan(self):
        w, f, o = fixtures()
        p = propose(w, f)
        f["exploration_budget"] = 1
        with self.assertRaises(InvalidWorld):
            execute(w, f, o, p)

    def test_renegotiated_plan_can_select_different_instrument(self):
        w, f, _ = fixtures()
        f["apertures"][1]["available"] = False
        p = propose(w, f)
        self.assertEqual(p["selected"]["aperture_id"], "material-backlog")
        self.assertEqual(p["selected"]["inspection_cost"], 2)

    def test_oracle_is_bound_to_exact_instrument_and_epoch(self):
        w, f, o = fixtures()
        for key, value in (("aperture_id", "radio-far-edge"),
                           ("instrument_id", "wrong-probe"),
                           ("owner_epoch", 3), ("cut_id", "different-cut")):
            changed = copy.deepcopy(o)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(InvalidWorld):
                execute(w, f, changed)

    def test_empty_window_is_not_claim_of_world_silence(self):
        w, f, o = fixtures()
        o["measurement_kind"] = "SIMULATED_EMPTY_WINDOW"
        o["signal"] = None
        r = execute(w, f, o)
        self.assertEqual(r["simulation_outcome"], "SIMULATED_EMPTY_WINDOW")
        self.assertIsNone(r["synthetic_source_disclosed"])
        self.assertEqual(r["source_attention_before"], r["source_attention_after"])
        self.assertFalse(r["real_world_observed"])

    def test_empty_window_cannot_carry_signal(self):
        w, f, o = fixtures()
        o["measurement_kind"] = "SIMULATED_EMPTY_WINDOW"
        with self.assertRaises(InvalidWorld):
            execute(w, f, o)

    def test_declared_no_consent_withholds_source(self):
        w, f, o = fixtures()
        o["signal"]["consent_to_review"] = False
        r = execute(w, f, o)
        self.assertEqual(r["simulation_outcome"], "HELD_UNREVIEWED_DECLARED_CONSENT")
        self.assertIsNone(r["synthetic_source_disclosed"])
        self.assertEqual(r["source_attention_before"], r["source_attention_after"])

    def test_missing_signal_or_bogus_sensor_claim_refused(self):
        w, f, o = fixtures()
        for mutation in ("missing-field", "physical-claim", "wrong-source-ref",
                         "script-injection"):
            x = copy.deepcopy(o)
            if mutation == "missing-field":
                del x["signal"]["cue"]
            elif mutation == "physical-claim":
                x["signal"]["evidence_status"] = "PHYSICAL_RF_RECEIVED"
            elif mutation == "wrong-source-ref":
                x["signal"]["source_ref"] = "simulated:someone-else"
            else:
                x["signal"]["execute"] = "curl unexpected"
            with self.subTest(mutation=mutation), self.assertRaises(InvalidWorld):
                execute(w, f, x)

    def test_repeated_signal_identity_refused(self):
        w, f, o = fixtures()
        o["signal"]["signal_id"] = "repeater-east"
        o["signal"]["source_ref"] = "simulated:repeater-east"
        with self.assertRaises(InvalidWorld):
            execute(w, f, o)

    def test_field_source_digest_cannot_be_forged(self):
        w, f, _ = fixtures()
        f["source_world_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            propose(w, f)

    def test_bad_group_and_unreviewed_community_refused(self):
        w, f, _ = fixtures()
        for key, value in (("group", ["community"]),
                           ("group", "unknown"),
                           ("review_class", "ordinary"),
                           ("inspection_cost", True)):
            x = copy.deepcopy(f)
            x["apertures"][1][key] = value
            with self.subTest(key=key, value=str(value)), self.assertRaises(InvalidWorld):
                propose(w, x)

    def test_no_eligible_probes_hold_without_execution(self):
        w, f, _ = fixtures()
        for a in f["apertures"]:
            a["available"] = False
        p = propose(w, f)
        self.assertIsNone(p["selected"])
        self.assertEqual(p["hold_reason"], "HOLD_ALL_INSTRUMENTS_WITHDRAWN")
        with self.assertRaises(InvalidWorld):
            execute(w, f, proposal=p)

    def test_zero_proxy_holds(self):
        w, f, _ = fixtures()
        for a in f["apertures"]:
            a["expected_gain_proxy"] = 0
        p = propose(w, f)
        self.assertEqual(p["hold_reason"], "HOLD_NO_POSITIVE_DECLARED_GAIN")

    def test_tampered_receipt_fails_verification(self):
        w, f, o = fixtures()
        p = propose(w, f)
        r = execute(w, f, o, p)
        r["real_world_observed"] = True
        self.assertFalse(verify_simulation(w, f, p, o, r,
            approve_proposal=p["proposal_digest"], approve_aperture="community-queue"))

    def test_forged_receipt_digest_still_fails_replay(self):
        from unheard_choir import digest
        w, f, o = fixtures()
        p = propose(w, f)
        r = execute(w, f, o, p)
        r["source_attention_after"]["selection_order"] = []
        r["receipt_digest"] = digest({k: v for k, v in r.items() if k != "receipt_digest"})
        self.assertFalse(verify_simulation(w, f, p, o, r,
            approve_proposal=p["proposal_digest"], approve_aperture="community-queue"))

    def test_cold_process_plan_simulate_verify(self):
        w, f, o = fixtures()
        p = propose(w, f)
        with tempfile.TemporaryDirectory() as tmp:
            plan_file = Path(tmp) / "plan.json"
            receipt_file = Path(tmp) / "receipt.json"
            cli = str(ROOT / "ghot" / "unheard_choir_blindspot.py")
            common = ["--world", str(F / "observed-world.json"),
                      "--field", str(F / "field.json")]
            planning = subprocess.run([sys.executable, cli, "plan", *common],
                                      capture_output=True, text=True)
            self.assertEqual(planning.returncode, 0, planning.stderr)
            self.assertEqual(json.loads(planning.stdout), p)
            plan_file.write_text(planning.stdout, encoding="utf-8")
            flags = ["--plan", str(plan_file), "--oracle", str(F / "hidden-oracle.json"),
                     "--approve-proposal", p["proposal_digest"],
                     "--approve-aperture", "community-queue"]
            observed = subprocess.run([sys.executable, cli, "simulate", *common, *flags],
                                      capture_output=True, text=True)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertEqual(json.loads(observed.stdout)["simulation_outcome"], "SIMULATED_OBSERVATION")
            receipt_file.write_text(observed.stdout, encoding="utf-8")
            verified = subprocess.run(
                [sys.executable, cli, "verify", *common, *flags,
                 "--receipt", str(receipt_file)], capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout), {"verified": True})


if __name__ == "__main__":
    unittest.main()
