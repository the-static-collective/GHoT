#!/usr/bin/env python3
"""MAIL-005 independent off-chain external-wallet verification donor.

Implemented: Solana Ed25519 signMessage proof for one signed PostEmahh'n
wallet-door request, after dual owner+wallet link. DOES NOT spend, connect,
broadcast, authorize printing, or interpret chain state. EVM/Bitcoin profiles
are distinct unsupported verifier ports, never routed into Ed25519 code.
"""
from __future__ import annotations
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from postemahhn_mail import address, digest
from postemahhn_wallet_door import request_id, verify_request
from relatte_identity import IdentityKey, b64url, jcs_bytes, normalize_public_jwk, unb64url, verify_p256

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
LINK_SCHEMA = "postemahhn.external-wallet-link/v0"
PROOF_SCHEMA = "postemahhn.external-wallet-request-proof/v0"
SOLANA = "solana.ed25519-signed-message/v0"
OWNER_LINK_DOMAIN = b"PostEmahh-n-Owner-Wallet-Link-v0|"
WALLET_LINK_DOMAIN = b"PostEmahh-n-Solana-Wallet-Link-v0|"
PERMIT_DOMAIN = b"PostEmahh-n-Solana-Print-Authentication-v0|"
ALLOWED = {
    SOLANA: "implemented-off-chain-only",
    "evm.siwe-eip4361/v1": "unsupported",
    "evm.typed-eip712/v1": "unsupported",
    "evm.smart-eip1271/v1": "unsupported",
    "bitcoin.bip322/v1": "unsupported",
}

def encode_base58(raw: bytes) -> str:
    zeros = len(raw) - len(raw.lstrip(b"\x00"))
    number = int.from_bytes(raw, "big")
    chars = ""
    while number:
        number, value = divmod(number, 58)
        chars = B58[value] + chars
    return ("1" * zeros) + chars

def decode_base58(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError("bad Solana base58 public key")
    number = 0
    for letter in value:
        if letter not in B58:
            raise ValueError("non-base58 Solana public key")
        number = 58 * number + B58.index(letter)
    leading = len(value) - len(value.lstrip("1"))
    body = number.to_bytes((number.bit_length()+7)//8, "big")
    decoded = b"\x00" * leading + body
    if len(decoded) != 32 or encode_base58(decoded) != value:
        raise ValueError("Solana address must be canonical 32-byte Ed25519 key")
    return decoded

def check_supported(profile: str) -> None:
    if profile != SOLANA:
        if profile in ALLOWED:
            raise NotImplementedError("independent verifier not implemented for " + profile)
        raise ValueError("unknown external-wallet verification profile")

def expires_at(value: str, now: datetime | None = None) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("wallet binding expiration is not UTC")
    deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
    t = now or datetime.now(timezone.utc)
    if deadline <= t or deadline > t + timedelta(hours=1, minutes=1):
        raise ValueError("wallet binding expired or exceeds allowed window")

def link_body(owner_public: dict[str, Any], solana_address: str) -> dict[str, Any]:
    owner = normalize_public_jwk(owner_public)
    decode_base58(solana_address)
    return {
        "schema":LINK_SCHEMA, "profile":SOLANA,
        "recipient_address":address(owner),
        "owner_public_key":owner,
        "wallet_public_address":solana_address,
        "capability":"authenticate-one-print-request-only",
        "money_transfer_allowed":False,
        "print_effect_allowed":False,
        "expires_at":(
            datetime.now(timezone.utc)+timedelta(minutes=30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nonce":secrets.token_hex(16),
    }

def owner_link_bytes(body: dict[str, Any]) -> bytes:
    return OWNER_LINK_DOMAIN + jcs_bytes(body)

def solana_link_bytes(body: dict[str, Any]) -> bytes:
    return WALLET_LINK_DOMAIN + jcs_bytes(body)

def owner_link_signature(owner: IdentityKey, body: dict[str, Any]) -> str:
    if body.get("recipient_address") != address(owner.public_jwk()):
        raise ValueError("owner does not control mail address")
    return owner.sign(owner_link_bytes(body))

def signed_link(body: dict[str, Any], owner_sig: str, wallet_sig: str) -> dict[str, Any]:
    return {"body":body,"owner_signature":owner_sig,"wallet_signature":wallet_sig}

def verify_link(link: dict[str, Any], at: datetime | None = None) -> dict[str, Any]:
    if not isinstance(link, dict) or set(link) != {"body","owner_signature","wallet_signature"}:
        raise ValueError("malformed external wallet binding")
    body = link["body"]
    if not isinstance(body, dict) or set(body) != {
        "schema","profile","recipient_address","owner_public_key","wallet_public_address",
        "capability","money_transfer_allowed","print_effect_allowed","expires_at","nonce",
    } or body["schema"] != LINK_SCHEMA:
        raise ValueError("bad wallet link body")
    check_supported(body["profile"])
    if (body["recipient_address"] != address(body["owner_public_key"]) or
        body["capability"] != "authenticate-one-print-request-only" or
        body["money_transfer_allowed"] is not False or
        body["print_effect_allowed"] is not False or
        not isinstance(body["nonce"], str) or len(body["nonce"]) != 32 or
        any(c not in "0123456789abcdef" for c in body["nonce"])):
        raise ValueError("wallet link cannot expand permissions")
    expires_at(body["expires_at"],at)
    if not verify_p256(body["owner_public_key"], owner_link_bytes(body), link["owner_signature"]):
        raise ValueError("postal owner did not sign wallet binding")
    key = Ed25519PublicKey.from_public_bytes(decode_base58(body["wallet_public_address"]))
    try:
        key.verify(unb64url(link["wallet_signature"]), solana_link_bytes(body))
    except (InvalidSignature, ValueError) as e:
        raise ValueError("external wallet did not sign link") from e
    return body

def link_id(link: dict[str, Any]) -> str:
    return digest(jcs_bytes(link))

def permit_bytes(wallet_request: dict[str, Any], link: dict[str, Any],
                 policy: dict[str, Any], station_key: dict[str, Any]) -> bytes:
    binding = verify_link(link)
    verify_request(wallet_request, policy, station_key)
    if binding["recipient_address"] != policy["recipient_address"]:
        raise ValueError("wallet binding does not match mail recipient")
    body = wallet_request["body"]
    return PERMIT_DOMAIN + jcs_bytes({
        "schema":PROOF_SCHEMA, "profile":SOLANA,
        "purpose":"verify-control-of-linked-wallet-for-HELD-print-only",
        "request_id":request_id(wallet_request),
        "station_id":body["station_id"],
        "recipient_address":binding["recipient_address"],
        "artifact_sha256":body["artifact_sha256"],
        "binding_id":link_id(link),
        "wallet_address":binding["wallet_public_address"],
        "wallet_does_not_authorize": ["funds","transactions","printing","delivery"],
    })

def verify_external(request: dict[str, Any], policy: dict[str, Any],
                    trusted_station_key: dict[str, Any],
                    link: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(proof, dict) or set(proof) != {
        "schema","profile","request_id","binding_id","wallet_public_address","signature",
    } or proof.get("schema") != PROOF_SCHEMA:
        raise ValueError("bad external wallet proof")
    check_supported(proof["profile"])
    body = verify_link(link)
    verify_request(request, policy, trusted_station_key)
    if (proof["request_id"] != request_id(request) or
        proof["binding_id"] != link_id(link) or
        proof["wallet_public_address"] != body["wallet_public_address"] or
        body["recipient_address"] != policy["recipient_address"]):
        raise ValueError("wallet proof does not belong to this request or owner")
    message = permit_bytes(request,link,policy,trusted_station_key)
    key = Ed25519PublicKey.from_public_bytes(decode_base58(body["wallet_public_address"]))
    try:
        key.verify(unb64url(proof["signature"]), message)
    except (InvalidSignature, ValueError) as e:
        raise ValueError("external wallet proof signature invalid") from e
    return {
        "schema":"postemahhn.external-wallet-witness/v0",
        "profile":SOLANA, "request_id":request_id(request),
        "wallet_address":body["wallet_public_address"],
        "state":"VERIFIED_ONLY",
        "printing_authorized":False, "asset_transfer_authorized":False,
    }
