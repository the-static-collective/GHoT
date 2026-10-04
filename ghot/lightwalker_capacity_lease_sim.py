#!/usr/bin/env python3
"""Experiment 041 — capacity leases / partitioned authority."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_capacity_lease import (
    GuildCapacityLeaseIssuer,
    NodeLeaseBudget,
    make_lease_crossing,
    settle_closed_leases_to_treasury,
    verify_capacity_lease,
    verify_lease_use,
    verify_release_receipt,
)
from lightwalker_economy import LightwalkerEconomyError
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


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


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        node_a = StateParcelInbox(root / "node-a")
        node_b = StateParcelInbox(root / "node-b")
        node_c = StateParcelInbox(root / "node-c")

        compute_ref = "capability:compute-pool-041"
        compute = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref=compute_ref,
            source_ref="ghot-node:guild-compute-041",
            evidence_refs=["receipt:compute-probe-041"],
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

        issuer = GuildCapacityLeaseIssuer(root / "issuer-state", steward=guild)

        lease_a = issuer.issue(
            snapshot0,
            resource_entry_id=compute["entry_id"],
            node_id="guild-node-a",
            node_particular=node_a.signer.particular(),
            unit="compute-minute",
            quantity=60,
            issued_at_cut=1,
            expires_after_cut=8,
        )
        lease_b = issuer.issue(
            snapshot0,
            resource_entry_id=compute["entry_id"],
            node_id="guild-node-b",
            node_particular=node_b.signer.particular(),
            unit="compute-minute",
            quantity=60,
            issued_at_cut=1,
            expires_after_cut=8,
        )
        assert verify_capacity_lease(snapshot0, lease_a)
        assert verify_capacity_lease(snapshot0, lease_b)

        overlease_refused = refused(
            lambda: issuer.issue(
                snapshot0,
                resource_entry_id=compute["entry_id"],
                node_id="guild-node-c",
                node_particular=node_c.signer.particular(),
                unit="compute-minute",
                quantity=1,
                issued_at_cut=1,
                expires_after_cut=8,
            )
        )
        assert overlease_refused

        crossing_a = make_lease_crossing(lease_a, signer=guild)
        crossing_b = make_lease_crossing(lease_b, signer=guild)
        assert verify_crossing(crossing_a)
        assert verify_crossing(crossing_b)
        assert crossing_a["requested_effect"]["automatic_consumption_requested"] is False
        assert crossing_a["requested_effect"]["ownership_transfer_requested"] is False
        assert crossing_a["requested_effect"]["global_consensus_requested"] is False

        # Portable delivery remains HOLD-first.
        source = root / "lease-source"
        pa = source / "leases" / "a.json"
        pb = source / "leases" / "b.json"
        pa.parent.mkdir(parents=True, exist_ok=True)
        pa.write_text(
            json.dumps({"lease": lease_a, "crossing": crossing_a}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        pb.write_text(
            json.dumps({"lease": lease_b, "crossing": crossing_b}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        exporter = StateParcelExporter(source)
        ba = exporter.export(
            str(pa.relative_to(source)),
            selector="$",
            target_particular=node_a.signer.particular(),
        )
        bb = exporter.export(
            str(pb.relative_to(source)),
            selector="$",
            target_particular=node_b.signer.particular(),
        )
        held_a = node_a.receive(ba)
        held_b = node_b.receive(bb)
        assert held_a["kind"] == "HELD" and held_b["kind"] == "HELD"
        admitted_a = node_a.decide(
            ba["parcel"]["parcel_id"],
            "ADMIT",
            note="041 admit bounded capacity lease; no ownership transfer",
        )
        admitted_b = node_b.decide(
            bb["parcel"]["parcel_id"],
            "ADMIT",
            note="041 admit bounded capacity lease; no ownership transfer",
        )
        assert admitted_a["kind"] == "ADMITTED"
        assert admitted_b["kind"] == "ADMITTED"

        budget_a = NodeLeaseBudget(root / "node-a-budget", node=node_a.signer)
        budget_b = NodeLeaseBudget(root / "node-b-budget", node=node_b.signer)

        cross_node_use_refused = refused(
            lambda: budget_b.execute(
                lease_a,
                quantity=1,
                observed_cut=2,
                purpose_ref="purpose:wrong-node",
                success=True,
            )
        )
        assert cross_node_use_refused

        use_a = budget_a.execute(
            lease_a,
            quantity=50,
            observed_cut=2,
            purpose_ref="purpose:render-a",
            success=True,
        )
        assert verify_lease_use(lease_a, use_a)
        assert budget_a.state(lease_a)["remaining_quantity"] == 10

        a_overdraw_refused = refused(
            lambda: budget_a.execute(
                lease_a,
                quantity=20,
                observed_cut=3,
                purpose_ref="purpose:overdraw-a",
                success=True,
            )
        )
        assert a_overdraw_refused

        fail_b = budget_b.execute(
            lease_b,
            quantity=20,
            observed_cut=2,
            purpose_ref="purpose:failed-render-b",
            success=False,
        )
        assert verify_lease_use(lease_b, fail_b)
        assert fail_b["consumed_measure"] is None
        assert budget_b.state(lease_b)["remaining_quantity"] == 60

        use_b = budget_b.execute(
            lease_b,
            quantity=30,
            observed_cut=3,
            purpose_ref="purpose:render-b",
            success=True,
        )
        assert verify_lease_use(lease_b, use_b)
        assert budget_b.state(lease_b)["remaining_quantity"] == 30

        release_a = budget_a.release_receipt(lease_a, observed_cut=4)
        release_b = budget_b.release_receipt(lease_b, observed_cut=4)
        assert verify_release_receipt(lease_a, release_a)
        assert verify_release_receipt(lease_b, release_b)
        assert release_a["consumed_measure"]["quantity"] == 50
        assert release_a["returned_measure"]["quantity"] == 10
        assert release_b["consumed_measure"]["quantity"] == 30
        assert release_b["returned_measure"]["quantity"] == 30

        close_a = issuer.close(
            snapshot0,
            lease_a,
            node_release_receipt=release_a,
            observed_cut=5,
        )
        close_b = issuer.close(
            snapshot0,
            lease_b,
            node_release_receipt=release_b,
            observed_cut=5,
        )
        assert close_a["consumed_measure"]["quantity"] == 50
        assert close_b["consumed_measure"]["quantity"] == 30

        snapshot1 = settle_closed_leases_to_treasury(
            snapshot0,
            resource_entry_id=compute["entry_id"],
            closes=[close_a, close_b],
            steward=guild,
        )
        assert verify_treasury_snapshot(snapshot1)
        compute1 = resource_entry(snapshot1, compute_ref)
        assert compute1["native_measure"]["quantity"] == 40
        assert snapshot1["prior_snapshot_id"] == snapshot0["snapshot_id"]
        assert json.dumps(snapshot0, sort_keys=True) == frozen_snapshot0

        # Returned/unconsumed capacity is now available to a fresh partition on
        # the successor Treasury snapshot.
        successor_issuer = GuildCapacityLeaseIssuer(
            root / "successor-issuer-state",
            steward=guild,
        )
        lease_c = successor_issuer.issue(
            snapshot1,
            resource_entry_id=compute1["entry_id"],
            node_id="guild-node-c",
            node_particular=node_c.signer.particular(),
            unit="compute-minute",
            quantity=40,
            issued_at_cut=6,
            expires_after_cut=10,
        )
        assert verify_capacity_lease(snapshot1, lease_c)

        successor_overlease_refused = refused(
            lambda: successor_issuer.issue(
                snapshot1,
                resource_entry_id=compute1["entry_id"],
                node_id="guild-node-a",
                node_particular=node_a.signer.particular(),
                unit="compute-minute",
                quantity=1,
                issued_at_cut=6,
                expires_after_cut=10,
            )
        )
        assert successor_overlease_refused

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "partition": {
                        "treasury_capacity": 120,
                        "node_a_lease": 60,
                        "node_b_lease": 60,
                        "overlease_refused": overlease_refused,
                    },
                    "transport": {
                        "node_a_first": held_a["kind"],
                        "node_b_first": held_b["kind"],
                        "ownership_transfer": False,
                        "automatic_consumption": False,
                    },
                    "node_a": {
                        "consumed": 50,
                        "returned": 10,
                        "overdraw_refused": a_overdraw_refused,
                    },
                    "node_b": {
                        "failed_attempt_consumed": 0,
                        "successful_consumed": 30,
                        "returned": 30,
                        "failed_use_preserved_budget": True,
                    },
                    "authority": {
                        "cross_node_use_refused": cross_node_use_refused,
                        "shared_lock_required_between_nodes": False,
                    },
                    "treasury": {
                        "snapshot0_unchanged": True,
                        "total_consumed": 80,
                        "successor_capacity": 40,
                        "successor_fresh_lease": 40,
                        "successor_overlease_refused": successor_overlease_refused,
                    },
                    "laws": [
                        "SHARED CAPACITY != SHARED AUTHORITY",
                        "DELEGATED BUDGET != OWNERSHIP",
                        "LEASE != CONSUMPTION",
                        "PARTITION != GLOBAL CONSENSUS",
                        "FAILED USE != CONSUMPTION",
                        "UNUSED LEASE CAPACITY MAY RETURN WITHOUT HISTORY REWRITE",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
