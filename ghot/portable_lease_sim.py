#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 011."""

from __future__ import annotations

import copy
import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

from hold_queue import HoldQueue, iso_at
from lease_authority import LeaseAuthority
from portable_lease import make_crossing, verify_receipt

KEY = "test-key-material"
AUTHORITY_ID = "authority-sim"


def make_hold() -> dict[str, Any]:
    return {
        "kind": "ghot.hold",
        "version": "0",
        "hold_id": "hold-portable",
        "energy_plan_id": f"energy-origin-{uuid.uuid4()}",
        "created_at": iso_at(90.0),
        "expires_at_epoch": None,
        "expires_at": None,
        "requester_node_id": "sim-requester",
        "capability": "system.echo",
        "payload": {"message": "portable crossing"},
        "urgency": "normal",
        "deferrable": True,
        "data_node_id": None,
        "prefer_surplus_for_background": True,
        "reason": "simulation hold",
        "release_condition": "owner dispatch",
        "status": "held",
    }


def msg(action: str, worker: str, at: float, **kwargs: Any) -> dict[str, Any]:
    return make_crossing(
        action,
        secret=KEY,
        authority_id=AUTHORITY_ID,
        worker_id=worker,
        worker_node_id=f"node-{worker}",
        created_at=iso_at(at),
        nonce=f"nonce-{action}-{worker}-{at}",
        **kwargs,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        queue = HoldQueue(root)
        queue.enqueue(make_hold(), at=90.0)
        authority = LeaseAuthority(root, authority_id=AUTHORITY_ID, secret=KEY)

        dispatch_a = authority.prepare_dispatch(
            "hold-portable",
            target_worker_id="worker-a",
            child_energy_plan_id="energy-child-a",
            ttl_seconds=30.0,
            at=100.0,
        )

        poll_a = authority.handle_crossing(msg("POLL", "worker-a", 101.0), at=101.0)
        poll_b = authority.handle_crossing(msg("POLL", "worker-b", 101.0), at=101.0)
        assert verify_receipt(KEY, poll_a)
        assert len(poll_a["extensions"]["ghot_lease"]["dispatches"]) == 1
        assert poll_b["extensions"]["ghot_lease"]["dispatches"] == []

        wrong = authority.handle_crossing(msg(
            "CLAIM", "worker-b", 102.0,
            hold_id="hold-portable",
            dispatch_id=dispatch_a["dispatch_id"],
            lease_seconds=10.0,
        ), at=102.0)
        assert wrong["kind"] == "REFUSED"

        claim_a_msg = msg(
            "CLAIM", "worker-a", 103.0,
            hold_id="hold-portable",
            dispatch_id=dispatch_a["dispatch_id"],
            lease_seconds=10.0,
        )
        claim_a = authority.handle_crossing(claim_a_msg, at=103.0)
        assert claim_a["kind"] == "ADMITTED"
        replay_a = authority.handle_crossing(claim_a_msg, at=104.0)
        assert replay_a["receipt_id"] == claim_a["receipt_id"]
        lease_a = claim_a["extensions"]["ghot_lease"]["claim"]["lease_id"]

        renewed = authority.handle_crossing(msg(
            "RENEW", "worker-a", 105.0,
            hold_id="hold-portable",
            lease_id=lease_a,
            lease_seconds=10.0,
        ), at=105.0)
        assert renewed["kind"] == "VERIFIED"
        assert renewed["extensions"]["ghot_lease"]["claim"]["lease_until_epoch"] == 115.0

        blocked = False
        try:
            authority.prepare_dispatch(
                "hold-portable",
                target_worker_id="worker-b",
                child_energy_plan_id="energy-child-b-early",
                ttl_seconds=30.0,
                at=111.0,
            )
        except ValueError:
            blocked = True
        assert blocked

        dispatch_b = authority.prepare_dispatch(
            "hold-portable",
            target_worker_id="worker-b",
            child_energy_plan_id="energy-child-b",
            ttl_seconds=30.0,
            at=116.0,
        )

        stale = authority.handle_crossing(msg(
            "COMPLETE", "worker-a", 117.0,
            hold_id="hold-portable",
            lease_id=lease_a,
            child_energy_plan_id="energy-child-a",
            receipt_id="receipt-late",
            outcome="ok",
        ), at=117.0)
        assert stale["kind"] == "REFUSED"

        claim_b = authority.handle_crossing(msg(
            "CLAIM", "worker-b", 117.0,
            hold_id="hold-portable",
            dispatch_id=dispatch_b["dispatch_id"],
            lease_seconds=10.0,
        ), at=117.0)
        assert claim_b["kind"] == "ADMITTED"
        lease_b = claim_b["extensions"]["ghot_lease"]["claim"]["lease_id"]

        tampered_msg = msg(
            "RENEW", "worker-b", 117.5,
            hold_id="hold-portable",
            lease_id=lease_b,
            lease_seconds=10.0,
        )
        tampered_msg = copy.deepcopy(tampered_msg)
        tampered_msg["requested_effect"]["lease_seconds"] = 999.0
        tampered = authority.handle_crossing(tampered_msg, at=117.5)
        assert tampered["kind"] == "REFUSED"

        complete_msg = msg(
            "COMPLETE", "worker-b", 118.0,
            hold_id="hold-portable",
            lease_id=lease_b,
            child_energy_plan_id="energy-child-b",
            receipt_id="receipt-worker-b-ok",
            outcome="ok",
        )
        complete = authority.handle_crossing(complete_msg, at=118.0)
        assert complete["kind"] == "EXECUTED"
        assert verify_receipt(KEY, complete)
        replay_complete = authority.handle_crossing(complete_msg, at=119.0)
        assert replay_complete["receipt_id"] == complete["receipt_id"]

        final_hold = queue.get("hold-portable")
        assert final_hold is not None and final_hold["status"] == "released"

        passed = (
            wrong["kind"] == "REFUSED"
            and replay_a["receipt_id"] == claim_a["receipt_id"]
            and blocked
            and stale["kind"] == "REFUSED"
            and tampered["kind"] == "REFUSED"
            and complete["kind"] == "EXECUTED"
            and final_hold["status"] == "released"
        )

        print(json.dumps({
            "simulation_passed": passed,
            "crossing_schema": claim_a_msg["schema"],
            "receipt_schema": claim_a["schema"],
            "wrong_worker_claim": wrong["kind"],
            "replay_receipt_stable": replay_a["receipt_id"] == claim_a["receipt_id"],
            "renewed_until": renewed["extensions"]["ghot_lease"]["claim"]["lease_until_epoch"],
            "redispatch_blocked_while_live": blocked,
            "new_target_after_expiry": dispatch_b["target_worker_id"],
            "stale_completion": stale["kind"],
            "tampered_crossing": tampered["kind"],
            "final_hold_status": final_hold["status"],
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
