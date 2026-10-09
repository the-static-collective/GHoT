#!/usr/bin/env python3
"""ORSHOT-002: stage reLATTE-signed crossings/receipts bound to exact PDF bytes.

No printer commands execute. Two out-of-band signer trust pins are required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from relatte_identity import (
    IdentityKey, normalize_public_jwk, particular_for_public_key,
    sign_crossing, sign_receipt, timestamp_now, verify_crossing, verify_receipt,
)

PROFILE = "ghot.print-projection/v0"
MAX_PDF_BYTES = 20 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("expected JSON object")
    return result


def require_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-") or not (10 < len(data) <= MAX_PDF_BYTES):
        raise ValueError("input must be a PDF under the 20 MiB bound")


def validate(
    crossing: dict[str, Any], receipt: dict[str, Any], artifact: bytes,
    source_public_key: dict[str, Any], receiver_public_key: dict[str, Any],
) -> dict[str, str]:
    require_pdf(artifact)
    source_key = normalize_public_jwk(source_public_key)
    receiver_key = normalize_public_jwk(receiver_public_key)
    if not verify_crossing(crossing):
        raise ValueError("crossing signature or identity invalid")
    if crossing.get("signing", {}).get("public_key") != source_key:
        raise ValueError("crossing signer differs from trusted source pin")
    if crossing.get("source_particular") != particular_for_public_key(source_key):
        raise ValueError("crossing particular differs from source pin")
    if not verify_receipt(
        receipt, expected_public_key=receiver_key,
        expected_receiver_particular=particular_for_public_key(receiver_key),
    ):
        raise ValueError("receipt signature or trusted receiver pin invalid")
    if receipt.get("crossing_id") != crossing.get("crossing_id"):
        raise ValueError("receipt refers to a different crossing")
    if crossing.get("declared_kind") != "GHOT_PRINT_PROJECTION_TEST":
        raise ValueError("V0 accepts only explicitly identified print-projection tests")
    if receipt.get("kind") != "VERIFIED" or receipt.get("semantic_effect") != "none":
        raise ValueError("test receipt may not assert a physical or financial effect")
    ext = receipt.get("extensions") or {}
    projection = ext.get("ghot_print") if isinstance(ext, dict) else None
    if not isinstance(projection, dict) or projection.get("profile") != PROFILE:
        raise ValueError("no signed print-projection extension")
    if projection.get("format") != "pdf" or projection.get("status") != "test-no-print":
        raise ValueError("unsupported print status or format")
    digest = sha(artifact)
    if projection.get("artifact_sha256") != digest:
        raise ValueError("PDF bytes do not match signed artifact digest")
    if projection.get("physical_deposit_count") != 0:
        raise ValueError("test profile requires an explicit zero physical deposit")
    job_id = "ghot-print-v0-" + sha((receipt["receipt_id"] + ":" + digest).encode())[:32]
    return {
        "job_id": job_id, "artifact_sha256": digest,
        "crossing_id": crossing["crossing_id"], "receipt_id": receipt["receipt_id"],
    }


def stage(
    crossing: dict[str, Any], receipt: dict[str, Any], artifact: bytes,
    source_public_key: dict[str, Any], receiver_public_key: dict[str, Any],
    spool: Path,
) -> Path:
    identity = validate(crossing, receipt, artifact, source_public_key, receiver_public_key)
    spool.mkdir(parents=True, exist_ok=True)
    final = spool / identity["job_id"]
    if final.exists():
        verify_bundle(final, source_public_key, receiver_public_key)
        return final  # redelivery does not enqueue a second print
    temp = Path(tempfile.mkdtemp(prefix=".incoming-", dir=spool))
    try:
        (temp / "artifact.pdf").write_bytes(artifact)
        (temp / "crossing.json").write_text(json.dumps(crossing, indent=2, sort_keys=True) + "\n")
        (temp / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        manifest = {
            "schema": "ghot.print-job/v0", "status": "HELD",
            "device_selected": False, "physical_output_claimed": False,
            "rendering_authority": False, "identity": identity,
        }
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        try:
            temp.rename(final)
        except OSError:
            # Concurrent redelivery may create the same named bundle. Never
            # replace existing bytes; verify before treating it as a replay.
            if not final.exists():
                raise
            verify_bundle(final, source_public_key, receiver_public_key)
        return final
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def verify_bundle(
    bundle: Path, source_public_key: dict[str, Any],
    receiver_public_key: dict[str, Any],
) -> dict[str, Any]:
    for name in ("artifact.pdf", "crossing.json", "receipt.json", "manifest.json"):
        p = bundle / name
        if not p.is_file() or p.is_symlink():
            raise ValueError(f"missing or symlinked bundle member: {name}")
    identity = validate(
        read_json(bundle / "crossing.json"), read_json(bundle / "receipt.json"),
        (bundle / "artifact.pdf").read_bytes(), source_public_key, receiver_public_key,
    )
    manifest = read_json(bundle / "manifest.json")
    expected = {
        "schema": "ghot.print-job/v0", "status": "HELD",
        "device_selected": False, "physical_output_claimed": False,
        "rendering_authority": False, "identity": identity,
    }
    if manifest != expected or bundle.name != identity["job_id"]:
        raise ValueError("manifest or bundle name changed")
    return manifest


def demo(
    artifact: bytes, keys: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict, dict]:
    """Create real P-256 signatures for a LOCAL TEST (not physical custody)."""
    require_pdf(artifact)
    source = IdentityKey.load_or_create(keys / "source-p256.pem")
    receiver = IdentityKey.load_or_create(keys / "receiver-p256.pem")
    crossing = sign_crossing({
        "schema": "relatte.crossing-envelope/v0", "crossing_id": "",
        "protocol_version": "0", "source_particular": source.particular(),
        "source_world": "ghot-print-test",
        "declared_kind": "GHOT_PRINT_PROJECTION_TEST", "payload_refs": [],
        "requested_effect": {"action": "PROPOSE_PRINT", "nonce": str(uuid.uuid4())},
        "created_at": timestamp_now(),
        "extensions": {"ghot_print_profile": PROFILE}, "signing": {},
    }, source)
    receipt = sign_receipt({
        "schema": "relatte.receipt/v0", "receipt_id": "",
        "crossing_id": crossing["crossing_id"],
        "world_id": "ghot-print-test-receiver",
        "receiver_particular": receiver.particular(),
        "kind": "VERIFIED", "semantic_effect": "none",
        "created_at": timestamp_now(),
        "note": "PDF bytes bound for HELD test; no real deposit or print",
        "extensions": {"ghot_print": {
            "profile": PROFILE, "format": "pdf", "status": "test-no-print",
            "artifact_sha256": sha(artifact), "physical_deposit_count": 0,
        }},
        "signing": {},
    }, receiver)
    return crossing, receipt, source.public_jwk(), receiver.public_jwk()


def main() -> None:
    parser = argparse.ArgumentParser(description="Hold verified print witnesses (never prints)")
    sub = parser.add_subparsers(dest="action", required=True)
    d = sub.add_parser("demo-stage")
    d.add_argument("pdf", type=Path)
    d.add_argument("--spool", type=Path, required=True)
    d.add_argument("--keys", type=Path, required=True)
    s = sub.add_parser("stage")
    s.add_argument("pdf", type=Path)
    s.add_argument("--crossing", type=Path, required=True)
    s.add_argument("--receipt", type=Path, required=True)
    s.add_argument("--source-pin", type=Path, required=True)
    s.add_argument("--receiver-pin", type=Path, required=True)
    s.add_argument("--spool", type=Path, required=True)
    v = sub.add_parser("verify")
    v.add_argument("bundle", type=Path)
    v.add_argument("--source-pin", type=Path, required=True)
    v.add_argument("--receiver-pin", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "demo-stage":
        data = args.pdf.read_bytes()
        crossing, receipt, source, receiver = demo(data, args.keys)
        bundle = stage(crossing, receipt, data, source, receiver, args.spool)
        for name, value in (("source-pin.json", source), ("receiver-pin.json", receiver)):
            target = bundle / name
            if not target.exists():
                target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        print(json.dumps({
            "bundle": str(bundle), "status": "HELD", "print_claimed": False,
            "receipt_id": receipt["receipt_id"],
        }, indent=2))
    elif args.action == "stage":
        bundle = stage(
            read_json(args.crossing), read_json(args.receipt), args.pdf.read_bytes(),
            read_json(args.source_pin), read_json(args.receiver_pin), args.spool,
        )
        print(json.dumps({"bundle": str(bundle), "status": "HELD"}, indent=2))
    else:
        print(json.dumps(verify_bundle(
            args.bundle, read_json(args.source_pin), read_json(args.receiver_pin)
        ), indent=2))


if __name__ == "__main__":
    main()
