#!/usr/bin/env python3
"""019 adversarial coverage: local referee decision != source or owner authority."""
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
from unheard_choir_referee import (  # noqa: E402
    NO_EPOCH, EPOCH_COLLISION, NO_REFEREE, REFUSED,
    BAD_SELECTION, NO_OWNER, OWNER_REFUSED, BOUNDED, GENESIS,
    build_fixture, demo, signed_events, make_epoch, make_referee,
    make_owner, verify_epochs, verify_policy, assess,
    record_once, read_receipts, verify_receipt, PRIOR_NAMES, OTHER_NAMES,
)


class RefereeWhoRefusedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.sources, cls.keys = build_fixture()
        cls.source_docs = signed_events(cls.sources[0], cls.sources[1],
                                        cls.sources[4], cls.sources[6], cls.sources[7])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.database = Path(self.scratch.name) / "neutral-019.sqlite"

    def tearDown(self):
        self.scratch.cleanup()

    def inputs(self):
        # Fixture ancestry is an immutable tuple; hostile tests mutate only
        # their independently copied list, never the signed source fixture.
        return list(copy.deepcopy(self.sources))

    def calculate(self, sources=None, *, now=1350):
        return assess(*(self.inputs() if sources is None else sources), now=now)

    def store(self, sources=None, *, signer=None, now=1350):
        return record_once(
            self.database,
            *(self.inputs() if sources is None else sources),
            self.keys["019-neutral-recorder"] if signer is None else signer,
            now=now,
        )

    def other_event(self, current=None):
        chosen = current if current is not None else self.sources[11]["selected_event_digest"]
        return next(x for x in self.sources[8]["event_digest_set"] if x != chosen)

    def test_one_pinned_referee_and_owner_archive_decision_remains_hold(self):
        outcome = self.calculate()
        self.assertEqual(outcome["decision"], BOUNDED)
        self.assertEqual(outcome["authority"], "NONE")
        self.assertEqual(outcome["effects"], [])
        self.assertFalse(outcome["native_relatte_receive"])
        self.assertFalse(outcome["native_relatte_admission"])
        self.assertFalse(outcome["forwarding_permitted"])

    def test_historical_018_fork_and_015_approval_remain_intact(self):
        outcome = self.calculate()
        self.assertEqual(outcome["prior018_source_conflict"],
                         "HOLD_SOURCE_REVOCATION_REINSTATEMENT_UNRESOLVED")
        self.assertEqual(outcome["original_015_approval_digest"], digest(self.sources[0][11]))
        self.assertEqual(outcome["source_history_digest_set"], self.sources[8]["event_digest_set"])
        self.assertTrue(outcome["prior_source_statements_unchanged"])

    def test_no_signed_referee_choice_never_selects_epoch_winner(self):
        source = self.inputs()
        source[11] = None
        source[12] = None
        self.assertEqual(self.calculate(source)["decision"], NO_REFEREE)

    def test_referee_can_explicitly_decline_to_rule(self):
        source = self.inputs()
        source[11] = make_referee(source[8], source[10], self.keys["019-referee"],
                                 action="DECLINE")
        source[12] = None
        outcome = self.calculate(source)
        self.assertEqual(outcome["decision"], REFUSED)
        self.assertIsNone(outcome["chosen_for_local_archive_review_only"])

    def test_referee_refusal_cannot_secretly_choose_an_event(self):
        with self.assertRaises(InvalidWorld):
            make_referee(self.sources[8], self.sources[10],
                         self.keys["019-referee"], action="DECLINE",
                         selected=self.sources[11]["selected_event_digest"])

    def test_owner_cannot_select_when_referee_has_not_signed(self):
        source = self.inputs()
        source[11] = None
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_owner_absent_keeps_valid_referee_hold(self):
        source = self.inputs()
        source[12] = None
        self.assertEqual(self.calculate(source)["decision"], NO_OWNER)

    def test_owner_can_refuse_even_if_referee_rules(self):
        source = self.inputs()
        source[12] = make_owner(source[8], source[11],
                                self.keys["019-owner-selector"], action="REFUSE")
        result = self.calculate(source)
        self.assertEqual(result["decision"], OWNER_REFUSED)
        self.assertFalse(result["global_jurisdiction_established"])

    def test_owner_cannot_use_refusal_to_hide_selected_source_event(self):
        with self.assertRaises(InvalidWorld):
            make_owner(self.sources[8], self.sources[11],
                       self.keys["019-owner-selector"], action="REFUSE",
                       selected=self.sources[11]["selected_event_digest"])

    def test_owner_mismatch_is_signed_evidence_but_not_archival_selection(self):
        source = self.inputs()
        source[12] = make_owner(source[8], source[11],
                                self.keys["019-owner-selector"], action="SELECT",
                                selected=self.other_event())
        self.assertEqual(self.calculate(source)["decision"], OWNER_REFUSED)

    def test_wrong_referee_winner_cannot_become_selected_by_local_owner(self):
        source = self.inputs()
        wrong = self.other_event()
        source[11] = make_referee(source[8], source[10],
                                  self.keys["019-referee"],
                                  action="SELECT", selected=wrong)
        source[12] = make_owner(source[8], source[11],
                                self.keys["019-owner-selector"],
                                action="SELECT", selected=wrong)
        outcome = self.calculate(source)
        self.assertEqual(outcome["decision"], BAD_SELECTION)
        self.assertIsNone(outcome["chosen_for_local_archive_review_only"])

    def test_signed_epoch_certificate_set_must_cover_all_observed_events(self):
        source = self.inputs()
        source[10] = source[10][:-1]
        source[11] = None
        source[12] = None
        self.assertEqual(self.calculate(source)["decision"], NO_EPOCH)

    def test_independently_signed_epoch_collision_remains_unresolved(self):
        source = self.inputs()
        witness = self.keys["019-epoch-witness"]
        first, second = source[10][:2]
        more = make_epoch(source[8],
                          self.source_docs[second["source_event_digest"]]["document"],
                          witness, first["source_epoch"])
        source[10].append(more)
        source[11] = None
        source[12] = None
        outcome = self.calculate(source)
        self.assertEqual(outcome["decision"], EPOCH_COLLISION)
        self.assertEqual(outcome["epoch_evidence"]["winner"], None)

    def test_exact_duplicate_attestation_is_not_falsely_called_a_fork(self):
        source = self.inputs()
        source[10].append(copy.deepcopy(source[10][0]))
        referee = make_referee(source[8], source[10], self.keys["019-referee"],
                               action="SELECT",
                               selected=source[11]["selected_event_digest"])
        owner = make_owner(source[8], referee, self.keys["019-owner-selector"],
                           action="SELECT",
                           selected=source[11]["selected_event_digest"])
        source[11], source[12] = referee, owner
        self.assertEqual(self.calculate(source)["decision"], BOUNDED)

    def test_independently_signed_same_epoch_is_repeated_evidence_not_fork(self):
        source = self.inputs()
        first = source[10][0]
        second = make_epoch(source[8],
                            self.source_docs[first["source_event_digest"]]["document"],
                            self.keys["019-epoch-witness"], first["source_epoch"])
        source[10].append(second)
        referee = make_referee(source[8], source[10], self.keys["019-referee"],
                               action="SELECT",
                               selected=source[11]["selected_event_digest"])
        owner = make_owner(source[8], referee, self.keys["019-owner-selector"],
                           action="SELECT",
                           selected=source[11]["selected_event_digest"])
        source[11], source[12] = referee, owner
        self.assertEqual(self.calculate(source)["decision"], BOUNDED)

    def test_same_event_claims_two_valid_epochs_cannot_resolve_conflict(self):
        source = self.inputs()
        first = source[10][0]
        cert = make_epoch(source[8],
                          self.source_docs[first["source_event_digest"]]["document"],
                          self.keys["019-epoch-witness"], epoch=900)
        source[10].append(cert)
        source[11] = None
        source[12] = None
        self.assertEqual(self.calculate(source)["decision"], EPOCH_COLLISION)

    def test_unique_epoch_proofs_require_independently_pinned_witness(self):
        with self.assertRaises(InvalidWorld):
            make_epoch(self.sources[8],
                       self.source_docs[self.sources[10][0]["source_event_digest"]]["document"],
                       self.keys["015-source-reviewer"], epoch=5)

    def test_epoch_integer_cannot_be_bool_float_string_or_zero(self):
        doc = self.source_docs[self.sources[10][0]["source_event_digest"]]["document"]
        for epoch in (True, False, 0, 1.25, "2", -2, 1000001):
            with self.subTest(epoch=epoch), self.assertRaises(InvalidWorld):
                make_epoch(self.sources[8], doc, self.keys["019-epoch-witness"], epoch)

    def test_source_epoch_assignment_to_unseen_event_denied(self):
        with self.assertRaises(InvalidWorld):
            make_epoch(self.sources[8], {"schema": "invented"},
                       self.keys["019-epoch-witness"], epoch=10)

    def test_tampered_epoch_certificate_signature_fails_closed(self):
        source = self.inputs()
        source[10][0]["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_tampered_epoch_number_fails_closed(self):
        source = self.inputs()
        source[10][0]["source_epoch"] = 999
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_epoch_claiming_native_grant_refused(self):
        source = self.inputs()
        source[10][0]["grants_execution"] = True
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_local_policy_cannot_be_signed_by_old_source(self):
        source = self.inputs()
        source[9] = self.keys["015-source-reviewer"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_policy_cannot_substitute_a_claimant_as_epoch_attestor(self):
        source = self.inputs()
        source[8]["pinned_epoch_witness"] = self.keys["delegation-holder"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_policy_cannot_change_evidence_set_or_scope(self):
        for field, value in (
            ("event_digest_set", []),
            ("scope", "GLOBAL_SOURCE_PRIORITY"),
            ("winner_rule", "LATEST_TIMESTAMP"),
            ("creates_native_grant", True),
        ):
            source = self.inputs()
            source[8][field] = value
            with self.subTest(field=field), self.assertRaises(InvalidWorld):
                self.calculate(source)

    def test_referee_cannot_be_source_reviewer_or_successor(self):
        with self.assertRaises(InvalidWorld):
            make_referee(self.sources[8], self.sources[10],
                         self.keys["015-source-reviewer"], action="DECLINE")

    def test_referee_signature_forgery_rejected(self):
        source = self.inputs()
        source[11]["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_referee_cannot_claim_external_execution_or_global_ownership(self):
        for field, val in (("effect_permission", "EXECUTE"),
                           ("declares_global_authority", True)):
            source = self.inputs()
            source[11][field] = val
            with self.subTest(field=field), self.assertRaises(InvalidWorld):
                self.calculate(source)

    def test_referee_unrecognized_event_selection_rejected(self):
        with self.assertRaises(InvalidWorld):
            make_referee(self.sources[8], self.sources[10],
                         self.keys["019-referee"], action="SELECT",
                         selected="0"*64)

    def test_expired_referee_statement_does_not_choose_today(self):
        source = self.inputs()
        source[11] = make_referee(
            source[8], source[10], self.keys["019-referee"],
            action="SELECT", selected=source[11]["selected_event_digest"],
            claimed_at=1200, not_after=1300)
        source[12] = None
        self.assertEqual(self.calculate(source, now=1350)["decision"], REFUSED)

    def test_owner_signature_cannot_be_source_or_referee(self):
        for who in ("019-referee", "015-source-reviewer", "delegation-holder"):
            with self.subTest(who=who), self.assertRaises(InvalidWorld):
                make_owner(self.sources[8], self.sources[11], self.keys[who],
                           action="SELECT",
                           selected=self.sources[11]["selected_event_digest"])

    def test_owner_selection_wrong_referee_digest_rejected(self):
        source = self.inputs()
        source[12]["referee_digest"] = "0"*64
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_owner_selection_cannot_convert_archive_to_native_relatte(self):
        source = self.inputs()
        source[12]["creates_source_grant"] = True
        with self.assertRaises(InvalidWorld):
            self.calculate(source)

    def test_expired_owner_local_choice_refuses_active_archive_selection(self):
        source = self.inputs()
        selected = source[12]["selected_event_digest"]
        source[12] = make_owner(source[8], source[11],
                                self.keys["019-owner-selector"],
                                action="SELECT", selected=selected,
                                claimed_at=1200, not_after=1300)
        self.assertEqual(self.calculate(source, now=1350)["decision"], OWNER_REFUSED)

    def test_synthetic_clock_boolean_or_negative_not_admitted(self):
        for now in (True, False, -1, 1.25, "1350", None):
            with self.subTest(now=now), self.assertRaises(InvalidWorld):
                self.calculate(now=now)

    def test_pristine_signed_local_receipt_replays_as_historical_hold(self):
        result = self.store()
        self.assertEqual(result["status"], "SIGNED_PRECEDENCE_REVIEW_HOLD")
        self.assertEqual(result["receipt"]["assessment"]["decision"], BOUNDED)
        self.assertEqual(result["receipt"]["previous_receipt_digest"], GENESIS)
        self.assertEqual(verify_receipt(*self.inputs(), result["receipt"])["decision"], BOUNDED)
        self.assertEqual(len(read_receipts(self.database)), 1)

    def test_duplicate_receipt_preserves_identical_signature(self):
        first = self.store()
        second = self.store()
        self.assertEqual(second["status"], "DUPLICATE_UNCHANGED")
        self.assertEqual(first["receipt"], second["receipt"])
        self.assertEqual(len(read_receipts(self.database)), 1)

    def test_later_referee_change_cannot_rewrite_signed_local_history(self):
        self.store()
        source = self.inputs()
        source[11] = make_referee(source[8], source[10],
                                  self.keys["019-referee"], action="DECLINE")
        source[12] = None
        with self.assertRaises(InvalidWorld):
            self.store(source)
        self.assertEqual(read_receipts(self.database)[0]["assessment"]["decision"], BOUNDED)

    def test_recorder_cannot_be_referee_or_owner(self):
        for who in ("019-referee", "019-owner-selector"):
            with self.subTest(who=who), self.assertRaises(InvalidWorld):
                self.store(signer=self.keys[who])

    def test_corrupt_sqlite_record_fails_closed(self):
        self.store()
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE local_precedence_receipt SET receipt_json=?",
                       (json.dumps({"schema": "counterfeit"}),))
        with self.assertRaises(InvalidWorld):
            self.store()

    def test_public_only_receipt_forgery_or_effect_escalation_denied(self):
        r = self.store()["receipt"]
        fake = copy.deepcopy(r)
        fake["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.inputs(), fake)
        fake = copy.deepcopy(r)
        fake["assessment"]["native_relatte_receive"] = True
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.inputs(), fake)

    def test_cold_public_process_has_no_private_keys_or_journal(self):
        saved = self.store()["receipt"]
        case = self.inputs()
        values = list(case[0]) + list(case[1:]) + [saved]
        fields = PRIOR_NAMES + OTHER_NAMES
        with tempfile.TemporaryDirectory() as scratch:
            folder = Path(scratch)
            flags = []
            for name, value in zip(fields, values):
                path = folder / (name + ".json")
                path.write_text(json.dumps(value), encoding="utf-8")
                flags.extend(("--" + name, str(path)))
            cmd = [
                sys.executable,
                str(ROOT / "ghot" / "unheard_choir_referee.py"),
                "verify", *flags,
            ]
            run = subprocess.run(cmd, cwd=str(folder), text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout),
                             {"verified": True, "decision": BOUNDED})
            self.assertEqual(list(folder.glob("*.pem")), [])
            self.assertEqual(list(folder.glob("*.sqlite")), [])

    def test_standalone_demo_refusal_collision_and_archival_hold(self):
        result = demo()
        self.assertEqual(result["no_referee"], NO_REFEREE)
        self.assertEqual(result["signed_referee_declined"], REFUSED)
        self.assertEqual(result["independently_signed_epoch_collision"], EPOCH_COLLISION)
        self.assertEqual(result["referee_and_separate_owner_consented"], BOUNDED)
        self.assertTrue(result["old_source_fork_retained"])
        self.assertTrue(result["owner_local_receipt_durable"])
        self.assertTrue(result["cold_public_receipt_valid"])
        self.assertFalse(result["native_relatte_receive"])
        self.assertFalse(result["external_execution"])


if __name__ == "__main__":
    unittest.main()
