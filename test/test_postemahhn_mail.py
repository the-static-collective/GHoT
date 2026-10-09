"""PostEmahh'n MAIL-001: no unconsented paper and no spoofed delivery."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ghot"))

from postemahhn_mail import (
    address, authorize_export, compose, contact_for_key, export_pdf, inbox,
    load_json,
    receive, register, release, verify_parcel, write_json,
)
from relatte_identity import IdentityKey, sign_receipt

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


class AddressedMailTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.station = self.root / "mail-station"
        self.sender = IdentityKey.load_or_create(self.root / "secrets" / "sender.pem")
        self.owner = IdentityKey.load_or_create(self.root / "secrets" / "owner.pem")
        self.other = IdentityKey.load_or_create(self.root / "secrets" / "other.pem")
        self.contact = register(self.station, self.owner)
        self.parcel = compose(PDF, self.contact, self.sender, self.root / "parcel")

    def delivered(self):
        return receive(self.station, self.parcel)

    def test_address_is_public_key_bound(self):
        self.assertEqual(self.contact["address"], address(self.owner.public_jwk()))
        self.assertNotEqual(self.contact["address"], address(self.other.public_jwk()))
        self.assertEqual(self.contact, contact_for_key(self.owner))

    def test_sealed_send_receive_and_repeat_do_not_print(self):
        held = self.delivered()
        self.assertEqual(held, self.delivered())
        listing = inbox(self.station, self.owner)
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["state"], "HELD")
        self.assertFalse((self.root / "output").exists())

    def test_mismatched_mailbox_address_fails(self):
        fake = copy.deepcopy(self.contact)
        fake["public_key"] = self.other.public_jwk()
        write_json(self.parcel / "recipient.json", fake)
        with self.assertRaisesRegex(ValueError, "address/public-key mismatch"):
            self.delivered()

    def test_tampered_pdf_rejected(self):
        (self.parcel / "document.pdf").write_bytes(PDF + b"tamper")
        with self.assertRaisesRegex(ValueError, "PDF does not match"):
            self.delivered()

    def test_crossing_signature_rejected_if_changed(self):
        crossing = load_json(self.parcel / "crossing.json")
        crossing["requested_effect"]["recipient_address"] = "pm1-evil"
        write_json(self.parcel / "crossing.json", crossing)
        with self.assertRaisesRegex(ValueError, "invalid reLATTE source crossing"):
            self.delivered()

    def test_receiver_cannot_be_spoofed(self):
        self.delivered()
        cid = inbox(self.station, self.owner)[0]["crossing_id"]
        with self.assertRaisesRegex(ValueError, "owner/address/crossing mismatch"):
            release(self.station, self.other, cid, "station-1")

    def test_release_is_station_bound_and_only_exports_pdf(self):
        self.delivered()
        cid = inbox(self.station, self.owner)[0]["crossing_id"]
        signed = release(self.station, self.owner, cid, "library-station-001")
        with self.assertRaisesRegex(ValueError, "wrong release station"):
            export_pdf(self.station, signed, "other-station", self.root / "output")
        output = export_pdf(self.station, signed, "library-station-001", self.root / "output")
        self.assertEqual(output.read_bytes(), PDF)
        self.assertEqual(output, export_pdf(self.station, signed, "library-station-001", self.root / "output"))
        self.assertNotIn("print", output.name.lower())  # proof of export only

    def test_fake_signature_rejected(self):
        self.delivered()
        cid = inbox(self.station, self.owner)[0]["crossing_id"]
        signed = release(self.station, self.owner, cid, "library-station-001")
        signed["extensions"]["postemahhn_release"]["station_id"] = "evil"
        with self.assertRaisesRegex(ValueError, "invalid recipient release signature"):
            export_pdf(self.station, signed, "evil", self.root / "output")

    def test_other_signer_cannot_release(self):
        self.delivered()
        cid = inbox(self.station, self.owner)[0]["crossing_id"]
        signed = release(self.station, self.owner, cid, "library-station-001")
        forged = copy.deepcopy(signed)
        forged = sign_receipt(forged, self.other)
        with self.assertRaisesRegex(ValueError, "invalid recipient release signature"):
            export_pdf(self.station, forged, "library-station-001", self.root / "output")

    def test_expired_release_denied(self):
        self.delivered()
        cid = inbox(self.station, self.owner)[0]["crossing_id"]
        signed = release(self.station, self.owner, cid, "library-station-001", 1)
        future = datetime.now(timezone.utc) + timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "expired or invalid"):
            authorize_export(self.station, signed, "library-station-001", now=future)

    def test_different_destination_file_cannot_be_overwritten(self):
        self.delivered()
        cid = inbox(self.station, self.owner)[0]["crossing_id"]
        signed = release(self.station, self.owner, cid, "library-station-001")
        file = export_pdf(self.station, signed, "library-station-001", self.root / "output")
        file.write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "existing print-ready file differs"):
            export_pdf(self.station, signed, "library-station-001", self.root / "output")

    def test_release_cannot_claim_hardware_printing(self):
        self.delivered()
        cid = inbox(self.station, self.owner)[0]["crossing_id"]
        signed = release(self.station, self.owner, cid, "library-station-001")
        signed["extensions"]["postemahhn_release"]["physical_print_claimed"] = True
        signed = sign_receipt(signed, self.owner)
        with self.assertRaisesRegex(ValueError, "cannot claim physical printing"):
            export_pdf(self.station, signed, "library-station-001", self.root / "output")

    def test_deliver_requires_registered_mailbox(self):
        (self.station / "addresses" / (self.contact["address"]+".json")).unlink()
        with self.assertRaisesRegex(ValueError, "not registered"):
            self.delivered()


if __name__ == "__main__":
    unittest.main()
