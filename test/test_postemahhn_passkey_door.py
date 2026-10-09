"""MAIL-004: real WebAuthn ceremony-shaped fixtures and hostile assertions."""
from __future__ import annotations

import copy
import hashlib
import json
import secrets
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ghot"))
from relatte_identity import IdentityKey, b64url
from postemahhn_mail import contact_for_key, digest
from postemahhn_sealed_mail import make_sealed, stage_release
from postemahhn_wallet_door import approve, issue_request, policy_for
from postemahhn_passkey_door import (
    approve_enrollment, begin_assertion, begin_enrollment, finish_enrollment,
    stage_with_passkey, verify_assertion, approved_origin, passkey_record_path,
)

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"
RP = "localhost"
ORIGIN = "http://localhost:8000"


class PasskeyDoorTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        def key(name):
            return IdentityKey.load_or_create(self.root/"keys"/(name+".pem"))
        self.owner, self.sender, self.station, self.stranger = (
            key("owner"), key("sender"), key("station"), key("stranger")
        )
        self.policy = policy_for(self.owner.public_jwk())
        self.parcel = make_sealed(PDF, contact_for_key(self.owner), self.sender)
        self.mail_release = stage_release(self.parcel, self.owner, "kiosk-001")
        self.issued = self.root/"wallet"/"issued"
        self.req = issue_request(
            self.station,"kiosk-001",self.policy,
            self.parcel["crossing"]["crossing_id"],digest(PDF),self.issued
        )
        self.approval = approve(self.req,self.policy,self.owner,"owner",
                                self.station.public_jwk(),True)
        self.private = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = secrets.token_bytes(32)
        self.store = self.root/"passkeys"
        self.enrollment = begin_enrollment(self.owner.public_jwk(),RP,ORIGIN,self.store)

    def client(self, kind, challenge, origin=ORIGIN, cross=False):
        return b64url(json.dumps({
            "type":kind, "challenge":challenge, "origin":origin,"crossOrigin":cross,
        },separators=(",",":")).encode())

    def attested(self, flags=0x45, alg=-7, origin=ORIGIN):
        n = self.private.public_key().public_numbers()
        key = {
            1:2,3:alg,-1:1,
            -2:n.x.to_bytes(32,"big"),-3:n.y.to_bytes(32,"big"),
        }
        raw = (hashlib.sha256(RP.encode()).digest() + bytes([flags])
               + (0).to_bytes(4,"big") + bytes(16) + len(self.cred_id).to_bytes(2,"big")
               + self.cred_id + cbor2.dumps(key))
        obj = cbor2.dumps({"fmt":"none","attStmt":{},"authData":raw})
        return {
            "id":b64url(self.cred_id), "rawId":b64url(self.cred_id),
            "type":"public-key", "response":{
                "clientDataJSON":self.client("webauthn.create",self.enrollment["challenge"],origin),
                "attestationObject":b64url(obj),
            },
        }

    def enrolled(self):
        return finish_enrollment(
            self.store,self.enrollment,approve_enrollment(self.enrollment,self.owner),
            self.attested()
        )

    def assertion(self, ticket, counter=1, flags=0x05, origin=ORIGIN, challenge=None, cross=False):
        client=self.client("webauthn.get",challenge or ticket["challenge"],origin,cross)
        auth=hashlib.sha256(RP.encode()).digest()+bytes([flags])+counter.to_bytes(4,"big")
        sig=self.private.sign(auth+hashlib.sha256(
            __import__("base64").urlsafe_b64decode(client+"="*((-len(client))%4))
        ).digest(),ec.ECDSA(hashes.SHA256()))
        return {"id":b64url(self.cred_id), "rawId":b64url(self.cred_id),
                "type":"public-key", "response":{
                    "clientDataJSON":client,"authenticatorData":b64url(auth),
                    "signature":b64url(sig),
                }}

    def ready(self):
        record=self.enrolled()
        ticket=begin_assertion(self.store,self.req,self.policy,self.station.public_jwk(),record)
        return record,ticket

    def verify(self,ticket,assertion,**kwargs):
        return verify_assertion(self.store,ticket,self.req,self.policy,
                                self.station.public_jwk(),assertion,**kwargs)

    def test_owner_authorized_enrollment_and_passkey_stages_held(self):
        _,ticket=self.ready()
        signed=self.assertion(ticket)
        job,receipt,witness=stage_with_passkey(
            self.store,ticket,self.req,self.policy,self.station,signed,
            [self.approval],self.issued,self.parcel,PDF,self.mail_release,
            self.root/"spool"
        )
        self.assertEqual((job/"document.pdf").read_bytes(),PDF)
        self.assertEqual(witness["state"],"VERIFIED_ONLY")
        self.assertTrue(witness["user_verified"])
        self.assertFalse(witness["asset_transfer_claimed"])
        self.assertEqual(receipt["semantic_effect"],"none")
        self.assertFalse(receipt["extensions"]["postemahhn_wallet_door"]["physical_print_claimed"])

    def test_enrollment_requires_mail_owner_approval(self):
        with self.assertRaisesRegex(ValueError,"missing mail-owner"):
            finish_enrollment(
                self.store,self.enrollment,
                self.stranger.sign(b"incorrect"),self.attested()
            )

    def test_enrollment_origin_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError,"origin/challenge"):
            finish_enrollment(self.store,self.enrollment,
                approve_enrollment(self.enrollment,self.owner),
                self.attested(origin="https://evil.example"))

    def test_registration_uv_missing_denied(self):
        with self.assertRaisesRegex(ValueError,"presence and verification"):
            finish_enrollment(self.store,self.enrollment,
                approve_enrollment(self.enrollment,self.owner),
                self.attested(flags=0x41))

    def test_registration_wrong_cose_algorithm_denied(self):
        with self.assertRaisesRegex(ValueError,"ES256"):
            finish_enrollment(self.store,self.enrollment,
                approve_enrollment(self.enrollment,self.owner),
                self.attested(alg=-8))

    def test_enrollment_is_one_time(self):
        self.enrolled()
        with self.assertRaises(OSError):
            self.enrolled()

    def test_invalid_rp_origin_denied(self):
        with self.assertRaisesRegex(ValueError,"approved HTTPS RP"):
            approved_origin("example.com","http://example.com")
        with self.assertRaisesRegex(ValueError,"approved HTTPS RP"):
            approved_origin("example.com","https://other.example.com")

    def test_wrong_client_origin_denied(self):
        _,ticket=self.ready()
        with self.assertRaisesRegex(ValueError,"origin/challenge"):
            self.verify(ticket,self.assertion(ticket,origin="https://evil.example"))

    def test_wrong_challenge_denied(self):
        _,ticket=self.ready()
        with self.assertRaisesRegex(ValueError,"origin/challenge"):
            self.verify(ticket,self.assertion(ticket,challenge=b64url(bytes(32))))

    def test_cross_origin_iframe_denied(self):
        _,ticket=self.ready()
        with self.assertRaisesRegex(ValueError,"origin/challenge"):
            self.verify(ticket,self.assertion(ticket,cross=True))

    def test_no_user_verification_denied(self):
        _,ticket=self.ready()
        with self.assertRaisesRegex(ValueError,"presence and verification"):
            self.verify(ticket,self.assertion(ticket,flags=0x01))

    def test_wrong_credential_id_denied(self):
        _,ticket=self.ready()
        fake=self.assertion(ticket)
        fake["rawId"]=b64url(bytes(32))
        with self.assertRaisesRegex(ValueError,"wrong WebAuthn assertion credential"):
            self.verify(ticket,fake)

    def test_wrong_signer_denied(self):
        _,ticket=self.ready()
        forged=self.assertion(ticket)
        wrong=ec.generate_private_key(ec.SECP256R1())
        raw=__import__("base64").urlsafe_b64decode(
            forged["response"]["authenticatorData"]+"==")
        client=__import__("base64").urlsafe_b64decode(
            forged["response"]["clientDataJSON"]+"==")
        forged["response"]["signature"]=b64url(wrong.sign(
            raw+hashlib.sha256(client).digest(),ec.ECDSA(hashes.SHA256())))
        with self.assertRaisesRegex(ValueError,"signature invalid"):
            self.verify(ticket,forged)

    def test_passkey_challenge_replay_denied(self):
        _,ticket=self.ready()
        signed=self.assertion(ticket)
        self.verify(ticket,signed)
        with self.assertRaisesRegex(ValueError,"already consumed"):
            self.verify(ticket,signed)

    def test_signature_counter_replay_on_new_ticket_denied(self):
        rec,ticket=self.ready()
        self.verify(ticket,self.assertion(ticket,counter=3))
        other=begin_assertion(self.store,self.req,self.policy,self.station.public_jwk(),rec)
        with self.assertRaisesRegex(ValueError,"counter replay"):
            self.verify(other,self.assertion(other,counter=3))

    def test_expired_assertion_denied(self):
        _,ticket=self.ready()
        with self.assertRaisesRegex(ValueError,"expired"):
            self.verify(ticket,self.assertion(ticket),at=datetime.now(timezone.utc)+timedelta(hours=1))

    def test_passkey_cannot_skip_wallet_owner_approval(self):
        _,ticket=self.ready()
        with self.assertRaisesRegex(ValueError,"missing independent wallet approvals"):
            stage_with_passkey(self.store,ticket,self.req,self.policy,self.station,
                 self.assertion(ticket),[],self.issued,self.parcel,PDF,self.mail_release,
                 self.root/"spool")

    def test_passkey_cannot_skip_owner_mail_release(self):
        _,ticket=self.ready()
        changed=copy.deepcopy(self.mail_release)
        changed["extensions"]["postemahhn_sealed_release"]["station_id"]="wrong"
        with self.assertRaisesRegex(ValueError,"release signature"):
            stage_with_passkey(self.store,ticket,self.req,self.policy,self.station,
                 self.assertion(ticket),[self.approval],self.issued,self.parcel,PDF,
                 changed,self.root/"spool")

    def test_passkey_must_match_same_wallet_request(self):
        rec,ticket=self.ready()
        other=issue_request(self.station,"kiosk-001",self.policy,
                            self.parcel["crossing"]["crossing_id"],digest(PDF),self.issued)
        with self.assertRaisesRegex(ValueError,"not tied to print request"):
            verify_assertion(self.store,ticket,other,self.policy,
                             self.station.public_jwk(),self.assertion(ticket))


if __name__=="__main__":
    unittest.main()
