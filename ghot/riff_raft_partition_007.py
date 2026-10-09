#!/usr/bin/env python3
"""007 partition rehearsal on two *real*, separately checked-out repository blobs.

Only local temporary copies are removed. This does not take an actual GitHub
repository offline, and same-org repositories are not independent admins.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from riff_raft_custody_007 import (
    CustodyHold, SOURCE_SHA256, custody_statement, load_evidence,
    sign_statement, verify_local_receipt,
)


def must_fail(fn, reason: str) -> None:
    try:
        fn()
    except (CustodyHold, ValueError, KeyError, TypeError):
        return
    raise AssertionError("UNLAWFUL_CUSTODY_RECOVERY_ACCEPTED:" + reason)


def test_pair(source_relatte: Path, source_ghot: Path, output: Path) -> dict:
    old, _ = load_evidence(source_relatte)
    other, _ = load_evidence(source_ghot)
    assert old == other, "TWO_REPOSITORIES_DO_NOT_CONTAIN_IDENTICAL_SOURCE_BYTES"
    assert hashlib.sha256(old).hexdigest() == SOURCE_SHA256
    with tempfile.TemporaryDirectory(prefix="riff-raft-007-partition-") as tmp:
        root = Path(tmp)
        copy_a = root / "reLATTE-store.json"
        copy_b = root / "GHoT-store.json"
        copy_a.write_bytes(old)
        copy_b.write_bytes(other)
        receipt_a = sign_statement(custody_statement(copy_a, "reLATTE"))
        receipt_b = sign_statement(custody_statement(copy_b, "GHoT"))
        assert verify_local_receipt(receipt_a, copy_a, "reLATTE")
        assert verify_local_receipt(receipt_b, copy_b, "GHoT")
        assert receipt_a["statement"] != receipt_b["statement"]
        assert receipt_a["signing"]["public_key"] != receipt_b["signing"]["public_key"]
        observed = []

        for unavailable, surviving, absent_name, alive_name, receipt_alive in [
            (copy_a, copy_b, "reLATTE", "GHoT", receipt_b),
            (copy_b, copy_a, "GHoT", "reLATTE", receipt_a),
        ]:
            assert unavailable.exists() and surviving.exists()
            moved = unavailable.with_suffix(".unavailable")
            unavailable.rename(moved)
            try:
                must_fail(lambda: load_evidence(unavailable),
                          "MISSING_" + absent_name + "_DATA_CANNOT_BE_ASSUMED")
                assert verify_local_receipt(receipt_alive, surviving, alive_name)
                assert surviving.read_bytes() == old
                observed.append({
                    "missing_store": absent_name,
                    "surviving_store": alive_name,
                    "replayed_full_source_sha256": SOURCE_SHA256,
                    "replayed_004_and_005_signatures": True,
                    "surviving_local_signature_valid": True,
                    "source_reconstructed_without_missing_store": True,
                    "missing_store_automatically_repaired": False,
                    "source_organ_actuated": False,
                    "disposition": "HOLD",
                })
            finally:
                moved.rename(unavailable)

        altered = copy.deepcopy(receipt_b)
        altered["statement"]["admission"] = True
        must_fail(lambda: verify_local_receipt(altered, copy_b, "GHoT"),
                  "SIGNATURE_PROTECTS_NO_ADMISSION")
        altered = copy.deepcopy(receipt_a)
        altered["statement"]["declared_repository"] = "the-static-collective/GHoT"
        must_fail(lambda: verify_local_receipt(altered, copy_a, "reLATTE"),
                  "CUSTODY_ROLE_IMPERSONATION")
        copy_b.write_bytes(other[:-1])
        must_fail(lambda: load_evidence(copy_b), "TRUNCATED_MIRROR")
        copy_b.write_bytes(other)
        assert verify_local_receipt(receipt_b, copy_b, "GHoT")

        evidence = {
            "schema": "ghot.riff-raft-007-two-location-partition-replay/v0",
            "source_sha256": SOURCE_SHA256,
            "locations": ["the-static-collective/reLATTE",
                          "the-static-collective/GHoT"],
            "source_bytes_identical": True,
            "source_traces_and_signatures_independently_verified": True,
            "receipts_from_two_separate_ephemeral_keys": True,
            "partition_trials": observed,
            "actual_remote_repository_outage_executed": False,
            "administrative_independence_verified": False,
            "different_repository_is_not_different_administrator": True,
            "physical_actuation": False,
            "owner_admission": False,
            "final_disposition": "HOLD",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            **evidence,
            "local_receipts": {"reLATTE": receipt_a, "GHoT": receipt_b},
        }, indent=2) + "\n")
        return evidence


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("relatte_source", type=Path)
    p.add_argument("ghot_source", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    print(json.dumps(test_pair(args.relatte_source, args.ghot_source,
                               args.output), indent=2))


if __name__ == "__main__":
    main()
