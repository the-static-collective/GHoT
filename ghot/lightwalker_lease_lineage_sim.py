#!/usr/bin/env python3
"""Experiment 043 — lease lineage / current authority DAG."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_capacity_lease import GuildCapacityLeaseIssuer, NodeLeaseBudget
from lightwalker_economy import LightwalkerEconomyError
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from lightwalker_lease_handoff import (
    LeaseHandoffStore,
    materialize_children,
)
from lightwalker_lease_lineage import (
    compact_authority_view,
    derive_authority_dag,
)
from relatte_identity import IdentityKey
from state_parcel import StateParcelInbox


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
            subject_ref="capability:compute-pool-043",
            source_ref="ghot-node:guild-compute-043",
            evidence_refs=["receipt:compute-probe-043"],
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

        budget_a = NodeLeaseBudget(root / "node-a-budget", node=node_a.signer)
        parent_use = budget_a.execute(
            parent,
            quantity=20,
            observed_cut=2,
            purpose_ref="purpose:root-use",
            success=True,
        )

        root_handoff = LeaseHandoffStore(
            root / "node-a-budget",
            node=node_a.signer,
        )
        root_surrender = root_handoff.surrender(
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
        children = materialize_children(
            snapshot,
            parent,
            root_surrender,
            steward=guild,
            issued_at_cut=3,
            expires_after_cut=8,
        )
        child_a = next(
            x for x in children
            if x["node_particular"] == node_a.signer.particular()
        )
        child_b = next(
            x for x in children
            if x["node_particular"] == node_b.signer.particular()
        )

        child_a_use = budget_a.execute(
            child_a,
            quantity=5,
            observed_cut=4,
            purpose_ref="purpose:child-a-use",
            success=True,
        )
        child_a_handoff = LeaseHandoffStore(
            root / "node-a-budget",
            node=node_a.signer,
        )
        child_a_surrender = child_a_handoff.surrender(
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
        residual_child = materialize_children(
            snapshot,
            child_a,
            child_a_surrender,
            steward=guild,
            issued_at_cut=5,
            expires_after_cut=8,
        )[0]

        budget_b = NodeLeaseBudget(root / "node-b-budget", node=node_b.signer)
        child_b_use = budget_b.execute(
            child_b,
            quantity=20,
            observed_cut=4,
            purpose_ref="purpose:child-b-use",
            success=True,
        )
        child_b_handoff = LeaseHandoffStore(
            root / "node-b-budget",
            node=node_b.signer,
        )
        child_b_surrender = child_b_handoff.surrender(
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
        renewed_b = materialize_children(
            snapshot,
            child_b,
            child_b_surrender,
            steward=guild,
            issued_at_cut=5,
            expires_after_cut=12,
            allow_renewal=True,
        )[0]
        renewed_use = budget_b.execute(
            renewed_b,
            quantity=6,
            observed_cut=9,
            purpose_ref="purpose:renewed-use",
            success=True,
        )

        descendants = [
            child_a,
            child_b,
            residual_child,
            renewed_b,
        ]
        surrenders = [
            root_surrender,
            child_a_surrender,
            child_b_surrender,
        ]
        uses = [
            parent_use,
            child_a_use,
            child_b_use,
            renewed_use,
        ]

        dag = derive_authority_dag(
            snapshot,
            root_lease=parent,
            descendant_leases=descendants,
            surrenders=surrenders,
            uses=uses,
            observed_cut=9,
        )
        view = compact_authority_view(dag)

        assert dag["conservation_status"] == "BALANCED"
        assert dag["totals"]["root_quantity"] == 60
        assert dag["totals"]["consumed_quantity"] == 51
        assert dag["totals"]["returned_to_guild_quantity"] == 0
        assert dag["totals"]["live_leaf_remaining_quantity"] == 4
        assert dag["totals"]["expired_leaf_remaining_quantity"] == 5
        assert dag["totals"]["accounted_quantity"] == 60

        assert dag["live_leaf_lease_ids"] == [renewed_b["lease_id"]]
        assert dag["expired_leaf_lease_ids"] == [residual_child["lease_id"]]
        assert set(dag["ancestor_lease_ids"]) == {
            parent["lease_id"],
            child_a["lease_id"],
            child_b["lease_id"],
        }

        assert len(view["live_leaves"]) == 1
        assert view["live_leaves"][0]["lease_id"] == renewed_b["lease_id"]
        assert view["live_leaves"][0]["remaining_quantity"] == 4
        assert view["history_digest"] == dag["history_digest"]
        assert view["history_retained_by_digest"] is True

        # Duplicate descendant materialization from the same surrender slot is
        # signed but must be rejected by lineage reconstruction.
        duplicate_child = materialize_children(
            snapshot,
            child_a,
            child_a_surrender,
            steward=guild,
            issued_at_cut=6,
            expires_after_cut=8,
        )[0]
        duplicate_descendant_refused = refused(
            lambda: derive_authority_dag(
                snapshot,
                root_lease=parent,
                descendant_leases=[*descendants, duplicate_child],
                surrenders=surrenders,
                uses=uses,
                observed_cut=9,
            )
        )
        assert duplicate_descendant_refused

        missing_surrender_refused = refused(
            lambda: derive_authority_dag(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=[root_surrender, child_b_surrender],
                uses=uses,
                observed_cut=9,
            )
        )
        assert missing_surrender_refused

        missing_use_refused = refused(
            lambda: derive_authority_dag(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                uses=[
                    parent_use,
                    child_b_use,
                    renewed_use,
                ],
                observed_cut=9,
            )
        )
        assert missing_use_refused

        tampered_child = json.loads(json.dumps(residual_child))
        tampered_child["leased_measure"]["quantity"] = 6
        tampered_child_refused = refused(
            lambda: derive_authority_dag(
                snapshot,
                root_lease=parent,
                descendant_leases=[
                    child_a,
                    child_b,
                    tampered_child,
                    renewed_b,
                ],
                surrenders=surrenders,
                uses=uses,
                observed_cut=9,
            )
        )
        assert tampered_child_refused

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "lineage": {
                        "root_quantity": 60,
                        "lease_nodes": len(dag["nodes"]),
                        "edges": len(dag["edges"]),
                        "ancestor_count": len(dag["ancestor_lease_ids"]),
                        "live_leaf_count": len(dag["live_leaf_lease_ids"]),
                        "expired_leaf_count": len(
                            dag["expired_leaf_lease_ids"]
                        ),
                    },
                    "authority_surface_at_cut_9": {
                        "live_leaf": renewed_b["lease_id"],
                        "live_remaining": 4,
                        "expired_leaf": residual_child["lease_id"],
                        "expired_remaining": 5,
                        "consumed": 51,
                        "accounted": 60,
                    },
                    "hostile_controls": {
                        "duplicate_descendant_refused": (
                            duplicate_descendant_refused
                        ),
                        "missing_surrender_refused": (
                            missing_surrender_refused
                        ),
                        "missing_use_history_refused": missing_use_refused,
                        "tampered_child_refused": tampered_child_refused,
                    },
                    "compaction": {
                        "history_digest_preserved": True,
                        "live_leaf_set_preserved": True,
                        "history_deleted": False,
                    },
                    "laws": [
                        "ANCESTOR HISTORY != LIVE AUTHORITY",
                        "LEAF SET DEFINES CURRENT AUTHORITY",
                        "DESCENDANT != DUPLICATE",
                        "LINEAGE PROOF != OWNERSHIP",
                        "COMPACTION != HISTORY DELETION",
                        "CONSERVATION != GLOBAL CONSENSUS",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
