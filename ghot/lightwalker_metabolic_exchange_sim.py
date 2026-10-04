#!/usr/bin/env python3
"""Experiment 046 — Metabolic Exchange."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_authority_compost import ExpiredAuthorityReclaimStore
from lightwalker_authority_metabolism import derive_authority_metabolism
from lightwalker_capacity_lease import GuildCapacityLeaseIssuer, NodeLeaseBudget
from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    accept_exchange_offer,
    make_exchange_offer,
    make_obligation,
    settle_exchange,
    sign_obligation_performance,
    verify_exchange_settlement,
)
from lightwalker_lease_handoff import LeaseHandoffStore, materialize_children
from lightwalker_metabolic_exchange import (
    acquisition_to_treasury_entry,
    derive_metabolic_exchange_witness,
    make_metabolic_exchange_crossing,
    make_settled_capacity_acquisition,
    verify_settled_capacity_acquisition,
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

        provider = IdentityKey.load_or_create(root / "provider" / "body-p256.pem")
        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        node_a = StateParcelInbox(root / "node-a")
        node_b = StateParcelInbox(root / "node-b")
        node_c = StateParcelInbox(root / "node-c")

        # ECONOMIC SIDE -----------------------------------------------------
        capacity_obligation = make_obligation(
            obligation_type="compute-capacity-delivery",
            resource_ref="compute:provider-pool-046",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="signed-provider-capacity-delivery",
        )
        guild_obligation = make_obligation(
            obligation_type="documentation-service",
            resource_ref="guild:documentation-pass-046",
            terms={
                "scope": "one-documentation-pass",
                "acceptance_test": "provider-local-review",
            },
            evidence_policy="signed-documentation-output",
        )

        offer = make_exchange_offer(
            offeror_particular=provider.particular(),
            offeror_obligation=capacity_obligation,
            acceptor_obligation=guild_obligation,
            orientation_refs=[],
            valid_through_cut=5,
        )
        acceptance = accept_exchange_offer(
            offer,
            acceptor_particular=guild.particular(),
            accepted_at_cut=1,
        )
        provider_perf = sign_obligation_performance(
            offer,
            acceptance,
            role="OFFEROR",
            signer=provider,
            evidence_ref=content_address(
                {
                    "kind": "capacity-delivery-evidence",
                    "quantity": 60,
                    "unit": "compute-minute",
                }
            ),
        )
        guild_perf = sign_obligation_performance(
            offer,
            acceptance,
            role="ACCEPTOR",
            signer=guild,
            evidence_ref=content_address(
                {
                    "kind": "documentation-output",
                    "scope": "one-documentation-pass",
                }
            ),
        )
        attestations = [provider_perf, guild_perf]
        settlement = settle_exchange(
            offer,
            acceptance,
            attestations,
        )
        assert verify_exchange_settlement(
            offer, acceptance, attestations, settlement
        )

        incomplete_settlement_admission_refused = refused(
            lambda: make_settled_capacity_acquisition(
                offer,
                acceptance,
                [provider_perf],
                settlement,
                steward=guild,
                guild_id="guild:lantern-forge",
                capacity_subject_ref="capability:acquired-compute-046",
                admitted_at_cut=2,
            )
        )
        assert incomplete_settlement_admission_refused

        # A settled non-capacity exchange cannot be admitted as compute.
        artifact_obligation = make_obligation(
            obligation_type="artifact-access",
            resource_ref="artifact:046-control",
            terms={"scope": "read-only"},
            evidence_policy="signed-artifact-grant",
        )
        control_offer = make_exchange_offer(
            offeror_particular=provider.particular(),
            offeror_obligation=artifact_obligation,
            acceptor_obligation=guild_obligation,
            orientation_refs=[],
            valid_through_cut=5,
        )
        control_acceptance = accept_exchange_offer(
            control_offer,
            acceptor_particular=guild.particular(),
            accepted_at_cut=1,
        )
        control_provider_perf = sign_obligation_performance(
            control_offer,
            control_acceptance,
            role="OFFEROR",
            signer=provider,
            evidence_ref="evidence:artifact-grant-046",
        )
        control_guild_perf = sign_obligation_performance(
            control_offer,
            control_acceptance,
            role="ACCEPTOR",
            signer=guild,
            evidence_ref="evidence:documentation-control-046",
        )
        control_attestations = [
            control_provider_perf,
            control_guild_perf,
        ]
        control_settlement = settle_exchange(
            control_offer,
            control_acceptance,
            control_attestations,
        )
        noncapacity_admission_refused = refused(
            lambda: make_settled_capacity_acquisition(
                control_offer,
                control_acceptance,
                control_attestations,
                control_settlement,
                steward=guild,
                guild_id="guild:lantern-forge",
                capacity_subject_ref="capability:must-not-exist",
                admitted_at_cut=2,
            )
        )
        assert noncapacity_admission_refused

        acquisition = make_settled_capacity_acquisition(
            offer,
            acceptance,
            attestations,
            settlement,
            steward=guild,
            guild_id="guild:lantern-forge",
            capacity_subject_ref="capability:acquired-compute-046",
            admitted_at_cut=2,
        )
        assert verify_settled_capacity_acquisition(
            offer,
            acceptance,
            attestations,
            settlement,
            acquisition,
        )
        assert acquisition["execution_authority_granted"] is False
        assert acquisition["native_measure"] == {
            "unit": "compute-minute",
            "quantity": 60,
        }

        capacity_entry = acquisition_to_treasury_entry(acquisition)
        settlement_entry = make_treasury_entry(
            category="receipt",
            position="evidence",
            subject_ref="settlement:" + settlement["settlement_id"],
            source_ref=settlement["settlement_id"],
            evidence_refs=[
                settlement["settlement_id"],
                provider_perf["attestation_id"],
                guild_perf["attestation_id"],
            ],
            metadata={
                "economic_history_only": True,
                "creates_execution_authority": False,
            },
        )
        treasury = make_treasury_snapshot(
            guild_id="guild:lantern-forge",
            steward=guild,
            entries=[capacity_entry, settlement_entry],
            sequence=0,
        )
        assert verify_treasury_snapshot(treasury)
        frozen_treasury = json.dumps(treasury, sort_keys=True)

        # A settlement ID is not a Treasury resource entry and cannot be
        # leased directly.
        direct_settlement_lease_refused = refused(
            lambda: GuildCapacityLeaseIssuer(
                root / "bad-direct-issuer",
                steward=guild,
            ).issue(
                treasury,
                resource_entry_id=settlement["settlement_id"],
                node_id="guild-node-a",
                node_particular=node_a.signer.particular(),
                unit="compute-minute",
                quantity=1,
                issued_at_cut=2,
                expires_after_cut=8,
            )
        )
        assert direct_settlement_lease_refused

        # OPERATIONAL SIDE --------------------------------------------------
        issuer = GuildCapacityLeaseIssuer(
            root / "issuer-state",
            steward=guild,
        )
        parent = issuer.issue(
            treasury,
            resource_entry_id=capacity_entry["entry_id"],
            node_id="guild-node-a",
            node_particular=node_a.signer.particular(),
            unit="compute-minute",
            quantity=60,
            issued_at_cut=2,
            expires_after_cut=8,
        )

        budget_a = NodeLeaseBudget(root / "node-a-budget", node=node_a.signer)
        parent_use = budget_a.execute(
            parent,
            quantity=20,
            observed_cut=3,
            purpose_ref="purpose:acquired-root-use",
            success=True,
        )
        root_handoff = LeaseHandoffStore(
            root / "node-a-budget",
            node=node_a.signer,
        )
        root_surrender = root_handoff.surrender(
            treasury,
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
            observed_cut=4,
        )
        children = materialize_children(
            treasury,
            parent,
            root_surrender,
            steward=guild,
            issued_at_cut=4,
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
            observed_cut=5,
            purpose_ref="purpose:acquired-child-a",
            success=True,
        )
        child_a_handoff = LeaseHandoffStore(
            root / "node-a-budget",
            node=node_a.signer,
        )
        child_a_surrender = child_a_handoff.surrender(
            treasury,
            child_a,
            allocations=[
                {
                    "target_node_id": "guild-node-b",
                    "target_node_particular": node_b.signer.particular(),
                    "quantity": 5,
                }
            ],
            observed_cut=6,
        )
        residual_child = materialize_children(
            treasury,
            child_a,
            child_a_surrender,
            steward=guild,
            issued_at_cut=6,
            expires_after_cut=8,
        )[0]

        budget_b = NodeLeaseBudget(root / "node-b-budget", node=node_b.signer)
        child_b_use = budget_b.execute(
            child_b,
            quantity=20,
            observed_cut=5,
            purpose_ref="purpose:acquired-child-b",
            success=True,
        )
        child_b_handoff = LeaseHandoffStore(
            root / "node-b-budget",
            node=node_b.signer,
        )
        child_b_surrender = child_b_handoff.surrender(
            treasury,
            child_b,
            allocations=[
                {
                    "target_node_id": "guild-node-b",
                    "target_node_particular": node_b.signer.particular(),
                    "quantity": 10,
                }
            ],
            observed_cut=6,
        )
        renewed_b = materialize_children(
            treasury,
            child_b,
            child_b_surrender,
            steward=guild,
            issued_at_cut=6,
            expires_after_cut=12,
            allow_renewal=True,
        )[0]
        renewed_use = budget_b.execute(
            renewed_b,
            quantity=6,
            observed_cut=9,
            purpose_ref="purpose:acquired-renewed-b",
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
            treasury,
            root_lease=parent,
            descendant_leases=descendants,
            surrenders=surrenders,
            uses=source_uses,
            expired_lease_id=residual_child["lease_id"],
            observed_cut=9,
        )
        reclaimed_lease = reclaim_store.reissue(
            treasury,
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
            purpose_ref="purpose:acquired-metabolic-reuse",
            success=True,
        )

        metabolism = derive_authority_metabolism(
            treasury,
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
        assert metabolism["conservation_status"] == "BALANCED"
        assert metabolism["totals"]["accounted_quantity"] == 60

        witness = derive_metabolic_exchange_witness(
            offer,
            acceptance,
            attestations,
            settlement,
            acquisition,
            treasury,
            metabolism,
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
        assert witness["settlement_id"] == settlement["settlement_id"]
        assert witness["treasury_entry_id"] == capacity_entry["entry_id"]
        assert witness["metabolism_id"] == metabolism["metabolism_id"]
        assert witness["execution_authority"] == "none"
        assert witness["payment_inferred_from_consumption"] is False

        # Hostile bridge controls.
        missing_capacity_snapshot = make_treasury_snapshot(
            guild_id="guild:lantern-forge",
            steward=guild,
            entries=[settlement_entry],
            sequence=0,
        )
        missing_capacity_entry_refused = refused(
            lambda: derive_metabolic_exchange_witness(
                offer,
                acceptance,
                attestations,
                settlement,
                acquisition,
                missing_capacity_snapshot,
                metabolism,
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
        )
        assert missing_capacity_entry_refused

        tampered_acquisition = json.loads(json.dumps(acquisition))
        tampered_acquisition["native_measure"]["quantity"] = 61
        tampered_acquisition_refused = refused(
            lambda: derive_metabolic_exchange_witness(
                offer,
                acceptance,
                attestations,
                settlement,
                tampered_acquisition,
                treasury,
                metabolism,
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
        )
        assert tampered_acquisition_refused

        tampered_metabolism = json.loads(json.dumps(metabolism))
        tampered_metabolism["totals"]["recycled_live_quantity"] = 3
        tampered_metabolism_refused = refused(
            lambda: derive_metabolic_exchange_witness(
                offer,
                acceptance,
                attestations,
                settlement,
                acquisition,
                treasury,
                tampered_metabolism,
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
        )
        assert tampered_metabolism_refused

        crossing = make_metabolic_exchange_crossing(
            witness,
            signer=guild,
        )
        assert verify_crossing(crossing)
        assert (
            crossing["requested_effect"]["automatic_execution_requested"]
            is False
        )
        assert (
            crossing["requested_effect"]["payment_inference_requested"]
            is False
        )
        assert (
            crossing["requested_effect"]["ownership_transfer_requested"]
            is False
        )
        assert crossing["requested_effect"]["mint_authority_requested"] is False

        source = root / "metabolic-exchange-source"
        payload = source / "metabolic-exchange.json"
        source.mkdir(parents=True, exist_ok=True)
        payload.write_text(
            json.dumps(
                {
                    "settlement": settlement,
                    "acquisition": acquisition,
                    "treasury_snapshot_id": treasury["snapshot_id"],
                    "metabolism": metabolism,
                    "witness": witness,
                    "crossing": crossing,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        receiver = StateParcelInbox(root / "metabolic-exchange-receiver")
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
                "046 admit economic+operational audit as evidence only; "
                "do not infer payment, ownership, or execution authority"
            ),
        )
        assert admitted["kind"] == "ADMITTED"

        assert json.dumps(treasury, sort_keys=True) == frozen_treasury

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "economic_side": {
                        "settlement_status": settlement["status"],
                        "delivered_capacity": acquisition["native_measure"],
                        "execution_authority_granted_by_acquisition": False,
                    },
                    "treasury_bridge": {
                        "capacity_entry_id": capacity_entry["entry_id"],
                        "direct_settlement_lease_refused": (
                            direct_settlement_lease_refused
                        ),
                        "incomplete_settlement_admission_refused": (
                            incomplete_settlement_admission_refused
                        ),
                        "noncapacity_admission_refused": (
                            noncapacity_admission_refused
                        ),
                    },
                    "operational_side": {
                        "root_lease_quantity": 60,
                        "metabolism_accounted": (
                            metabolism["totals"]["accounted_quantity"]
                        ),
                        "source_consumed": (
                            metabolism["totals"][
                                "source_consumed_quantity"
                            ]
                        ),
                        "source_live": (
                            metabolism["totals"]["source_live_quantity"]
                        ),
                        "recycled_consumed": (
                            metabolism["totals"][
                                "recycled_consumed_quantity"
                            ]
                        ),
                        "recycled_live": (
                            metabolism["totals"][
                                "recycled_live_quantity"
                            ]
                        ),
                    },
                    "combined_witness": {
                        "economic_settlement_bound": True,
                        "treasury_admission_bound": True,
                        "authority_metabolism_recomputed": True,
                        "execution_authority": witness[
                            "execution_authority"
                        ],
                        "payment_inferred_from_consumption": False,
                    },
                    "hostile_controls": {
                        "missing_capacity_entry_refused": (
                            missing_capacity_entry_refused
                        ),
                        "tampered_acquisition_refused": (
                            tampered_acquisition_refused
                        ),
                        "tampered_metabolism_refused": (
                            tampered_metabolism_refused
                        ),
                    },
                    "crossing": {
                        "first_disposition": held["kind"],
                        "owner_disposition": admitted["kind"],
                        "automatic_execution_requested": False,
                        "payment_inference_requested": False,
                        "ownership_transfer_requested": False,
                        "mint_authority_requested": False,
                    },
                    "laws": [
                        "SETTLEMENT != CAPACITY",
                        "ACQUISITION != EXECUTION AUTHORITY",
                        "ECONOMIC VALUE != OPERATIONAL CAPACITY",
                        "TREASURY ENTRY != LEASE",
                        "CONSUMPTION != PAYMENT",
                        "ECONOMIC HISTORY + AUTHORITY HISTORY MAY CROSS WITHOUT COLLAPSE",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
