#!/usr/bin/env python3
"""Experiment 039 — reservation and concurrency safety."""

from __future__ import annotations

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_authorization import (
    apply_execution_to_treasury,
    make_resource_proposal,
)
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_finalization,
    verify_reservation,
)
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from relatte_identity import IdentityKey


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def resource_entry(snapshot: dict, subject_ref: str) -> dict:
    return next(
        item
        for item in snapshot["entries"]
        if item["subject_ref"] == subject_ref
        and item["category"] == "capability"
        and item["position"] == "available"
    )


def resource_quantity(snapshot: dict, subject_ref: str) -> int:
    return int(resource_entry(snapshot, subject_ref)["native_measure"]["quantity"])


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        worker_a = IdentityKey.load_or_create(root / "worker-a" / "body-p256.pem")
        worker_b = IdentityKey.load_or_create(root / "worker-b" / "body-p256.pem")

        compute_ref = "capability:compute-pool-039"
        compute = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref=compute_ref,
            source_ref="ghot-node:guild-compute-039",
            evidence_refs=["receipt:compute-probe-039"],
            native_measure={"unit": "compute-minute", "quantity": 120},
            metadata={"capability": "render.verified"},
        )
        snapshot0 = make_treasury_snapshot(
            guild_id="guild:lantern-forge",
            steward=guild,
            entries=[compute],
            sequence=0,
        )
        assert verify_treasury_snapshot(snapshot0)
        frozen_snapshot0 = json.dumps(snapshot0, sort_keys=True)

        store = GuildReservationStore(root / "reservation-state", steward=guild)

        proposal_a = make_resource_proposal(
            snapshot0,
            proposer=worker_a,
            resource_entry_id=compute["entry_id"],
            requested_quantity=80,
            requested_unit="compute-minute",
            purpose_ref="purpose:concurrent-a",
            proposed_at_cut=1,
        )
        proposal_b = make_resource_proposal(
            snapshot0,
            proposer=worker_b,
            resource_entry_id=compute["entry_id"],
            requested_quantity=80,
            requested_unit="compute-minute",
            purpose_ref="purpose:concurrent-b",
            proposed_at_cut=1,
        )

        def attempt(label: str, proposal: dict, worker: IdentityKey):
            try:
                auth, reservation = store.reserve_and_authorize(
                    snapshot0,
                    proposal,
                    executor_particular=worker.particular(),
                    authorized_at_cut=1,
                    expires_after_cut=4,
                )
                return {
                    "label": label,
                    "ok": True,
                    "proposal": proposal,
                    "worker": worker,
                    "authorization": auth,
                    "reservation": reservation,
                }
            except LightwalkerEconomyError as exc:
                return {
                    "label": label,
                    "ok": False,
                    "error": str(exc),
                    "proposal": proposal,
                    "worker": worker,
                }

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda args: attempt(*args),
                    [
                        ("A", proposal_a, worker_a),
                        ("B", proposal_b, worker_b),
                    ],
                )
            )

        winners = [item for item in results if item["ok"]]
        losers = [item for item in results if not item["ok"]]
        assert len(winners) == 1
        assert len(losers) == 1
        winner = winners[0]
        loser = losers[0]
        assert "unencumbered" in loser["error"]

        capacity_after_race = store.capacity_state(
            snapshot0, compute["entry_id"]
        )
        assert capacity_after_race["visible_quantity"] == 120
        assert capacity_after_race["reserved_quantity"] == 80
        assert capacity_after_race["unencumbered_quantity"] == 40
        assert json.dumps(snapshot0, sort_keys=True) == frozen_snapshot0

        winner_auth = winner["authorization"]
        winner_reservation = winner["reservation"]
        winner_proposal = winner["proposal"]

        assert verify_reservation(
            snapshot0,
            winner_proposal,
            winner_auth,
            winner_reservation,
        )

        # Releasing the winning reservation does not execute or consume.
        release = store.release(
            snapshot0,
            winner_proposal,
            winner_auth,
            winner_reservation,
            observed_cut=2,
            reason="GUILD_CANCELLED_BEFORE_EXECUTION",
        )
        assert verify_finalization(winner_reservation, release)
        assert release["status"] == "RELEASED"
        assert release["consumed_measure"] is None
        assert release["released_measure"]["quantity"] == 80

        released_execution_refused = refused(
            lambda: store.execute_reserved(
                snapshot0,
                winner_proposal,
                winner_auth,
                winner_reservation,
                executor=winner["worker"],
                observed_cut=2,
                simulate_success=True,
                result_ref="result:must-not-run",
            )
        )
        assert released_execution_refused

        after_release = store.capacity_state(snapshot0, compute["entry_id"])
        assert after_release["reserved_quantity"] == 0
        assert after_release["unencumbered_quantity"] == 120

        # The proposal that lost the race can now receive its own fresh
        # authorization + reservation.
        loser_auth, loser_reservation = store.reserve_and_authorize(
            snapshot0,
            loser["proposal"],
            executor_particular=loser["worker"].particular(),
            authorized_at_cut=2,
            expires_after_cut=4,
        )
        assert verify_reservation(
            snapshot0,
            loser["proposal"],
            loser_auth,
            loser_reservation,
        )

        success_receipt, success_finalization = store.execute_reserved(
            snapshot0,
            loser["proposal"],
            loser_auth,
            loser_reservation,
            executor=loser["worker"],
            observed_cut=3,
            simulate_success=True,
            result_ref=content_address(
                {
                    "kind": "reserved-render-result",
                    "proposal_id": loser["proposal"]["proposal_id"],
                    "quantity": 80,
                }
            ),
        )
        assert success_receipt["success"] is True
        assert success_finalization["status"] == "CONSUMED"
        assert verify_finalization(
            loser_reservation, success_finalization
        )

        snapshot1 = apply_execution_to_treasury(
            snapshot0,
            loser["proposal"],
            loser_auth,
            success_receipt,
            steward=guild,
        )
        assert verify_treasury_snapshot(snapshot1)
        assert resource_quantity(snapshot1, compute_ref) == 40
        assert snapshot1["prior_snapshot_id"] == snapshot0["snapshot_id"]
        assert json.dumps(snapshot0, sort_keys=True) == frozen_snapshot0
        frozen_snapshot1 = json.dumps(snapshot1, sort_keys=True)

        # Expiry releases reservation without execution or consumption.
        compute1 = resource_entry(snapshot1, compute_ref)
        expiry_proposal = make_resource_proposal(
            snapshot1,
            proposer=worker_a,
            resource_entry_id=compute1["entry_id"],
            requested_quantity=30,
            requested_unit="compute-minute",
            purpose_ref="purpose:expiry-control",
            proposed_at_cut=4,
        )
        expiry_auth, expiry_reservation = store.reserve_and_authorize(
            snapshot1,
            expiry_proposal,
            executor_particular=worker_a.particular(),
            authorized_at_cut=4,
            expires_after_cut=4,
        )
        expiry_release = store.release_expired(
            snapshot1,
            expiry_proposal,
            expiry_auth,
            expiry_reservation,
            observed_cut=5,
        )
        assert expiry_release["status"] == "RELEASED"
        assert expiry_release["reason"] == "AUTHORIZATION_EXPIRED"
        assert expiry_release["consumed_measure"] is None
        assert resource_quantity(snapshot1, compute_ref) == 40

        # Failure spends authorization but releases reservation and preserves
        # capacity. The failure is still applied to the treasury as evidence.
        failure_proposal = make_resource_proposal(
            snapshot1,
            proposer=worker_b,
            resource_entry_id=compute1["entry_id"],
            requested_quantity=30,
            requested_unit="compute-minute",
            purpose_ref="purpose:failure-control",
            proposed_at_cut=5,
        )
        failure_auth, failure_reservation = store.reserve_and_authorize(
            snapshot1,
            failure_proposal,
            executor_particular=worker_b.particular(),
            authorized_at_cut=5,
            expires_after_cut=7,
        )
        failure_receipt, failure_finalization = store.execute_reserved(
            snapshot1,
            failure_proposal,
            failure_auth,
            failure_reservation,
            executor=worker_b,
            observed_cut=6,
            simulate_success=False,
            error="simulation: execution failed before compute consumption",
        )
        assert failure_receipt["status"] == "FAILED"
        assert failure_receipt["authorization_spent"] is True
        assert failure_receipt["consumed_measure"] is None
        assert failure_finalization["status"] == "RELEASED"
        assert failure_finalization["reason"] == "EXECUTION_FAILED"

        snapshot2 = apply_execution_to_treasury(
            snapshot1,
            failure_proposal,
            failure_auth,
            failure_receipt,
            steward=guild,
        )
        assert verify_treasury_snapshot(snapshot2)
        assert resource_quantity(snapshot2, compute_ref) == 40
        assert json.dumps(snapshot1, sort_keys=True) == frozen_snapshot1

        # Failure release makes capacity authorizable again, but against the
        # new treasury snapshot/evidence head.
        compute2 = resource_entry(snapshot2, compute_ref)
        recovery_proposal = make_resource_proposal(
            snapshot2,
            proposer=worker_a,
            resource_entry_id=compute2["entry_id"],
            requested_quantity=30,
            requested_unit="compute-minute",
            purpose_ref="purpose:post-failure-recovery",
            proposed_at_cut=7,
        )
        recovery_auth, recovery_reservation = store.reserve_and_authorize(
            snapshot2,
            recovery_proposal,
            executor_particular=worker_a.particular(),
            authorized_at_cut=7,
            expires_after_cut=9,
        )
        recovery_state = store.capacity_state(
            snapshot2, compute2["entry_id"]
        )
        assert recovery_state["visible_quantity"] == 40
        assert recovery_state["reserved_quantity"] == 30
        assert recovery_state["unencumbered_quantity"] == 10

        recovery_release = store.release(
            snapshot2,
            recovery_proposal,
            recovery_auth,
            recovery_reservation,
            observed_cut=7,
            reason="END_OF_SPECIMEN",
        )
        assert recovery_release["status"] == "RELEASED"

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "concurrent_race": {
                        "visible_capacity": 120,
                        "requests": [80, 80],
                        "reservations_granted": 1,
                        "reservations_refused": 1,
                        "reserved_after_race": 80,
                        "unencumbered_after_race": 40,
                    },
                    "release": {
                        "status": release["status"],
                        "released_quantity": release["released_measure"]["quantity"],
                        "execution_after_release_refused": released_execution_refused,
                        "capacity_after_release": 120,
                    },
                    "successful_execution": {
                        "consumed_quantity": 80,
                        "reservation_status": success_finalization["status"],
                        "treasury_capacity_after_success": 40,
                    },
                    "expiry": {
                        "reservation_status": expiry_release["status"],
                        "reason": expiry_release["reason"],
                        "treasury_capacity_after_expiry": 40,
                    },
                    "failure": {
                        "execution_status": failure_receipt["status"],
                        "authorization_spent": failure_receipt["authorization_spent"],
                        "reservation_status": failure_finalization["status"],
                        "reservation_reason": failure_finalization["reason"],
                        "treasury_capacity_after_failure": 40,
                    },
                    "recovery": {
                        "fresh_snapshot_required": True,
                        "reserved_quantity": recovery_state["reserved_quantity"],
                        "unencumbered_quantity": recovery_state["unencumbered_quantity"],
                    },
                    "laws": [
                        "VISIBLE CAPACITY != UNENCUMBERED CAPACITY",
                        "AUTHORIZATION != RESERVATION",
                        "RESERVATION != CONSUMPTION",
                        "RELEASE != EXECUTION",
                        "RELEASED RESERVATION INVALIDATES RESERVED EXECUTION",
                        "ACTIVE RESERVATIONS MAY NOT EXCEED VISIBLE CAPACITY",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
