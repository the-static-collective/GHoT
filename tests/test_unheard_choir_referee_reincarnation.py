#!/usr/bin/env python3
"""020 adversarial cases: dead referee signatures remain history, not fresh authority."""
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
from unheard_choir_referee_reincarnation import (  # noqa: E402
    NO_RETIRE, NO_REFEREE, REFUSED, NO_OWNER, OWNER_REFUSED, BOUNDED,
    GENESIS, build_fixture, historical, make_policy, make_retirement,
    make_referee, make_owner, verify_policy, verify_retirement,
    assess, record_once, read_receipts, verify_receipt, demo,
    PRIOR_NAMES, HISTORIC_NAMES, CURRENT_NAMES,
)


class DeadRefereeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.tmp, cls.ancestors, cls.old_receipt, cls.policy,
         cls.root, cls.retirement, cls.fresh, cls.owner, cls.keys) = build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.db = Path(self.scratch.name) / "020-case.sqlite"

    def tearDown(self):
        self.scratch.cleanup()

    def evidence(self):
        return [copy.deepcopy(x) for x in (
            self.old_receipt, self.policy, self.root,
            self.retirement, self.fresh, self.owner,
        )]

    def assess_new(self, contents=None, *, now=1500):
        return assess(self.ancestors, *(self.evidence() if contents is None else contents), now=now)

    def write(self, contents=None, *, now=1500, signer=None):
        return record_once(
            self.db, self.ancestors,
            *(self.evidence() if contents is None else contents),
            self.keys["020-neutral"] if signer is None else signer, now=now,
        )

    def test_old_referee_private_file_simulated_retired(self):
        self.assertFalse((Path(self.tmp.name) / "019-referee.pem").exists())

    def test_public_historical_receipt_verifies_without_old_signer_file(self):
        result = historical(self.ancestors, self.old_receipt)
        self.assertEqual(result["decision"], "HOLD_SCOPED_ARCHIVAL_REVIEW_SELECTED_NOT_ADMITTED")

    def test_old_019_decision_does_not_authorize_fresh_case(self):
        e = self.evidence()
        e[3:] = [None, None, None]
        self.assertEqual(self.assess_new(e)["decision"], NO_RETIRE)

    def test_independent_reconstitution_alone_cannot_select(self):
        e = self.evidence()
        e[4:] = [None, None]
        self.assertEqual(self.assess_new(e)["decision"], NO_REFEREE)

    def test_fresh_referee_without_new_case_owner_consent_is_hold(self):
        e = self.evidence()
        e[5] = None
        self.assertEqual(self.assess_new(e)["decision"], NO_OWNER)

    def test_new_referee_and_owner_signatures_allow_only_archival_hold(self):
        a = self.assess_new()
        self.assertEqual(a["decision"], BOUNDED)
        self.assertEqual(a["authority"], "NONE")
        self.assertEqual(a["effects"], [])
        self.assertFalse(a["native_relatte_receive"])
        self.assertFalse(a["native_relatte_admission"])
        self.assertFalse(a["forwarding_permitted"])
        self.assertFalse(a["external_execution"])

    def test_old_source_fork_digest_preserved(self):
        a = self.assess_new()
        self.assertEqual(a["preserved_source_event_digests"], self.ancestors[8]["event_digest_set"])
        self.assertEqual(a["historic_019_receipt_digest"], digest(self.old_receipt))
        self.assertTrue(a["historical_signatures_remain_verifiable"])

    def test_old_referee_signature_cannot_be_new_referee_statement(self):
        e = self.evidence()
        e[4] = self.ancestors[11]
        e[5] = None
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_old_referee_private_key_cannot_sign_new_case(self):
        with self.assertRaises(InvalidWorld):
            make_referee(self.policy, self.retirement, self.keys["019-referee"],
                         action="SELECT", selected=self.fresh["selected_event_digest"])

    def test_old_owner_019_signature_cannot_be_new_case_consent(self):
        e = self.evidence()
        e[5] = self.ancestors[12]
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_old_owner_private_key_cannot_issue_new_consent(self):
        with self.assertRaises(InvalidWorld):
            make_owner(self.policy, self.fresh, self.keys["019-owner-selector"],
                       action="CONSENT", selected=self.fresh["selected_event_digest"])

    def test_referee_can_decline_a_new_case(self):
        e = self.evidence()
        e[4] = make_referee(self.policy, self.retirement, self.keys["020-referee"], action="DECLINE")
        e[5] = None
        self.assertEqual(self.assess_new(e)["decision"], REFUSED)

    def test_owner_may_refuse_against_valid_fresh_referee(self):
        e = self.evidence()
        e[5] = make_owner(self.policy, self.fresh, self.keys["020-owner"], action="REFUSE")
        self.assertEqual(self.assess_new(e)["decision"], OWNER_REFUSED)

    def test_owner_cannot_choose_other_document_without_explicit_alignment(self):
        e = self.evidence()
        different = next(x for x in self.policy["allowed_event_digests"]
                         if x != self.fresh["selected_event_digest"])
        e[5] = make_owner(self.policy, self.fresh, self.keys["020-owner"],
                          action="CONSENT", selected=different)
        self.assertEqual(self.assess_new(e)["decision"], OWNER_REFUSED)

    def test_owner_cannot_sign_without_referee(self):
        e = self.evidence()
        e[4] = None
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_fresh_referee_cannot_sign_without_reconstitution(self):
        e = self.evidence()
        e[3] = None
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_new_policy_cannot_be_signed_with_an_old_referee_key(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.ancestors, self.old_receipt,
                        self.keys["019-referee"], self.keys["020-referee"],
                        self.keys["020-owner"], self.keys["020-neutral"])

    def test_new_policy_cannot_pin_old_referee_as_successor(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.ancestors, self.old_receipt,
                        self.keys["020-root"], self.keys["019-referee"],
                        self.keys["020-owner"], self.keys["020-neutral"])

    def test_new_policy_cannot_pin_old_owner_as_new_owner(self):
        with self.assertRaises(InvalidWorld):
            make_policy(self.ancestors, self.old_receipt,
                        self.keys["020-root"], self.keys["020-referee"],
                        self.keys["019-owner-selector"], self.keys["020-neutral"])

    def test_pinned_policy_rejects_changed_case_digest_and_case_id(self):
        for field, new in (("new_case_id", "OTHER-CASE"),
                           ("new_case_question_digest", "0" * 64),
                           ("old_referee_epoch", 2), ("new_referee_epoch", 1),
                           ("native_source_grant", True)):
            e = self.evidence()
            e[1][field] = new
            with self.subTest(field=field), self.assertRaises(InvalidWorld):
                self.assess_new(e)

    def test_retirement_cannot_claim_biological_death_proven(self):
        e = self.evidence()
        e[3]["claims_actual_biological_death"] = True
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_retirement_cannot_erase_old_019_signatures(self):
        e = self.evidence()
        e[3]["historical_signature_still_valid"] = False
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_retirement_cannot_transfer_native_source_grants(self):
        e = self.evidence()
        e[3]["transfers_native_authority"] = True
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_retirement_must_be_signed_by_independent_root(self):
        e = self.evidence()
        e[3]["signature"] = "counterfeit"
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_referee_cannot_claim_old_epoch_or_a_different_case(self):
        for field, val in (("referee_epoch", 1), ("case_id", "DIFFERENT"),
                           ("effect_permission", "EXECUTE"),
                           ("native_authority", True), ("retirement_digest", "0"*64)):
            e = self.evidence()
            e[4][field] = val
            with self.subTest(field=field), self.assertRaises(InvalidWorld):
                self.assess_new(e)

    def test_new_referee_forged_signature_fails_closed(self):
        e = self.evidence()
        e[4]["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_new_referee_expired_interval_holds(self):
        e = self.evidence()
        e[4] = make_referee(self.policy, self.retirement,
                            self.keys["020-referee"], action="SELECT",
                            selected=self.fresh["selected_event_digest"],
                            claimed_at=1400, not_after=1450)
        e[5] = None
        self.assertEqual(self.assess_new(e, now=1500)["decision"], REFUSED)

    def test_new_referee_selecting_unseen_source_artifact_fails(self):
        with self.assertRaises(InvalidWorld):
            make_referee(self.policy, self.retirement, self.keys["020-referee"],
                         action="SELECT", selected="0" * 64)

    def test_owner_must_bind_exact_fresh_referee_choice(self):
        e = self.evidence()
        e[5]["referee_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.assess_new(e)

    def test_owner_must_bind_exact_case_and_epoch(self):
        for field, val in (("case_id", "OTHER"), ("referee_epoch", 1),
                           ("native_authority", True), ("effect_permission", "NATIVE")):
            e = self.evidence()
            e[5][field] = val
            with self.subTest(field=field), self.assertRaises(InvalidWorld):
                self.assess_new(e)

    def test_owner_expired_does_not_authorize_fresh_case(self):
        e = self.evidence()
        e[5] = make_owner(self.policy, self.fresh, self.keys["020-owner"],
                          action="CONSENT", selected=self.fresh["selected_event_digest"],
                          claimed_at=1400, not_after=1450)
        self.assertEqual(self.assess_new(e, now=1500)["decision"], OWNER_REFUSED)

    def test_invalid_boolean_local_clock_rejected(self):
        for now in (True, False, -1, 1.5, "1500", None):
            with self.subTest(now=now), self.assertRaises(InvalidWorld):
                self.assess_new(now=now)

    def test_signed_neutral_receipt_preserves_historical_receipt_digest(self):
        record = self.write()
        self.assertEqual(record["status"], "SIGNED_FRESH_CASE_HOLD_RECORDED")
        self.assertEqual(record["receipt"]["previous_digest"], GENESIS)
        self.assertEqual(record["receipt"]["assessment"]["historic_019_receipt_digest"],
                         digest(self.old_receipt))
        self.assertEqual(verify_receipt(self.ancestors, *self.evidence(), record["receipt"])["decision"], BOUNDED)

    def test_duplicate_reuses_exact_signed_receipt(self):
        initial = self.write()
        repeat = self.write()
        self.assertEqual(repeat["status"], "DUPLICATE_UNCHANGED")
        self.assertEqual(initial["receipt"], repeat["receipt"])
        self.assertEqual(len(read_receipts(self.db)), 1)

    def test_old_referee_cannot_sign_neutral_new_case_receipt(self):
        with self.assertRaises(InvalidWorld):
            self.write(signer=self.keys["019-referee"])

    def test_fresh_referee_cannot_sign_neutral_case_receipt(self):
        with self.assertRaises(InvalidWorld):
            self.write(signer=self.keys["020-referee"])

    def test_new_referee_change_cannot_retroactively_rewrite_case_receipt(self):
        first = self.write()
        e = self.evidence()
        e[4] = make_referee(self.policy, self.retirement, self.keys["020-referee"],
                            action="DECLINE")
        e[5] = None
        with self.assertRaises(InvalidWorld):
            self.write(e)
        self.assertEqual(read_receipts(self.db)[0], first["receipt"])

    def test_corrupt_sqlite_receipt_refuses_new_write(self):
        self.write()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE new_case_receipts SET signed_json=?",
                       (json.dumps({"fake": True}),))
        with self.assertRaises(InvalidWorld):
            self.write()

    def test_receipt_forgery_or_effect_claim_denied_on_cold_replay(self):
        saved = self.write()["receipt"]
        altered = copy.deepcopy(saved)
        altered["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            verify_receipt(self.ancestors, *self.evidence(), altered)
        altered = copy.deepcopy(saved)
        altered["assessment"]["native_relatte_receive"] = True
        with self.assertRaises(InvalidWorld):
            verify_receipt(self.ancestors, *self.evidence(), altered)

    def test_public_only_subprocess_without_any_private_signer_files(self):
        saved = self.write()["receipt"]
        values = list(self.ancestors[0]) + list(self.ancestors[1:]) + self.evidence() + [saved]
        names = PRIOR_NAMES + HISTORIC_NAMES + CURRENT_NAMES
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            flags = []
            for name, item in zip(names, values):
                f = folder / (name + ".json")
                f.write_text(json.dumps(item), encoding="utf-8")
                flags.extend(("--" + name, str(f)))
            proc = subprocess.run([
                sys.executable, str(ROOT / "ghot" / "unheard_choir_referee_reincarnation.py"),
                "verify", *flags,
            ], cwd=str(folder), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout), {"verified": True, "decision": BOUNDED})
            self.assertEqual(list(folder.glob("*.pem")), [])
            self.assertEqual(list(folder.glob("*.sqlite")), [])

    def test_020_demo_dies_without_erasing_019(self):
        outcome = demo()
        self.assertTrue(outcome["old_private_file_deleted_in_fixture"])
        self.assertEqual(outcome["old_signed_historical_decision"],
                         "HOLD_SCOPED_ARCHIVAL_REVIEW_SELECTED_NOT_ADMITTED")
        self.assertEqual(outcome["without_reconstitution"], NO_RETIRE)
        self.assertEqual(outcome["without_fresh_referee"], NO_REFEREE)
        self.assertEqual(outcome["without_fresh_owner"], NO_OWNER)
        self.assertEqual(outcome["with_fresh_separate_approvals"], BOUNDED)
        self.assertTrue(outcome["historic_receipt_preserved"])
        self.assertTrue(outcome["old_source_event_set_preserved"])
        self.assertTrue(outcome["public_cold_replay_without_old_private_file"])
        self.assertTrue(outcome["one_neutral_durable_receipt"])
        self.assertFalse(outcome["native_relatte_receive"])
        self.assertFalse(outcome["external_execution"])


if __name__ == "__main__":
    unittest.main()
