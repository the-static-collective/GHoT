#!/usr/bin/env python3
"""Experiment 045 — Authority Metabolism."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_authority_compost import (
    ExpiredAuthorityReclaimStore,
)
from lightwalker_authority_metabolism import (
    derive_authority_metabolism,
    make_metabolism_crossing,
)
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
    materialize_children,
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
        node_c = StateParcelInbox(root / "node-c")

        compute = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref="capability:compute-pool-045",
            source_ref="ghot-node:guild-compute-045",
            evidence_refs=["receipt:compute-probe-045"],
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

        descendants = [child_a, child_b, residual_child, renewed_b]
        surrenders = [
            root_surrender,
            child_a_surrender,
            child_b_surrender,
        ]
        source_uses = [
            parent_use,
            child_a_use,
            child_b_use,
            renewed_use,
        ]

        reclaim_store = ExpiredAuthorityReclaimStore(
            root / "reclaim-state",
            steward=guild,
        )
        dag9, reclaim = reclaim_store.reclaim(
            snapshot,
            root_lease=parent,
            descendant_leases=descendants,
            surrenders=surrenders,
            uses=source_uses,
            expired_lease_id=residual_child["lease_id"],
            observed_cut=9,
        )

        # Intermediate form: reclaimed, but not yet reissued.
        composted_unissued = derive_authority_metabolism(
            snapshot,
            root_lease=parent,
            descendant_leases=descendants,
            surrenders=surrenders,
            source_uses=source_uses,
            reclaim_receipts=[reclaim],
            reissued_leases=[],
            recycled_uses=[],
            source_observed_cut=9,
            observed_cut=9,
        )
        assert composted_unissued["totals"]["root_quantity"] == 60
        assert composted_unissued["totals"]["source_consumed_quantity"] == 51
        assert composted_unissued["totals"]["source_live_quantity"] == 4
        assert (
            composted_unissued["totals"][
                "source_unreclaimed_expired_quantity"
            ]
            == 0
        )
        assert (
            composted_unissued["totals"]["reclaimed_unissued_quantity"]
            == 5
        )
        assert composted_unissued["totals"]["accounted_quantity"] == 60

        reclaimed_lease = reclaim_store.reissue(
            snapshot,
            dag9,
            reclaim,
            node_id="guild-node-c",
            node_particular=node_c.signer.particular(),
            issued_at_cut=9,
            expires_after_cut=14,
        )

        budget_c = NodeLeaseBudget(root / "node-c-budget", node=node_c.signer)
        recycled_use = budget_c.execute(
            reclaimed_lease,
            quantity=3,
            observed_cut=10,
            purpose_ref="purpose:metabolic-reuse",
            success=True,
        )

        metabolism = derive_authority_metabolism(
            snapshot,
            root_lease=parent,
            descendant_leases=descendants,
            surrenders=surrenders,
            source_uses=source_uses,
            reclaim_receipts=[reclaim],
            reissued_leases=[reclaimed_lease],
            recycled_uses=[recycled_use],
            source_observed_cut=9,
            observed_cut=10,
        )

        totals = metabolism["totals"]
        assert totals["root_quantity"] == 60
        assert totals["source_consumed_quantity"] == 51
        assert totals["source_returned_quantity"] == 0
        assert totals["source_live_quantity"] == 4
        assert totals["source_unreclaimed_expired_quantity"] == 0
        assert totals["reclaimed_unissued_quantity"] == 0
        assert totals["recycled_consumed_quantity"] == 3
        assert totals["recycled_live_quantity"] == 2
        assert totals["recycled_expired_quantity"] == 0
        assert totals["accounted_quantity"] == 60
        assert metabolism["conservation_status"] == "BALANCED"
        assert metabolism["spending_authority"] == "none"

        # Hostile controls.
        missing_reclaim_refused = refused(
            lambda: derive_authority_metabolism(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                source_uses=source_uses,
                reclaim_receipts=[],
                reissued_leases=[reclaimed_lease],
                recycled_uses=[recycled_use],
                source_observed_cut=9,
                observed_cut=10,
            )
        )
        assert missing_reclaim_refused

        duplicate_reissue_refused = refused(
            lambda: derive_authority_metabolism(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                source_uses=source_uses,
                reclaim_receipts=[reclaim],
                reissued_leases=[reclaimed_lease, reclaimed_lease],
                recycled_uses=[recycled_use],
                source_observed_cut=9,
                observed_cut=10,
            )
        )
        assert duplicate_reissue_refused

        duplicate_recycled_use_refused = refused(
            lambda: derive_authority_metabolism(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                source_uses=source_uses,
                reclaim_receipts=[reclaim],
                reissued_leases=[reclaimed_lease],
                recycled_uses=[recycled_use, recycled_use],
                source_observed_cut=9,
                observed_cut=10,
            )
        )
        assert duplicate_recycled_use_refused

        tampered_reissue = json.loads(json.dumps(reclaimed_lease))
        tampered_reissue["leased_measure"]["quantity"] = 6
        tampered_reissue_refused = refused(
            lambda: derive_authority_metabolism(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                source_uses=source_uses,
                reclaim_receipts=[reclaim],
                reissued_leases=[tampered_reissue],
                recycled_uses=[],
                source_observed_cut=9,
                observed_cut=10,
            )
        )
        assert tampered_reissue_refused

        missing_source_history_refused = refused(
            lambda: derive_authority_metabolism(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                source_uses=[
                    parent_use,
                    child_b_use,
                    renewed_use,
                ],
                reclaim_receipts=[reclaim],
                reissued_leases=[reclaimed_lease],
                recycled_uses=[recycled_use],
                source_observed_cut=9,
                observed_cut=10,
            )
        )
        assert missing_source_history_refused

        crossing = make_metabolism_crossing(
            metabolism,
            signer=guild,
        )
        assert verify_crossing(crossing)
        assert (
            crossing["requested_effect"]["automatic_execution_requested"]
            is False
        )
        assert crossing["requested_effect"]["mint_authority_requested"] is False
        assert crossing["requested_effect"]["history_rewrite_requested"] is False

        source = root / "metabolism-source"
        payload = source / "metabolism.json"
        source.mkdir(parents=True, exist_ok=True)
        payload.write_text(
            json.dumps(
                {
                    "metabolism": metabolism,
                    "crossing": crossing,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        receiver = StateParcelInbox(root / "metabolism-receiver")
        bundle = StateParcelExporter(source).export(
            str(payload.relative_to(source)),
            selector="$",
            target_particular=receiver.signer.particular(),
        )
        held = receiver.receive(bundle)
        assert held["kind"] == "HELD"
        assert held["semantic_effect"] == "none"
        admitted = receiver.decide(
            bundle["parcel"]["parcel_id"],
            "ADMIT",
            note=(
                "045 admit conservation audit as evidence only; "
                "no spending authority, minting, or history rewrite"
            ),
        )
        assert admitted["kind"] == "ADMITTED"

        # All historical objects remain unchanged.
        assert json.dumps(snapshot, sort_keys=True) == frozen_snapshot
        assert json.dumps(parent, sort_keys=True) == frozen_parent

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "cycle": [
                        "issue",
                        "partition",
                        "use",
                        "handoff",
                        "expire",
                        "reclaim",
                        "reissue",
                        "use-again",
                    ],
                    "intermediate_compost": {
                        "source_consumed": 51,
                        "source_live": 4,
                        "reclaimed_unissued": 5,
                        "accounted": 60,
                    },
                    "final_metabolism": {
                        "source_consumed": 51,
                        "source_live": 4,
                        "source_unreclaimed_expired": 0,
                        "recycled_consumed": 3,
                        "recycled_live": 2,
                        "accounted": 60,
                        "status": metabolism["conservation_status"],
                    },
                    "hostile_controls": {
                        "missing_reclaim_refused": missing_reclaim_refused,
                        "duplicate_reissue_refused": duplicate_reissue_refused,
                        "duplicate_recycled_use_refused": (
                            duplicate_recycled_use_refused
                        ),
                        "tampered_reissue_refused": tampered_reissue_refused,
                        "missing_source_history_refused": (
                            missing_source_history_refused
                        ),
                    },
                    "crossing": {
                        "first_disposition": held["kind"],
                        "owner_disposition": admitted["kind"],
                        "automatic_execution_requested": False,
                        "mint_authority_requested": False,
                        "history_rewrite_requested": False,
                    },
                    "laws": [
                        "AUTHORITY CHANGES FORM; ACCOUNTABILITY CONSERVES",
                        "EXPIRED + RECLAIMED MAY NOT BE DOUBLE COUNTED",
                        "RECLAIM != REVIVAL",
                        "REISSUE != CONTINUATION",
                        "METABOLISM WITNESS != SPENDING AUTHORITY",
                        "CONSERVATION != GLOBAL CONSENSUS",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
