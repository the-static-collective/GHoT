#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 010."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

from hold_queue import HoldQueue, iso_at
from work_lease import WorkLeaseStore


def make_hold(hold_id: str, *, expires_at: float | None = None) -> dict[str, Any]:
    return {
        "kind": "ghot.hold",
        "version": "0",
        "hold_id": hold_id,
        "energy_plan_id": f"energy-origin-{uuid.uuid4()}",
        "created_at": iso_at(1.0),
        "expires_at_epoch": expires_at,
        "expires_at": iso_at(expires_at) if expires_at is not None else None,
        "requester_node_id": "sim-requester",
        "capability": "render.video",
        "payload": {"simulation": True},
        "urgency": "background",
        "deferrable": True,
        "data_node_id": None,
        "prefer_surplus_for_background": True,
        "reason": "simulation",
        "release_condition": "simulation",
        "status": "held",
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        queue = HoldQueue(root)
        leases = WorkLeaseStore(root)

        queue.enqueue(make_hold("hold-exclusive"), at=100.0)
        first = queue.claim_for_execution(
            "hold-exclusive",
            worker_id="worker-a",
            lease_seconds=10.0,
            at=100.0,
        )
        assert first["status"] == "claimed"

        blocked = queue.claim_for_execution(
            "hold-exclusive",
            worker_id="worker-b",
            lease_seconds=10.0,
            at=105.0,
        )
        assert blocked["status"] == "busy"
        assert blocked["claim"]["worker_id"] == "worker-a"

        renewed = leases.renew(
            first["claim"],
            lease_seconds=10.0,
            at=106.0,
        )
        assert renewed is not None
        assert renewed["lease_until_epoch"] == 116.0

        still_blocked = queue.claim_for_execution(
            "hold-exclusive",
            worker_id="worker-b",
            lease_seconds=10.0,
            at=111.0,
        )
        assert still_blocked["status"] == "busy"

        recovered = queue.claim_for_execution(
            "hold-exclusive",
            worker_id="worker-b",
            lease_seconds=10.0,
            at=117.0,
        )
        assert recovered["status"] == "claimed"
        assert recovered["recovered"] is True
        assert recovered["claim"]["worker_id"] == "worker-b"
        assert (
            recovered["claim"]["recovered_from_lease_id"]
            == first["claim"]["lease_id"]
        )
        leases.finish(
            recovered["claim"],
            outcome="simulation-complete",
            at=118.0,
        )

        queue.enqueue(make_hold("hold-cancel-first"), at=200.0)
        cancelled = queue.cancel(
            "hold-cancel-first",
            "simulation cancellation",
            at=201.0,
        )
        assert cancelled["status"] == "cancelled"
        cancelled_claim = queue.claim_for_execution(
            "hold-cancel-first",
            worker_id="worker-c",
            lease_seconds=10.0,
            at=202.0,
        )
        assert cancelled_claim["status"] == "inactive"
        assert cancelled_claim["hold_status"] == "cancelled"

        queue.enqueue(
            make_hold("hold-expire-first", expires_at=211.0),
            at=210.0,
        )
        expired_claim = queue.claim_for_execution(
            "hold-expire-first",
            worker_id="worker-d",
            lease_seconds=10.0,
            at=212.0,
        )
        assert expired_claim["status"] == "expired"
        assert queue.get("hold-expire-first")["status"] == "expired"

        queue.enqueue(make_hold("hold-active-claim"), at=300.0)
        active = queue.claim_for_execution(
            "hold-active-claim",
            worker_id="worker-e",
            lease_seconds=10.0,
            at=300.0,
        )
        assert active["status"] == "claimed"

        blocked_cancel = queue.cancel(
            "hold-active-claim",
            "too late to cancel before claim",
            at=301.0,
        )
        assert blocked_cancel["status"] == "held"
        assert blocked_cancel["transition_blocked"] == "active-claim"

        leases.abandon(
            active["claim"],
            reason="simulation worker stopped",
            at=302.0,
        )
        later_cancel = queue.cancel(
            "hold-active-claim",
            "cancel after claim ended",
            at=303.0,
        )
        assert later_cancel["status"] == "cancelled"

        queue.enqueue(make_hold("hold-stale-commit"), at=400.0)
        stale = queue.claim_for_execution(
            "hold-stale-commit",
            worker_id="worker-f",
            lease_seconds=5.0,
            at=400.0,
        )
        assert stale["status"] == "claimed"

        stale_release = queue.release(
            "hold-stale-commit",
            child_energy_plan_id="energy-stale",
            receipt_id="receipt-stale",
            lease_id=stale["claim"]["lease_id"],
            at=406.0,
        )
        assert stale_release["status"] == "held"

        fresh = queue.claim_for_execution(
            "hold-stale-commit",
            worker_id="worker-g",
            lease_seconds=10.0,
            at=406.0,
        )
        assert fresh["status"] == "claimed"
        assert fresh["recovered"] is True

        fresh_release = queue.release(
            "hold-stale-commit",
            child_energy_plan_id="energy-fresh",
            receipt_id="receipt-fresh",
            lease_id=fresh["claim"]["lease_id"],
            at=407.0,
        )
        assert fresh_release["status"] == "released"
        assert fresh_release["released_lease_id"] == fresh["claim"]["lease_id"]
        leases.finish(
            fresh["claim"],
            outcome="ok",
            receipt_id="receipt-fresh",
            at=407.0,
        )

        passed = (
            blocked["status"] == "busy"
            and still_blocked["status"] == "busy"
            and recovered["recovered"] is True
            and cancelled_claim["hold_status"] == "cancelled"
            and expired_claim["status"] == "expired"
            and blocked_cancel["transition_blocked"] == "active-claim"
            and stale_release["status"] == "held"
            and fresh_release["status"] == "released"
        )

        print(json.dumps({
            "simulation_passed": passed,
            "exclusive_claim": {
                "first_worker": first["claim"]["worker_id"],
                "second_worker_before_expiry": blocked["status"],
            },
            "renewal": {
                "lease_until_epoch": renewed["lease_until_epoch"],
                "second_worker_after_renewal": still_blocked["status"],
            },
            "recovery": {
                "worker": recovered["claim"]["worker_id"],
                "recovered": recovered["recovered"],
                "recovered_from": recovered["claim"]["recovered_from_lease_id"],
            },
            "cancel_before_claim": cancelled_claim,
            "expire_before_claim": expired_claim,
            "cancel_after_claim": {
                "blocked": blocked_cancel["transition_blocked"],
                "final_status": later_cancel["status"],
            },
            "stale_worker_fence": {
                "stale_release_status": stale_release["status"],
                "fresh_release_status": fresh_release["status"],
            },
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
