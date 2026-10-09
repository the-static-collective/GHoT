"""ORSHOT-002 signed print staging: local cryptographic tests."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ghot"))
from physical_receipt_router import demo, stage, verify_bundle
from relatte_identity import IdentityKey, sign_receipt

PDF = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n"


class PhysicalReceiptRouterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.crossing, self.receipt, self.source, self.receiver = demo(
            PDF, self.root / "keys"
        )

    def stage(self, artifact=PDF, crossing=None, receipt=None, source=None, receiver=None):
        return stage(
            crossing or self.crossing, receipt or self.receipt, artifact,
            source or self.source, receiver or self.receiver, self.root / "spool"
        )

    def test_signed_round_trip_and_idempotence(self):
        one = self.stage()
        self.assertEqual(one, self.stage())
        self.assertEqual(len(list((self.root / "spool").iterdir())), 1)
        result = verify_bundle(one, self.source, self.receiver)
        self.assertEqual(result["status"], "HELD")
        self.assertFalse(result["physical_output_claimed"])
        self.assertFalse(result["device_selected"])

    def test_byte_flip_rejected(self):
        with self.assertRaisesRegex(ValueError, "do not match"):
            self.stage(artifact=PDF + b"tampered")

    def test_rewritten_receipt_rejected(self):
        altered = copy.deepcopy(self.receipt)
        altered["extensions"]["ghot_print"]["physical_deposit_count"] = 100
        with self.assertRaisesRegex(ValueError, "receipt signature"):
            self.stage(receipt=altered)

    def test_wrong_source_trust_pin_rejected(self):
        with self.assertRaisesRegex(ValueError, "trusted source pin"):
            self.stage(source=self.receiver)

    def test_wrong_receiver_trust_pin_rejected(self):
        with self.assertRaisesRegex(ValueError, "receipt signature"):
            self.stage(receiver=self.source)

    def test_crossing_mismatch_rejected(self):
        other_crossing, _, _, _ = demo(PDF, self.root / "keys")
        with self.assertRaisesRegex(ValueError, "different crossing"):
            self.stage(crossing=other_crossing)

    def test_no_real_deposit_claim_accepted(self):
        altered = copy.deepcopy(self.receipt)
        altered["semantic_effect"] = "penny-deposited"
        altered = sign_receipt(
            altered, IdentityKey(self.root / "keys" / "receiver-p256.pem")
        )
        with self.assertRaisesRegex(ValueError, "may not assert"):
            self.stage(receipt=altered)

    def test_tamper_on_disk_detected(self):
        one = self.stage()
        (one / "artifact.pdf").write_bytes(PDF + b"extra")
        with self.assertRaisesRegex(ValueError, "do not match"):
            verify_bundle(one, self.source, self.receiver)
        with self.assertRaisesRegex(ValueError, "do not match"):
            self.stage()

    def test_bad_extension_rejected_even_if_signed(self):
        altered = copy.deepcopy(self.receipt)
        altered["extensions"]["ghot_print"]["physical_deposit_count"] = 1
        altered = sign_receipt(
            altered, IdentityKey(self.root / "keys" / "receiver-p256.pem")
        )
        with self.assertRaisesRegex(ValueError, "explicit zero"):
            self.stage(receipt=altered)


if __name__ == "__main__":
    unittest.main()
