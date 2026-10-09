#!/usr/bin/env python3
"""UNHEARD CHOIR 013 — hostile historical signature / new incarnation boundary."""
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
from unheard_choir_reincarnation import (  # noqa: E402
    ACTION, ARCHIVED, GENESIS, HOLD,
    assess, build_fixture, demo, import_once, make_archive_grant,
    make_incarnation, read_receipts, verify_incarnation, verify_receipt,
)


class ReconstitutedReceiverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture, cls.parcel, cls.old_local, cls.old_pins, cls.incarnation, cls.current_pin, cls.grant, cls.keys = build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "owner-local.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def inputs(self):
        return [copy.deepcopy(x) for x in (
            self.parcel, self.old_local, self.old_pins,
            self.incarnation, self.current_pin, self.grant,
        )]

    def assess_(self, args=None, *, grant=True, now=1100):
        args = self.inputs() if args is None else args
        return assess(*args[:5], args[5] if grant else None, now=now)

    def import_(self, args=None, *, grant=True, now=1100, signer=None):
        args = self.inputs() if args is None else args
        return import_once(
            *args[:5], args[5] if grant else None,
            self.keys["east-reconstituted"] if signer is None else signer,
            self.db, now=now,
        )

    def test_historically_valid_parcel_expires_before_new_owner_epoch(self):
        r = self.assess_(grant=False)
        self.assertEqual(r["original_parcel_not_after"], 1050)
        self.assertEqual(r["simulated_receiver_clock"], 1100)
        self.assertTrue(r["historical_parcel_signatures_verified"])
        self.assertEqual(r["decision"], HOLD)

    def test_old_address_not_new_authority_without_grant(self):
        r = self.assess_(grant=False)
        self.assertFalse(r["old_receiver_identity_has_current_grants"])
        self.assertFalse(r["historical_expiry_extends_current_authority"])
        self.assertFalse(r["forward_or_redirect_permitted"])
        self.assertFalse(r["native_relatte_receive"])
        self.assertEqual(r["authority"], "NONE")

    def test_explicit_new_owner_grant_archives_history_only(self):
        r = self.assess_()
        self.assertEqual(r["decision"], ARCHIVED)
        self.assertFalse(r["archived_evidence_is_native_admission"])
        self.assertFalse(r["forward_or_redirect_permitted"])
        self.assertEqual(r["effects"], [])
        self.assertFalse(r["external_execution"])

    def test_historical_witnessed_fork_remains_verifiable(self):
        r = self.assess_()
        self.assertTrue(r["historical_parcel_signatures_verified"])
        self.assertEqual(len(r["historic_fork_assessment_digest"]), 64)

    def test_new_incarnation_key_distinct_from_old(self):
        self.assertNotEqual(self.current_pin, self.old_pins["recipient_public_key"])
        self.assertEqual(self.incarnation["incarnation_epoch"], 2)
        self.assertEqual(self.incarnation["logical_address"], "east")

    def test_genuine_new_epoch_and_pinset_validate(self):
        ancestors = verify_incarnation(self.parcel, self.old_pins,
                                       self.incarnation, self.current_pin)
        self.assertEqual(len(ancestors), 6)

    def test_old_private_key_cannot_sign_new_current_receipt(self):
        with self.assertRaises(InvalidWorld):
            self.import_(signer=self.keys["gossip-east"])
        self.assertFalse(self.db.exists())

    def test_previous_owner_cannot_grant_archival_permissions(self):
        with self.assertRaises(InvalidWorld):
            make_archive_grant(self.parcel, self.incarnation,
                               self.keys["gossip-east"], not_after=5000)

    def test_current_new_owner_must_be_independently_pinned(self):
        a = self.inputs()
        a[4] = self.keys["gossip-east"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_sender_supplied_new_key_does_not_replace_current_pin(self):
        a = self.inputs()
        a[3]["new_owner_public_key"] = self.keys["gossip-west"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_owner_self_signed_epoch_is_not_current_authority_if_unpinned(self):
        a = self.inputs()
        fake = self.keys["gossip-west"]
        a[3] = make_incarnation(a[0], a[2], fake, epoch=3)
        a[5] = make_archive_grant(a[0], a[3], fake, not_after=5000)
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_reusing_old_owner_identity_for_new_incarnation_denied(self):
        with self.assertRaises(InvalidWorld):
            make_incarnation(self.parcel, self.old_pins,
                             self.keys["gossip-east"], epoch=2)

    def test_epoch_one_cannot_be_new_incarnation(self):
        with self.assertRaises(InvalidWorld):
            make_incarnation(self.parcel, self.old_pins,
                             self.keys["east-reconstituted"], epoch=1)

    def test_mutated_signed_epoch_refused(self):
        a = self.inputs()
        a[3]["incarnation_epoch"] = 4
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_epoch_boolean_cannot_bypass_integer_validation(self):
        a = self.inputs()
        a[3]["incarnation_epoch"] = True
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_changed_old_pins_digest_refused(self):
        a = self.inputs()
        a[3]["old_pins_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_modified_historical_parcel_digest_refused(self):
        a = self.inputs()
        a[3]["historical_parcel_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_forged_new_owner_incarnation_signature_refused(self):
        a = self.inputs()
        a[3]["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_forged_archival_grant_signature_refused(self):
        a = self.inputs()
        a[5]["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_archival_grant_cannot_expand_to_forwarding(self):
        a = self.inputs()
        a[5]["action"] = "FORWARD_AND_ADMIT"
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_archival_grant_cannot_grant_native_relatte_effect(self):
        a = self.inputs()
        a[5]["native_relatte_crossing"] = True
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_archival_grant_does_not_apply_to_another_parcel(self):
        a = self.inputs()
        a[5]["historical_parcel_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_archival_grant_bound_to_new_epoch(self):
        a = self.inputs()
        a[5]["epoch"] = 99
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_expired_new_owner_grant_does_not_archive(self):
        a = self.inputs()
        a[5] = make_archive_grant(a[0], a[3],
                                  self.keys["east-reconstituted"], not_after=1099)
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_no_grant_still_issues_signed_hold_at_late_clock(self):
        first = self.import_(grant=False, now=5001)
        self.assertEqual(first["status"], "SIGNED_HISTORY_RECEIPT_WRITTEN")
        self.assertEqual(first["receipt"]["assessment"]["decision"], HOLD)

    def test_boolean_clock_refused(self):
        for clock in (True, -1, 1.25, "1100", None):
            with self.subTest(now=clock), self.assertRaises(InvalidWorld):
                self.assess_(now=clock)

    def test_older_signed_parcel_cannot_be_retargeted_to_new_logical_address(self):
        a = self.inputs()
        a[0]["recipient"] = "west"
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_historical_evidence_modification_refused(self):
        a = self.inputs()
        a[0]["cargo"]["011_envelope"]["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_receiver_must_have_independent_historical_local_package(self):
        a = self.inputs()
        a[1]["site"] = "west"
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_source_witness_forgery_refused_even_as_historical_evidence(self):
        a = self.inputs()
        a[1]["observations"][0]["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            self.assess_(a)

    def test_signed_hold_receipt_durable(self):
        result = self.import_(grant=False)
        r = result["receipt"]
        self.assertEqual(result["status"], "SIGNED_HISTORY_RECEIPT_WRITTEN")
        self.assertEqual(r["previous_receipt_digest"], GENESIS)
        self.assertEqual(r["local_index"], 0)
        self.assertEqual(len(read_receipts(self.db)), 1)
        self.assertEqual(verify_receipt(*self.inputs()[:5], None, r)["decision"], HOLD)

    def test_signed_archive_receipt_durable_without_granting_admission(self):
        result = self.import_()
        receipt = result["receipt"]
        self.assertEqual(receipt["assessment"]["decision"], ARCHIVED)
        self.assertEqual(verify_receipt(*self.inputs()[:5], self.grant,
                                        receipt)["decision"], ARCHIVED)
        self.assertFalse(receipt["assessment"]["native_relatte_receive"])

    def test_duplicate_import_same_disposition_returns_same_bytes(self):
        a = self.import_()
        b = self.import_()
        self.assertEqual(a["receipt"], b["receipt"])
        self.assertEqual(b["status"], "DUPLICATE_UNCHANGED")
        self.assertEqual(len(read_receipts(self.db)), 1)

    def test_late_grant_cannot_reclassify_old_held_history(self):
        self.import_(grant=False)
        with self.assertRaises(InvalidWorld):
            self.import_(grant=True)
        self.assertEqual(read_receipts(self.db)[0]["assessment"]["decision"], HOLD)

    def test_changed_local_clock_cannot_reclassify_signed_receipt(self):
        self.import_(grant=False, now=1100)
        with self.assertRaises(InvalidWorld):
            self.import_(grant=False, now=1200)

    def test_forged_owner_local_receipt_signature_refused(self):
        receipt = self.import_()["receipt"]
        receipt["signature"] = "bogus"
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.inputs()[:5], self.grant, receipt)

    def test_forged_receipt_cannot_claim_execution(self):
        receipt = self.import_()["receipt"]
        receipt["assessment"]["external_execution"] = True
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.inputs()[:5], self.grant, receipt)

    def test_mutated_stored_journal_fails_closed(self):
        self.import_()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE owner_history SET receipt_json=? WHERE local_index=0",
                       (json.dumps({"schema": "fake"}),))
        with self.assertRaises(InvalidWorld):
            self.import_()

    def test_wrong_new_owner_key_file_cannot_sign(self):
        self.assertFalse(self.db.exists())
        with self.assertRaises(InvalidWorld):
            self.import_(signer=self.keys["gossip-west"])

    def test_explicit_scope_not_device_execution(self):
        r = self.assess_()
        self.assertEqual(r["authority"], "NONE")
        self.assertEqual(r["effects"], [])
        self.assertFalse(r["old_receiver_identity_has_current_grants"])
        self.assertFalse(r["forward_or_redirect_permitted"])

    def test_subprocess_import_and_keyless_cold_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)
            args = []
            names = ("parcel", "historic-local-package", "historic-pins",
                     "incarnation", "current-owner-pin", "archive-grant")
            for name, data in zip(names, self.inputs()):
                path = f / (name + ".json")
                path.write_text(json.dumps(data), encoding="utf-8")
                args.extend(("--" + name, str(path)))
            key = f / "reconstituted.pem"
            key.write_bytes((Path(self.fixture.name) / "east-reconstituted.pem").read_bytes())
            db = f / "reborn.sqlite"
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_reincarnation.py")]
            imported = subprocess.run(cmd + ["import"] + args + [
                "--new-owner-key", str(key), "--receiver-db", str(db),
                "--now", "1100"], cwd=str(f), capture_output=True, text=True)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            receipt = json.loads(imported.stdout)["receipt"]
            self.assertEqual(receipt["assessment"]["decision"], ARCHIVED)
            key.unlink()
            receipt_path = f / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            cold = subprocess.run(cmd + ["verify"] + args + [
                "--receipt", str(receipt_path)], cwd=str(f), capture_output=True, text=True)
            self.assertEqual(cold.returncode, 0, cold.stderr)
            self.assertEqual(json.loads(cold.stdout), {"verified": True, "decision": ARCHIVED})
            self.assertFalse(key.exists())

    def test_standalone_demo_history_survives_owner_reconstitution(self):
        result = demo()
        self.assertEqual(result["new_incarnation_epoch"], 2)
        self.assertTrue(result["new_receiver_key_distinct"])
        self.assertEqual(result["no_grant_decision"], HOLD)
        self.assertEqual(result["owner_archival_decision"], ARCHIVED)
        self.assertTrue(result["cold_public_receipt_verifies"])
        self.assertTrue(result["signed_receipts_persisted"])
        self.assertFalse(result["no_native_relatte_receipt"] is False)
        self.assertTrue(result["no_forwarding"])
        self.assertTrue(result["no_execution"])


if __name__ == "__main__":
    unittest.main()
