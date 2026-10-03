#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 012 automatic remote dispatch."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

from hold_queue import HoldQueue, iso_at
from lease_authority import LeaseAuthority
from portable_lease import IdentityKey, make_crossing
from wake_composer import reevaluate_hold


def make_hold(hold_id: str) -> dict[str, Any]:
    return {
        "kind": "ghot.hold",
        "version": "0",
        "hold_id": hold_id,
        "energy_plan_id": f"energy-origin-{uuid.uuid4()}",
        "created_at": iso_at(90.0),
        "expires_at_epoch": None,
        "expires_at": None,
        "requester_node_id": "sim-requester",
        "capability": "system.echo",
        "payload": {"message": "automatic remote organ"},
        "urgency": "normal",
        "deferrable": True,
        "data_node_id": None,
        "prefer_surplus_for_background": True,
        "reason": "simulation",
        "release_condition": "field change",
        "status": "held",
    }


def remote_candidate(
    node: str,
    signer: IdentityKey,
    *,
    identity_available: bool = True,
) -> dict[str, Any]:
    identity = {
        "available": identity_available,
        "profile": "relatte.identity-signature/v0",
        "particular": signer.particular() if identity_available else None,
        "public_key": signer.public_jwk() if identity_available else None,
    }
    return {
        "node_id": node,
        "location": "remote",
        "url": f"http://{node}.invalid:7788",
        "field_state": "awake",
        "body": {
            "node_id": node,
            "identity": identity,
            "power": {
                "willingness": "normal",
                "source": "ac",
                "charging": True,
                "renewable_surplus": False,
            },
            "offers": [{
                "kind": "ghot.offer",
                "version": "0",
                "capability": "system.echo",
                "available": True,
                "power": {
                    "class": "essential",
                    "willingness": "normal",
                    "policy_reasons": [],
                },
            }],
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        queue = HoldQueue(root)
        remote_key = IdentityKey.load_or_create(root / "remote.pem")
        wrong_key = IdentityKey.load_or_create(root / "wrong.pem")
        remote_node = "node-remote"

        queue.enqueue(make_hold("hold-auto"), at=90.0)
        candidate = remote_candidate(remote_node, remote_key)

        first = reevaluate_hold(
            "hold-auto",
            queue=queue,
            candidates=[candidate],
            field_policy={},
            at=100.0,
            trigger="simulation.auto-dispatch",
        )
        assert first["action"] == "remote-dispatched"
        dispatch = first["dispatch"]
        assert dispatch["target_worker_id"] == remote_node
        assert dispatch["target_particular"] == remote_key.particular()
        assert dispatch["target_public_key"] == remote_key.public_jwk()

        second = reevaluate_hold(
            "hold-auto",
            queue=queue,
            candidates=[candidate],
            field_policy={},
            at=101.0,
            trigger="simulation.second-wake",
        )
        assert second["action"] == "remote-dispatch-active"
        assert second["dispatch"]["dispatch_id"] == dispatch["dispatch_id"]

        authority = LeaseAuthority(root)
        advert = authority.advert()

        wrong_claim = make_crossing(
            "CLAIM",
            signer=wrong_key,
            authority_id=advert["authority_id"],
            worker_id=remote_node,
            worker_node_id=remote_node,
            hold_id="hold-auto",
            dispatch_id=dispatch["dispatch_id"],
            lease_seconds=10,
        )
        wrong_receipt = authority.handle_crossing(wrong_claim, at=102.0)
        assert wrong_receipt["kind"] == "REFUSED"

        claim = make_crossing(
            "CLAIM",
            signer=remote_key,
            authority_id=advert["authority_id"],
            worker_id=remote_node,
            worker_node_id=remote_node,
            hold_id="hold-auto",
            dispatch_id=dispatch["dispatch_id"],
            lease_seconds=10,
        )
        claim_receipt = authority.handle_crossing(claim, at=103.0)
        assert claim_receipt["kind"] == "ADMITTED"
        lease_id = claim_receipt["extensions"]["ghot_lease"]["claim"]["lease_id"]

        complete = make_crossing(
            "COMPLETE",
            signer=remote_key,
            authority_id=advert["authority_id"],
            worker_id=remote_node,
            worker_node_id=remote_node,
            hold_id="hold-auto",
            lease_id=lease_id,
            child_energy_plan_id=dispatch["child_energy_plan_id"],
            receipt_id="receipt-remote-sim",
            outcome="ok",
        )
        complete_receipt = authority.handle_crossing(complete, at=104.0)
        assert complete_receipt["kind"] == "EXECUTED"
        final_hold = queue.get("hold-auto")
        assert final_hold is not None and final_hold["status"] == "released"

        queue.enqueue(make_hold("hold-no-identity"), at=200.0)
        unavailable = remote_candidate(
            "node-no-identity",
            remote_key,
            identity_available=False,
        )
        no_identity = reevaluate_hold(
            "hold-no-identity",
            queue=queue,
            candidates=[unavailable],
            field_policy={},
            at=201.0,
            trigger="simulation.no-identity",
        )
        assert no_identity["action"] == "remote-identity-unavailable"
        assert queue.get("hold-no-identity")["status"] == "held"

        passed = (
            first["action"] == "remote-dispatched"
            and second["action"] == "remote-dispatch-active"
            and wrong_receipt["kind"] == "REFUSED"
            and claim_receipt["kind"] == "ADMITTED"
            and complete_receipt["kind"] == "EXECUTED"
            and final_hold["status"] == "released"
            and no_identity["action"] == "remote-identity-unavailable"
        )

        print(json.dumps({
            "simulation_passed": passed,
            "automatic_dispatch": {
                "dispatch_id": dispatch["dispatch_id"],
                "target_node_id": dispatch["target_node_id"],
                "target_particular": dispatch["target_particular"],
            },
            "duplicate_wake": second["action"],
            "wrong_key_claim": wrong_receipt["kind"],
            "selected_key_claim": claim_receipt["kind"],
            "completion": complete_receipt["kind"],
            "final_hold_status": final_hold["status"],
            "identityless_remote": no_identity["action"],
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
