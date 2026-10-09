#!/usr/bin/env python3
"""UNHEARD CHOIR 014 hostile test matrix: conflicting successors are not authority."""
from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ghot"))

from unheard_choir import InvalidWorld, digest  # noqa: E402
from unheard_choir_reincarnation import make_incarnation, make_archive_grant  # noqa: E402
from unheard_choir_successors import (  # noqa: E402
    CONTESTED, EQUIVOCATED, NO_GRANT, ARCHIVED,
    GENESIS, SCOPE, assess, build_fixture, make_policy, make_selection,
    read_receipts, record_once, verify_policy, verify_selection,
    verify_receipt, demo,
)


class TwoEqualSuccessorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.parcel, cls.old_local, cls.pins, cls.policy, cls.root, cls.grants, cls.keys = build_fixture()
        cls.north = make_selection(cls.policy, cls.keys["succession-reviewer"], "north")
        cls.south = make_selection(cls.policy, cls.keys["succession-reviewer"], "south")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.database = Path(self.scratch.name) / "neutral-local.sqlite"

    def tearDown(self):
        self.scratch.cleanup()

    def args(self):
        return [copy.deepcopy(x) for x in (
            self.parcel, self.old_local, self.pins, self.policy, self.root,
        )]

    def evaluate(self, selections=None, grants=None, args=None, *, now=1100):
        return assess(*(self.args() if args is None else args),
                      [] if selections is None else selections,
                      self.grants if grants is None else grants, now=now)

    def write(self, selections=None, grants=None, *, now=1100, signer=None):
        return record_once(self.database, *self.args(),
                           [] if selections is None else selections,
                           self.grants if grants is None else grants,
                           self.keys["neutral-recorder"] if signer is None else signer,
                           now=now)

    def test_two_valid_same_epoch_owner_claims_do_not_choose_owner(self):
        result = self.evaluate()
        self.assertEqual(result["decision"], CONTESTED)
        self.assertIsNone(result["selected_for_bounded_local_archival_review"])
        self.assertFalse(result["global_rightful_successor_proven"])
        self.assertEqual(set(result["claims"]), {"north", "south"})
        self.assertTrue(result["competing_successors_have_separate_signatures"])

    def test_two_well_signed_opposed_review_claims_halt(self):
        result = self.evaluate([self.north, self.south])
        self.assertEqual(result["decision"], EQUIVOCATED)
        self.assertEqual(len(result["signed_selection_claims"]), 2)
        self.assertIsNone(result["selected_for_bounded_local_archival_review"])

    def test_reverse_selection_order_cannot_hide_equivocation(self):
        result = self.evaluate([self.south, self.north])
        self.assertEqual(result["decision"], EQUIVOCATED)
        self.assertFalse(result["review_root_is_universal_authority"])

    def test_valid_single_north_selection_only_archival_hold(self):
        result = self.evaluate([self.north])
        self.assertEqual(result["decision"], ARCHIVED)
        self.assertEqual(result["selected_for_bounded_local_archival_review"], "north")
        self.assertFalse(result["native_relatte_receive"])
        self.assertFalse(result["native_relatte_admission"])
        self.assertFalse(result["local_review_authorizes_forwarding"])
        self.assertEqual(result["effects"], [])

    def test_valid_single_south_selection_only_archival_hold(self):
        result = self.evaluate([self.south])
        self.assertEqual(result["decision"], ARCHIVED)
        self.assertEqual(result["selected_for_bounded_local_archival_review"], "south")

    def test_selected_successor_without_own_archival_grant_holds(self):
        grants = copy.deepcopy(self.grants)
        grants["north"] = None
        result = self.evaluate([self.north], grants)
        self.assertEqual(result["decision"], NO_GRANT)
        self.assertFalse(result["signed_history_creates_current_grant"])

    def test_selected_other_successor_grant_cannot_substitute(self):
        grants = copy.deepcopy(self.grants)
        grants["north"] = grants["south"]
        with self.assertRaises(InvalidWorld):
            self.evaluate([self.north], grants)

    def test_policy_locally_pinned_distinct_from_all_prior_signers(self):
        verify_policy(self.parcel, self.pins, self.policy, self.root)
        self.assertEqual(self.policy["scope"], SCOPE)
        self.assertNotEqual(self.policy["candidates"]["north"]["owner_public_key"],
                            self.policy["candidates"]["south"]["owner_public_key"])

    def test_claimant_supplied_unpinned_review_root_does_not_work(self):
        forged_root = self.keys["gossip-west"].public_jwk()
        args = self.args()
        args[4] = forged_root
        with self.assertRaises(InvalidWorld):
            self.evaluate(args=args)

    def test_review_root_cannot_equal_owner_north_identity(self):
        args = self.args()
        args[4] = self.policy["candidates"]["north"]["owner_public_key"]
        with self.assertRaises(InvalidWorld):
            self.evaluate(args=args)

    def test_review_root_signer_cannot_be_inherited_old_owner(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.parcel, self.pins, self.policy["candidates"],
                        self.keys["gossip-east"], self.keys["succession-reviewer"],
                        self.keys["neutral-recorder"])

    def test_reviewer_cannot_equal_either_candidate(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.parcel, self.pins, self.policy["candidates"],
                        self.keys["succession-root"],
                        self.keys["east-reconstituted"],
                        self.keys["neutral-recorder"])

    def test_recorder_cannot_equal_reviewer(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.parcel, self.pins, self.policy["candidates"],
                        self.keys["succession-root"],
                        self.keys["succession-reviewer"],
                        self.keys["succession-reviewer"])

    def test_unsigned_change_of_north_identity_fails_closed(self):
        args = self.args()
        args[3]["candidates"]["north"]["owner_public_key"] = self.keys["gossip-west"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.evaluate(args=args)

    def test_unsigned_change_of_south_epoch_fails_closed(self):
        args = self.args()
        args[3]["candidates"]["south"]["incarnation"]["incarnation_epoch"] = 3
        with self.assertRaises(InvalidWorld):
            self.evaluate(args=args)

    def test_policy_extra_global_ownership_field_fails_closed(self):
        args = self.args()
        args[3]["global_rightful_owner"] = "north"
        with self.assertRaises(InvalidWorld):
            self.evaluate(args=args)

    def test_policy_foreign_historical_parcel_fails_closed(self):
        args = self.args()
        args[3]["old_parcel_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.evaluate(args=args)

    def test_policy_wrong_008_trust_pins_fails_closed(self):
        args = self.args()
        args[2]["010_external_root"] = self.keys["succession-reviewer"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.evaluate(args=args)

    def test_forged_reviewer_selection_signature_denied(self):
        s = copy.deepcopy(self.north)
        s["signature"] = "not-a-p256-signature"
        with self.assertRaises(InvalidWorld):
            self.evaluate([s])

    def test_old_receiver_signing_review_selection_denied(self):
        with self.assertRaises(InvalidWorld):
            make_selection(self.policy, self.keys["gossip-east"], "north")

    def test_new_owner_cannot_self_appoint_reviewer(self):
        with self.assertRaises(InvalidWorld):
            make_selection(self.policy, self.keys["east-reconstituted"], "north")

    def test_selection_wrong_candidate_signature_not_transferable(self):
        s = copy.deepcopy(self.north)
        s["chosen_candidate"] = "south"
        with self.assertRaises(InvalidWorld):
            self.evaluate([s])

    def test_selection_wrong_incarnation_digest_denied(self):
        s = copy.deepcopy(self.north)
        s["chosen_incarnation_digest"] = digest(self.policy["candidates"]["south"]["incarnation"])
        with self.assertRaises(InvalidWorld):
            self.evaluate([s])

    def test_selection_from_wrong_review_policy_denied(self):
        s = copy.deepcopy(self.north)
        s["policy_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.evaluate([s])

    def test_selection_expired_does_not_promote(self):
        expired = make_selection(self.policy, self.keys["succession-reviewer"],
                                 "north", claimed_at=1100, not_after=1101)
        result = self.evaluate([expired], now=1200)
        self.assertEqual(result["decision"], CONTESTED)
        self.assertEqual(result["expired_selection_candidates"], ["north"])

    def test_two_opposed_expired_signed_claims_still_record_conflict(self):
        s1 = make_selection(self.policy, self.keys["succession-reviewer"],
                            "north", claimed_at=900, not_after=1000)
        s2 = make_selection(self.policy, self.keys["succession-reviewer"],
                            "south", claimed_at=900, not_after=1000)
        result = self.evaluate([s1, s2], now=1100)
        self.assertEqual(result["decision"], EQUIVOCATED)
        self.assertEqual(result["expired_selection_candidates"], ["north", "south"])

    def test_selection_extra_effect_permission_denied(self):
        s = copy.deepcopy(self.north)
        s["effect_permission"] = "EXECUTE"
        with self.assertRaises(InvalidWorld):
            self.evaluate([s])

    def test_selection_invalid_time_bool_denied(self):
        s = copy.deepcopy(self.north)
        s["simulated_not_after"] = True
        with self.assertRaises(InvalidWorld):
            self.evaluate([s])

    def test_duplicate_selection_for_one_candidate_denied(self):
        with self.assertRaises(InvalidWorld):
            self.evaluate([self.north, copy.deepcopy(self.north)])

    def test_more_than_two_selections_denied(self):
        with self.assertRaises(InvalidWorld):
            self.evaluate([self.north, self.south, copy.deepcopy(self.north)])

    def test_selection_list_must_be_explicit_not_dictionary(self):
        with self.assertRaises(InvalidWorld):
            self.evaluate({"north": self.north})

    def test_archival_grant_forgery_even_if_unselected_denied(self):
        grants = copy.deepcopy(self.grants)
        grants["south"]["signature"] = "forgery"
        with self.assertRaises(InvalidWorld):
            self.evaluate([self.north], grants)

    def test_selected_archive_expiry_stays_hold(self):
        grants = copy.deepcopy(self.grants)
        grants["north"] = make_archive_grant(self.parcel,
            self.policy["candidates"]["north"]["incarnation"],
            self.keys["east-reconstituted"], not_after=1101)
        result = self.evaluate([self.north], grants, now=1200)
        self.assertEqual(result["decision"], NO_GRANT)

    def test_archival_grant_cannot_be_mutated_into_forwarding(self):
        grants = copy.deepcopy(self.grants)
        grants["north"]["action"] = "FORWARD"
        with self.assertRaises(InvalidWorld):
            self.evaluate([self.north], grants)

    def test_both_candidates_are_historically_verifiable_without_transfer(self):
        result = self.evaluate()
        self.assertEqual(len(result["claims"]["north"]["inherited_013_digest"]), 64)
        self.assertEqual(len(result["claims"]["south"]["inherited_013_digest"]), 64)
        self.assertFalse(result["claims"]["north"]["history_alone_is_owner_authority"])
        self.assertFalse(result["claims"]["south"]["history_alone_is_owner_authority"])

    def test_contestation_receipt_signed_by_neutral_identity(self):
        written = self.write([self.north, self.south])
        self.assertEqual(written["status"], "SIGNED_LOCAL_CONTROVERSY_RECORDED")
        self.assertEqual(written["receipt"]["local_index"], 0)
        self.assertEqual(written["receipt"]["previous_receipt_digest"], GENESIS)
        replay = verify_receipt(*self.args(), [self.north, self.south],
                                self.grants, written["receipt"])
        self.assertEqual(replay["decision"], EQUIVOCATED)

    def test_duplicate_neutral_receipt_reused_not_resigned(self):
        a = self.write([self.north, self.south])
        b = self.write([self.north, self.south])
        self.assertEqual(b["status"], "DUPLICATE_UNCHANGED")
        self.assertEqual(a["receipt"], b["receipt"])
        self.assertEqual(len(read_receipts(self.database)), 1)

    def test_changed_selection_cannot_overwrite_recorded_hold(self):
        self.write([self.north, self.south])
        with self.assertRaises(InvalidWorld):
            self.write([self.north])
        self.assertEqual(read_receipts(self.database)[0]["assessment"]["decision"], EQUIVOCATED)

    def test_neutral_signer_cannot_be_either_successor(self):
        with self.assertRaises(InvalidWorld):
            self.write([self.north, self.south],
                       signer=self.keys["east-reconstituted"])

    def test_corrupted_durable_receipt_blocks_replay(self):
        self.write([self.north, self.south])
        with sqlite3.connect(str(self.database)) as db:
            db.execute("UPDATE disputed_succession SET signed_receipt_json=?",
                       (json.dumps({"schema": "corrupt"}),))
        with self.assertRaises(InvalidWorld):
            self.write([self.north, self.south])

    def test_forged_receipt_cannot_claim_native_admission(self):
        receipt = self.write([self.north, self.south])["receipt"]
        receipt["assessment"]["native_relatte_receive"] = True
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.args(), [self.north, self.south],
                           self.grants, receipt)

    def test_forged_receipt_signature_denied(self):
        receipt = self.write([self.north, self.south])["receipt"]
        receipt["signature"] = "invalid"
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.args(), [self.north, self.south],
                           self.grants, receipt)

    def test_receipt_keyless_in_separate_python_process(self):
        written = self.write([self.north, self.south])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = {
                "parcel": self.parcel, "old-local-package": self.old_local,
                "historical-pins": self.pins, "policy": self.policy,
                "local-review-root": self.root,
                "selections": [self.north, self.south],
                "archive-grants": self.grants,
                "receipt": written["receipt"],
            }
            opts = []
            for name, value in data.items():
                path = root / (name + ".json")
                path.write_text(json.dumps(value), encoding="utf-8")
                opts += ["--" + name, str(path)]
            cli = [sys.executable, str(ROOT / "ghot" / "unheard_choir_successors.py")]
            checked = subprocess.run(cli + ["verify"] + opts,
                                     cwd=str(root), capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout),
                             {"verified": True, "decision": EQUIVOCATED})

    def test_demo_conflict_and_archive_only_selection(self):
        result = demo()
        self.assertEqual(result["unselected"], CONTESTED)
        self.assertEqual(result["two_signed_valid_but_incompatible_selections"], EQUIVOCATED)
        self.assertEqual(result["single_bounded_archival_selection"], ARCHIVED)
        self.assertTrue(result["cold_receipt_verified"])
        self.assertTrue(result["one_neutral_receipt"])
        self.assertFalse(result["global_successor_proven"])
        self.assertFalse(result["forwarding_permitted"])
        self.assertFalse(result["external_execution"])


if __name__ == "__main__":
    unittest.main()
