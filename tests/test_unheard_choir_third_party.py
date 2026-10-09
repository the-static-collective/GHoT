#!/usr/bin/env python3
"""015 hostile matrix: old delegation, claimant signature and double current consent."""
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
from unheard_choir_successors import make_selection  # noqa: E402
from unheard_choir_third_party import (  # noqa: E402
    ACTION, BOUNDED, CONTEST, UNPRESENTED, SOURCE_MISSING,
    OWNER_MISSING, GENESIS, build_fixture, assess, demo,
    make_legacy, verify_legacy, make_policy, verify_policy,
    make_presentation, make_source, make_owner_consent,
    make_receipt, verify_receipt, record_once, read_receipts,
)


class RightfulThirdPartyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.evidence, cls.keys = build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Path(self.dir.name) / "015-neutral.sqlite"

    def tearDown(self):
        self.dir.cleanup()

    def parts(self):
        return copy.deepcopy(self.evidence)

    def review(self, changed=None, *, now=1100):
        return assess(*(self.parts() if changed is None else changed), now=now)

    def record(self, changed=None, *, now=1100, recorder=None):
        return record_once(
            self.db,
            *(self.parts() if changed is None else changed),
            recorder=self.keys["015-neutral-recorder"] if recorder is None else recorder,
            now=now,
        )

    def test_old_signatures_do_not_prove_current_authority(self):
        e = self.parts()
        self.assertTrue(verify_legacy(e[0], e[2], e[7]))
        r = self.review()
        self.assertEqual(r["old_delegation_simulated_not_after"], 1050)
        self.assertEqual(r["simulated_receiver_clock"], 1100)
        self.assertFalse(r["historical_signer_authorizes_current_effects"])
        self.assertTrue(r["old_delegation_remains_historical"])

    def test_old_delegation_with_no_014_selection_cannot_act(self):
        e = self.parts()
        e[5] = []
        r = self.review(e)
        self.assertEqual(r["decision"], CONTEST)
        self.assertFalse(r["global_rightful_owner_proven"])

    def test_two_014_selected_successors_still_hold_with_all_other_approvals(self):
        e = self.parts()
        e[5] = [
            make_selection(e[3], self.keys["succession-reviewer"], "north"),
            make_selection(e[3], self.keys["succession-reviewer"], "south"),
        ]
        r = self.review(e)
        self.assertEqual(r["decision"], CONTEST)
        self.assertEqual(r["014_decision"], "HOLD_CONTRADICTORY_SIGNED_SUCCESSION_SELECTIONS")

    def test_third_party_must_present_own_signed_claim(self):
        e = self.parts()
        e[10:] = [None, None, None]
        r = self.review(e)
        self.assertEqual(r["decision"], UNPRESENTED)
        self.assertFalse(r["third_party_self_admitted"])

    def test_historical_instrument_and_claim_without_source_review_holds(self):
        e = self.parts()
        e[11:] = [None, None]
        r = self.review(e)
        self.assertEqual(r["decision"], SOURCE_MISSING)
        self.assertFalse(r["separate_source_signer_verified"])

    def test_source_review_without_new_owner_consent_holds(self):
        e = self.parts()
        e[12] = None
        r = self.review(e)
        self.assertEqual(r["decision"], OWNER_MISSING)
        self.assertTrue(r["separate_source_signer_verified"])
        self.assertFalse(r["selected_owner_local_consent_verified"])

    def test_all_three_are_signed_but_still_only_archival_hold(self):
        r = self.review()
        self.assertEqual(r["decision"], BOUNDED)
        self.assertEqual(r["014_decision"], "HOLD_SELECTED_SUCCESSOR_ARCHIVAL_ONLY_NOT_ADMITTED")
        self.assertEqual(r["owner_relative_archive_review_choice"], "north")
        self.assertTrue(r["separate_source_signer_verified"])
        self.assertTrue(r["selected_owner_local_consent_verified"])
        self.assertFalse(r["native_relatte_receive"])
        self.assertFalse(r["native_relatte_admission"])
        self.assertFalse(r["forwarding_authorized"])
        self.assertEqual(r["effects"], [])
        self.assertEqual(r["authority"], "NONE")

    def test_p256_legitimate_legacy_holder_cannot_self_sign_old_owner(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_legacy(e[0], e[2], self.keys["delegation-holder"],
                        self.keys["delegation-holder"])

    def test_old_owner_delegation_signed_by_unpinned_key_fails(self):
        e = self.parts()
        e[7]["signature"] = "counterfeit"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_altered_historic_scope_cannot_become_live_delegation(self):
        e = self.parts()
        e[7]["scope"] = "LIVE_CURRENT_AUTHORITY"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_altered_historic_action_cannot_enable_effect(self):
        e = self.parts()
        e[7]["action"] = "NATIVE_RELATTE_RECEIVE"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_historical_delegation_cannot_extend_original_012_ttl(self):
        e = self.parts()
        e[7]["simulated_not_after"] = 5000
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_historical_claim_before_signed_challenge_denied(self):
        e = self.parts()
        e[7]["simulated_claimed_issued_at"] = 1
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_wrong_historical_owner_key_denied(self):
        e = self.parts()
        e[7]["original_owner_public_key"] = self.keys["gossip-west"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_old_parcel_swap_not_cured_by_valid_other_signatures(self):
        e = self.parts()
        e[7]["original_parcel_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_third_party_must_be_separate_key_not_former_owner(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_legacy(e[0], e[2], self.keys["gossip-east"],
                        self.keys["gossip-east"])

    def test_015_source_key_cannot_overlap_014_review_key(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_policy(e[0], e[2], e[3], e[4], e[7],
                        self.keys["015-trust-root"],
                        self.keys["succession-reviewer"],
                        self.keys["015-neutral-recorder"])

    def test_015_root_cannot_overlap_historical_owner(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_policy(e[0], e[2], e[3], e[4], e[7],
                        self.keys["gossip-east"],
                        self.keys["015-source-reviewer"],
                        self.keys["015-neutral-recorder"])

    def test_015_recorder_cannot_overlap_external_source(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_policy(e[0], e[2], e[3], e[4], e[7],
                        self.keys["015-trust-root"],
                        self.keys["015-source-reviewer"],
                        self.keys["015-source-reviewer"])

    def test_sender_supplied_root_cannot_replace_independent_pin(self):
        e = self.parts()
        e[9] = self.keys["gossip-east"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_policy_must_bind_unmodified_014_review_cause(self):
        e = self.parts()
        e[8]["policy014_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_015_policy_must_bind_historic_delegation(self):
        e = self.parts()
        e[8]["old_instrument_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_policy_scope_cannot_escalate_to_execution(self):
        e = self.parts()
        e[8]["allowed_action"] = "FORWARD_AND_EXECUTE"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_third_party_impostor_cannot_sign_presentation(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_presentation(e[8], e[7], self.keys["gossip-east"])

    def test_third_party_presentation_signature_forgery_refused(self):
        e = self.parts()
        e[10]["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_expired_signed_third_party_request_holds_not_executes(self):
        e = self.parts()
        e[10] = make_presentation(
            e[8], e[7], self.keys["delegation-holder"], claimed_at=1000, not_after=1050)
        e[11:] = [None, None]
        self.assertEqual(self.review(e)["decision"], UNPRESENTED)

    def test_source_key_must_be_independently_pinned(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_source(e[8], e[10], e[3], "north", self.keys["delegation-holder"])

    def test_source_claim_cannot_change_target_successor(self):
        e = self.parts()
        e[11]["selected_candidate"] = "south"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_source_grant_cannot_authorize_forwarding(self):
        e = self.parts()
        e[11]["effect_permission"] = "FORWARD"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_missing_presentation_with_fresh_source_claim_is_invalid_partial_world(self):
        e = self.parts()
        e[10] = None
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_source_review_signature_forgery_fails_closed(self):
        e = self.parts()
        e[11]["signature"] = "not-a-source-signature"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_signed_source_review_for_other_candidate_cannot_cross_014_selection(self):
        e = self.parts()
        e[11] = make_source(e[8], e[10], e[3], "south",
                            self.keys["015-source-reviewer"])
        e[12] = None
        self.assertEqual(self.review(e)["decision"], CONTEST)

    def test_expired_source_review_holds_without_current_scope(self):
        e = self.parts()
        e[11] = make_source(e[8], e[10], e[3], "north",
                            self.keys["015-source-reviewer"],
                            claimed_at=1000, not_after=1050)
        e[12] = None
        self.assertEqual(self.review(e)["decision"], SOURCE_MISSING)

    def test_old_successor_cannot_impersonate_new_owner_consent(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_owner_consent(e[8], e[10], e[11], e[3], self.keys["gossip-east"])

    def test_source_reviewer_cannot_impersonate_new_owner_consent(self):
        e = self.parts()
        with self.assertRaises(InvalidWorld):
            make_owner_consent(e[8], e[10], e[11], e[3],
                               self.keys["015-source-reviewer"])

    def test_owner_consent_cannot_refer_to_other_source_review(self):
        e = self.parts()
        e[12]["source_approval_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_owner_consent_signature_forgery_fails_closed(self):
        e = self.parts()
        e[12]["signature"] = "bogus"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_owner_consent_is_not_native_authority(self):
        e = self.parts()
        e[12]["allowed_action"] = "NATIVE_DISPATCH"
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_expired_new_owner_consent_holds(self):
        e = self.parts()
        e[12] = make_owner_consent(
            e[8], e[10], e[11], e[3],
            self.keys["east-reconstituted"], claimed_at=1000, not_after=1050)
        self.assertEqual(self.review(e)["decision"], OWNER_MISSING)

    def test_missing_current_source_even_with_stale_old_delegation_does_not_promote(self):
        e = self.parts()
        e[11:] = [None, None]
        r = self.review(e)
        self.assertEqual(r["decision"], SOURCE_MISSING)
        self.assertFalse(r["historical_signer_authorizes_current_effects"])

    def test_consenter_missing_fresh_source_is_invalid(self):
        e = self.parts()
        e[11] = None
        with self.assertRaises(InvalidWorld):
            self.review(e)

    def test_neutral_signed_receipt_preserves_exact_three_door_outcome(self):
        saved = self.record()
        self.assertEqual(saved["status"], "SIGNED_LOCAL_EVIDENCE_RECORDED")
        self.assertEqual(saved["receipt"]["previous_receipt_digest"], GENESIS)
        self.assertEqual(saved["receipt"]["assessment"]["decision"], BOUNDED)
        replayed = verify_receipt(*self.parts(), receipt=saved["receipt"])
        self.assertEqual(replayed["decision"], BOUNDED)
        self.assertEqual(len(read_receipts(self.db)), 1)

    def test_duplicate_neutral_record_reuses_existing_signature(self):
        first = self.record()
        second = self.record()
        self.assertEqual(second["status"], "DUPLICATE_UNCHANGED")
        self.assertEqual(first["receipt"], second["receipt"])

    def test_old_source_signer_cannot_write_neutral_journal(self):
        with self.assertRaises(InvalidWorld):
            self.record(recorder=self.keys["gossip-east"])

    def test_third_party_cannot_write_neutral_journal(self):
        with self.assertRaises(InvalidWorld):
            self.record(recorder=self.keys["delegation-holder"])

    def test_later_consent_cannot_rewrite_older_signed_no_consent_hold(self):
        e = self.parts()
        e[12] = None
        saved = self.record(e)
        self.assertEqual(saved["receipt"]["assessment"]["decision"], OWNER_MISSING)
        with self.assertRaises(InvalidWorld):
            self.record()
        self.assertEqual(read_receipts(self.db)[0]["assessment"]["decision"], OWNER_MISSING)

    def test_replay_under_modified_local_clock_refused(self):
        self.record()
        with self.assertRaises(InvalidWorld):
            self.record(now=1200)

    def test_db_corruption_blocks_further_receipt_writes(self):
        self.record()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source_owner_history SET signed_receipt_json=?",
                       (json.dumps({"schema": "forged"}),))
        with self.assertRaises(InvalidWorld):
            self.record()

    def test_forged_receipt_digest_recomputed_without_recorder_signature_denied(self):
        receipt = self.record()["receipt"]
        receipt["assessment"]["native_relatte_admission"] = True
        receipt["assessment"]["assessment_digest"] = digest(receipt["assessment"])
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.parts(), receipt=receipt)

    def test_neutral_signature_cannot_be_swapped(self):
        receipt = self.record()["receipt"]
        receipt["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.parts(), receipt=receipt)

    def test_keyless_cold_verify_new_process_after_deleting_private_signers(self):
        result = self.record()
        with tempfile.TemporaryDirectory() as working:
            folder = Path(working)
            fields = [
                "parcel", "historical-local-package", "historical-pins",
                "succession-policy", "succession-root", "reviewer-selections",
                "candidate-archive-grants", "legacy-delegation",
                "third-party-policy", "third-party-root",
                "third-party-presentation", "fresh-source-review", "new-owner-consent",
            ]
            args = []
            for name, value in zip(fields, self.parts()):
                f = folder / (name + ".json")
                f.write_text(json.dumps(value), encoding="utf-8")
                args.extend(("--" + name, str(f)))
            receipt = folder / "receipt.json"
            receipt.write_text(json.dumps(result["receipt"]), encoding="utf-8")
            run = subprocess.run([
                sys.executable, str(ROOT / "ghot" / "unheard_choir_third_party.py"),
                "verify", *args, "--receipt", str(receipt),
            ], cwd=str(folder), capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout), {"verified": True, "decision": BOUNDED})
            self.assertFalse(list(folder.glob("*.pem")))

    def test_demo_stage_gates_and_expired_historical_claim(self):
        r = demo()
        self.assertEqual(r["historic_delegation_alone"], CONTEST)
        self.assertEqual(r["third_party_presents"], SOURCE_MISSING)
        self.assertEqual(r["source_reviews"], OWNER_MISSING)
        self.assertEqual(r["fresh_three_party"], BOUNDED)
        self.assertEqual(r["legacy_instrument_expired_at"], 1050)
        self.assertEqual(r["receiver_simulated_now"], 1100)
        self.assertTrue(r["cold_receipt_verified"])
        self.assertTrue(r["one_signed_receipt"])
        self.assertTrue(r["no_native_admission"])
        self.assertTrue(r["no_forwarding"])
        self.assertTrue(r["no_external_execution"])


if __name__ == "__main__":
    unittest.main()
