#!/usr/bin/env python3
"""Hostile tests for WORLD-ASKS-BACK-001. Requires OpenSSL, no network."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ghot import world_asks_back as wab
from ghot.relatte_identity import IdentityKey


class WorldAsksBackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.packet = wab.demo(self.root)

    def changed(self):
        return copy.deepcopy(self.packet)

    def test_three_distinct_signers_eleven_instruments_and_options(self):
        o = wab.observe(self.packet["claims"], self.packet["pinned"])
        self.assertEqual(len(o["instruments"]), 11)
        self.assertEqual(len(self.packet["proposal"]["options"]), 11)
        self.assertEqual(len(set(x["instrument"] for x in o["instruments"])), 11)
        self.assertEqual(len(set(wab.digest(x) for x in self.packet["pinned"].values())), 3)

    def test_unassigned_task_is_inferred_not_received(self):
        p = self.packet["proposal"]
        self.assertFalse(p["task_request_present"])
        self.assertEqual(p["origin"], "inferred-from-condition-not-assigned-task")
        self.assertEqual([o["mode"] for o in p["options"] if o["eligible"]], ["print"])
        self.assertTrue(wab.verify(self.packet))

    def test_simulated_output_is_not_a_physical_part_or_economic_credit(self):
        a = self.packet["artifact"]
        self.assertTrue(a["simulated"])
        self.assertFalse(a["physical_part_produced"])
        self.assertFalse(a["physical_repair_completed"])
        self.assertEqual(a["economic_credit"], 0)
        self.assertEqual(a["virtual_remaining_stock_g"], 18)
        self.assertEqual(self.packet["status"], "SIMULATED_PART_CREATED")

    def test_missing_grants_produce_signed_hold(self):
        self.assertEqual(wab.demo(self.root, approve=False)["status"], "HOLD_AWAITING_GRANTS")
        hold = wab.demo(self.root, approve=False)
        self.assertIsNone(hold["artifact"])
        self.assertEqual(hold["disposition"]["kind"], "HELD")
        self.assertTrue(wab.verify(hold))

    def test_partial_grant_is_not_authority(self):
        keys = {r: IdentityKey(self.root / (r + ".pem")) for r in wab.ROLES}
        p = wab.compose(self.packet["claims"], self.packet["pinned"])
        grants = {r: wab.grant(r, p, keys[r]) for r in ("household", "fabricator")}
        hold = wab.assemble(self.packet["claims"], self.packet["pinned"], keys, grants)
        self.assertEqual(hold["status"], "HOLD_AWAITING_GRANTS")
        self.assertTrue(wab.verify(hold))

    def test_stock_shortage_is_hold_not_fabrication(self):
        p = wab.demo(self.root, stock=11)
        self.assertEqual(p["status"], "HOLD_NO_FEASIBLE_WORK")
        self.assertIsNone(p["proposal"]["selected"])
        self.assertTrue(wab.verify(p))

    def test_fabricated_success_without_grants_denied(self):
        hold = wab.demo(self.root, approve=False)
        hold["status"] = "SIMULATED_PART_CREATED"
        with self.assertRaises(ValueError):
            wab.verify(hold)

    def test_rewritten_artifact_denied(self):
        packet = self.changed()
        packet["artifact"]["physical_part_produced"] = True
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_grant_scope_expansion_denied(self):
        packet = self.changed()
        packet["grants"]["stockist"]["scope"] = "unlimited-material-use"
        # Invalid approval cannot authorize an EXECUTED receipt.
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_other_owners_key_cannot_sign_this_role(self):
        packet = self.changed()
        packet["grants"]["stockist"] = copy.deepcopy(packet["grants"]["household"])
        packet["grants"]["stockist"]["role"] = "stockist"
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_stale_claim_cut_denied(self):
        packet = self.changed()
        packet["claims"]["stockist"]["epoch"] += 1
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_false_observation_denied_even_if_it_seems_useful(self):
        packet = self.changed()
        packet["claims"]["fabricator"]["state"]["printer"] = "idle-unlimited"
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_wrong_proposal_denied(self):
        packet = self.changed()
        packet["proposal"]["mass_g"] = 1
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_receiver_identity_is_not_inherited_from_crossing(self):
        packet = self.changed()
        packet["received"]["receiver_particular"] = packet["crossing"]["source_particular"]
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_crossing_cannot_expand_intent(self):
        packet = self.changed()
        packet["crossing"]["requested_effect"] = {"action": "real-print"}
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_result_receipt_cannot_be_transmuted_into_real_execution(self):
        packet = self.changed()
        packet["disposition"]["extensions"]["world_asks_back"]["physical_execution"] = True
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_stale_approval_is_not_transferable(self):
        packet = self.changed()
        packet["grants"]["fabricator"]["proposal_id"] = "wab-proposal:other"
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_privacy_withdrawal_blocks_new_composition(self):
        keys = {r: IdentityKey(self.root / (r + ".pem")) for r in wab.ROLES}
        claims = copy.deepcopy(self.packet["claims"])
        state = copy.deepcopy(claims["household"]["state"])
        state["privacy"] = "not-shared"
        claims["household"] = wab.signed_claim("household", state, keys["household"])
        proposal = wab.compose(claims, self.packet["pinned"])
        self.assertEqual(proposal["status"], "HOLD")
        self.assertIsNone(proposal["selected"])
        # Old grants and candidate cannot be replayed against the new cut.
        packet = self.changed()
        packet["claims"] = claims
        with self.assertRaises(ValueError):
            wab.verify(packet)

    def test_cold_verifier_without_private_keys(self):
        path = self.root / "public-packet.json"
        path.write_text(json.dumps(self.packet), encoding="utf-8")
        for role in wab.ROLES:
            (self.root / (role + ".pem")).unlink()
        outcome = subprocess.run(
            [sys.executable, "-m", "ghot.world_asks_back", "verify", str(path)],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(outcome.stdout),
                         {"verified": True, "status": "SIMULATED_PART_CREATED"})


if __name__ == "__main__":
    unittest.main()
