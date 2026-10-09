"""MAIL-005: independent Ed25519 off-chain wallet proof, no money effect."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"ghot"))
from relatte_identity import IdentityKey, b64url
from postemahhn_mail import address, digest
from postemahhn_wallet_door import policy_for, issue_request, request_id
from postemahhn_external_wallets import (
    ALLOWED, SOLANA, check_supported, encode_base58, decode_base58,
    link_body, owner_link_signature, signed_link, solana_link_bytes,
    verify_link, permit_bytes, verify_external, link_id,
)

PDF_HASH = "e"*64


class ExternalWalletTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        root=Path(d.name)
        self.owner=IdentityKey.load_or_create(root/"keys"/"owner.pem")
        self.stranger=IdentityKey.load_or_create(root/"keys"/"other.pem")
        self.station=IdentityKey.load_or_create(root/"keys"/"station.pem")
        self.wallet=Ed25519PrivateKey.generate()
        self.alt=Ed25519PrivateKey.generate()
        self.wallet_address=encode_base58(self.wallet.public_key().public_bytes_raw())
        self.policy=policy_for(self.owner.public_jwk())
        self.req=issue_request(self.station,"station-101",self.policy,
                "relatte-crossing-v0:"+"a"*64,PDF_HASH,root/"issued")
        self.body=link_body(self.owner.public_jwk(),self.wallet_address)
        self.link=signed_link(
            self.body,owner_link_signature(self.owner,self.body),
            b64url(self.wallet.sign(solana_link_bytes(self.body))),
        )

    def proof(self, request=None, wallet=None, link=None):
        target=request or self.req
        bind=link or self.link
        return {
            "schema":"postemahhn.external-wallet-request-proof/v0",
            "profile":SOLANA,
            "request_id":request_id(target),
            "binding_id":link_id(bind),
            "wallet_public_address":self.wallet_address,
            "signature":b64url((wallet or self.wallet).sign(
                permit_bytes(target,bind,self.policy,self.station.public_jwk())
            )),
        }

    def verify(self, proof=None, request=None, link=None):
        return verify_external(
            request or self.req,self.policy,self.station.public_jwk(),
            link or self.link,proof or self.proof(request,link=link)
        )

    def test_valid_solana_offchain_proof(self):
        witness=self.verify()
        self.assertEqual(witness["state"],"VERIFIED_ONLY")
        self.assertEqual(witness["wallet_address"],self.wallet_address)
        self.assertFalse(witness["printing_authorized"])
        self.assertFalse(witness["asset_transfer_authorized"])

    def test_address_codec_round_trip_and_canonicalization(self):
        self.assertEqual(decode_base58(self.wallet_address),self.wallet.public_key().public_bytes_raw())
        self.assertEqual(encode_base58(b"\0"*32),"1"*32)
        with self.assertRaisesRegex(ValueError,"base58"):
            decode_base58("0"*32)

    def test_external_wallet_link_needs_owner_signature(self):
        altered=copy.deepcopy(self.link)
        altered["owner_signature"]=self.stranger.sign(b"wrong")
        with self.assertRaisesRegex(ValueError,"postal owner"):
            verify_link(altered)

    def test_external_wallet_link_needs_wallet_signature(self):
        altered=copy.deepcopy(self.link)
        altered["wallet_signature"]=b64url(self.alt.sign(solana_link_bytes(self.body)))
        with self.assertRaisesRegex(ValueError,"external wallet did not sign link"):
            verify_link(altered)

    def test_witness_does_not_accept_other_ed25519_signer(self):
        fake=self.proof()
        fake["signature"]=b64url(self.alt.sign(permit_bytes(
            self.req,self.link,self.policy,self.station.public_jwk()
        )))
        with self.assertRaisesRegex(ValueError,"wallet proof signature invalid"):
            self.verify(fake)

    def test_wallet_link_cannot_gain_financial_power(self):
        altered=copy.deepcopy(self.link)
        altered["body"]["money_transfer_allowed"]=True
        with self.assertRaisesRegex(ValueError,"cannot expand permissions"):
            verify_link(altered)

    def test_wallet_link_cannot_gain_physical_printing_power(self):
        altered=copy.deepcopy(self.link)
        altered["body"]["print_effect_allowed"]=True
        with self.assertRaisesRegex(ValueError,"cannot expand permissions"):
            verify_link(altered)

    def test_external_wallet_cannot_approve_another_request(self):
        proof=self.proof()
        other=issue_request(self.station,"station-101",self.policy,
             "relatte-crossing-v0:"+"a"*64,PDF_HASH,self.req_dir())
        with self.assertRaisesRegex(ValueError,"not belong to this request"):
            self.verify(proof,request=other)

    def req_dir(self):
        return Path(self.station.private_key_path).parent.parent/"more-issued"

    def test_relay_address_does_not_become_wallet_address(self):
        self.assertNotEqual(self.body["recipient_address"],self.wallet_address)
        self.assertEqual(self.body["recipient_address"],address(self.owner.public_jwk()))

    def test_expired_wallet_link_rejected(self):
        changed=copy.deepcopy(self.link)
        changed["body"]["expires_at"]=(datetime.now(timezone.utc)-timedelta(minutes=1)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.assertRaisesRegex(ValueError,"expired"):
            verify_link(changed)

    def test_wallet_binding_not_self_declared_as_owner(self):
        changed=copy.deepcopy(self.link)
        changed["body"]["owner_public_key"]=self.stranger.public_jwk()
        with self.assertRaisesRegex(ValueError,"cannot expand permissions"):
            verify_link(changed)

    def test_fake_wallet_profile_fails_closed(self):
        for profile in ("evm.siwe-eip4361/v1","evm.typed-eip712/v1",
                        "evm.smart-eip1271/v1","bitcoin.bip322/v1"):
            self.assertEqual(ALLOWED[profile],"unsupported")
            with self.assertRaises(NotImplementedError):
                check_supported(profile)
        with self.assertRaises(ValueError):
            check_supported("any-chain.any-signature")

    def test_profile_substitution_denied_before_crypto(self):
        fake=self.proof()
        fake["profile"]="evm.siwe-eip4361/v1"
        with self.assertRaises(NotImplementedError):
            self.verify(fake)

    def test_mutated_wallet_proof_request_id_rejected(self):
        fake=self.proof()
        fake["request_id"]="0"*64
        with self.assertRaisesRegex(ValueError,"does not belong"):
            self.verify(fake)

    def test_tampered_signed_station_document_denied(self):
        changed=copy.deepcopy(self.req)
        changed["body"]["artifact_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"station challenge signature"):
            permit_bytes(changed,self.link,self.policy,self.station.public_jwk())


if __name__ == "__main__":
    unittest.main()
