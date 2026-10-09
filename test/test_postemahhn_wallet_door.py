"""MAIL-003 wallet-key authority may stage, never spend or print."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ghot"))

from postemahhn_mail import contact_for_key, digest
from postemahhn_sealed_mail import make_sealed, stage_release
from postemahhn_wallet_door import (
    approve, issue_request, policy_for, policy_id, request_id,
    stage_via_wallet_door, verify_approvals, verify_request,
)
from relatte_identity import IdentityKey

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


class WalletDoorTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        def key(label):
            return IdentityKey.load_or_create(self.root / "keys" / (label + ".pem"))
        self.owner = key("owner")
        self.guardian = key("guardian")
        self.attacker = key("attacker")
        self.station = key("station")
        self.another_station = key("fake-station")
        self.sender = key("sender")
        self.policy = policy_for(self.owner.public_jwk())
        self.parcel = make_sealed(PDF, contact_for_key(self.owner), self.sender)
        self.mail_release = stage_release(self.parcel, self.owner, "kiosk-001")
        self.issued = self.root / "door" / "issued"
        self.req = issue_request(
            self.station, "kiosk-001", self.policy,
            self.parcel["crossing"]["crossing_id"], digest(PDF), self.issued,
        )

    def permit(self, role="owner", signer=None, policy=None, consent=True):
        return approve(
            self.req, policy or self.policy, signer or self.owner,
            role, self.station.public_jwk(), explicit_user_consent=consent,
        )

    def stage(self, approvals, policy=None, request=None, data=PDF, station=None):
        return stage_via_wallet_door(
            request or self.req, approvals, policy or self.policy,
            station or self.station, self.issued, self.parcel, data,
            self.mail_release, self.root / "spool",
        )

    def test_owner_signature_and_local_release_stage_held(self):
        job, receipt = self.stage([self.permit()])
        self.assertEqual((job / "document.pdf").read_bytes(), PDF)
        self.assertEqual(receipt["semantic_effect"], "none")
        self.assertEqual(receipt["extensions"]["postemahhn_wallet_door"]["state"], "HELD")
        self.assertFalse(receipt["extensions"]["postemahhn_wallet_door"]["physical_print_claimed"])
        self.assertFalse(receipt["extensions"]["postemahhn_wallet_door"]["asset_transfer_claimed"])

    def test_wallet_approval_is_one_use(self):
        sign = self.permit()
        self.stage([sign])
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self.stage([sign])
        self.assertEqual(len(list((self.root / "spool").iterdir())), 1)

    def test_user_consent_required_at_signing_door(self):
        with self.assertRaisesRegex(ValueError, "explicitly approve"):
            self.permit(consent=False)

    def test_guardian_two_keys_required(self):
        policy = policy_for(self.owner.public_jwk(), self.guardian.public_jwk())
        request = issue_request(
            self.station, "kiosk-001", policy,
            self.parcel["crossing"]["crossing_id"], digest(PDF), self.issued,
        )
        self.req = request
        self.policy = policy
        owner = self.permit()
        with self.assertRaisesRegex(ValueError, "missing independent"):
            self.stage([owner])
        guardian = self.permit(role="guardian", signer=self.guardian)
        job, receipt = self.stage([guardian, owner])
        self.assertTrue(job.is_dir())
        self.assertEqual(receipt["extensions"]["postemahhn_wallet_door"]["approved_roles"],
                         ["guardian", "owner"])

    def test_signer_and_guardian_must_be_independent(self):
        with self.assertRaisesRegex(ValueError, "independent"):
            policy_for(self.owner.public_jwk(), self.owner.public_jwk())

    def test_fake_guardian_denied(self):
        policy = policy_for(self.owner.public_jwk(), self.guardian.public_jwk())
        request = issue_request(
            self.station, "kiosk-001", policy,
            self.parcel["crossing"]["crossing_id"], digest(PDF), self.issued,
        )
        with self.assertRaisesRegex(ValueError, "not trusted"):
            approve(request, policy, self.attacker, "guardian",
                    self.station.public_jwk(), True)

    def test_unrecognized_wallet_role_refused(self):
        with self.assertRaisesRegex(ValueError, "unauthorized wallet role"):
            self.permit(role="treasury")

    def test_fake_station_challenge_denied(self):
        with self.assertRaisesRegex(ValueError, "station key not explicitly trusted"):
            approve(self.req, self.policy, self.owner, "owner",
                    self.another_station.public_jwk(), True)

    def test_tampered_signed_station_challenge_denied(self):
        changed = copy.deepcopy(self.req)
        changed["body"]["artifact_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "invalid station challenge"):
            approve(changed, self.policy, self.owner, "owner",
                    self.station.public_jwk(), True)

    def test_stale_approval_does_not_authorize_other_request(self):
        signed = self.permit()
        other = issue_request(
            self.station, "kiosk-001", self.policy,
            self.parcel["crossing"]["crossing_id"], digest(PDF), self.issued,
        )
        with self.assertRaisesRegex(ValueError, "another challenge"):
            self.stage([signed], request=other)

    def test_wallet_door_cannot_override_pdf_hash(self):
        with self.assertRaisesRegex(ValueError, "requested mail"):
            self.stage([self.permit()], data=PDF + b"changed")

    def test_wallet_door_needs_existing_mail_release(self):
        self.mail_release = copy.deepcopy(self.mail_release)
        self.mail_release["extensions"]["postemahhn_sealed_release"]["station_id"] = "wrong-station"
        with self.assertRaisesRegex(ValueError, "release signature"):
            self.stage([self.permit()])

    def test_no_asset_transfer_via_policy(self):
        fake = copy.deepcopy(self.policy)
        fake["asset_transfer_allowed"] = True
        with self.assertRaisesRegex(ValueError, "cannot grant other powers"):
            policy_id(fake)

    def test_expired_request_denied(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            verify_request(
                self.req, self.policy, self.station.public_jwk(),
                at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

    def test_other_station_cannot_accept(self):
        with self.assertRaisesRegex(ValueError, "station key not explicitly trusted"):
            self.stage([self.permit()], station=self.another_station)

    def test_valid_approval_is_typed_and_verifiable(self):
        approval = self.permit()
        self.assertEqual(approval["request_id"], request_id(self.req))
        verify_approvals(self.req, [approval], self.policy, self.station.public_jwk())
        tampered = copy.deepcopy(approval)
        tampered["role"] = "guardian"
        with self.assertRaises(ValueError):
            verify_approvals(self.req, [tampered], self.policy, self.station.public_jwk())


if __name__ == "__main__":
    unittest.main()
