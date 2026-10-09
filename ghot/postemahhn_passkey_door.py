#!/usr/bin/env python3
"""MAIL-004 WebAuthn passkey co-gate. No crypto funds, no hardware printing.

A key-owner-authorized, RP-bound none-attestation enrollment is required.
Assertions require challenge, origin, RP, UV/UP, ES256 and one-time consumption.
This gate is ADDITIONAL to MAIL-002 owner release + MAIL-003 P-256 approvals.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import cbor2
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from postemahhn_mail import address, digest, load_json
from postemahhn_wallet_door import request_id, stage_via_wallet_door, verify_request
from relatte_identity import IdentityKey, b64url, jcs_bytes, normalize_public_jwk, unb64url, verify_p256

REG_SCHEMA = "postemahhn.passkey-enrollment/v0"
GET_SCHEMA = "postemahhn.passkey-challenge/v0"
ENROLL_DOMAIN = b"PostEmahh-n-Passkey-Enrollment-v0|"
GET_DOMAIN = b"PostEmahh-n-Passkey-PrintRequest-v0|"
UP, UV, AT, ED = 1, 4, 64, 128

def nowz():
    return datetime.now(timezone.utc)

def stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

def period(created, expires, at=None):
    c = datetime.fromisoformat(created.replace("Z", "+00:00"))
    e = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    n = at or nowz()
    if not created.endswith("Z") or not expires.endswith("Z") or not (
        c - timedelta(seconds=60) <= n <= e and c < e <= c + timedelta(minutes=5)
    ):
        raise ValueError("expired or premature WebAuthn challenge")

def approved_origin(rp, origin):
    if rp == "localhost" and origin == "http://localhost:8000":
        return
    if (not isinstance(rp, str) or "." not in rp or
            rp.startswith(".") or rp.endswith(".") or
            not isinstance(origin, str) or origin != "https://" + rp or
            any(c in rp for c in "/:#?@ ")):
        raise ValueError("WebAuthn origin must exactly match approved HTTPS RP")

def save_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("unsafe passkey storage")
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True)
        f.write("\n")

def checked_client(encoded, kind, challenge, origin):
    raw = unb64url(encoded)
    if len(raw) > 8192:
        raise ValueError("WebAuthn client data too large")
    obj = json.loads(raw)
    if (not isinstance(obj, dict) or obj.get("type") != kind or
        obj.get("challenge") != challenge or obj.get("origin") != origin or
        obj.get("crossOrigin", False) is not False or "topOrigin" in obj):
        raise ValueError("WebAuthn origin/challenge/type mismatch")
    return raw

def auth_header(raw, rp, registration=False):
    if len(raw) < 37 or raw[:32] != hashlib.sha256(rp.encode()).digest():
        raise ValueError("WebAuthn RP hash invalid")
    flags = raw[32]
    if flags & (UP | UV) != (UP | UV):
        raise ValueError("WebAuthn user presence and verification required")
    if flags & ED or flags & 0x22 or (flags & 0x10 and not flags & 0x08):
        raise ValueError("WebAuthn flags unsupported")
    if bool(flags & AT) != registration or (not registration and len(raw) != 37):
        raise ValueError("WebAuthn authenticator data format unsupported")
    return flags, int.from_bytes(raw[33:37], "big")

def credential_file(root, cred_id):
    return root / "credentials" / (digest(unb64url(cred_id)) + ".json")

def begin_enrollment(owner_public, rp, origin, root):
    approved_origin(rp, origin)
    pub = normalize_public_jwk(owner_public)
    ticket = {
        "schema": REG_SCHEMA, "address": address(pub), "owner_public_key": pub,
        "rp_id": rp, "origin": origin,
        "challenge": b64url(secrets.token_bytes(32)),
        "created_at": stamp(nowz()), "expires_at": stamp(nowz() + timedelta(minutes=3)),
    }
    save_once(root / "enrollment" / (digest(unb64url(ticket["challenge"])) + ".json"), ticket)
    return ticket

def approve_enrollment(ticket, owner):
    if ticket["address"] != address(owner.public_jwk()):
        raise ValueError("mail owner does not control enrollment key")
    return owner.sign(ENROLL_DOMAIN + jcs_bytes(ticket))

def cose_to_key(attestation, rp):
    blob = unb64url(attestation)
    if len(blob) > 65536:
        raise ValueError("attestation too large")
    obj = cbor2.loads(blob)
    if (not isinstance(obj, dict) or set(obj) != {"fmt", "attStmt", "authData"}
            or obj["fmt"] != "none" or obj["attStmt"] != {} or
            not isinstance(obj["authData"], bytes)):
        raise ValueError("only none attestation is accepted")
    data = obj["authData"]
    flags, count = auth_header(data, rp, registration=True)
    if len(data) < 55:
        raise ValueError("attested credential too short")
    length = int.from_bytes(data[53:55], "big")
    if length < 16 or length > 1024 or len(data) < 55 + length:
        raise ValueError("invalid credential id length")
    cid = b64url(data[55:55+length])
    remaining = io.BytesIO(data[55+length:])
    key = cbor2.CBORDecoder(remaining).decode()
    if remaining.read() or not isinstance(key, dict) or set(key) != {1, 3, -1, -2, -3}:
        raise ValueError("invalid COSE trailing data or fields")
    if key[1] != 2 or key[3] != -7 or key[-1] != 1:
        raise ValueError("only ES256 P-256 credential keys supported")
    x, y = key[-2], key[-3]
    if not isinstance(x, bytes) or len(x) != 32 or not isinstance(y, bytes) or len(y) != 32:
        raise ValueError("invalid EC coordinates")
    ec.EllipticCurvePublicNumbers(int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()).public_key()
    return cid, {"kty":"EC", "crv":"P-256", "x":b64url(x), "y":b64url(y)}, count, bool(flags & 0x08)

def finish_enrollment(root, ticket, owner_signature, attested, at=None):
    if ticket.get("schema") != REG_SCHEMA:
        raise ValueError("wrong enrollment schema")
    approved_origin(ticket["rp_id"], ticket["origin"])
    period(ticket["created_at"], ticket["expires_at"], at)
    if ticket["address"] != address(ticket["owner_public_key"]):
        raise ValueError("mail address mismatch")
    stored = root / "enrollment" / (digest(unb64url(ticket["challenge"])) + ".json")
    if not stored.is_file() or stored.is_symlink() or load_json(stored) != ticket:
        raise ValueError("unknown enrollment ticket")
    if not verify_p256(ticket["owner_public_key"], ENROLL_DOMAIN+jcs_bytes(ticket), owner_signature):
        raise ValueError("missing mail-owner enrollment approval")
    if (not isinstance(attested, dict) or set(attested) != {"id","rawId","type","response"}
        or attested["type"] != "public-key"):
        raise ValueError("bad registration response")
    response = attested["response"]
    if not isinstance(response, dict) or set(response) != {"clientDataJSON","attestationObject"}:
        raise ValueError("bad registration response body")
    checked_client(response["clientDataJSON"], "webauthn.create", ticket["challenge"], ticket["origin"])
    cid, public, count, backup = cose_to_key(response["attestationObject"], ticket["rp_id"])
    if attested["id"] != cid or attested["rawId"] != cid:
        raise ValueError("attested credential ID mismatch")
    record = {
        "schema": "postemahhn.passkey-credential/v0",
        "credential_id":cid, "address":ticket["address"], "public_key":public,
        "rp_id":ticket["rp_id"], "origin":ticket["origin"],
        "sign_count":count, "backup_eligible":backup,
        "attestation_trust":"none-no-device-provenance",
    }
    path = credential_file(root, cid)
    if path.exists():
        raise ValueError("credential ID already enrolled")
    marker = stored.with_suffix(".used")
    fd = os.open(marker, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0), 0o600)
    os.close(fd)
    save_once(path, record)
    return record

def begin_assertion(root, wallet_request, policy, trusted_station_key, credential):
    verify_request(wallet_request, policy, trusted_station_key)
    if credential["address"] != policy["recipient_address"]:
        raise ValueError("credential address differs from mail owner")
    approved_origin(credential["rp_id"], credential["origin"])
    nonce = secrets.token_bytes(32)
    challenge = b64url(hashlib.sha256(
        GET_DOMAIN + request_id(wallet_request).encode("ascii") + nonce
    ).digest())
    ticket = {
        "schema":GET_SCHEMA, "challenge":challenge,
        "request_id":request_id(wallet_request),
        "recipient_address":policy["recipient_address"],
        "credential_id":credential["credential_id"],
        "rp_id":credential["rp_id"], "origin":credential["origin"],
        "created_at":stamp(nowz()), "expires_at":stamp(nowz()+timedelta(minutes=3)),
    }
    save_once(root / "assertions" / (digest(unb64url(challenge))+".json"), ticket)
    return ticket

def verify_assertion(root, ticket, wallet_request, policy, station_public, assertion, at=None):
    verify_request(wallet_request, policy, station_public, at)
    if (not isinstance(ticket, dict) or set(ticket) != {
            "schema","challenge","request_id","recipient_address","credential_id",
            "rp_id","origin","created_at","expires_at"
        } or ticket["schema"] != GET_SCHEMA):
        raise ValueError("bad assertion ticket")
    period(ticket["created_at"], ticket["expires_at"], at)
    if (ticket["request_id"] != request_id(wallet_request) or
        ticket["recipient_address"] != policy["recipient_address"]):
        raise ValueError("assertion challenge not tied to print request")
    issued = root / "assertions" / (digest(unb64url(ticket["challenge"]))+".json")
    if not issued.is_file() or issued.is_symlink() or load_json(issued) != ticket:
        raise ValueError("unknown assertion challenge")
    if issued.with_suffix(".used").exists():
        raise ValueError("passkey challenge already consumed")
    file = credential_file(root, ticket["credential_id"])
    if not file.is_file() or file.is_symlink():
        raise ValueError("credential not registered")
    record = load_json(file)
    if (record["schema"] != "postemahhn.passkey-credential/v0"
        or record["credential_id"] != ticket["credential_id"]
        or record["address"] != ticket["recipient_address"]
        or record["origin"] != ticket["origin"] or record["rp_id"] != ticket["rp_id"]):
        raise ValueError("registered passkey binding mismatch")
    approved_origin(record["rp_id"], record["origin"])
    if (not isinstance(assertion, dict) or set(assertion) != {"id","rawId","type","response"}
        or assertion["type"] != "public-key" or assertion["id"] != ticket["credential_id"]
        or assertion["rawId"] != ticket["credential_id"]):
        raise ValueError("wrong WebAuthn assertion credential")
    response = assertion["response"]
    if not isinstance(response, dict) or set(response) not in (
        {"clientDataJSON","authenticatorData","signature"},
        {"clientDataJSON","authenticatorData","signature","userHandle"},
    ):
        raise ValueError("malformed WebAuthn assertion body")
    client = checked_client(response["clientDataJSON"], "webauthn.get",ticket["challenge"],record["origin"])
    auth = unb64url(response["authenticatorData"])
    flags, counter = auth_header(auth, record["rp_id"], registration=False)
    if bool(flags & 0x08) != record["backup_eligible"]:
        raise ValueError("passkey backup eligibility changed")
    if (counter or record["sign_count"]) and counter <= record["sign_count"]:
        raise ValueError("passkey signature counter replay detected")
    pub = normalize_public_jwk(record["public_key"])
    key = ec.EllipticCurvePublicNumbers(
        int.from_bytes(unb64url(pub["x"]), "big"),
        int.from_bytes(unb64url(pub["y"]), "big"), ec.SECP256R1(),
    ).public_key()
    try:
        signature = unb64url(response["signature"])
        if len(signature) > 128:
            raise ValueError("signature too large")
        key.verify(signature, auth+hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as e:
        raise ValueError("WebAuthn ES256 assertion signature invalid") from e
    marker = issued.with_suffix(".used")
    try:
        fd = os.open(marker, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0), 0o600)
    except FileExistsError as e:
        raise ValueError("passkey challenge already consumed") from e
    os.close(fd)
    record["sign_count"] = counter
    temp = file.with_suffix(".pending")
    save_once(temp, record)
    temp.replace(file)
    return {
        "schema":"postemahhn.passkey-witness/v0",
        "request_id":request_id(wallet_request),
        "credential_fingerprint":digest(unb64url(record["credential_id"])),
        "user_verified":True, "state":"VERIFIED_ONLY",
        "asset_transfer_claimed":False, "physical_print_claimed":False,
    }

def stage_with_passkey(root, ticket, wallet_request, policy, station, assertion,
                       raw_approvals, issued_dir, parcel, pdf, mail_release, spool):
    witness = verify_assertion(root, ticket, wallet_request, policy, station.public_jwk(), assertion)
    job, receipt = stage_via_wallet_door(
        wallet_request, raw_approvals, policy, station, issued_dir,
        parcel, pdf, mail_release, spool
    )
    return job, receipt, witness
