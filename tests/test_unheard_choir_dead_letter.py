#!/usr/bin/env python3
"""UNHEARD CHOIR 012: offline import, stale policy, signed receipt and cold replay."""
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
from unheard_choir_dead_letter import (  # noqa: E402
    HELD, EXPIRED, WRONG, NO_FORK, build_fixture, demo,
    make_parcel, make_local_pins, unpack, assess_parcel, import_once,
    verify_receipt, read_receipts, verify_history,
)

class DeadLetterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture, cls.original, cls.recipient_package, cls.pins, cls.keys = build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "recipient-custody.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def parcel(self):
        return copy.deepcopy(self.original)

    def received(self, *, parcel=None, pkg=None, pins=None, now=1001):
        return import_once(
            self.original if parcel is None else parcel,
            self.recipient_package if pkg is None else pkg,
            self.pins if pins is None else pins,
            self.keys["gossip-east"], self.db, now=now,
        )

    def test_signed_parcel_fork_is_receiver_local_hold(self):
        result = self.received()
        a = result["receipt"]["assessment"]
        self.assertEqual(result["status"], "RECEIPT_DURABLY_WRITTEN")
        self.assertEqual(a["decision"], HELD)
        self.assertFalse(a["native_relatte_receive"])
        self.assertFalse(a["native_relatte_admission"])
        self.assertFalse(a["external_execution"])

    def test_receiver_receipt_signed_by_its_independently_pinned_key(self):
        r = self.received()["receipt"]
        assessed = verify_receipt(self.original, self.recipient_package, self.pins, r)
        self.assertEqual(assessed, r["assessment"])
        self.assertEqual(r["local_index"], 0)
        self.assertEqual(r["previous_receipt_digest"],
                         digest({"domain": "ghot.unheard-choir-012-local-custody-genesis/v0"}))

    def test_duplicate_import_same_parcel_returns_same_receipt(self):
        first = self.received()
        second = self.received()
        self.assertEqual(second["status"], "DUPLICATE_RECEIPT_REPLAY")
        self.assertEqual(first["receipt"], second["receipt"])
        self.assertEqual(len(read_receipts(self.db)), 1)

    def test_same_signed_parcel_different_clock_replay_not_reclassified(self):
        self.received()
        with self.assertRaises(InvalidWorld):
            self.received(now=1051)
        self.assertEqual(len(read_receipts(self.db)), 1)

    def test_valid_expired_parcel_gets_locally_signed_rejection(self):
        res = self.received(now=1051)
        self.assertEqual(res["receipt"]["assessment"]["decision"], EXPIRED)
        self.assertEqual(verify_receipt(self.original, self.recipient_package,
                                        self.pins, res["receipt"])["decision"], EXPIRED)
        self.assertEqual(len(read_receipts(self.db)), 1)

    def test_expired_challenge_beyond_its_window_rejected_not_admitted(self):
        res = self.received(now=2000)
        self.assertEqual(res["receipt"]["assessment"]["decision"], EXPIRED)

    def test_source_signer_private_key_absent_from_portable_payload(self):
        j = json.dumps(self.original)
        self.assertNotIn("PRIVATE KEY", j)
        self.assertIn("ghot.unheard-choir-011", j)
        self.assertEqual(self.original["sender"], "west")
        self.assertEqual(self.original["recipient"], "east")

    def test_local_trust_roots_are_checked_against_parcel(self):
        common, policy, logroot, roster, root, envelope = unpack(self.original, self.pins)
        self.assertEqual(len(common), 17)
        self.assertEqual(envelope["recipient"], "east")
        self.assertEqual(self.pins["roster_digest"], digest(roster))
        self.assertEqual(self.pins["009_external_root"], logroot)

    def test_swapped_local_008_trust_root_refused(self):
        pins = copy.deepcopy(self.pins)
        pins["008_external_root"] = self.keys["gossip-west"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.received(pins=pins)

    def test_swapped_local_009_trust_root_refused(self):
        pins = copy.deepcopy(self.pins)
        pins["009_external_root"] = self.keys["gossip-west"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.received(pins=pins)

    def test_swapped_local_010_trust_root_refused(self):
        pins = copy.deepcopy(self.pins)
        pins["010_external_root"] = self.keys["owner"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.received(pins=pins)

    def test_unpinned_receiving_owner_private_key_denied(self):
        with self.assertRaises(InvalidWorld):
            import_once(self.original, self.recipient_package, self.pins,
                        self.keys["gossip-west"], self.db, now=1001)

    def test_cargo_must_not_authorize_substitution_of_local_pins(self):
        parcel = self.parcel()
        parcel["cargo"]["gossip_root"] = self.keys["owner"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.received(parcel=parcel)

    def test_extra_effect_permission_in_parcel_denied(self):
        p = self.parcel()
        p["native_relatte_admission"] = True
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_extra_effect_in_envelope_denied(self):
        p = self.parcel()
        p["cargo"]["011_envelope"]["effects"] = ["DO_SOMETHING"]
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_modified_signed_parcel_not_after_denied(self):
        p = self.parcel()
        p["simulated_not_after"] = 999
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_silent_added_evidence_field_denied(self):
        p = self.parcel()
        p["cargo"]["common_evidence"]["unauthorized"] = {}
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_changed_source_evidence_digest_denied(self):
        p = self.parcel()
        p["cargo_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_bad_sender_signature_denied(self):
        p = self.parcel()
        p["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_wrong_sender_identity_denied(self):
        p = self.parcel()
        p["sender"] = "east"
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_forged_destination_cannot_relabel_existing_011_envelope(self):
        p = self.parcel()
        p["recipient"] = "west"
        with self.assertRaises(InvalidWorld):
            self.received(parcel=p)

    def test_invalid_or_infinite_clock_values_rejected(self):
        for clock in (True, 1.5, -1, "tomorrow", None):
            with self.subTest(clock=clock), self.assertRaises(InvalidWorld):
                assess_parcel(self.original, self.recipient_package, self.pins, now=clock)

    def test_local_package_not_found_in_parcel_and_cannot_be_swapped(self):
        p = copy.deepcopy(self.recipient_package)
        p["observations"][0]["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            self.received(pkg=p)

    def test_modified_local_audit_roster_denied(self):
        p = copy.deepcopy(self.recipient_package)
        p["checkpoints"][0]["head"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.received(pkg=p)

    def test_unrecognized_local_owner_site_denied(self):
        pins = copy.deepcopy(self.pins)
        pins["recipient_site"] = "other"
        with self.assertRaises(InvalidWorld):
            self.received(pins=pins)

    def test_forged_local_signature_rejected_on_cold_verify(self):
        receipt = self.received()["receipt"]
        receipt["signature"] = "fraud"
        with self.assertRaises(InvalidWorld):
            verify_receipt(self.original, self.recipient_package, self.pins, receipt)

    def test_receipt_cannot_promote_held_custody_to_relatte_admission(self):
        receipt = self.received()["receipt"]
        receipt["assessment"]["native_relatte_admission"] = True
        with self.assertRaises(InvalidWorld):
            verify_receipt(self.original, self.recipient_package, self.pins, receipt)

    def test_receipt_with_new_digest_is_not_valid_authority(self):
        receipt = self.received()["receipt"]
        receipt["assessment"]["parcel_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            verify_receipt(self.original, self.recipient_package, self.pins, receipt)

    def test_sqlite_copy_remains_verifiable_after_restart(self):
        self.received()
        after_restart = read_receipts(self.db)
        self.assertEqual(len(after_restart), 1)
        verify_history(after_restart, self.original, self.recipient_package, self.pins)

    def test_modified_sqlite_record_prevents_replay_write(self):
        self.received()
        import sqlite3
        with sqlite3.connect(str(self.db)) as db:
            db.execute("UPDATE custody SET receipt_json=? WHERE local_index=0",
                       (json.dumps({"schema": "forged"}),))
        with self.assertRaises(InvalidWorld):
            self.received()

    def test_receiver_independent_process_no_sender_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for name, data in (("parcel", self.original),
                               ("local-package", self.recipient_package),
                               ("pins", self.pins)):
                (folder / (name + ".json")).write_text(
                    json.dumps(data, sort_keys=True), encoding="utf-8")
            # Recipient provisions its private key as a local file, NEVER via parcel.
            receiver_key = folder / "east-private.pem"
            receiver_key.write_bytes((Path(self.fixture.name) / "gossip-east.pem").read_bytes())
            cli = [sys.executable, str(ROOT / "ghot" / "unheard_choir_dead_letter.py")]
            common = [
                "--parcel", str(folder / "parcel.json"),
                "--local-package", str(folder / "local-package.json"),
                "--pins", str(folder / "pins.json"),
            ]
            db = folder / "imported.sqlite"
            run = subprocess.run(cli + ["import"] + common + [
                "--receiver-key", str(receiver_key), "--receiver-db", str(db),
                "--now", "1001",
            ], capture_output=True, text=True, cwd=str(folder))
            self.assertEqual(run.returncode, 0, run.stderr)
            imported = json.loads(run.stdout)
            self.assertEqual(imported["receipt"]["assessment"]["decision"], HELD)
            receiver_key.unlink()
            receipt_path = folder / "receipt.json"
            receipt_path.write_text(json.dumps(imported["receipt"]), encoding="utf-8")
            verified = subprocess.run(cli + ["verify"] + common + [
                "--receipt", str(receipt_path),
            ], capture_output=True, text=True, cwd=str(folder))
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout), {"verified": True, "decision": HELD})
            self.assertEqual(len(read_receipts(db)), 1)
            self.assertFalse(receiver_key.exists())

    def test_sender_cli_exports_standalone_public_parcel(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            cargo = self.original["cargo"]
            fields = {
                "source-evidence": cargo["common_evidence"],
                "log-policy": cargo["log_policy"],
                "log-root": cargo["log_root"],
                "gossip-roster": cargo["gossip_roster"],
                "gossip-root": cargo["gossip_root"],
                "sender-envelope": cargo["011_envelope"],
            }
            argv = []
            for field, data in fields.items():
                file = folder / (field + ".json")
                file.write_text(json.dumps(data), encoding="utf-8")
                argv.extend(("--" + field, str(file)))
            # Existing west signing key is kept on sender side only.
            west_key = Path(self.fixture.name) / "gossip-west.pem"
            outgoing = folder / "outgoing.json"
            cli = [sys.executable, str(ROOT / "ghot" / "unheard_choir_dead_letter.py")]
            result = subprocess.run(cli + ["export"] + argv + [
                "--sender-key", str(west_key),
                "--not-after", "1050", "--nonce", "b" * 32,
                "--output", str(outgoing),
            ], capture_output=True, text=True, cwd=str(folder))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "EXPORTED")
            self.assertTrue(outgoing.is_file())
            self.assertNotIn("PRIVATE KEY", outgoing.read_text())
            parcel = json.loads(outgoing.read_text())
            a = assess_parcel(parcel, self.recipient_package, self.pins, now=1001)
            self.assertEqual(a["decision"], HELD)
            self.assertEqual(a["recipient_site"], "east")

    def test_export_wont_overwrite_existing_parcel(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            outgoing = folder / "already-exists.json"
            outgoing.write_text("DO NOT DELETE")
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_dead_letter.py"),
                   "export", "--output", str(outgoing)]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(outgoing.read_text(), "DO NOT DELETE")

    def test_demo_owner_local_receipt_and_dedupe(self):
        result = demo()
        self.assertTrue(result["portable_public_parcel"])
        self.assertTrue(result["sender_private_key_absent_from_parcel"])
        self.assertEqual(result["import_decision"], HELD)
        self.assertEqual(result["new_receipt"], "RECEIPT_DURABLY_WRITTEN")
        self.assertEqual(result["duplicate_import"], "DUPLICATE_RECEIPT_REPLAY")
        self.assertEqual(result["recipient_journal_entries"], 1)
        self.assertTrue(result["cold_public_verification"])
        self.assertFalse(result["native_relatte_receive"])
        self.assertFalse(result["external_execution"])


if __name__ == "__main__":
    unittest.main()
