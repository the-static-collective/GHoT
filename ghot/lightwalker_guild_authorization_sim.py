#!/usr/bin/env python3
"""Experiment 038 — Guild Proposal / Treasury Authorization."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_authorization import (
    GuildAuthorizationStore,
    apply_execution_to_treasury,
    authorize_resource_proposal,
    make_resource_proposal,
    verify_execution_receipt,
    verify_resource_authorization,
    verify_resource_proposal,
)
from lightwalker_guild_treasury import (
    make_resource_view,
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


def capability_quantity(snapshot: dict, subject_ref: str) -> int:
    matches = [
        item
        for item in snapshot["entries"]
        if item["subject_ref"] == subject_ref
        and item["category"] == "capability"
        and item["position"] == "available"
    ]
    assert len(matches) == 1
    return int(matches[0]["native_measure"]["quantity"])


def capability_entry(snapshot: dict, subject_ref: str) -> dict:
    return next(
        item
        for item in snapshot["entries"]
        if item["subject_ref"] == subject_ref
        and item["category"] == "capability"
        and item["position"] == "available"
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        worker = IdentityKey.load_or_create(root / "worker" / "body-p256.pem")
        outsider = IdentityKey.load_or_create(root / "outsider" / "body-p256.pem")

        compute_ref = "capability:compute-pool-038"
        compute = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref=compute_ref,
            source_ref="ghot-node:guild-compute-038",
            evidence_refs=["receipt:compute-probe-038"],
            native_measure={"unit": "compute-minute", "quantity": 120},
            metadata={"capability": "render.verified"},
        )
        storage = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref="capability:storage-pool-038",
            source_ref="ghot-node:guild-storage-038",
            evidence_refs=["receipt:storage-probe-038"],
            native_measure={"unit": "gb-hour", "quantity": 480},
            metadata={"capability": "store.verified"},
        )
        snapshot0 = make_treasury_snapshot(
            guild_id="guild:lantern-forge",
            steward=guild,
            entries=[compute, storage],
            sequence=0,
        )
        assert verify_treasury_snapshot(snapshot0)
        assert capability_quantity(snapshot0, compute_ref) == 120
        frozen_snapshot0 = json.dumps(snapshot0, sort_keys=True)

        store = GuildAuthorizationStore(root / "guild-execution-state")

        # Capacity by itself cannot execute.
        proposal0 = make_resource_proposal(
            snapshot0,
            proposer=worker,
            resource_entry_id=compute["entry_id"],
            requested_quantity=30,
            requested_unit="compute-minute",
            purpose_ref="purpose:render-fractal-batch-038a",
            proposed_at_cut=1,
        )
        assert verify_resource_proposal(snapshot0, proposal0)

        capacity_alone_refused = refused(
            lambda: store.execute(
                snapshot0,
                proposal0,
                None,
                executor=worker,
                observed_cut=2,
                simulate_success=True,
                result_ref="result:must-not-exist",
            )
        )
        assert capacity_alone_refused

        outsider_authorization_refused = refused(
            lambda: authorize_resource_proposal(
                snapshot0,
                proposal0,
                steward=outsider,
                executor_particular=worker.particular(),
                authorized_at_cut=1,
                expires_after_cut=4,
            )
        )
        assert outsider_authorization_refused

        auth0 = authorize_resource_proposal(
            snapshot0,
            proposal0,
            steward=guild,
            executor_particular=worker.particular(),
            authorized_at_cut=1,
            expires_after_cut=4,
        )
        assert verify_resource_authorization(snapshot0, proposal0, auth0)

        # Exact proposal binding: rewriting purpose after authorization breaks it.
        tampered = json.loads(json.dumps(proposal0))
        tampered["purpose_ref"] = "purpose:other-work"
        tampered["proposal_id"] = content_address(
            {
                key: value
                for key, value in tampered.items()
                if key not in {"proposal_id", "signing"}
            }
        )
        tampered_auth_refused = not verify_resource_authorization(
            snapshot0,
            tampered,
            auth0,
        )
        assert tampered_auth_refused

        success_receipt = store.execute(
            snapshot0,
            proposal0,
            auth0,
            executor=worker,
            observed_cut=2,
            simulate_success=True,
            result_ref=content_address(
                {
                    "kind": "render-result",
                    "purpose_ref": proposal0["purpose_ref"],
                    "authorized_measure": auth0["authorized_measure"],
                }
            ),
        )
        assert verify_execution_receipt(
            snapshot0,
            proposal0,
            auth0,
            success_receipt,
        )
        assert success_receipt["success"] is True
        assert success_receipt["status"] == "EXECUTED"

        replay_success_refused = refused(
            lambda: store.execute(
                snapshot0,
                proposal0,
                auth0,
                executor=worker,
                observed_cut=3,
                simulate_success=True,
                result_ref="result:replay",
            )
        )
        assert replay_success_refused

        snapshot1 = apply_execution_to_treasury(
            snapshot0,
            proposal0,
            auth0,
            success_receipt,
            steward=guild,
        )
        assert verify_treasury_snapshot(snapshot1)
        assert snapshot1["prior_snapshot_id"] == snapshot0["snapshot_id"]
        assert capability_quantity(snapshot1, compute_ref) == 90
        assert json.dumps(snapshot0, sort_keys=True) == frozen_snapshot0
        frozen_snapshot1 = json.dumps(snapshot1, sort_keys=True)

        # A second, independently authorized attempt fails. Authorization is
        # spent, but no compute capacity is claimed as consumed.
        compute1 = capability_entry(snapshot1, compute_ref)
        proposal1 = make_resource_proposal(
            snapshot1,
            proposer=worker,
            resource_entry_id=compute1["entry_id"],
            requested_quantity=20,
            requested_unit="compute-minute",
            purpose_ref="purpose:render-fractal-batch-038b",
            proposed_at_cut=3,
        )
        auth1 = authorize_resource_proposal(
            snapshot1,
            proposal1,
            steward=guild,
            executor_particular=worker.particular(),
            authorized_at_cut=3,
            expires_after_cut=5,
        )

        failure_receipt = store.execute(
            snapshot1,
            proposal1,
            auth1,
            executor=worker,
            observed_cut=4,
            simulate_success=False,
            error="simulation: renderer crashed before resource consumption",
        )
        assert verify_execution_receipt(
            snapshot1,
            proposal1,
            auth1,
            failure_receipt,
        )
        assert failure_receipt["status"] == "FAILED"
        assert failure_receipt["success"] is False
        assert failure_receipt["authorization_spent"] is True
        assert failure_receipt["consumed_measure"] is None

        replay_failure_refused = refused(
            lambda: store.execute(
                snapshot1,
                proposal1,
                auth1,
                executor=worker,
                observed_cut=4,
                simulate_success=True,
                result_ref="result:retry-with-spent-authorization",
            )
        )
        assert replay_failure_refused

        snapshot2 = apply_execution_to_treasury(
            snapshot1,
            proposal1,
            auth1,
            failure_receipt,
            steward=guild,
        )
        assert verify_treasury_snapshot(snapshot2)
        assert snapshot2["prior_snapshot_id"] == snapshot1["snapshot_id"]
        assert capability_quantity(snapshot2, compute_ref) == 90
        assert json.dumps(snapshot1, sort_keys=True) == frozen_snapshot1

        # Fresh proposal requires fresh authorization. An expired authorization
        # cannot be revived merely because capacity still exists.
        compute2 = capability_entry(snapshot2, compute_ref)
        proposal2 = make_resource_proposal(
            snapshot2,
            proposer=worker,
            resource_entry_id=compute2["entry_id"],
            requested_quantity=10,
            requested_unit="compute-minute",
            purpose_ref="purpose:expired-auth-control",
            proposed_at_cut=5,
        )
        expired_auth = authorize_resource_proposal(
            snapshot2,
            proposal2,
            steward=guild,
            executor_particular=worker.particular(),
            authorized_at_cut=5,
            expires_after_cut=5,
        )
        expired_execution_refused = refused(
            lambda: store.execute(
                snapshot2,
                proposal2,
                expired_auth,
                executor=worker,
                observed_cut=6,
                simulate_success=True,
                result_ref="result:too-late",
            )
        )
        assert expired_execution_refused

        view2 = make_resource_view(snapshot2)
        assert view2["universal_total"] is None
        evidence_receipts = [
            item
            for item in snapshot2["entries"]
            if item["category"] == "receipt"
            and item["position"] == "evidence"
        ]
        assert len(evidence_receipts) == 2

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "capacity": {
                        "initial_compute_minutes": 120,
                        "after_success": 90,
                        "after_failure": 90,
                    },
                    "authority": {
                        "capacity_alone_refused": capacity_alone_refused,
                        "outsider_authorization_refused": outsider_authorization_refused,
                        "tampered_proposal_breaks_authorization": tampered_auth_refused,
                        "expired_authorization_refused": expired_execution_refused,
                    },
                    "successful_execution": {
                        "status": success_receipt["status"],
                        "authorization_spent": success_receipt["authorization_spent"],
                        "consumed_measure": success_receipt["consumed_measure"],
                        "replay_refused": replay_success_refused,
                    },
                    "failed_execution": {
                        "status": failure_receipt["status"],
                        "authorization_spent": failure_receipt["authorization_spent"],
                        "consumed_measure": failure_receipt["consumed_measure"],
                        "capacity_unchanged": True,
                        "replay_refused": replay_failure_refused,
                    },
                    "treasury_history": {
                        "snapshot0_immutable": True,
                        "snapshot1_immutable_after_failure": True,
                        "snapshot2_prior": snapshot2["prior_snapshot_id"],
                        "execution_evidence_receipts": len(evidence_receipts),
                        "universal_total": view2["universal_total"],
                    },
                    "laws": [
                        "CAPACITY != SPENDING AUTHORITY",
                        "PROPOSAL != AUTHORIZATION",
                        "AUTHORIZATION != EXECUTION",
                        "EXECUTION != SUCCESS",
                        "FAILED EXECUTION != RESOURCE CONSUMPTION",
                        "ONE AUTHORIZATION -> AT MOST ONE EXECUTION ATTEMPT",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
