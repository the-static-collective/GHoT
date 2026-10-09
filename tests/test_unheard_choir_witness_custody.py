#!/usr/bin/env python3
"""016 hostile suite: witness custody != source permission; silence != refusal."""
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
from unheard_choir_witness_custody import (  # noqa: E402
    CUSTODY_ONLY, UNKNOWN, UNAVAILABLE, RECORD_GAP, DECLINED,
    REVOKED, OWNER_UNKNOWN, PREDECESSOR_HOLD, GENESIS,
    assess, build_fixture, make_manifest, make_notice,
    make_policy, verify_manifest, verify_notice,
    record_once, read_receipts, verify_receipt, demo,
)


class UnheardWitnessCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.prior, cls.policy, cls.root, cls.manifest, cls.keys = build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.db = Path(self.workspace.name) / "witness-016.sqlite"

    def tearDown(self):
        self.workspace.cleanup()

    def evidence(self):
        return copy.deepcopy(self.prior)

    def inputs(self, *, missing_source=False, missing_owner=False):
        prior = self.evidence()
        if missing_source:
            prior[11], prior[12] = None, None
        elif missing_owner:
            prior[12] = None
        return prior

    def manifest_for(self, prior):
        return make_manifest(prior, self.policy, self.keys["delegation-holder"])

    def notice_for(self, prior, kind, *, when=1100, effective=1200, end=5000):
        return make_notice(
            prior, self.policy, self.keys["015-source-reviewer"],
            kind, claimed_at=when, effective_at=effective, not_after=end,
        )

    def evaluate(self, prior=None, manifest=None, notice=None, *,
                 policy=None, root=None, now=1250):
        prior = self.evidence() if prior is None else prior
        manifest = self.manifest_for(prior) if manifest is None else manifest
        return assess(prior, self.policy if policy is None else policy,
                      self.root if root is None else root,
                      manifest, notice, now=now)

    def store(self, prior=None, manifest=None, notice=None, *, now=1250, signer=None):
        prior = self.evidence() if prior is None else prior
        manifest = self.manifest_for(prior) if manifest is None else manifest
        return record_once(
            self.db, prior, self.policy, self.root, manifest, notice,
            self.keys["016-neutral-recorder"] if signer is None else signer, now=now,
        )

    def test_full_prior_015_reviews_are_custody_only(self):
        r = self.evaluate()
        self.assertEqual(r["decision"], CUSTODY_ONLY)
        self.assertEqual(r["015_decision"],
                         "HOLD_THREE_PARTY_ARCHIVAL_EVIDENCE_ONLY_NOT_ADMITTED")
        self.assertFalse(r["holder_has_current_source_power"])
        self.assertFalse(r["native_relatte_receive"])
        self.assertEqual(r["authority"], "NONE")

    def test_no_response_is_unknown_not_source_refusal(self):
        prior = self.inputs(missing_source=True)
        r = self.evaluate(prior)
        self.assertEqual(r["decision"], UNKNOWN)
        self.assertFalse(r["source_response_observed"])
        self.assertFalse(r["missing_source_response_is_refusal"])
        self.assertFalse(r["missing_document_proves_world_nonexistence"])

    def test_local_omission_is_accurate_but_not_world_absence(self):
        prior = self.inputs(missing_source=True)
        manifest = self.manifest_for(prior)
        self.assertEqual(manifest["slots"][1]["status"], "ABSENT_FROM_HOLDER_PACKET")
        self.assertIsNone(manifest["slots"][1]["document_digest"])
        self.assertFalse(manifest["negative_evidence_is_global_absence"])
        verify_manifest(prior, self.policy, manifest)

    def test_signed_source_unavailable_is_not_denial(self):
        prior = self.inputs(missing_source=True)
        note = self.notice_for(prior, "SOURCE_UNAVAILABLE_LOCAL")
        outcome = self.evaluate(prior, notice=note)
        self.assertEqual(outcome["decision"], UNAVAILABLE)
        self.assertTrue(outcome["source_response_observed"])
        self.assertFalse(outcome["missing_source_response_is_refusal"])

    def test_signed_source_cannot_find_local_record(self):
        prior = self.inputs(missing_source=True)
        note = self.notice_for(prior, "SOURCE_RECORD_NOT_FOUND_LOCAL")
        outcome = self.evaluate(prior, notice=note)
        self.assertEqual(outcome["decision"], RECORD_GAP)
        self.assertTrue(outcome["old_delegation_remains_historical"] if
                        "old_delegation_remains_historical" in outcome else
                        not outcome["historical_document_erased_by_revocation"])

    def test_explicit_signed_decline_is_not_global_erasure(self):
        prior = self.inputs(missing_source=True)
        note = self.notice_for(prior, "SOURCE_DECLINED_NEW_REVIEW")
        outcome = self.evaluate(prior, notice=note)
        self.assertEqual(outcome["decision"], DECLINED)
        self.assertFalse(outcome["historical_document_erased_by_revocation"])
        self.assertFalse(outcome["external_execution"])

    def test_signed_revocation_blocks_current_archival_review(self):
        prior = self.evidence()
        note = self.notice_for(prior, "REVOKE_EXACT_SOURCE_REVIEW")
        outcome = self.evaluate(prior, notice=note)
        self.assertEqual(outcome["decision"], REVOKED)
        self.assertEqual(note["review_target_digest"], digest(prior[11]))
        self.assertEqual(outcome["retained_legacy_delegation_digest"], digest(prior[7]))
        self.assertFalse(outcome["historical_document_erased_by_revocation"])

    def test_future_revocation_does_not_preempt_its_effective_instant(self):
        prior = self.evidence()
        note = self.notice_for(prior, "REVOKE_EXACT_SOURCE_REVIEW",
                               when=1100, effective=1200, end=5000)
        before = self.evaluate(prior, notice=note, now=1150)
        after = self.evaluate(prior, notice=note, now=1250)
        self.assertEqual(before["decision"], CUSTODY_ONLY)
        self.assertEqual(after["decision"], REVOKED)
        self.assertEqual(before["source_notice_status"]["active_at_simulated_clock"], False)

    def test_expired_source_status_never_becomes_current_authority(self):
        prior = self.evidence()
        note = self.notice_for(prior, "REVOKE_EXACT_SOURCE_REVIEW",
                               when=1000, effective=1050, end=1100)
        result = self.evaluate(prior, notice=note, now=1250)
        self.assertEqual(result["decision"], CUSTODY_ONLY)
        self.assertFalse(result["source_notice_status"]["active_at_simulated_clock"])

    def test_missing_owner_consent_stays_unknown(self):
        prior = self.inputs(missing_owner=True)
        outcome = self.evaluate(prior)
        self.assertEqual(outcome["decision"], OWNER_UNKNOWN)
        self.assertEqual(outcome["holder_custody_slots"]["new_owner_consent"]["status"],
                         "ABSENT_FROM_HOLDER_PACKET")
        self.assertFalse(outcome["forwarding_authorized"])

    def test_inherited_014_conflict_cannot_be_cured_by_source_report(self):
        prior = self.evidence()
        prior[5] = [
            make_selection(prior[3], self.keys["succession-reviewer"], "north"),
            make_selection(prior[3], self.keys["succession-reviewer"], "south"),
        ]
        outcome = self.evaluate(prior)
        self.assertEqual(outcome["decision"], PREDECESSOR_HOLD)
        self.assertEqual(outcome["015_decision"],
                         "HOLD_014_SUCCESSION_NOT_RESOLVED_FOR_ARCHIVAL_REVIEW")

    def test_revocation_without_exact_historical_source_review_denied(self):
        prior = self.inputs(missing_source=True)
        with self.assertRaises(InvalidWorld):
            self.notice_for(prior, "REVOKE_EXACT_SOURCE_REVIEW")

    def test_third_party_cannot_self_issue_source_unavailable_notice(self):
        with self.assertRaises(InvalidWorld):
            make_notice(self.evidence(), self.policy,
                        self.keys["delegation-holder"], "SOURCE_UNAVAILABLE_LOCAL")

    def test_historical_owner_cannot_issue_new_source_notice(self):
        with self.assertRaises(InvalidWorld):
            make_notice(self.evidence(), self.policy,
                        self.keys["gossip-east"], "SOURCE_UNAVAILABLE_LOCAL")

    def test_new_successor_cannot_issue_source_revocation(self):
        with self.assertRaises(InvalidWorld):
            make_notice(self.evidence(), self.policy,
                        self.keys["east-reconstituted"], "REVOKE_EXACT_SOURCE_REVIEW")

    def test_notice_wrong_legacy_instrument_digest_rejected(self):
        note = self.notice_for(self.evidence(), "REVOKE_EXACT_SOURCE_REVIEW")
        note["historic_instrument_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.evaluate(notice=note)

    def test_notice_wrong_specific_source_review_digest_rejected(self):
        note = self.notice_for(self.evidence(), "REVOKE_EXACT_SOURCE_REVIEW")
        note["review_target_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.evaluate(notice=note)

    def test_notice_rewritten_into_global_denial_rejected(self):
        note = self.notice_for(self.evidence(), "SOURCE_RECORD_NOT_FOUND_LOCAL")
        note["scope"] = "GLOBAL_NONEXISTENCE_CLAIM"
        with self.assertRaises(InvalidWorld):
            self.evaluate(notice=note)

    def test_notice_claiming_effect_permission_rejected(self):
        note = self.notice_for(self.evidence(), "REVOKE_EXACT_SOURCE_REVIEW")
        note["effect_permission"] = "EXECUTE"
        with self.assertRaises(InvalidWorld):
            self.evaluate(notice=note)

    def test_notice_claiming_third_party_nonresponse_proof_rejected(self):
        note = self.notice_for(self.evidence(), "SOURCE_UNAVAILABLE_LOCAL")
        note["proves_nonresponse_elsewhere"] = True
        with self.assertRaises(InvalidWorld):
            self.evaluate(notice=note)

    def test_tampered_signed_source_notice_rejected(self):
        note = self.notice_for(self.evidence(), "SOURCE_UNAVAILABLE_LOCAL")
        note["signature"] = "bogus"
        with self.assertRaises(InvalidWorld):
            self.evaluate(notice=note)

    def test_source_notice_clock_inconsistent_rejected(self):
        note = self.notice_for(self.evidence(), "REVOKE_EXACT_SOURCE_REVIEW")
        note["simulated_effective_at"] = 1000
        with self.assertRaises(InvalidWorld):
            self.evaluate(notice=note)

    def test_no_synthetic_boolean_clock_accepted(self):
        for value in (True, -1, 1.5, "1250", None):
            with self.subTest(clock=value), self.assertRaises(InvalidWorld):
                self.evaluate(now=value)

    def test_manifest_holder_must_match_signed_015_holder(self):
        with self.assertRaises(InvalidWorld):
            make_manifest(self.evidence(), self.policy, self.keys["gossip-east"])

    def test_manifest_cannot_claim_omitted_source_if_present_in_packet(self):
        prior = self.evidence()
        manifest = self.manifest_for(prior)
        manifest["slots"][1]["status"] = "ABSENT_FROM_HOLDER_PACKET"
        manifest["slots"][1]["document_digest"] = None
        with self.assertRaises(InvalidWorld):
            self.evaluate(prior, manifest=manifest)

    def test_manifest_cannot_claim_present_source_if_packet_lacks_it(self):
        prior = self.inputs(missing_source=True)
        manifest = self.manifest_for(prior)
        manifest["slots"][1]["status"] = "PRESENT"
        manifest["slots"][1]["document_digest"] = "a" * 64
        with self.assertRaises(InvalidWorld):
            self.evaluate(prior, manifest=manifest)

    def test_manifest_extra_absence_is_world_proof_flag_rejected(self):
        manifest = self.manifest_for(self.evidence())
        manifest["negative_evidence_is_global_absence"] = True
        with self.assertRaises(InvalidWorld):
            self.evaluate(manifest=manifest)

    def test_manifest_cannot_reorder_the_specific_evidence_slots(self):
        manifest = self.manifest_for(self.evidence())
        manifest["slots"].reverse()
        with self.assertRaises(InvalidWorld):
            self.evaluate(manifest=manifest)

    def test_manifest_signature_forgery_rejected(self):
        manifest = self.manifest_for(self.evidence())
        manifest["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.evaluate(manifest=manifest)

    def test_016_policy_cannot_use_015_source_key_as_local_root(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.evidence(),
                        self.keys["015-source-reviewer"],
                        self.keys["016-neutral-recorder"])

    def test_016_policy_cannot_use_holder_as_local_root(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.evidence(),
                        self.keys["delegation-holder"],
                        self.keys["016-neutral-recorder"])

    def test_016_recorder_cannot_be_source_reviewer(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.evidence(),
                        self.keys["016-custody-root"],
                        self.keys["015-source-reviewer"])

    def test_policy_unpinned_source_root_denied(self):
        wrong = self.keys["gossip-west"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.evaluate(root=wrong)

    def test_policy_cannot_expand_to_admission(self):
        policy = copy.deepcopy(self.policy)
        policy["authorized_local_action"] = "NATIVE_RECEIVE"
        with self.assertRaises(InvalidWorld):
            self.evaluate(policy=policy)

    def test_policy_cannot_change_third_party_holder(self):
        policy = copy.deepcopy(self.policy)
        policy["holder_public_key"] = self.keys["gossip-west"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.evaluate(policy=policy)

    def test_policy_cannot_smuggle_untrusted_omission_grant(self):
        policy = copy.deepcopy(self.policy)
        policy["absence_is_denial"] = True
        with self.assertRaises(InvalidWorld):
            self.evaluate(policy=policy)

    def test_new_source_notice_never_rewrites_existing_signed_receipt(self):
        prior = self.evidence()
        a = self.store(prior)
        self.assertEqual(a["receipt"]["assessment"]["decision"], CUSTODY_ONLY)
        notice = self.notice_for(prior, "REVOKE_EXACT_SOURCE_REVIEW")
        with self.assertRaises(InvalidWorld):
            self.store(prior, notice=notice)
        self.assertEqual(read_receipts(self.db)[0]["assessment"]["decision"], CUSTODY_ONLY)

    def test_duplicate_signed_receipt_is_byte_for_byte_stable(self):
        prior = self.inputs(missing_source=True)
        a = self.store(prior)
        b = self.store(prior)
        self.assertEqual(a["receipt"], b["receipt"])
        self.assertEqual(b["status"], "DUPLICATE_UNCHANGED")
        self.assertEqual(len(read_receipts(self.db)), 1)

    def test_source_reviewer_cannot_sign_neutral_custody(self):
        with self.assertRaises(InvalidWorld):
            self.store(signer=self.keys["015-source-reviewer"])

    def test_holder_cannot_sign_neutral_custody(self):
        with self.assertRaises(InvalidWorld):
            self.store(signer=self.keys["delegation-holder"])

    def test_corrupt_sqlite_record_refuses_replay(self):
        self.store()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE custody SET receipt_json=?",
                       (json.dumps({"schema": "fabricated"}),))
        with self.assertRaises(InvalidWorld):
            self.store()

    def test_forged_receipt_cannot_claim_native_effect(self):
        receipt = self.store()["receipt"]
        receipt["assessment"]["native_relatte_admission"] = True
        with self.assertRaises(InvalidWorld):
            verify_receipt(self.evidence(), self.policy, self.root,
                           self.manifest_for(self.evidence()), None, receipt)

    def test_source_history_can_still_be_replayed_after_revocation(self):
        prior = self.evidence()
        notice = self.notice_for(prior, "REVOKE_EXACT_SOURCE_REVIEW")
        output = self.store(prior, notice=notice)["receipt"]
        r = verify_receipt(prior, self.policy, self.root,
                           self.manifest_for(prior), notice, output)
        self.assertEqual(r["decision"], REVOKED)
        self.assertFalse(r["historical_document_erased_by_revocation"])

    def test_subprocess_cold_receipt_without_signers_or_sqlite(self):
        prior = self.inputs(missing_source=True)
        manifest = self.manifest_for(prior)
        notice = self.notice_for(prior, "SOURCE_RECORD_NOT_FOUND_LOCAL")
        receipt = self.store(prior, manifest=manifest, notice=notice)["receipt"]
        names = (
            "parcel", "historical-local-package", "historical-pins",
            "succession-policy", "succession-root", "reviewer-selections",
            "candidate-archive-grants", "legacy-delegation",
            "third-party-policy", "third-party-root",
            "third-party-presentation", "fresh-source-review", "new-owner-consent",
        )
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            flags = []
            for name, entry in zip(names, prior):
                if entry is None:
                    continue
                f = folder / (name + ".json")
                f.write_text(json.dumps(entry), encoding="utf-8")
                flags += ["--" + name, str(f)]
            for name, content in (
                ("custody-policy", self.policy), ("custody-root", self.root),
                ("holder-inventory", manifest), ("source-notice", notice),
                ("receipt", receipt),
            ):
                f = folder / (name + ".json")
                f.write_text(json.dumps(content), encoding="utf-8")
                flags += ["--" + name, str(f)]
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_witness_custody.py"),
                   "verify", *flags]
            output = subprocess.run(cmd, cwd=str(folder), capture_output=True, text=True)
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertEqual(json.loads(output.stdout),
                             {"verified": True, "decision": RECORD_GAP})
            self.assertFalse(list(folder.glob("*.pem")))
            self.assertFalse(list(folder.glob("*.sqlite")))

    def test_standalone_demo_all_gap_states(self):
        r = demo()
        self.assertEqual(r["full_prior_evidence_archive_only"], CUSTODY_ONLY)
        self.assertEqual(r["source_never_responded"], UNKNOWN)
        self.assertEqual(r["signed_source_unavailable"], UNAVAILABLE)
        self.assertEqual(r["signed_exact_source_review_revocation"], REVOKED)
        self.assertTrue(r["revoked_source_history_retained"])
        self.assertTrue(r["no_reply_does_not_mean_refusal"])
        self.assertTrue(r["signed_omission_does_not_prove_absence"])
        self.assertTrue(r["neutral_signed_local_receipt"])
        self.assertTrue(r["cold_public_receipt_verified"])
        self.assertFalse(r["native_relatte_admission"])
        self.assertFalse(r["external_execution"])


if __name__ == "__main__":
    unittest.main()
