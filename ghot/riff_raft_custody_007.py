#!/usr/bin/env python3
"""RIFF-RAFT-007: sovereign, read-only evidence custody; P-256 local receipts.

Two GitHub repositories under one organization are distinct *storage locations*,
not two independent administrators. Local signer key is ephemeral and untrusted.
No dispatch, replication daemon, escrow, physical rights or auto admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from relatte_identity import IdentityKey, jcs_bytes, verify_p256, particular_for_public_key
from riff_raft_counterfactual_return import receive, ReturnHold

SCHEMA = "ghot.riff-raft-local-custody-receipt/v0"
DOMAIN = b"RIFF-RAFT-007-local-custody-v0|"
SOURCE_SHA256 = "da6c556051f197e1d07578b5e435ae3b7132538c7c098a4add9e4acfd4572d42"
RETURN_CROSSING = "relatte-crossing-v0:bceaf6c25b074b0e1eed56c157368dae7aa97c99d33c382d5d00c96ddb91dda1"
RETURN_RECEIPT = "relatte-receipt-v0:c4c8dd65fb645fded4ef8175d734d94fb1145be1cbf9b2f4fab7acf89cd856c3"
PARENT_CROSSING = "relatte-crossing-v0:0b61b9476c0ab3e2b57a5090781d2591e8c1145ac84c2eea2f67efb301d54fa3"
STORES = {
    "GHoT": "the-static-collective/GHoT",
    "reLATTE": "the-static-collective/reLATTE",
}
SOURCE_LIMIT = 4 * 1024 * 1024


class CustodyHold(ValueError):
    pass


def hold(condition: bool, reason: str) -> None:
    if not condition:
        raise CustodyHold("RIFF_RAFT_007_HOLD:" + reason)


def load_evidence(path: Path) -> tuple[bytes, dict[str, Any]]:
    hold(path.is_file() and path.stat().st_size <= SOURCE_LIMIT, "SOURCE_UNAVAILABLE")
    raw = path.read_bytes()
    hold(bool(raw) and hashlib.sha256(raw).hexdigest() == SOURCE_SHA256,
         "SOURCE_BYTE_IDENTITY_CHANGED")
    try:
        bundle = json.loads(raw)
        result = receive(bundle)  # independently re-verifies entire signed 004 + 005 ancestry
    except (ValueError, TypeError, KeyError) as exc:
        raise CustodyHold("RIFF_RAFT_007_HOLD:CRYPTOGRAPHIC_LINEAGE_FAILED") from exc
    hold(result["disposition"] == "HOLD" and result["world_count"] == 2 and
         result["crossing_signature_valid"] is True and
         result["receipt_signature_valid"] is True and
         result["remote_work_dispatch"] is False and
         result["physical_actuation"] is False and
         result["owner_admitted"] is False and
         result["ghot_energy_or_water_moved"] is False and
         all(w["source_verified"] is True for w in result["verified_sources"]),
         "SOURCE_NOT_VERIFIED_LOCAL_HOLD")
    hold(bundle["crossing"]["crossing_id"] == RETURN_CROSSING and
         bundle["receipt"]["receipt_id"] == RETURN_RECEIPT and
         bundle["ancestral_source_004"]["crossing"]["crossing_id"] == PARENT_CROSSING,
         "ORIGINAL_SIGNED_ANCESTRY_CHANGED")
    return raw, result


def custody_statement(source_path: Path, store: str) -> dict[str, Any]:
    hold(store in STORES, "UNKNOWN_CUSTODIAN")
    source, verified = load_evidence(source_path)
    return {
        "schema": SCHEMA,
        "custody_label": store,
        "declared_repository": STORES[store],
        "source_full_bundle_sha256": hashlib.sha256(source).hexdigest(),
        "source_return_crossing": RETURN_CROSSING,
        "source_return_receipt": RETURN_RECEIPT,
        "signed_004_parent_crossing": PARENT_CROSSING,
        "signed_005_world_count": verified["world_count"],
        "source_004_and_005_signatures_reverified": True,
        "disposition": "HOLD",
        "local_result_only": True,
        "source_organ_execution": False,
        "physical_actuation": False,
        "admission": False,
        "transfer": False,
        "administrative_independence_verified": False,
        "signer_is_org_trust_root": False,
        "auto_repair": False,
    }


def sign_statement(statement: dict[str, Any]) -> dict[str, Any]:
    """Ephemeral signature witnesses same source bytes, not identity or authority."""
    with tempfile.TemporaryDirectory() as work:
        key = IdentityKey.load_or_create(Path(work) / "temporary-local-key.pem")
        public = key.public_jwk()
        signature = key.sign(DOMAIN + jcs_bytes(statement))
        return {
            "statement": statement,
            "signing": {
                "profile": "ECDSA-P256-SHA256-ephemeral-local-only",
                "public_key": public,
                "signature": signature,
                "local_particular": particular_for_public_key(public),
            },
        }


def verify_local_receipt(receipt: Any, source: Path, store: str) -> bool:
    hold(isinstance(receipt, dict) and set(receipt) == {"statement", "signing"},
         "RECEIPT_FIELDS")
    hold(isinstance(receipt["signing"], dict) and
         set(receipt["signing"]) == {
             "profile", "public_key", "signature", "local_particular",
         }, "SIGNATURE_FIELDS")
    sign = receipt["signing"]
    hold(sign["profile"] == "ECDSA-P256-SHA256-ephemeral-local-only" and
         sign["local_particular"] == particular_for_public_key(sign["public_key"]),
         "EPHEMERAL_SIGNER_PROFILE")
    hold(verify_p256(sign["public_key"], DOMAIN + jcs_bytes(receipt["statement"]),
                     sign["signature"]), "LOCAL_SIGNATURE_CHANGED")
    hold(receipt["statement"] == custody_statement(source, store),
         "CUSTODY_RECEIPT_SOURCE_OR_AUTHORITY_CHANGED")
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["check", "receipt", "verify-receipt"])
    p.add_argument("source", type=Path)
    p.add_argument("--store", required=True, choices=sorted(STORES))
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    if args.command == "check":
        result = custody_statement(args.source, args.store)
        print(json.dumps(result, indent=2))
    elif args.command == "receipt":
        hold(args.receipt is not None, "RECEIPT_OUTPUT_REQUIRED")
        output = sign_statement(custody_statement(args.source, args.store))
        hold(verify_local_receipt(output, args.source, args.store),
             "SELF_RECEIPT_REJECTED")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(output, indent=2) + "\n")
        print(json.dumps({"custody_label": args.store,
                          "evidence_sha256": SOURCE_SHA256,
                          "local_signature_verified": True,
                          "disposition": "HOLD"}))
    else:
        hold(args.receipt is not None and args.receipt.exists(), "RECEIPT_REQUIRED")
        receipt = json.loads(args.receipt.read_text())
        assert verify_local_receipt(receipt, args.source, args.store)
        print(json.dumps({"verified": True, "store": args.store, "disposition": "HOLD"}))


if __name__ == "__main__":
    try:
        main()
    except (CustodyHold, OSError, KeyError, TypeError, AssertionError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
