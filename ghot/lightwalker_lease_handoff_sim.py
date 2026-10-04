#!/usr/bin/env python3
"""Experiment 042 — lease repartition / handoff / renewal."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_capacity_lease import (
    GuildCapacityLeaseIssuer,
    NodeLeaseBudget,
)
from lightwalker_economy import LightwalkerEconomyError
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from lightwalker_lease_handoff import (
    LeaseHandoffStore,
    make_child_lease_crossing,
    materialize_children,
    verify_child_lease,
    verify_surrender,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        node_a = StateParcelInbox(root / "node-a")
        node_b = StateParcelInbox(root / "node-b")

        compute = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref="capability:compute-pool-042",
            source_ref="ghot-node:guild-compute-042",
            evidence_refs=["receipt:compute-probe-042"],
            native_measure={"unit": "compute-minute", "quantity": 120},
            metadata={"capability": "render.verified"},
        )
        snapshot = make_treasury_snapshot(
            guild_id="guild:lantern-forge",
            steward=guild,
            entries=[compute],
            sequence=0,
        )
        assert verify_treasury_snapshot(snapshot)
        frozen_snapshot = json.dumps(snapshot, sort_keys=True)

        issuer = GuildCapacityLeaseIssuer(root / "issuer-state", steward=guild)
        parent = issuer.issue(
            snapshot,
            resource_entry_id=compute["entry_id"],
            node_id="guild-node-a",
            node_particular=node_a.signer.particular(),
            unit="compute-minute",
            quantity=60,
            issued_at_cut=1,
            expires_after_cut=8,
        )
        frozen_parent = json.dumps(parent, sort_keys=True)

        budget_a = NodeLeaseBudget(root / "node-a-budget", node=node_a.signer)
        use_parent = budget_a.execute(
            parent,
            quantity=20,
            observed_cut=2,
            purpose_ref="purpose:parent-use-before-handoff",
            success=True,
        )
        assert use_parent["consumed_measure"]["quantity"] == 20
        assert budget_a.state(parent)["remaining_quantity"] == 40

        handoff_a = LeaseHandoffStore(
            root / "node-a-budget",
            node=node_a.signer,
        )

        overpartition_refused = refused(
            lambda: handoff_a.surrender(
                snapshot,
                parent,
                allocations=[
                    {
                        "target_node_id": "guild-node-a",
                        "target_node_particular": node_a.signer.particular(),
                        "quantity": 20,
                    },
                    {
                        "target_node_id": "guild-node-b",
                        "target_node_particular": node_b.signer.particular(),
                        "quantity": 30,
                    },
                ],
                observed_cut=3,
            )
        )
        assert overpartition_refused

        surrender = handoff_a.surrender(
            snapshot,
            parent,
            allocations=[
                {
                    "target_node_id": "guild-node-a",
                    "target_node_particular": node_a.signer.particular(),
                    "quantity": 10,
                },
                {
                    "target_node_id": "guild-node-b",
                    "target_node_particular": node_b.signer.particular(),
                    "quantity": 30,
                },
            ],
            observed_cut=3,
        )
        assert verify_surrender(snapshot, parent, surrender)
        assert surrender["remaining_before_surrender"] == 40
        assert surrender["allocated_quantity"] == 40
        assert surrender["returned_to_guild_quantity"] == 0

        parent_reuse_refused = refused(
            lambda: budget_a.execute(
                parent,
                quantity=1,
                observed_cut=3,
                purpose_ref="purpose:parent-reuse-after-surrender",
                success=True,
            )
        )
        assert parent_reuse_refused

        expiry_extension_without_renewal_refused = refused(
            lambda: materialize_children(
                snapshot,
                parent,
                surrender,
                steward=guild,
                issued_at_cut=3,
                expires_after_cut=9,
                allow_renewal=False,
            )
        )
        assert expiry_extension_without_renewal_refused

        children = materialize_children(
            snapshot,
            parent,
            surrender,
            steward=guild,
            issued_at_cut=3,
            expires_after_cut=8,
            allow_renewal=False,
        )
        assert len(children) == 2
        assert all(verify_child_lease(snapshot, item) for item in children)
        assert sum(item["leased_measure"]["quantity"] for item in children) == 40

        child_a = next(
            item for item in children
            if item["node_particular"] == node_a.signer.particular()
        )
        child_b = next(
            item for item in children
            if item["node_particular"] == node_b.signer.particular()
        )
        assert child_a["leased_measure"]["quantity"] == 10
        assert child_b["leased_measure"]["quantity"] == 30
        assert child_a["parent_lease_id"] == parent["lease_id"]
        assert child_b["surrender_id"] == surrender["surrender_id"]

        # Child B crosses the sovereign boundary and still requires HOLD/ADMIT.
        crossing_b = make_child_lease_crossing(child_b, signer=guild)
        assert verify_crossing(crossing_b)
        assert crossing_b["requested_effect"]["automatic_consumption_requested"] is False
        assert crossing_b["requested_effect"]["parent_reactivation_requested"] is False

        source = root / "handoff-source"
        child_file = source / "child-b.json"
        source.mkdir(parents=True, exist_ok=True)
        child_file.write_text(
            json.dumps(
                {"child_lease": child_b, "crossing": crossing_b},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        bundle = StateParcelExporter(source).export(
            str(child_file.relative_to(source)),
            selector="$",
            target_particular=node_b.signer.particular(),
        )
        held_b = node_b.receive(bundle)
        assert held_b["kind"] == "HELD"
        admitted_b = node_b.decide(
            bundle["parcel"]["parcel_id"],
            "ADMIT",
            note="042 admit child lease after parent surrender; no parent reactivation",
        )
        assert admitted_b["kind"] == "ADMITTED"

        # The child leases now have independent, non-overlapping authority.
        use_a_child = budget_a.execute(
            child_a,
            quantity=5,
            observed_cut=4,
            purpose_ref="purpose:residual-a",
            success=True,
        )
        assert use_a_child["consumed_measure"]["quantity"] == 5
        assert budget_a.state(child_a)["remaining_quantity"] == 5

        budget_b = NodeLeaseBudget(root / "node-b-budget", node=node_b.signer)
        use_b_child = budget_b.execute(
            child_b,
            quantity=20,
            observed_cut=4,
            purpose_ref="purpose:handoff-b",
            success=True,
        )
        assert use_b_child["consumed_measure"]["quantity"] == 20
        assert budget_b.state(child_b)["remaining_quantity"] == 10

        # Renewal is a successor lease, never an in-place expiry edit.
        handoff_b = LeaseHandoffStore(
            root / "node-b-budget",
            node=node_b.signer,
        )
        renewal_surrender = handoff_b.surrender(
            snapshot,
            child_b,
            allocations=[
                {
                    "target_node_id": "guild-node-b",
                    "target_node_particular": node_b.signer.particular(),
                    "quantity": 10,
                }
            ],
            observed_cut=5,
        )
        assert verify_surrender(snapshot, child_b, renewal_surrender)

        old_child_reuse_refused = refused(
            lambda: budget_b.execute(
                child_b,
                quantity=1,
                observed_cut=5,
                purpose_ref="purpose:old-child-after-renewal-surrender",
                success=True,
            )
        )
        assert old_child_reuse_refused

        renewed = materialize_children(
            snapshot,
            child_b,
            renewal_surrender,
            steward=guild,
            issued_at_cut=5,
            expires_after_cut=12,
            allow_renewal=True,
        )
        assert len(renewed) == 1
        renewed_b = renewed[0]
        assert verify_child_lease(snapshot, renewed_b)
        assert renewed_b["renewal"] is True
        assert renewed_b["expires_after_cut"] == 12
        assert renewed_b["leased_measure"]["quantity"] == 10
        assert renewed_b["parent_lease_id"] == child_b["lease_id"]

        renewed_use = budget_b.execute(
            renewed_b,
            quantity=6,
            observed_cut=9,
            purpose_ref="purpose:renewed-b",
            success=True,
        )
        assert renewed_use["consumed_measure"]["quantity"] == 6
        assert budget_b.state(renewed_b)["remaining_quantity"] == 4

        # Renewal to another node while extending expiry is refused in v0.
        handoff_a_residual = LeaseHandoffStore(
            root / "node-a-budget",
            node=node_a.signer,
        )
        residual_surrender = handoff_a_residual.surrender(
            snapshot,
            child_a,
            allocations=[
                {
                    "target_node_id": "guild-node-b",
                    "target_node_particular": node_b.signer.particular(),
                    "quantity": 5,
                }
            ],
            observed_cut=5,
        )
        cross_node_renewal_refused = refused(
            lambda: materialize_children(
                snapshot,
                child_a,
                residual_surrender,
                steward=guild,
                issued_at_cut=5,
                expires_after_cut=12,
                allow_renewal=True,
            )
        )
        assert cross_node_renewal_refused

        # Plain handoff of that residual 5 remains legal if expiry is not extended.
        residual_child = materialize_children(
            snapshot,
            child_a,
            residual_surrender,
            steward=guild,
            issued_at_cut=5,
            expires_after_cut=8,
            allow_renewal=False,
        )[0]
        assert verify_child_lease(snapshot, residual_child)
        assert residual_child["node_particular"] == node_b.signer.particular()
        assert residual_child["leased_measure"]["quantity"] == 5

        assert json.dumps(snapshot, sort_keys=True) == frozen_snapshot
        assert json.dumps(parent, sort_keys=True) == frozen_parent

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "parent": {
                        "leased": 60,
                        "consumed_before_handoff": 20,
                        "remaining_before_handoff": 40,
                        "overpartition_refused": overpartition_refused,
                        "reuse_after_surrender_refused": parent_reuse_refused,
                    },
                    "repartition": {
                        "child_a": 10,
                        "child_b": 30,
                        "child_sum": 40,
                        "simultaneous_parent_authority": False,
                        "expiry_extension_without_renewal_refused": (
                            expiry_extension_without_renewal_refused
                        ),
                    },
                    "crossing": {
                        "child_b_first_disposition": held_b["kind"],
                        "child_b_owner_disposition": admitted_b["kind"],
                        "parent_reactivation_requested": False,
                    },
                    "child_use": {
                        "a_consumed": 5,
                        "a_remaining_before_second_handoff": 5,
                        "b_consumed": 20,
                        "b_remaining_before_renewal": 10,
                    },
                    "renewal": {
                        "old_child_reuse_refused": old_child_reuse_refused,
                        "renewed_quantity": 10,
                        "old_expiry": 8,
                        "new_expiry": 12,
                        "renewed_consumed": 6,
                        "renewed_remaining": 4,
                        "cross_node_expiry_extension_refused": (
                            cross_node_renewal_refused
                        ),
                    },
                    "history": {
                        "treasury_snapshot_unchanged": True,
                        "parent_lease_unchanged": True,
                        "surrender_is_new_history": True,
                        "children_are_new_authority_objects": True,
                    },
                    "laws": [
                        "TRANSFER != DUPLICATION",
                        "HANDOFF != SIMULTANEOUS AUTHORITY",
                        "CHILD LEASE SUM <= PARENT REMAINDER",
                        "RENEWAL != NEW OWNERSHIP",
                        "EXPIRY != HISTORY ERASURE",
                        "SURRENDER != CONSUMPTION",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
