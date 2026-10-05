#!/usr/bin/env python3
"""Experiment 059 — Long-Running Execution / Checkpoint Revalidation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lightwalker_constraint_routing import make_constraint_attestation
from lightwalker_economy import LightwalkerEconomyError, content_address
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
from lightwalker_long_running_execution import (
    LongRunningExecutionStore,
    verify_execution_checkpoint,
)
from lightwalker_multi_source_service import make_multi_source_promise
from lightwalker_policy_composition import make_policy_fragment
from lightwalker_policy_transition import make_policy_transition
from lightwalker_policy_versioning import (
    derive_active_policy_set,
    derive_revalidation,
    make_policy_version,
)
from lightwalker_route_policy import make_route_policy
from lightwalker_route_scoring import make_route_measurement
from lightwalker_transition_composition import derive_temporal_intersection
from relatte_identity import IdentityKey


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def source_treasury(
    guild_id: str,
    steward: IdentityKey,
) -> tuple[dict, dict, dict]:
    entry = make_treasury_entry(
        category="capability",
        position="available",
        subject_ref=f"capability:{guild_id}-render-059",
        source_ref=f"ghot-node:{guild_id}-059",
        evidence_refs=[f"receipt:{guild_id}-probe-059"],
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


def policy_fragment(
    *,
    promise: dict,
    route_policy: dict,
    issuer: IdentityKey,
    issuer_role: str,
    policy_name: str,
    assessor: IdentityKey,
    measurer: IdentityKey,
    created_at_cut: int,
    forbidden_groups: list[str],
) -> dict:
    return make_policy_fragment(
        promise,
        route_policy,
        issuer=issuer,
        issuer_role=issuer_role,
        policy_name=policy_name,
        trusted_assessor_particular=assessor.particular(),
        trusted_measurer_particular=measurer.particular(),
        allowed_jurisdictions=["zone:b"],
        min_privacy_class=3,
        require_renewable_evidence=True,
        max_expected_completion_cuts=5,
        forbidden_sovereign_groups=forbidden_groups,
        max_attestation_age_cuts=4,
        created_at_cut=created_at_cut,
    )


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
        customer_assessor = IdentityKey.load_or_create(
            root / "customer-assessor" / "body.pem"
        )
        promisor_assessor = IdentityKey.load_or_create(
            root / "promisor-assessor" / "body.pem"
        )
        measurer = IdentityKey.load_or_create(root / "measurer" / "body.pem")

        treasury_b, entry_b, proof_b = source_treasury("guild:b", guild_b)
        treasury_c, entry_c, proof_c = source_treasury("guild:c", guild_c)
        treasury_f, entry_f, proof_f = source_treasury("guild:f", guild_f)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:long-running-059",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="checkpoint-revalidation",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:059",
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

        customer_v1 = policy_fragment(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-long-run-boundary",
            assessor=customer_assessor,
            measurer=measurer,
            created_at_cut=5,
            forbidden_groups=[],
        )
        customer_v2 = policy_fragment(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-long-run-boundary",
            assessor=customer_assessor,
            measurer=measurer,
            created_at_cut=6,
            forbidden_groups=[],
        )
        customer_v3 = policy_fragment(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-long-run-boundary",
            assessor=customer_assessor,
            measurer=measurer,
            created_at_cut=7,
            forbidden_groups=["group:f"],
        )

        promisor_v1 = policy_fragment(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-long-run-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
            created_at_cut=5,
            forbidden_groups=[],
        )
        promisor_v2 = policy_fragment(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-long-run-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
            created_at_cut=6,
            forbidden_groups=[],
        )
        promisor_v3 = policy_fragment(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-long-run-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
            created_at_cut=7,
            forbidden_groups=[],
        )

        cv1 = make_policy_version(
            promise,
            route_policy,
            customer_v1,
            issuer=customer,
            version_number=1,
            effective_from_cut=5,
            declared_at_cut=5,
        )
        cv2 = make_policy_version(
            promise,
            route_policy,
            customer_v2,
            issuer=customer,
            version_number=2,
            effective_from_cut=7,
            declared_at_cut=6,
            previous_version=cv1,
        )
        cv3 = make_policy_version(
            promise,
            route_policy,
            customer_v3,
            issuer=customer,
            version_number=3,
            effective_from_cut=8,
            declared_at_cut=7,
            previous_version=cv2,
        )

        pv1 = make_policy_version(
            promise,
            route_policy,
            promisor_v1,
            issuer=guild_a,
            version_number=1,
            effective_from_cut=5,
            declared_at_cut=5,
        )
        pv2 = make_policy_version(
            promise,
            route_policy,
            promisor_v2,
            issuer=guild_a,
            version_number=2,
            effective_from_cut=7,
            declared_at_cut=6,
            previous_version=pv1,
        )
        pv3 = make_policy_version(
            promise,
            route_policy,
            promisor_v3,
            issuer=guild_a,
            version_number=3,
            effective_from_cut=8,
            declared_at_cut=7,
            previous_version=pv2,
        )

        customer_t12 = make_policy_transition(
            promise,
            route_policy,
            previous_version=cv1,
            current_version=cv2,
            issuer=customer,
            mode="IMMEDIATE_REVALIDATION",
            declared_at_cut=6,
        )
        promisor_t12 = make_policy_transition(
            promise,
            route_policy,
            previous_version=pv1,
            current_version=pv2,
            issuer=guild_a,
            mode="IMMEDIATE_REVALIDATION",
            declared_at_cut=6,
        )
        customer_t23 = make_policy_transition(
            promise,
            route_policy,
            previous_version=cv2,
            current_version=cv3,
            issuer=customer,
            mode="IMMEDIATE_REVALIDATION",
            declared_at_cut=7,
        )
        promisor_t23 = make_policy_transition(
            promise,
            route_policy,
            previous_version=pv2,
            current_version=pv3,
            issuer=guild_a,
            mode="IMMEDIATE_REVALIDATION",
            declared_at_cut=7,
        )

        bundles_12 = [
            bundle("customer", cv1, cv2, customer_t12),
            bundle("promisor", pv1, pv2, promisor_t12),
        ]
        bundles_23 = [
            bundle("customer", cv2, cv3, customer_t23),
            bundle("promisor", pv2, pv3, promisor_t23),
        ]

        policies = [
            customer_v1,
            customer_v2,
            customer_v3,
            promisor_v1,
            promisor_v2,
            promisor_v3,
        ]
        versions = [cv1, cv2, cv3, pv1, pv2, pv3]

        policy_set_6 = derive_active_policy_set(
            promise,
            route_policy,
            policies,
            versions,
            observed_cut=6,
        )
        policy_set_7 = derive_active_policy_set(
            promise,
            route_policy,
            policies,
            versions,
            observed_cut=7,
        )
        policy_set_8 = derive_active_policy_set(
            promise,
            route_policy,
            policies,
            versions,
            observed_cut=8,
        )

        reservation_store = GuildReservationStore(
            root / "reservations-f",
            steward=guild_f,
        )
        proposal_f = make_resource_proposal(
            treasury_f,
            proposer=guild_f,
            resource_entry_id=entry_f["entry_id"],
            requested_quantity=30,
            requested_unit="compute-minute",
            purpose_ref="059-long-running-f",
            proposed_at_cut=6,
        )
        auth_f, reservation_f = reservation_store.reserve_and_authorize(
            treasury_f,
            proposal_f,
            executor_particular=worker_f.particular(),
            authorized_at_cut=6,
            expires_after_cut=12,
        )

        temporal_6 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_12,
            reservation_f,
            observed_cut=6,
        )
        assert temporal_6["aggregate_action"] == "LEGACY_PATH_OPEN"

        long_store = LongRunningExecutionStore(
            root / "long-run-f",
            steward=guild_f,
            reservation_store=reservation_store,
        )
        run = long_store.start(
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles_12,
            supplied_temporal_intersection=temporal_6,
            executor=worker_f,
            observed_cut=6,
        )
        assert run["status"] == "RUNNING"
        assert run["progress_percent"] == 0

        temporal_7 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_12,
            reservation_f,
            observed_cut=7,
            execution_started_at_cut=6,
        )
        assert temporal_7["aggregate_action"] == "REVALIDATION_REQUIRED"

        stale_start_authority_refused = refused(
            lambda: long_store.checkpoint(
                run,
                treasury_f,
                proposal_f,
                auth_f,
                reservation_f,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles_12,
                supplied_temporal_intersection=temporal_6,
                executor=worker_f,
                observed_cut=7,
                progress_percent=20,
                partial_result_ref="partial:059-stale",
            )
        )
        assert stale_start_authority_refused

        measurement_7 = make_route_measurement(
            treasury_f,
            proof_f,
            measurer=measurer,
            latency_ms=20,
            reliability_ppm=995_000,
            energy_mwh_per_compute_minute=20,
            expected_completion_cuts=2,
            observed_cut=7,
        )
        facts_f = dict(
            jurisdiction="zone:b",
            privacy_class=5,
            renewable_evidence_present=True,
            sovereign_group="group:f",
        )
        attestations_7 = [
            make_constraint_attestation(
                treasury_f,
                proof_f,
                assessor=customer_assessor,
                observed_cut=7,
                **facts_f,
            ),
            make_constraint_attestation(
                treasury_f,
                proof_f,
                assessor=promisor_assessor,
                observed_cut=7,
                **facts_f,
            ),
        ]
        candidate_f = {"snapshot": treasury_f, "proof": proof_f}
        prior_binding = content_address(
            {"kind": "059-route-binding", "cut": 6}
        )
        prior_admission = content_address(
            {"kind": "059-admission", "cut": 6}
        )
        revalidation_7 = derive_revalidation(
            promise,
            route_policy,
            previous_policy_set=policy_set_6,
            current_policy_set=policy_set_7,
            policies=policies,
            candidate=candidate_f,
            measurements=[measurement_7],
            attestations=attestations_7,
            reservation=reservation_f,
            prior_binding_id=prior_binding,
            prior_admission_response_id=prior_admission,
            evaluation_cut=7,
        )
        assert revalidation_7["status"] == "COMPLIANT"
        revalidation_context_7 = {
            "policies": policies,
            "versions": versions,
            "previous_policy_set": policy_set_6,
            "current_policy_set": policy_set_7,
            "candidate": candidate_f,
            "measurements": [measurement_7],
            "attestations": attestations_7,
            "prior_binding_id": prior_binding,
            "prior_admission_response_id": prior_admission,
            "revalidation": revalidation_7,
        }

        checkpoint_1 = long_store.checkpoint(
            run,
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles_12,
            supplied_temporal_intersection=temporal_7,
            executor=worker_f,
            observed_cut=7,
            progress_percent=40,
            partial_result_ref="partial:059-f-40",
            revalidation_context=revalidation_context_7,
        )
        assert verify_execution_checkpoint(run, checkpoint_1)
        assert checkpoint_1["checkpoint_index"] == 1
        assert checkpoint_1["underlying_execution_attempted"] is False
        assert checkpoint_1["service_complete"] is False
        assert checkpoint_1["settlement_authority"] == "none"
        assert reservation_store.capacity_state(
            treasury_f,
            entry_f["entry_id"],
        )["reserved_quantity"] == 30

        temporal_8 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_23,
            reservation_f,
            observed_cut=8,
            execution_started_at_cut=6,
        )
        assert temporal_8["aggregate_action"] == "REVALIDATION_REQUIRED"

        measurement_8 = make_route_measurement(
            treasury_f,
            proof_f,
            measurer=measurer,
            latency_ms=18,
            reliability_ppm=996_000,
            energy_mwh_per_compute_minute=19,
            expected_completion_cuts=2,
            observed_cut=8,
        )
        attestations_8 = [
            make_constraint_attestation(
                treasury_f,
                proof_f,
                assessor=customer_assessor,
                observed_cut=8,
                **facts_f,
            ),
            make_constraint_attestation(
                treasury_f,
                proof_f,
                assessor=promisor_assessor,
                observed_cut=8,
                **facts_f,
            ),
        ]
        revalidation_8 = derive_revalidation(
            promise,
            route_policy,
            previous_policy_set=policy_set_7,
            current_policy_set=policy_set_8,
            policies=policies,
            candidate=candidate_f,
            measurements=[measurement_8],
            attestations=attestations_8,
            reservation=reservation_f,
            prior_binding_id=prior_binding,
            prior_admission_response_id=prior_admission,
            evaluation_cut=8,
        )
        assert revalidation_8["status"] == "NONCOMPLIANT"
        customer_v3_verdict = next(
            row
            for row in revalidation_8["policy_failures"]
            if row["policy_id"] == customer_v3["policy_id"]
        )
        assert "SOVEREIGN_GROUP_FORBIDDEN" in (
            customer_v3_verdict["failures"]
        )
        revalidation_context_8 = {
            "policies": policies,
            "versions": versions,
            "previous_policy_set": policy_set_7,
            "current_policy_set": policy_set_8,
            "candidate": candidate_f,
            "measurements": [measurement_8],
            "attestations": attestations_8,
            "prior_binding_id": prior_binding,
            "prior_admission_response_id": prior_admission,
            "revalidation": revalidation_8,
        }

        continuation_refused = refused(
            lambda: long_store.checkpoint(
                run,
                treasury_f,
                proposal_f,
                auth_f,
                reservation_f,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles_23,
                supplied_temporal_intersection=temporal_8,
                executor=worker_f,
                observed_cut=8,
                progress_percent=70,
                partial_result_ref="partial:059-f-70-must-not-exist",
                revalidation_context=revalidation_context_8,
            )
        )
        assert continuation_refused

        after_refusal = long_store.state(run["run_id"])
        assert after_refusal["progress_percent"] == 40
        assert after_refusal["checkpoint_count"] == 1
        assert after_refusal["partial_result_ref"] == "partial:059-f-40"

        pause = long_store.pause(
            run,
            observed_cut=8,
            reason="CURRENT_POLICY_REVALIDATION_FAILED",
        )
        assert pause["failure"] is False
        assert pause["service_complete"] is False
        assert pause["reservation_released"] is False
        assert reservation_store.capacity_state(
            treasury_f,
            entry_f["entry_id"],
        )["reserved_quantity"] == 30

        checkpoint_while_paused_refused = refused(
            lambda: long_store.checkpoint(
                run,
                treasury_f,
                proposal_f,
                auth_f,
                reservation_f,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles_23,
                supplied_temporal_intersection=temporal_8,
                executor=worker_f,
                observed_cut=8,
                progress_percent=50,
                partial_result_ref="partial:059-paused-must-not-advance",
                revalidation_context=revalidation_context_8,
            )
        )
        assert checkpoint_while_paused_refused

        stop = long_store.stop(
            run,
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            observed_cut=9,
            reason="OWNER_STOP_AFTER_POLICY_PAUSE",
        )
        assert stop["failure"] is False
        assert stop["service_complete"] is False
        assert stop["history_rewritten"] is False
        assert stop["settlement_authority"] == "none"
        assert stop["progress_percent"] == 40
        assert stop["partial_result_ref"] == "partial:059-f-40"
        assert stop["reservation_status"] == "RELEASED"
        assert reservation_store.capacity_state(
            treasury_f,
            entry_f["entry_id"],
        )["reserved_quantity"] == 0

        final_state = long_store.state(run["run_id"])
        assert final_state["status"] == "STOPPED"
        assert final_state["checkpoint_count"] == 1
        assert final_state["progress_percent"] == 40
        assert checkpoint_1["partial_result_ref"] == "partial:059-f-40"

        print({
            "simulation_passed": True,
            "start": {
                "cut": 6,
                "status": run["status"],
                "evidence_path": run["start_evidence_path"],
            },
            "checkpoint_1": {
                "cut": 7,
                "progress_percent": 40,
                "revalidation": revalidation_7["status"],
                "underlying_execution_attempted": False,
                "service_complete": False,
            },
            "policy_change": {
                "cut": 8,
                "revalidation": revalidation_8["status"],
                "failure": "SOVEREIGN_GROUP_FORBIDDEN",
                "continuation_refused": continuation_refused,
                "progress_preserved": 40,
            },
            "pause": {
                "failure": pause["failure"],
                "reservation_released": pause["reservation_released"],
                "checkpoint_while_paused_refused": (
                    checkpoint_while_paused_refused
                ),
            },
            "stop": {
                "status": final_state["status"],
                "reservation_status": stop["reservation_status"],
                "history_rewritten": stop["history_rewritten"],
                "service_complete": stop["service_complete"],
                "settlement_authority": stop["settlement_authority"],
            },
            "laws": [
                "START AUTHORITY != CONTINUATION AUTHORITY",
                "CHECKPOINT REVALIDATION != REEXECUTION",
                "PAUSE != FAILURE",
                "STOP != HISTORY REWRITE",
                "PARTIAL RESULT != SETTLEMENT",
                "CONTINUATION MUST REMAIN OWNER-LOCAL",
            ],
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
