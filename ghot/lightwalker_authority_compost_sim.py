#!/usr/bin/env python3
"""Experiment 044 — expiry reclamation / authority compost."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_authority_compost import (
    ExpiredAuthorityReclaimStore,
    make_reclaim_overlay,
    make_reclaimed_lease_crossing,
    verify_reclaim_receipt,
    verify_reclaimed_lease,
)
from lightwalker_capacity_lease import GuildCapacityLeaseIssuer, NodeLeaseBudget
from lightwalker_economy import LightwalkerEconomyError
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    next_treasury_snapshot,
    verify_treasury_snapshot,
)
from lightwalker_lease_handoff import LeaseHandoffStore, materialize_children
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
        outsider = IdentityKey.load_or_create(root / "outsider" / "body-p256.pem")
        node_a = StateParcelInbox(root / "node-a")
        node_b = StateParcelInbox(root / "node-b")
        node_c = StateParcelInbox(root / "node-c")

        compute = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref="capability:compute-pool-044",
            source_ref="ghot-node:guild-compute-044",
            evidence_refs=["receipt:compute-probe-044"],
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
            item
            for item in children
            if item["node_particular"] == node_a.signer.particular()
        )
        child_b = next(
            item
            for item in children
            if item["node_particular"] == node_b.signer.particular()
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
        uses = [parent_use, child_a_use, child_b_use, renewed_use]

        reclaim_store = ExpiredAuthorityReclaimStore(
            root / "reclaim-state",
            steward=guild,
        )

        pre_expiry_refused = refused(
            lambda: reclaim_store.reclaim(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                uses=[
                    parent_use,
                    child_a_use,
                    child_b_use,
                ],
                expired_lease_id=residual_child["lease_id"],
                observed_cut=8,
            )
        )
        assert pre_expiry_refused

        live_leaf_refused = refused(
            lambda: reclaim_store.reclaim(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                uses=uses,
                expired_lease_id=renewed_b["lease_id"],
                observed_cut=9,
            )
        )
        assert live_leaf_refused

        outsider_store = ExpiredAuthorityReclaimStore(
            root / "outsider-reclaim-state",
            steward=outsider,
        )
        outsider_refused = refused(
            lambda: outsider_store.reclaim(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                uses=uses,
                expired_lease_id=residual_child["lease_id"],
                observed_cut=9,
            )
        )
        assert outsider_refused

        missing_history_refused = refused(
            lambda: reclaim_store.reclaim(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                uses=[parent_use, child_b_use, renewed_use],
                expired_lease_id=residual_child["lease_id"],
                observed_cut=9,
            )
        )
        assert missing_history_refused

        dag, reclaim = reclaim_store.reclaim(
            snapshot,
            root_lease=parent,
            descendant_leases=descendants,
            surrenders=surrenders,
            uses=uses,
            expired_lease_id=residual_child["lease_id"],
            observed_cut=9,
        )
        assert verify_reclaim_receipt(snapshot, dag, reclaim)
        assert reclaim["reclaimed_quantity"] == 5
        assert reclaim["revival_requested"] is False

        overlay = make_reclaim_overlay(snapshot, dag, [reclaim])
        assert overlay["reclaimed_expired_quantity"] == 5
        assert overlay["unreclaimed_expired_quantity"] == 0
        assert overlay["live_leaf_remaining_quantity"] == 4
        assert overlay["consumed_quantity"] == 51
        assert overlay["accounted_quantity"] == 60

        duplicate_reclaim_refused = refused(
            lambda: reclaim_store.reclaim(
                snapshot,
                root_lease=parent,
                descendant_leases=descendants,
                surrenders=surrenders,
                uses=uses,
                expired_lease_id=residual_child["lease_id"],
                observed_cut=10,
            )
        )
        assert duplicate_reclaim_refused

        # Expired authority remains dead after reclamation.
        expired_use_refused = refused(
            lambda: budget_b.execute(
                residual_child,
                quantity=1,
                observed_cut=9,
                purpose_ref="purpose:revive-expired",
                success=True,
            )
        )
        assert expired_use_refused

        reclaimed_lease = reclaim_store.reissue(
            snapshot,
            dag,
            reclaim,
            node_id="guild-node-c",
            node_particular=node_c.signer.particular(),
            issued_at_cut=9,
            expires_after_cut=14,
        )
        assert verify_reclaimed_lease(
            snapshot, dag, reclaim, reclaimed_lease
        )
        assert reclaimed_lease["leased_measure"]["quantity"] == 5
        assert (
            reclaimed_lease["reclaimed_from_lease_id"]
            == residual_child["lease_id"]
        )
        assert reclaimed_lease["lease_id"] != residual_child["lease_id"]

        duplicate_reissue_refused = refused(
            lambda: reclaim_store.reissue(
                snapshot,
                dag,
                reclaim,
                node_id="guild-node-a",
                node_particular=node_a.signer.particular(),
                issued_at_cut=10,
                expires_after_cut=14,
            )
        )
        assert duplicate_reissue_refused

        crossing = make_reclaimed_lease_crossing(
            reclaimed_lease,
            signer=guild,
        )
        assert verify_crossing(crossing)
        assert (
            crossing["requested_effect"]["expired_lease_revival_requested"]
            is False
        )
        assert (
            crossing["requested_effect"]["automatic_consumption_requested"]
            is False
        )

        source = root / "reclaim-source"
        payload = source / "reclaimed-lease.json"
        source.mkdir(parents=True, exist_ok=True)
        payload.write_text(
            json.dumps(
                {
                    "reclaim": reclaim,
                    "reclaimed_lease": reclaimed_lease,
                    "crossing": crossing,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        bundle = StateParcelExporter(source).export(
            str(payload.relative_to(source)),
            selector="$",
            target_particular=node_c.signer.particular(),
        )
        held = node_c.receive(bundle)
        assert held["kind"] == "HELD"
        assert held["semantic_effect"] == "none"
        admitted = node_c.decide(
            bundle["parcel"]["parcel_id"],
            "ADMIT",
            note=(
                "044 admit reclaimed lease as fresh authority; "
                "do not revive expired source lease"
            ),
        )
        assert admitted["kind"] == "ADMITTED"

        budget_c = NodeLeaseBudget(
            root / "node-c-budget",
            node=node_c.signer,
        )
        reclaimed_use = budget_c.execute(
            reclaimed_lease,
            quantity=3,
            observed_cut=10,
            purpose_ref="purpose:composted-capacity-use",
            success=True,
        )
        assert reclaimed_use["consumed_measure"]["quantity"] == 3
        assert budget_c.state(reclaimed_lease)["remaining_quantity"] == 2

        evidence_entry = make_treasury_entry(
            category="receipt",
            position="evidence",
            subject_ref="authority-reclaim:" + reclaim["reclaim_id"],
            source_ref=reclaim["reclaim_id"],
            evidence_refs=[
                dag["dag_id"],
                reclaim["reclaim_id"],
                reclaimed_lease["lease_id"],
            ],
            metadata={
                "expired_lease_id": residual_child["lease_id"],
                "reclaimed_quantity": 5,
                "fresh_lease_id": reclaimed_lease["lease_id"],
                "revival": False,
            },
        )
        successor_treasury = next_treasury_snapshot(
            snapshot,
            steward=guild,
            add_entries=[evidence_entry],
        )
        assert verify_treasury_snapshot(successor_treasury)
        assert successor_treasury["prior_snapshot_id"] == snapshot["snapshot_id"]
        assert json.dumps(snapshot, sort_keys=True) == frozen_snapshot

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "expired_authority": {
                        "expired_lease_id": residual_child["lease_id"],
                        "stranded_quantity": 5,
                        "pre_expiry_reclaim_refused": pre_expiry_refused,
                        "live_leaf_reclaim_refused": live_leaf_refused,
                        "expired_use_after_reclaim_refused": expired_use_refused,
                    },
                    "reclaim": {
                        "status": reclaim["status"],
                        "reclaimed_quantity": reclaim["reclaimed_quantity"],
                        "revival_requested": reclaim["revival_requested"],
                        "outsider_refused": outsider_refused,
                        "missing_history_refused": missing_history_refused,
                        "duplicate_reclaim_refused": duplicate_reclaim_refused,
                    },
                    "overlay": {
                        "consumed": overlay["consumed_quantity"],
                        "live_remaining": overlay[
                            "live_leaf_remaining_quantity"
                        ],
                        "expired_before_reclaim": overlay[
                            "expired_leaf_remaining_quantity"
                        ],
                        "reclaimed": overlay["reclaimed_expired_quantity"],
                        "unreclaimed_expired": overlay[
                            "unreclaimed_expired_quantity"
                        ],
                        "accounted": overlay["accounted_quantity"],
                    },
                    "fresh_authority": {
                        "new_lease_quantity": 5,
                        "new_lease_is_old_lease": False,
                        "duplicate_reissue_refused": duplicate_reissue_refused,
                        "node_c_consumed": 3,
                        "node_c_remaining": 2,
                    },
                    "crossing": {
                        "first_disposition": held["kind"],
                        "owner_disposition": admitted["kind"],
                        "expired_lease_revival_requested": False,
                    },
                    "treasury_history": {
                        "original_snapshot_unchanged": True,
                        "successor_records_reclaim_evidence": True,
                    },
                    "laws": [
                        "EXPIRY != RETURN",
                        "RECLAIM != REVIVAL",
                        "STRANDED AUTHORITY != LIVE AUTHORITY",
                        "RECLAIMED CAPACITY REQUIRES EVIDENCE",
                        "COMPOST != HISTORY ERASURE",
                        "REISSUE != CONTINUATION",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
