#!/usr/bin/env python3
"""Experiment 057 — Multi-Policy Transition Composition."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_federated_service import make_remote_capacity_proof
from lightwalker_guild_authorization import make_resource_proposal
from lightwalker_guild_reservation import GuildReservationStore
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    make_exchange_offer,
    make_obligation,
)
from lightwalker_multi_source_service import make_multi_source_promise
from lightwalker_policy_composition import make_policy_fragment
from lightwalker_policy_transition import make_policy_transition
from lightwalker_policy_versioning import make_policy_version
from lightwalker_route_policy import make_route_policy
from lightwalker_transition_composition import (
    derive_temporal_intersection,
    verify_temporal_intersection,
)
from relatte_identity import IdentityKey


def source_treasury(
    guild_id: str,
    steward: IdentityKey,
) -> tuple[dict, dict, dict]:
    entry = make_treasury_entry(
        category="capability",
        position="available",
        subject_ref=f"capability:{guild_id}-render-057",
        source_ref=f"ghot-node:{guild_id}-057",
        evidence_refs=[f"receipt:{guild_id}-probe-057"],
        native_measure={"unit": "compute-minute", "quantity": 60},
        metadata={"capability": "render.verified"},
    )
    snapshot = make_treasury_snapshot(
        guild_id=guild_id,
        steward=steward,
        entries=[entry],
        sequence=0,
    )
    proof = make_remote_capacity_proof(
        snapshot,
        steward=steward,
        resource_entry_id=entry["entry_id"],
        observed_cut=1,
        valid_through_cut=20,
    )
    return snapshot, entry, proof


def reserve(
    store: GuildReservationStore,
    snapshot: dict,
    entry: dict,
    *,
    proposer: IdentityKey,
    executor: IdentityKey,
    quantity: int,
    authorized_at_cut: int,
    expires_after_cut: int,
) -> tuple[dict, dict, dict]:
    proposal = make_resource_proposal(
        snapshot,
        proposer=proposer,
        resource_entry_id=entry["entry_id"],
        requested_quantity=quantity,
        requested_unit="compute-minute",
        purpose_ref="transition-composition-057",
        proposed_at_cut=authorized_at_cut,
    )
    authorization, reservation = store.reserve_and_authorize(
        snapshot,
        proposal,
        executor_particular=executor.particular(),
        authorized_at_cut=authorized_at_cut,
        expires_after_cut=expires_after_cut,
    )
    return proposal, authorization, reservation


def policy_pair(
    *,
    promise: dict,
    route_policy: dict,
    issuer: IdentityKey,
    issuer_role: str,
    policy_name: str,
    assessor: IdentityKey,
    measurer: IdentityKey,
    v2_forbidden_group: str,
) -> tuple[dict, dict, dict, dict]:
    v1 = make_policy_fragment(
        promise,
        route_policy,
        issuer=issuer,
        issuer_role=issuer_role,
        policy_name=policy_name,
        trusted_assessor_particular=assessor.particular(),
        trusted_measurer_particular=measurer.particular(),
        allowed_jurisdictions=["zone:b"],
        min_privacy_class=2,
        require_renewable_evidence=False,
        max_expected_completion_cuts=6,
        forbidden_sovereign_groups=[],
        max_attestation_age_cuts=5,
        created_at_cut=5,
    )
    v2 = make_policy_fragment(
        promise,
        route_policy,
        issuer=issuer,
        issuer_role=issuer_role,
        policy_name=policy_name,
        trusted_assessor_particular=assessor.particular(),
        trusted_measurer_particular=measurer.particular(),
        allowed_jurisdictions=["zone:b"],
        min_privacy_class=2,
        require_renewable_evidence=False,
        max_expected_completion_cuts=6,
        forbidden_sovereign_groups=[v2_forbidden_group],
        max_attestation_age_cuts=5,
        created_at_cut=7,
    )
    version1 = make_policy_version(
        promise,
        route_policy,
        v1,
        issuer=issuer,
        version_number=1,
        effective_from_cut=5,
        declared_at_cut=5,
    )
    version2 = make_policy_version(
        promise,
        route_policy,
        v2,
        issuer=issuer,
        version_number=2,
        effective_from_cut=7,
        declared_at_cut=7,
        previous_version=version1,
    )
    return v1, v2, version1, version2


def bundle(
    role: str,
    previous_version: dict,
    current_version: dict,
    transition: dict,
) -> dict:
    return {
        "issuer_role": role,
        "previous_version": previous_version,
        "current_version": current_version,
        "transition": transition,
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild_a = IdentityKey.load_or_create(root / "guild-a" / "body.pem")
        guild_b = IdentityKey.load_or_create(root / "guild-b" / "body.pem")
        guild_c = IdentityKey.load_or_create(root / "guild-c" / "body.pem")
        guild_f = IdentityKey.load_or_create(root / "guild-f" / "body.pem")
        worker_f = IdentityKey.load_or_create(root / "worker-f" / "body.pem")

        customer = IdentityKey.load_or_create(root / "customer" / "body.pem")
        project = IdentityKey.load_or_create(root / "project" / "body.pem")
        customer_assessor = IdentityKey.load_or_create(
            root / "customer-assessor" / "body.pem"
        )
        promisor_assessor = IdentityKey.load_or_create(
            root / "promisor-assessor" / "body.pem"
        )
        project_assessor = IdentityKey.load_or_create(
            root / "project-assessor" / "body.pem"
        )
        measurer = IdentityKey.load_or_create(root / "measurer" / "body.pem")

        treasury_b, entry_b, proof_b = source_treasury("guild:b", guild_b)
        treasury_c, entry_c, proof_c = source_treasury("guild:c", guild_c)
        treasury_f, entry_f, proof_f = source_treasury("guild:f", guild_f)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:multi-transition-057",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="multi-transition-aware",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:057",
            terms={"deliverable": "signed review"},
            evidence_policy="signed-performance",
        )
        offer = make_exchange_offer(
            offeror_particular=guild_a.particular(),
            offeror_obligation=service,
            acceptor_obligation=consideration,
            orientation_refs=[],
            valid_through_cut=20,
        )
        original_sources = [
            {"snapshot": treasury_b, "proof": proof_b, "quantity": 30},
            {"snapshot": treasury_c, "proof": proof_c, "quantity": 30},
        ]
        promise = make_multi_source_promise(
            offer,
            original_sources,
            promisor=guild_a,
            promised_at_cut=2,
        )
        source_b = next(
            row
            for row in promise["sources"]
            if row["capacity_guild_id"] == "guild:b"
        )
        route_policy = make_route_policy(
            offer,
            original_sources,
            promise,
            source_slot_id=source_b["source_id"],
            promisor=guild_a,
            ordered_guild_ids=["guild:b", "guild:f"],
            required_capability="render.verified",
            max_proof_age_cuts=20,
            max_failover_hops=2,
            created_at_cut=2,
        )

        (
            customer_v1,
            customer_v2,
            customer_version1,
            customer_version2,
        ) = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-temporal-boundary",
            assessor=customer_assessor,
            measurer=measurer,
            v2_forbidden_group="group:customer-block",
        )
        (
            promisor_v1,
            promisor_v2,
            promisor_version1,
            promisor_version2,
        ) = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-temporal-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
            v2_forbidden_group="group:promisor-block",
        )
        (
            project_v1,
            project_v2,
            project_version1,
            project_version2,
        ) = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=project,
            issuer_role="project",
            policy_name="project-temporal-boundary",
            assessor=project_assessor,
            measurer=measurer,
            v2_forbidden_group="group:project-block",
        )

        frozen_sources = [
            json.dumps(item, sort_keys=True)
            for item in (
                customer_v1,
                customer_v2,
                promisor_v1,
                promisor_v2,
                project_v1,
                project_v2,
            )
        ]

        store_f = GuildReservationStore(
            root / "reservations-f",
            steward=guild_f,
        )
        proposal_f, auth_f, reservation_f = reserve(
            store_f,
            treasury_f,
            entry_f,
            proposer=guild_f,
            executor=worker_f,
            quantity=10,
            authorized_at_cut=6,
            expires_after_cut=12,
        )
        assert reservation_f["authorized_at_cut"] == 6

        # Specimen A: customer grants grace, promisor requires immediate
        # revalidation, project permits already-started work to finish.
        customer_grace = make_policy_transition(
            promise,
            route_policy,
            previous_version=customer_version1,
            current_version=customer_version2,
            issuer=customer,
            mode="GRACE_UNTIL_CUT",
            grace_until_cut=10,
            declared_at_cut=7,
        )
        promisor_immediate = make_policy_transition(
            promise,
            route_policy,
            previous_version=promisor_version1,
            current_version=promisor_version2,
            issuer=guild_a,
            mode="IMMEDIATE_REVALIDATION",
            declared_at_cut=7,
        )
        project_finish = make_policy_transition(
            promise,
            route_policy,
            previous_version=project_version1,
            current_version=project_version2,
            issuer=project,
            mode="FINISH_IN_FLIGHT_ONLY",
            declared_at_cut=7,
        )
        mixed_bundles = [
            bundle(
                "customer",
                customer_version1,
                customer_version2,
                customer_grace,
            ),
            bundle(
                "promisor",
                promisor_version1,
                promisor_version2,
                promisor_immediate,
            ),
            bundle(
                "project",
                project_version1,
                project_version2,
                project_finish,
            ),
        ]
        mixed = derive_temporal_intersection(
            promise,
            route_policy,
            mixed_bundles,
            reservation_f,
            observed_cut=7,
            execution_started_at_cut=6,
        )
        assert verify_temporal_intersection(
            promise,
            route_policy,
            mixed_bundles,
            reservation_f,
            mixed,
        )
        assert mixed["result"] == "COMMON_PATH"
        assert mixed["aggregate_action"] == "REVALIDATION_REQUIRED"
        assert mixed["legacy_path_open"] is False
        assert mixed["revalidation_required"] is True
        assert promisor_immediate["transition_id"] in (
            mixed["blocking_transition_ids"]
        )
        mixed_roles = {
            row["issuer_role"]: row
            for row in mixed["temporal_provenance"]
        }
        assert mixed_roles["customer"]["individual_legacy_path_open"] is True
        assert mixed_roles["project"]["individual_legacy_path_open"] is True
        assert (
            mixed_roles["promisor"]["individual_revalidation_required"]
            is True
        )

        # Specimen B: every source policy permits a legacy path, but their
        # temporal bounds differ. The earliest enforcement boundary wins.
        promisor_grace = make_policy_transition(
            promise,
            route_policy,
            previous_version=promisor_version1,
            current_version=promisor_version2,
            issuer=guild_a,
            mode="GRACE_UNTIL_CUT",
            grace_until_cut=8,
            declared_at_cut=7,
        )
        project_new_work = make_policy_transition(
            promise,
            route_policy,
            previous_version=project_version1,
            current_version=project_version2,
            issuer=project,
            mode="NEW_WORK_ONLY",
            declared_at_cut=7,
        )
        compatible_bundles = [
            bundle(
                "customer",
                customer_version1,
                customer_version2,
                customer_grace,
            ),
            bundle(
                "promisor",
                promisor_version1,
                promisor_version2,
                promisor_grace,
            ),
            bundle(
                "project",
                project_version1,
                project_version2,
                project_new_work,
            ),
        ]
        compatible7 = derive_temporal_intersection(
            promise,
            route_policy,
            compatible_bundles,
            reservation_f,
            observed_cut=7,
        )
        assert compatible7["aggregate_action"] == "LEGACY_PATH_OPEN"
        assert compatible7["legacy_path_open"] is True
        assert compatible7["enforcement_deferred_until_cut"] == 8
        assert compatible7["blocking_transition_ids"] == []

        compatible9 = derive_temporal_intersection(
            promise,
            route_policy,
            compatible_bundles,
            reservation_f,
            observed_cut=9,
        )
        assert compatible9["aggregate_action"] == "REVALIDATION_REQUIRED"
        assert compatible9["legacy_path_open"] is False
        assert compatible9["revalidation_required"] is True
        assert promisor_grace["transition_id"] in (
            compatible9["blocking_transition_ids"]
        )

        # Specimen C: already-started work is allowed to finish by one
        # sovereign, while another demands migration before execution. Since
        # execution already started at cut 6, there is no honest common path.
        customer_migrate = make_policy_transition(
            promise,
            route_policy,
            previous_version=customer_version1,
            current_version=customer_version2,
            issuer=customer,
            mode="MIGRATE_BEFORE_EXECUTION",
            declared_at_cut=7,
        )
        conflict_bundles = [
            bundle(
                "customer",
                customer_version1,
                customer_version2,
                customer_migrate,
            ),
            bundle(
                "project",
                project_version1,
                project_version2,
                project_finish,
            ),
        ]
        conflict = derive_temporal_intersection(
            promise,
            route_policy,
            conflict_bundles,
            reservation_f,
            observed_cut=7,
            execution_started_at_cut=6,
        )
        assert conflict["result"] == "NO_COMMON_TRANSITION_PATH"
        assert conflict["aggregate_action"] == "NO_COMMON_TRANSITION_PATH"
        assert conflict["legacy_path_open"] is False
        assert conflict["revalidation_required"] is False
        assert conflict["migration_required"] is False
        assert (
            "MIGRATION_BEFORE_EXECUTION_COLLIDES_WITH_ALREADY_STARTED_WORK"
            in conflict["conflicts"]
        )
        assert conflict["relaxation_authority"] == "none"
        assert conflict["mode_override_authority"] == "none"

        # Composition must not mutate any policy fragment or source transition.
        assert [
            json.dumps(item, sort_keys=True)
            for item in (
                customer_v1,
                customer_v2,
                promisor_v1,
                promisor_v2,
                project_v1,
                project_v2,
            )
        ] == frozen_sources
        for intersection in (mixed, compatible7, compatible9, conflict):
            assert intersection["source_transitions_rewritten"] is False
            assert intersection["reservation_authority"] == "none"
            assert intersection["execution_authority"] == "none"

        print(json.dumps({
            "simulation_passed": True,
            "mixed_modes": {
                "customer": "GRACE_UNTIL_CUT:10",
                "promisor": "IMMEDIATE_REVALIDATION",
                "project": "FINISH_IN_FLIGHT_ONLY",
                "execution_started_at_cut": 6,
                "aggregate_action": mixed["aggregate_action"],
                "legacy_path_open": mixed["legacy_path_open"],
                "blocking_role": "promisor",
                "temporal_provenance_count": len(
                    mixed["temporal_provenance"]
                ),
            },
            "compatible_legacy": {
                "customer_grace_until": 10,
                "promisor_grace_until": 8,
                "project": "NEW_WORK_ONLY",
                "cut7_action": compatible7["aggregate_action"],
                "aggregate_enforcement_cut": (
                    compatible7["enforcement_deferred_until_cut"]
                ),
                "cut9_action": compatible9["aggregate_action"],
            },
            "conflict": {
                "customer": "MIGRATE_BEFORE_EXECUTION",
                "project": "FINISH_IN_FLIGHT_ONLY",
                "execution_started_at_cut": 6,
                "result": conflict["result"],
                "reason": conflict["conflicts"][0],
                "relaxation_authority": "none",
                "mode_override_authority": "none",
            },
            "laws": [
                "TRANSITION A != TRANSITION B",
                "TEMPORAL INTERSECTION != MODE REWRITE",
                "GRACE IN ONE POLICY != GRACE IN ALL POLICIES",
                "ONE IMMEDIATE REQUIREMENT MAY CLOSE THE LEGACY PATH",
                "NO COMMON TRANSITION PATH != PERMISSION TO INVENT ONE",
                "TEMPORAL PROVENANCE MUST SURVIVE COMPOSITION",
            ],
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
