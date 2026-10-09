#!/usr/bin/env python3
"""SOVEREIGN-PRINT-SHOP-002: native Static OS -> GHoT -> reLATTE lab composer.

All participants are independent: source-owned Static OS cold-verifies the real
CAD/toolpath and its original signed crossing; GHoT issues a local proposal-only
adapter result; reLATTE signs and cold-verifies an independent three-owner-world
simulation. There is NO physical printer transport, start or inventory event.

Never infer real printer identity or owner consent from lab keys or digests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from external_adapters import execute_external_adapter
from printer_organ import (
    digest, load_owner_manifest, observe, propose, require, verify_source_request
)

SCHEMA = "ghot.sovereign-print-shop-002/v0"
NATIVE_SELECTED = ("example:machine-01", "example:machine-02", "virtual:fff-pla-180")
MAX_BYTES = 2_000_000


def file_json(path, max_bytes=MAX_BYTES):
    p = Path(path).resolve(strict=True)
    require(p.is_file() and p.stat().st_size <= max_bytes, "SOURCE_FILE_INVALID_OR_UNBOUNDED")
    with p.open("rb") as handle:
        return json.loads(handle.read().decode("utf8"))


def native_result(text, expected):
    lines = text.strip().splitlines()
    require(lines and len(text) < 10000, "NATIVE_VERIFIER_OUTPUT_INVALID")
    result = json.loads(lines[-1])
    require(type(result) is dict and result.get("status") == expected, "NATIVE_VERIFIER_FAILED")
    return result


def validate_binding(request, owner, status, proposal, source_result, relatte_proof, relatte_result):
    """Check exact provenance linkages AFTER source-owned native processes succeeded.

    This function alone does not authenticate signatures; the subprocess cold
    verifier is a separate mandatory step of run_lab.
    """
    req = verify_source_request(request)
    expected_ids = tuple(n["machine_id"] for n in req["selected_nodes"])
    require(expected_ids == NATIVE_SELECTED, "SOURCE_SELECTION_CHANGED")
    expected = propose(owner, req)
    require(proposal == expected and expected["route"] == "R3_HOLD", "GHOT_PROPOSAL_OR_AUTHORITY_MISMATCH")
    require(status == observe(owner), "GHOT_MACHINE_OBSERVATION_NOT_CURRENT")
    require(status["status"] == "NO_DEVICE_CONTACTED" and
            status["hardware_actions"] == [] and not status["machine_authenticated"],
            "PRINTER_IO_NOT_ALLOWED_IN_NATIVE_LAB")
    require(source_result["status"] == "THREE_NODE_FABRICATION_PROPOSAL_ONLY" and
            source_result["request_id"] == req["request_id"] and
            source_result["selected_nodes"] == list(NATIVE_SELECTED) and
            source_result["native_cad_cold_verified"] is True and
            source_result["physical_print_grants_issued"] == 0 and
            source_result["physical_parts_created"] == 0, "SOURCE_NATIVE_RECEIPT_WRONG")
    require(relatte_proof["request"] == req, "RELATTE_PROOF_SOURCE_CHANGED")
    require(relatte_result["status"] == "SIGNED_SIMULATED_OWNER_HOLD_AND_RECONSTITUTION_VERIFIED" and
            relatte_result["request_id"] == req["request_id"] and
            relatte_result["hold_decisions"] == 3 and
            relatte_result["software_review_proposals"] == 1 and
            relatte_result["physical_parts"] == 0 and
            relatte_result["physical_prints_started"] == 0 and
            relatte_result["stale_grants_restored"] == 0 and
            relatte_result["requires_external_trust"] is True,
            "RELATTE_NATIVE_VERIFIER_NOT_HOLDING")
    require(relatte_proof["fresh_ticket"]["operation"] == "propose" and
            relatte_proof["fresh_ticket"]["permission"] == "propose" and
            relatte_proof["claims"]["grants_for_physical_print"] == 0 and
            relatte_proof["claims"]["machine_dispatched"] is False and
            relatte_proof["claims"]["physical_parts"] == 0 and
            relatte_proof["claims"]["actual_native_013_crossing_to_remote_printer"] is False,
            "PHYSICAL_GRANT_LAUNDERING")
    require(len(relatte_proof["decisions"]) == 4 and
            [d["target_machine_id"] for d in relatte_proof["decisions"]] ==
            [*NATIVE_SELECTED, NATIVE_SELECTED[2]] and
            [d["decision"] for d in relatte_proof["decisions"]] ==
            ["R3_HOLD", "R3_HOLD", "R3_HOLD", "PROPOSAL_ONLY"],
            "OWNER_DECISION_TOPOLOGY_WRONG")
    body = {
        "schema": SCHEMA,
        "source_request_id": req["request_id"],
        "original_signed_cad_crossing_id": req["original_signed_cad_crossing_id"],
        "static_os_source_verified_by_native_process": True,
        "static_os_request_digest": digest(req),
        "ghot_adapter_id": "printer-organ-001",
        "ghot_machine_id": owner["machine_id"],
        "ghot_owner_digest": digest(owner),
        "ghot_status_digest": digest(status),
        "ghot_held_proposal_id": proposal["proposal_id"],
        "ghot_proposal_digest": digest(proposal),
        "relatte_native_signed_lab_proof_id": relatte_proof["proof_id"],
        "relatte_lab_proof_digest": digest(relatte_proof),
        "relatte_signature_and_history_verified_by_native_process": True,
        "lab_owner_trust_pins": "EPHEMERAL_SELF_GENERATED_NOT_INDEPENDENTLY_VERIFIED",
        "source_and_owner_network_connectivity": False,
        "operation": "PROPOSE_ONLY",
        "state": "R3_HOLD_COMPOSED_PROPOSAL_NOT_NATIVE_CROSSING",
        "actual_remote_printer_crossing": False,
        "physical_printer_authenticated": False,
        "physical_execution_approved": False,
        "physical_printer_contacted": False,
        "physical_parts": 0,
        "material_consumed": 0,
        "cash_or_token_minted": 0,
        "operator_present_or_manufacturing_approved": False,
    }
    return {**body, "composition_id": "ghot-print-shop-002:" + digest(body)}


def run_command(argv, cwd):
    p = subprocess.run(
        argv, cwd=str(cwd), stdin=subprocess.DEVNULL, capture_output=True,
        text=True, timeout=120, shell=False, check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    )
    require(p.returncode == 0 and len(p.stdout) <= 100_000,
            "NATIVE_OWNER_COMMAND_REFUSED_" + str(p.returncode) + ":" + p.stderr[-400:])
    return p.stdout


def pin_checkout(folder, ref):
    path = Path(folder).resolve(strict=True)
    require((path / ".git").exists(), "MISSING_SOURCE_REPOSITORY_CHECKOUT")
    result = run_command(["git", "rev-parse", "HEAD"], path).strip()
    require(result == ref and len(ref) == 40, "SOURCE_REPOSITORY_HEAD_NOT_PINNED")
    return path


def run_lab(static_root, relatte_root, original_source, print_packet, fleet, selection, request_file, owner_file, output_dir,
            static_sha, relatte_sha):
    # Pin repositories before loading untrusted input; original source owner
    # must be cold re-verified, NOT only request-hash-verified.
    static_root = pin_checkout(static_root, static_sha)
    relatte_root = pin_checkout(relatte_root, relatte_sha)
    request = verify_source_request(file_json(request_file))
    owner = load_owner_manifest(owner_file)
    root = Path(output_dir).expanduser().resolve()
    require(not root.exists(), "OCCURRENCE_EXISTS_NO_AUTORETRY")
    root.mkdir(mode=0o700, parents=True)
    # Source owner owns original signed CAD, machine field and real slicer proof.
    source_stdout = run_command([
        sys.executable, str(static_root / "scripts/static-fabrication-request.py"),
        "verify", "--source", str(Path(original_source).resolve()),
        "--packet", str(Path(print_packet).resolve()),
        "--fleet", str(Path(fleet).resolve()),
        "--selection", str(Path(selection).resolve()),
        "--out", str(Path(request_file).resolve())
    ], static_root)
    source_report = native_result(source_stdout, "THREE_NODE_FABRICATION_PROPOSAL_ONLY")
    require(source_report["request_id"] == request["request_id"], "SOURCE_COLD_VERIFICATION_REQUEST_DRIFT")

    # Use GHoT's actual opt-in subprocess adapter rather than duplicating the
    # printer organ as another custom executor.
    status_envelope = execute_external_adapter("printer.status.read", {
        "schema": "ghot.printer-organ-command/v0", "action": "status", "request": None})
    proposal_envelope = execute_external_adapter("printer.fabrication.propose", {
        "schema": "ghot.printer-organ-command/v0", "action": "propose", "request": request})
    status = status_envelope["result"]
    proposal = proposal_envelope["result"]
    require(status_envelope["adapter_id"] == proposal_envelope["adapter_id"] == "printer-organ-001",
            "NOT_NATIVE_GHOT_PRINTER_ADAPTER")

    # Lab-generated Ed25519 worlds are native reLATTE LocalWorld owners,
    # but they are NOT externally established physical printer identities.
    proof_dir = root / "native-relatte-lab"
    run_command(["node", str(relatte_root / "experiments/fabrication-crossing-013/run.mjs"),
                 str(Path(request_file).resolve()), str(proof_dir)], relatte_root)
    relatte_stdout = run_command([
        "node", str(relatte_root / "experiments/fabrication-crossing-013/verify-run.mjs"),
        str(proof_dir / "proof.json"), str(proof_dir / "trust-pins.json")
    ], relatte_root)
    relatte_report = json.loads(relatte_stdout)
    relatte_proof = file_json(proof_dir / "proof.json")
    artifact = validate_binding(request, owner, status, proposal, source_report, relatte_proof, relatte_report)
    # No secrets, customer image or machine controls appear in this source-cut.
    out_path = root / "shop-hold-receipt.json"
    with out_path.open("x", encoding="utf8") as handle:
        json.dump(artifact, handle, sort_keys=True, indent=2)
        handle.write("\n")
    return artifact


def main():
    p = argparse.ArgumentParser(description="Compose cold-verified Static OS, GHoT and native reLATTE printer owner proof")
    for option in ("static-root", "relatte-root", "original-source", "print-packet", "fleet",
                   "selection", "request", "owner", "out", "static-commit", "relatte-commit"):
        p.add_argument("--" + option, required=True)
    a = p.parse_args()
    result = run_lab(
        a.static_root, a.relatte_root, a.original_source, a.print_packet,
        a.fleet, a.selection, a.request, a.owner, a.out, a.static_commit, a.relatte_commit)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as e:
        print("R3_HOLD / " + str(e)[:600], file=sys.stderr)
        raise SystemExit(2)
