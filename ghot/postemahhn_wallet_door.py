#!/usr/bin/env python3
"""MAIL-003 wallet-style print door: signed challenges and separately held approvals.

P-256 proof-of-control only. No blockchain, token, payment, seed phrase,
real financial wallet integration, physical printing or legal identity claim.
A signed approval is a one-use, named-station authority to STAGE (HOLD) only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from postemahhn_mail import ADDRESS_RE, STATION_RE, address, digest, load_json, write_json
from postemahhn_sealed_mail import accept_at_station, verify_sealed
from relatte_identity import (
    IdentityKey, jcs_bytes, normalize_public_jwk,
    sign_receipt, timestamp_now, verify_p256,
)

POLICY_SCHEMA = "postemahhn.wallet-door-policy/v0"
REQUEST_SCHEMA = "postemahhn.wallet-door-request/v0"
APPROVAL_SCHEMA = "postemahhn.wallet-door-approval/v0"
CAPABILITY = "postemahhn.print-stage"
ALGORITHM = "ECDSA-P256-SHA256"
REQUEST_DOMAIN = b"PostEmahh-n-WalletDoor-Request-v0|"
APPROVAL_DOMAIN = b"PostEmahh-n-WalletDoor-Approval-v0|"
HASH_DOMAIN = b"PostEmahh-n-WalletDoor-Request-ID-v0|"
ALLOWED_ROLES = {"owner", "guardian"}


def policy_for(owner_pub: dict[str, Any],
               guardian_pub: dict[str, Any] | None = None) -> dict[str, Any]:
    owner = normalize_public_jwk(owner_pub)
    roles = {"owner": owner}
    required = ["owner"]
    if guardian_pub is not None:
        guardian = normalize_public_jwk(guardian_pub)
        if guardian == owner:
            raise ValueError("guardian key must be independent")
        roles["guardian"] = guardian
        required.append("guardian")
    return {
        "schema": POLICY_SCHEMA, "recipient_address": address(owner),
        "capability": CAPABILITY, "roles": roles, "required_roles": required,
        "scope": "stage-held-pdf-only", "asset_transfer_allowed": False,
        "physical_print_claimed": False,
    }


def validate_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict) or set(policy) != {
        "schema", "recipient_address", "capability", "roles", "required_roles",
        "scope", "asset_transfer_allowed", "physical_print_claimed",
    }:
        raise ValueError("malformed wallet-door policy")
    if (policy["schema"] != POLICY_SCHEMA or policy["capability"] != CAPABILITY
            or policy["scope"] != "stage-held-pdf-only"
            or policy["asset_transfer_allowed"] is not False
            or policy["physical_print_claimed"] is not False):
        raise ValueError("wallet policy cannot grant other powers")
    roles = policy["roles"]
    required = policy["required_roles"]
    if (not isinstance(roles, dict) or set(roles) not in
            ({"owner"}, {"owner", "guardian"})):
        raise ValueError("unsupported wallet roles")
    if required != (["owner", "guardian"] if "guardian" in roles else ["owner"]):
        raise ValueError("all present wallet signers must approve")
    owners = [normalize_public_jwk(roles[role]) for role in required]
    if len({json.dumps(k, sort_keys=True) for k in owners}) != len(owners):
        raise ValueError("signer roles must be independent")
    if policy["recipient_address"] != address(owners[0]):
        raise ValueError("wallet owner does not match mail address")


def policy_id(policy: dict[str, Any]) -> str:
    validate_policy(policy)
    return digest(jcs_bytes(policy))


def body_bytes(request: dict[str, Any]) -> bytes:
    return REQUEST_DOMAIN + jcs_bytes({
        "schema": request["schema"], "body": request["body"],
        "station_public_key": request["station_signing"]["public_key"],
        "algorithm": request["station_signing"]["algorithm"],
    })


def request_id(request: dict[str, Any]) -> str:
    return digest(HASH_DOMAIN + jcs_bytes(request))


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be a UTC Z string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return parsed


def verify_request(
    request: dict[str, Any], policy: dict[str, Any],
    trusted_station_public_key: dict[str, Any],
    at: datetime | None = None,
) -> None:
    validate_policy(policy)
    if not isinstance(request, dict) or set(request) != {
        "schema", "body", "station_signing",
    } or request["schema"] != REQUEST_SCHEMA:
        raise ValueError("invalid wallet-door request")
    signing = request["station_signing"]
    if not isinstance(signing, dict) or set(signing) != {
        "algorithm", "public_key", "signature",
    } or signing["algorithm"] != ALGORITHM:
        raise ValueError("invalid station signing profile")
    trusted = normalize_public_jwk(trusted_station_public_key)
    if normalize_public_jwk(signing["public_key"]) != trusted:
        raise ValueError("station key not explicitly trusted")
    if not verify_p256(trusted, body_bytes(request), signing["signature"]):
        raise ValueError("invalid station challenge signature")
    body = request["body"]
    if not isinstance(body, dict) or set(body) != {
        "capability", "recipient_address", "station_id", "crossing_id",
        "artifact_sha256", "nonce", "created_at", "expires_at", "policy_id",
    }:
        raise ValueError("invalid wallet-door challenge fields")
    if (body["capability"] != CAPABILITY
            or body["recipient_address"] != policy["recipient_address"]
            or body["policy_id"] != policy_id(policy)
            or not STATION_RE.fullmatch(body["station_id"])
            or not isinstance(body["crossing_id"], str)
            or not body["crossing_id"].startswith("relatte-crossing-v0:")
            or not isinstance(body["artifact_sha256"], str)
            or len(body["artifact_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in body["artifact_sha256"])
            or not isinstance(body["nonce"], str)
            or len(body["nonce"]) != 32
            or any(c not in "0123456789abcdef" for c in body["nonce"])):
        raise ValueError("unsupported challenge scope")
    created = _utc(body["created_at"])
    expires = _utc(body["expires_at"])
    now = at or datetime.now(timezone.utc)
    if (expires <= created or expires - created > timedelta(minutes=5)
            or now > expires or now < created - timedelta(seconds=60)):
        raise ValueError("expired or future wallet challenge")


def issue_request(
    station: IdentityKey, station_id: str, policy: dict[str, Any],
    crossing_id: str, pdf_hash: str, issued_dir: Path, ttl_seconds: int = 180,
) -> dict[str, Any]:
    validate_policy(policy)
    if (not isinstance(station_id, str) or not STATION_RE.fullmatch(station_id)
            or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 300):
        raise ValueError("bad station request parameters")
    created = timestamp_now()
    expires = (datetime.now(timezone.utc)
               + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    request = {
        "schema": REQUEST_SCHEMA,
        "body": {
            "capability": CAPABILITY, "recipient_address": policy["recipient_address"],
            "station_id": station_id, "crossing_id": crossing_id,
            "artifact_sha256": pdf_hash, "nonce": secrets.token_hex(16),
            "created_at": created, "expires_at": expires, "policy_id": policy_id(policy),
        },
        "station_signing": {
            "algorithm": ALGORITHM, "public_key": station.public_jwk(), "signature": "",
        },
    }
    # Verify a complete request before registering it for subsequent user approval.
    request["station_signing"]["signature"] = station.sign(body_bytes(request))
    verify_request(request, policy, station.public_jwk())
    issued_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if issued_dir.is_symlink():
        raise ValueError("unsafe challenge directory")
    path = issued_dir / (request["body"]["nonce"] + ".json")
    with path.open("x", encoding="utf-8") as f:
        f.write(json.dumps(request, sort_keys=True) + "\n")
    return request


def approval_bytes(approval: dict[str, Any]) -> bytes:
    return APPROVAL_DOMAIN + jcs_bytes({
        "schema": approval["schema"],
        "request_id": approval["request_id"],
        "role": approval["role"],
        "signer_public_key": approval["signer_public_key"],
    })


def approve(
    request: dict[str, Any], policy: dict[str, Any],
    signer: IdentityKey, role: str,
    trusted_station_public_key: dict[str, Any],
    explicit_user_consent: bool = False,
    at: datetime | None = None,
) -> dict[str, Any]:
    if explicit_user_consent is not True:
        raise ValueError("user must explicitly approve wallet-door challenge")
    verify_request(request, policy, trusted_station_public_key, at)
    if role not in policy["required_roles"]:
        raise ValueError("unauthorized wallet role")
    if signer.public_jwk() != normalize_public_jwk(policy["roles"][role]):
        raise ValueError("wallet signer is not trusted for role")
    approval = {
        "schema": APPROVAL_SCHEMA, "request_id": request_id(request),
        "role": role, "signer_public_key": signer.public_jwk(), "signature": "",
    }
    approval["signature"] = signer.sign(approval_bytes(approval))
    return approval


def verify_approvals(
    request: dict[str, Any], approvals: list[dict[str, Any]],
    policy: dict[str, Any], station_public_key: dict[str, Any],
    at: datetime | None = None,
) -> None:
    verify_request(request, policy, station_public_key, at)
    if not isinstance(approvals, list) or len(approvals) != len(policy["required_roles"]):
        raise ValueError("missing independent wallet approvals")
    seen = set()
    for approval in approvals:
        if not isinstance(approval, dict) or set(approval) != {
            "schema", "request_id", "role", "signer_public_key", "signature",
        } or approval.get("schema") != APPROVAL_SCHEMA:
            raise ValueError("unsupported wallet approval")
        role = approval.get("role")
        if role not in policy["required_roles"] or role in seen:
            raise ValueError("duplicate or unauthorized wallet role")
        if approval.get("request_id") != request_id(request):
            raise ValueError("wallet approval is for another challenge")
        trusted = normalize_public_jwk(policy["roles"][role])
        if normalize_public_jwk(approval["signer_public_key"]) != trusted:
            raise ValueError("wrong signer for wallet role")
        if not verify_p256(trusted, approval_bytes(approval), approval["signature"]):
            raise ValueError("wallet approval signature invalid")
        seen.add(role)
    if seen != set(policy["required_roles"]):
        raise ValueError("required wallet approval missing")


def stage_via_wallet_door(
    request: dict[str, Any], approvals: list[dict[str, Any]],
    policy: dict[str, Any], station: IdentityKey, issued_dir: Path,
    parcel: dict[str, Any], pdf: bytes, mail_release: dict[str, Any],
    spool: Path,
    at: datetime | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Policy + signature approval is ADDITIONAL to MAIL-002 recipient release.

    V0 only creates/observes HELD artifacts; never invokes physical printers.
    """
    verify_approvals(request, approvals, policy, station.public_jwk(), at)
    body = request["body"]
    nonce = body["nonce"]
    stored = issued_dir / (nonce + ".json")
    if not stored.is_file() or stored.is_symlink() or load_json(stored) != request:
        raise ValueError("challenge was not issued by this station")
    recipient_address, crossing_id = verify_sealed(parcel)
    if (body["recipient_address"] != recipient_address
            or body["crossing_id"] != crossing_id
            or body["artifact_sha256"] != digest(pdf)):
        raise ValueError("wallet challenge does not match requested mail")
    # Station's physical-world permission is narrower than PDF staging.
    spool_job = accept_at_station(
        parcel, pdf, mail_release, body["station_id"], recipient_address, spool, now=at
    )
    consumed_dir = issued_dir.parent / "consumed"
    consumed_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if consumed_dir.is_symlink():
        raise ValueError("unsafe consumed directory")
    destination = consumed_dir / (nonce + ".json")
    if destination.exists() or destination.is_symlink():
        raise ValueError("wallet permit already consumed")
    receipt = sign_receipt({
        "schema": "relatte.receipt/v0", "receipt_id": "",
        "crossing_id": crossing_id,
        "world_id": "postemahhn-print-station:" + body["station_id"],
        "receiver_particular": station.particular(),
        "kind": "VERIFIED", "semantic_effect": "none",
        "created_at": timestamp_now(),
        "note": "Wallet door staged a HELD print candidate; no paper or funds effect",
        "extensions": {"postemahhn_wallet_door": {
            "request_id": request_id(request),
            "policy_id": policy_id(policy),
            "approved_roles": sorted(policy["required_roles"]),
            "station_id": body["station_id"], "artifact_sha256": digest(pdf),
            "job": spool_job.name, "state": "HELD",
            "physical_print_claimed": False, "asset_transfer_claimed": False,
        }}, "signing": {},
    }, station)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(receipt, f, sort_keys=True)
        f.write("\n")
    return spool_job, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="MAIL-003 P-256 wallet-key print-stage door")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pol = sub.add_parser("policy")
    pol.add_argument("--owner-key", type=Path, required=True)
    pol.add_argument("--guardian-key", type=Path)
    pol.add_argument("--out", type=Path, required=True)
    issue = sub.add_parser("issue")
    issue.add_argument("--station-key", type=Path, required=True)
    issue.add_argument("--station", required=True)
    issue.add_argument("--policy", type=Path, required=True)
    issue.add_argument("--crossing", required=True)
    issue.add_argument("--sha256", required=True)
    issue.add_argument("--issued-dir", type=Path, required=True)
    issue.add_argument("--out", type=Path, required=True)
    auth = sub.add_parser("approve")
    auth.add_argument("--request", type=Path, required=True)
    auth.add_argument("--policy", type=Path, required=True)
    auth.add_argument("--signer-key", type=Path, required=True)
    auth.add_argument("--station-pin", type=Path, required=True)
    auth.add_argument("--role", choices=["owner", "guardian"], required=True)
    auth.add_argument("--i-approve", action="store_true")
    auth.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "policy":
        owner = IdentityKey.load_or_create(args.owner_key)
        guardian = (IdentityKey.load_or_create(args.guardian_key).public_jwk()
                    if args.guardian_key else None)
        result = policy_for(owner.public_jwk(), guardian)
    elif args.cmd == "issue":
        result = issue_request(
            IdentityKey.load_or_create(args.station_key), args.station,
            load_json(args.policy), args.crossing, args.sha256, args.issued_dir
        )
    else:
        result = approve(
            load_json(args.request), load_json(args.policy),
            IdentityKey(args.signer_key), args.role,
            load_json(args.station_pin), args.i_approve
        )
    if args.out.exists():
        raise ValueError("output already exists")
    write_json(args.out, result)
    print(json.dumps({"file": str(args.out), "profile": result["schema"]}))


if __name__ == "__main__":
    main()
