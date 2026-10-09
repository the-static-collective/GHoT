"""MAIL-002: recipient ciphertext, untrusted relay, signed local print door."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ghot"))

from postemahhn_mail import register, digest
from postemahhn_sealed_mail import (
    OpaqueRelay, accept_at_station, fetch_http, make_sealed,
    open_sealed, relay_handler, send_http, stage_release, verify_sealed, approved_relay_bind,
)
from relatte_identity import IdentityKey, sign_receipt

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


class TravelingPostOfficeTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.owner = IdentityKey.load_or_create(self.root / "keys" / "owner.pem")
        self.sender = IdentityKey.load_or_create(self.root / "keys" / "sender.pem")
        self.stranger = IdentityKey.load_or_create(self.root / "keys" / "stranger.pem")
        self.recipient = register(self.root / "local-owner", self.owner)
        self.parcel = make_sealed(PDF, self.recipient, self.sender)
        self.spool = self.root / "print-station"

    def authorized(self, station="kiosk-001", seconds=900):
        return stage_release(self.parcel, self.owner, station, seconds)

    def stage(self, release=None, pdf=PDF, station="kiosk-001", pin=None):
        return accept_at_station(
            self.parcel, pdf, release or self.authorized(), station,
            pin or self.recipient["address"], self.spool,
        )

    def test_private_bytes_not_in_relay_object(self):
        serialized = json.dumps(self.parcel, sort_keys=True)
        self.assertNotIn("%PDF-1.4", serialized)
        self.assertNotIn("Catalog", serialized)
        self.assertNotIn(digest(PDF), serialized)
        self.assertEqual(verify_sealed(self.parcel)[0], self.recipient["address"])
        self.assertEqual(open_sealed(self.parcel, self.owner), PDF)

    def test_new_encryption_is_randomized(self):
        second = make_sealed(PDF, self.recipient, self.sender)
        self.assertNotEqual(second["sealed"]["ciphertext"], self.parcel["sealed"]["ciphertext"])
        self.assertNotEqual(second["crossing"]["crossing_id"], self.parcel["crossing"]["crossing_id"])

    def test_wrong_recipient_private_key_denied(self):
        with self.assertRaisesRegex(ValueError, "does not own address"):
            open_sealed(self.parcel, self.stranger)

    def test_ciphertext_mutation_rejected_by_sender_crossing(self):
        altered = copy.deepcopy(self.parcel)
        altered["sealed"]["ciphertext"] = altered["sealed"]["ciphertext"][:-2] + "AA"
        with self.assertRaises(ValueError):
            verify_sealed(altered)

    def test_swapped_recipient_card_rejected(self):
        altered = copy.deepcopy(self.parcel)
        altered["recipient"]["public_key"] = self.stranger.public_jwk()
        with self.assertRaisesRegex(ValueError, "contact card address"):
            verify_sealed(altered)

    def test_crossing_sender_change_rejected(self):
        altered = copy.deepcopy(self.parcel)
        altered["crossing"]["source_world"] = "intruder"
        with self.assertRaisesRegex(ValueError, "invalid sender crossing signature"):
            verify_sealed(altered)

    def test_relay_opaque_storage_and_deduplication(self):
        relay = OpaqueRelay(self.root / "relay-node")
        addr, token = relay.put(self.parcel)
        self.assertEqual((addr, token), relay.put(self.parcel))
        self.assertEqual(relay.list_ids(addr), [token])
        self.assertEqual(relay.get(addr, token), self.parcel)
        disk = (self.root / "relay-node" / addr / (token + ".json")).read_bytes()
        self.assertNotIn(b"%PDF-", disk)
        self.assertNotIn(PDF, disk)

    def test_http_between_two_independent_nodes(self):
        relay = OpaqueRelay(self.root / "relay-node")
        server = ThreadingHTTPServer(("127.0.0.1", 0), relay_handler(relay))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = "http://127.0.0.1:" + str(server.server_port)
            received = send_http(url, self.parcel)
            self.assertEqual(received["state"], "STORED_OPAQUE")
            fetched = fetch_http(url, self.recipient["address"])
            self.assertEqual(fetched, [self.parcel])
            self.assertEqual(open_sealed(fetched[0], self.owner), PDF)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_owner_signature_required_for_print_door(self):
        signed = self.authorized()
        wrong = sign_receipt(copy.deepcopy(signed), self.stranger)
        with self.assertRaisesRegex(ValueError, "release signature"):
            self.stage(wrong)

    def test_named_station_and_digest_are_enforced(self):
        signed = self.authorized()
        with self.assertRaisesRegex(ValueError, "print release boundaries"):
            self.stage(signed, pdf=PDF + b"other")
        with self.assertRaisesRegex(ValueError, "print release boundaries"):
            self.stage(signed, station="different-kiosk")
        with self.assertRaisesRegex(ValueError, "trusted address mismatch"):
            self.stage(signed, pin="pm1-" + "a" * 40)

    def test_valid_print_door_only_stages_held_bundle(self):
        signed = self.authorized()
        bundle = self.stage(signed)
        self.assertEqual(bundle, self.stage(signed))
        self.assertEqual(len(list(self.spool.iterdir())), 1)
        manifest = json.loads((bundle / "manifest.json").read_text())
        self.assertEqual(manifest["state"], "HELD")
        self.assertFalse(manifest["physical_print_claimed"])
        self.assertEqual((bundle / "document.pdf").read_bytes(), PDF)

    def test_release_tampering_detected(self):
        signed = self.authorized()
        signed["extensions"]["postemahhn_sealed_release"]["artifact_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "release signature"):
            self.stage(signed)

    def test_expiry_rejected(self):
        signed = self.authorized(seconds=1)
        with self.assertRaisesRegex(ValueError, "expired"):
            accept_at_station(self.parcel, PDF, signed, "kiosk-001",
                              self.recipient["address"], self.spool,
                              now=datetime.now(timezone.utc) + timedelta(minutes=2))

    def test_unowned_address_cannot_make_release(self):
        with self.assertRaisesRegex(ValueError, "does not own address"):
            stage_release(self.parcel, self.stranger, "kiosk-001")

    def test_unsigned_physical_print_claim_denied(self):
        signed = self.authorized()
        signed["extensions"]["postemahhn_sealed_release"]["physical_print_claimed"] = True
        signed = sign_receipt(signed, self.owner)
        with self.assertRaisesRegex(ValueError, "print release boundaries"):
            self.stage(signed)

    def test_local_relay_only_exposes_opaque_data(self):
        relay = OpaqueRelay(self.root / "relay-node")
        relay.put(self.parcel)
        for f in (self.root / "relay-node").rglob("*"):
            if f.is_file():
                self.assertNotIn(b"%PDF-", f.read_bytes())


    def test_nonlocal_relay_requires_explicit_opt_in(self):
        self.assertEqual(approved_relay_bind("127.0.0.1", False), "127.0.0.1")
        with self.assertRaisesRegex(ValueError, "explicit --allow-insecure-lan"):
            approved_relay_bind("0.0.0.0", False)
        self.assertEqual(approved_relay_bind("0.0.0.0", True), "0.0.0.0")


if __name__ == "__main__":
    unittest.main()
