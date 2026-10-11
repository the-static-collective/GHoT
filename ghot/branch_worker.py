#!/usr/bin/env python3
"""Human-operated GHoT branch-work console (030): preview -> ACT -> signed receipt.

Uses GHoT activation 028's real atomic one-use claim and signer.
There is deliberately no daemon, scheduler, shell or HTTP action endpoint.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from activation_ticket import ActivationStore, verify_execution_receipt
from branch_work import candidate_from_file, make_descriptor
from launch_preflight import preflight_launch
from reference_node import ROOT
from relatte_identity import identity_safe
from state_migration import semantic_address


def preview(candidate_path: Path, *, root: Path) -> dict:
    descriptor = make_descriptor(candidate_from_file(candidate_path))
    preflight = preflight_launch(descriptor, root=root)
    proposal = preflight.get("proposal")
    is_ready = preflight.get("status") == "ready" and isinstance(proposal, dict)
    return identity_safe({
        "schema": "ghot.branch-worker-preview/v0",
        "status": "READY" if is_ready else "HOLD",
        "descriptor": descriptor,
        "preflight": preflight,
        "proposal_address": semantic_address(proposal) if is_ready else None,
        "act_required": True,
        "act_authorized": False,
        "owner_identity_authenticated": False,
        "execution_performed": False,
        "allowed_execution": "one local Git source SHA-256 inspection only",
    })


def act(
    candidate_path: Path, *,
    expected: str, confirm: str, root: Path,
    ttl_seconds: int = 120,
) -> dict:
    if confirm != "ACT":
        raise ValueError("EXPLICIT_LOCAL_ACT_REQUIRED")
    state = preview(candidate_path, root=root)
    if state["status"] != "READY":
        raise ValueError("BRANCH_WORK_PREVIEW_ON_HOLD")
    if state["proposal_address"] != expected:
        raise ValueError("PREVIEWED_PROPOSAL_HAS_CHANGED")
    store = ActivationStore(root)
    issued = store.issue(
        state["descriptor"], consent_phrase=confirm,
        ttl_seconds=ttl_seconds, expected_proposal_address=expected,
    )
    executed = store.execute(issued["ticket"]["ticket_id"])
    receipt = executed["receipt"]
    verified = verify_execution_receipt(receipt)
    success = bool(
        verified and receipt.get("status") == "EXECUTED"
        and receipt.get("success") is True
        and receipt.get("operation_attempted") is True
    )
    return identity_safe({
        "schema": "ghot.branch-worker-result/v0",
        "ticket_id": issued["ticket"]["ticket_id"],
        "activation_ticket_verified": True,
        "execution_receipt": receipt,
        "execution_receipt_verified": verified,
        "verified_success": success,
        "job": executed["result"] if success else None,
        "operator_identity_proven": False,
        "remote_execution": False,
        "donor_program_executed": False,
        "additional_work_permission": False,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("preview")
    p.add_argument("candidate", type=Path)
    a = sub.add_parser("act")
    a.add_argument("candidate", type=Path)
    a.add_argument("--expected", required=True)
    a.add_argument("--confirm", required=True)
    a.add_argument("--ttl", type=int, default=120)
    args = parser.parse_args()
    try:
        if args.mode == "preview":
            report = preview(args.candidate, root=ROOT)
            print(json.dumps(report, indent=2))
            return 0 if report["status"] == "READY" else 2
        result = act(
            args.candidate, expected=args.expected, confirm=args.confirm,
            ttl_seconds=args.ttl, root=ROOT,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["verified_success"] else 2
    except Exception as exc:
        # No accidental stdout success on error.
        print(json.dumps({
            "schema": "ghot.branch-worker-hold/v0",
            "status": "HOLD",
            "reason": f"{type(exc).__name__}: {str(exc)[:220]}",
            "executed": False,
            "consent_inferred": False,
        }, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
