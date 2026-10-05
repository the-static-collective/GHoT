#!/usr/bin/env python3
"""Experiment 060 — Resume / Migration of Paused Execution."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lightwalker_constraint_routing import make_constraint_attestation
from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_execution_resume import (
    ResumedExecutionStore,
    verify_resume,
)
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
from lightwalker_long_running_execution import LongRunningExecutionStore
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
    *,
    quantity: int = 60,
) -> tuple[dict, dict, dict]:
    entry = make_treasury_entry(
        category="capability",
        position="available",
        subject_ref=f"capability:{guild_id}-render-060",
        source_ref=f"ghot-node:{guild_id}-060",
        evidence_refs=[f"receipt:{guild_id}-probe-060"],
        native_measure={
            "unit": "compute-minute",
            "quantity": quantity,
        },
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
        max_attestation_age_cuts=5,
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
        guild_e = IdentityKey.load_or_create(root / "guild-e" / "body.pem")
        guild_f = IdentityKey.load_or_create(root / "guild-f" / "body.pem")
        worker_e = IdentityKey.load_or_create(root / "worker-e" / "body.pem")
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
        treasury_e, entry_e, proof_e = source_treasury("guild:e", guild_e)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:resume-migration-060",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="checkpoint-lineage-and-current-authority",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:060",
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
            ordered_guild_ids=["guild:b", "guild:f", "guild:e"],
            required_capability="render.verified",
            max_proof_age_cuts=20,
            max_failover_hops=3,
            created_at_cut=2,
        )

        customer_v1 = policy_fragment(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-resume-boundary",
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
            policy_name="customer-resume-boundary",
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
            policy_name="customer-resume-boundary",
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
            policy_name="promisor-resume-boundary",
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
            policy_name="promisor-resume-boundary",
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
            policy_name="promisor-resume-boundary",
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

        policy_sets = {
            cut: derive_active_policy_set(
                promise,
                route_policy,
                policies,
                versions,
                observed_cut=cut,
            )
            for cut in (6, 7, 8, 9, 10, 11)
        }

        # F owns 30 compute-minutes for the original long-running attempt.
        store_f = GuildReservationStore(root / "reservations-f", steward=guild_f)
        proposal_f = make_resource_proposal(
            treasury_f,
            proposer=guild_f,
            resource_entry_id=entry_f["entry_id"],
            requested_quantity=30,
            requested_unit="compute-minute",
            purpose_ref="060-original-f",
            proposed_at_cut=6,
        )
        auth_f, reservation_f = store_f.reserve_and_authorize(
            treasury_f,
            proposal_f,
            executor_particular=worker_f.particular(),
            authorized_at_cut=6,
            expires_after_cut=14,
        )

        temporal_6 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_12,
            reservation_f,
            observed_cut=6,
        )
        long_f = LongRunningExecutionStore(
            root / "long-f",
            steward=guild_f,
            reservation_store=store_f,
        )
        run_f = long_f.start(
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

        facts_f = dict(
            jurisdiction="zone:b",
            privacy_class=5,
            renewable_evidence_present=True,
            sovereign_group="group:f",
        )
        measurement_f7 = make_route_measurement(
            treasury_f,
            proof_f,
            measurer=measurer,
            latency_ms=20,
            reliability_ppm=995_000,
            energy_mwh_per_compute_minute=20,
            expected_completion_cuts=2,
            observed_cut=7,
        )
        attest_f7 = [
            make_constraint_attestation(
                treasury_f,
                proof_f,
                assessor=assessor,
                observed_cut=7,
                **facts_f,
            )
            for assessor in (customer_assessor, promisor_assessor)
        ]
        candidate_f = {"snapshot": treasury_f, "proof": proof_f}
        binding_f = content_address({"kind": "060-binding-f"})
        admission_f = content_address({"kind": "060-admission-f"})
        reval_f7 = derive_revalidation(
            promise,
            route_policy,
            previous_policy_set=policy_sets[6],
            current_policy_set=policy_sets[7],
            policies=policies,
            candidate=candidate_f,
            measurements=[measurement_f7],
            attestations=attest_f7,
            reservation=reservation_f,
            prior_binding_id=binding_f,
            prior_admission_response_id=admission_f,
            evaluation_cut=7,
        )
        assert reval_f7["status"] == "COMPLIANT"
        ctx_f7 = {
            "policies": policies,
            "versions": versions,
            "previous_policy_set": policy_sets[6],
            "current_policy_set": policy_sets[7],
            "candidate": candidate_f,
            "measurements": [measurement_f7],
            "attestations": attest_f7,
            "prior_binding_id": binding_f,
            "prior_admission_response_id": admission_f,
            "revalidation": reval_f7,
        }
        temporal_f7 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_12,
            reservation_f,
            observed_cut=7,
            execution_started_at_cut=6,
        )
        checkpoint_f = long_f.checkpoint(
            run_f,
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles_12,
            supplied_temporal_intersection=temporal_f7,
            executor=worker_f,
            observed_cut=7,
            progress_percent=40,
            partial_result_ref="partial:060-f-40",
            revalidation_context=ctx_f7,
        )
        assert checkpoint_f["progress_percent"] == 40

        # V3 makes F noncompliant. Preserve the checkpoint, then pause and stop.
        measurement_f8 = make_route_measurement(
            treasury_f,
            proof_f,
            measurer=measurer,
            latency_ms=20,
            reliability_ppm=995_000,
            energy_mwh_per_compute_minute=20,
            expected_completion_cuts=2,
            observed_cut=8,
        )
        attest_f8 = [
            make_constraint_attestation(
                treasury_f,
                proof_f,
                assessor=assessor,
                observed_cut=8,
                **facts_f,
            )
            for assessor in (customer_assessor, promisor_assessor)
        ]
        reval_f8 = derive_revalidation(
            promise,
            route_policy,
            previous_policy_set=policy_sets[7],
            current_policy_set=policy_sets[8],
            policies=policies,
            candidate=candidate_f,
            measurements=[measurement_f8],
            attestations=attest_f8,
            reservation=reservation_f,
            prior_binding_id=binding_f,
            prior_admission_response_id=admission_f,
            evaluation_cut=8,
        )
        assert reval_f8["status"] == "NONCOMPLIANT"
        pause_f = long_f.pause(
            run_f,
            observed_cut=8,
            reason="MIGRATE_PARTIAL_EXECUTION",
        )
        stop_f = long_f.stop(
            run_f,
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            observed_cut=8,
            reason="RELEASE_FOR_RESUME_MIGRATION",
        )
        assert stop_f["reservation_status"] == "PARTIALLY_CONSUMED"
        assert stop_f["progress_percent"] == 40

        # 40% of 30 = 12 completed lineage units. E may reserve exactly 18.
        store_e = GuildReservationStore(root / "reservations-e", steward=guild_e)
        proposal_e = make_resource_proposal(
            treasury_e,
            proposer=guild_e,
            resource_entry_id=entry_e["entry_id"],
            requested_quantity=18,
            requested_unit="compute-minute",
            purpose_ref="060-resumed-e-remaining",
            proposed_at_cut=9,
        )
        auth_e, reservation_e = store_e.reserve_and_authorize(
            treasury_e,
            proposal_e,
            executor_particular=worker_e.particular(),
            authorized_at_cut=9,
            expires_after_cut=15,
        )

        # Attempting to reserve the original 30 again must fail resume accounting.
        store_e_bad = GuildReservationStore(root / "reservations-e-bad", steward=guild_e)
        proposal_e_bad = make_resource_proposal(
            treasury_e,
            proposer=guild_e,
            resource_entry_id=entry_e["entry_id"],
            requested_quantity=30,
            requested_unit="compute-minute",
            purpose_ref="060-bad-double-count",
            proposed_at_cut=9,
        )
        auth_e_bad, reservation_e_bad = store_e_bad.reserve_and_authorize(
            treasury_e,
            proposal_e_bad,
            executor_particular=worker_e.particular(),
            authorized_at_cut=9,
            expires_after_cut=15,
        )

        facts_e = dict(
            jurisdiction="zone:b",
            privacy_class=5,
            renewable_evidence_present=True,
            sovereign_group="group:e",
        )
        candidate_e = {"snapshot": treasury_e, "proof": proof_e}
        binding_e = content_address({"kind": "060-binding-e"})
        admission_e = content_address({"kind": "060-admission-e"})

        def e_context(cut: int, previous_cut: int, reservation: dict) -> tuple[dict, dict]:
            measurement = make_route_measurement(
                treasury_e,
                proof_e,
                measurer=measurer,
                latency_ms=12,
                reliability_ppm=999_000,
                energy_mwh_per_compute_minute=12,
                expected_completion_cuts=2,
                observed_cut=cut,
            )
            attestations = [
                make_constraint_attestation(
                    treasury_e,
                    proof_e,
                    assessor=assessor,
                    observed_cut=cut,
                    **facts_e,
                )
                for assessor in (customer_assessor, promisor_assessor)
            ]
            revalidation = derive_revalidation(
                promise,
                route_policy,
                previous_policy_set=policy_sets[previous_cut],
                current_policy_set=policy_sets[cut],
                policies=policies,
                candidate=candidate_e,
                measurements=[measurement],
                attestations=attestations,
                reservation=reservation,
                prior_binding_id=binding_e,
                prior_admission_response_id=admission_e,
                evaluation_cut=cut,
            )
            assert revalidation["status"] == "COMPLIANT"
            return revalidation, {
                "policies": policies,
                "versions": versions,
                "previous_policy_set": policy_sets[previous_cut],
                "current_policy_set": policy_sets[cut],
                "candidate": candidate_e,
                "measurements": [measurement],
                "attestations": attestations,
                "prior_binding_id": binding_e,
                "prior_admission_response_id": admission_e,
                "revalidation": revalidation,
            }

        reval_e9, ctx_e9 = e_context(9, 8, reservation_e)
        temporal_e9 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_23,
            reservation_e,
            observed_cut=9,
        )
        resumed_e = ResumedExecutionStore(
            root / "resumed-e",
            steward=guild_e,
            reservation_store=store_e,
        )

        bad_resume_refused = refused(
            lambda: ResumedExecutionStore(
                root / "resumed-e-bad",
                steward=guild_e,
                reservation_store=store_e_bad,
            ).resume(
                old_run=run_f,
                old_checkpoint=checkpoint_f,
                old_pause=pause_f,
                old_stop=stop_f,
                old_authorization=auth_f,
                new_snapshot=treasury_e,
                new_proposal=proposal_e_bad,
                new_authorization=auth_e_bad,
                new_reservation=reservation_e_bad,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles_23,
                supplied_temporal_intersection=derive_temporal_intersection(
                    promise,
                    route_policy,
                    bundles_23,
                    reservation_e_bad,
                    observed_cut=9,
                ),
                executor=worker_e,
                observed_cut=9,
                revalidation_context=e_context(9, 8, reservation_e_bad)[1],
            )
        )
        assert bad_resume_refused

        resume = resumed_e.resume(
            old_run=run_f,
            old_checkpoint=checkpoint_f,
            old_pause=pause_f,
            old_stop=stop_f,
            old_authorization=auth_f,
            new_snapshot=treasury_e,
            new_proposal=proposal_e,
            new_authorization=auth_e,
            new_reservation=reservation_e,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles_23,
            supplied_temporal_intersection=temporal_e9,
            executor=worker_e,
            observed_cut=9,
            revalidation_context=ctx_e9,
        )
        assert verify_resume(resume)
        assert resume["prior_progress_percent"] == 40
        assert resume["source_work_measure"]["quantity"] == 30
        assert resume["prior_work_measure"]["quantity"] == 12
        assert resume["remaining_work_measure"]["quantity"] == 18
        assert resume["new_reservation_id"] != run_f["reservation_id"]
        assert resume["ownership_transfer"] is False

        # Resume at 40%, then continue to 70% under a fresh cut-10 gate.
        reval_e10, ctx_e10 = e_context(10, 9, reservation_e)
        temporal_e10 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_23,
            reservation_e,
            observed_cut=10,
            execution_started_at_cut=9,
        )
        resumed_checkpoint = resumed_e.checkpoint(
            resume,
            treasury_e,
            proposal_e,
            auth_e,
            reservation_e,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles_23,
            supplied_temporal_intersection=temporal_e10,
            executor=worker_e,
            observed_cut=10,
            total_progress_percent=70,
            partial_result_ref="partial:060-e-70",
            revalidation_context=ctx_e10,
        )
        assert resumed_checkpoint["prior_progress_percent"] == 40
        assert resumed_checkpoint["new_work_progress_percent"] == 30
        assert resumed_checkpoint["total_progress_percent"] == 70
        assert resumed_checkpoint["prior_work_reexecuted"] is False

        # Final completion uses another current cut-11 gate and counts only 18
        # remaining native units as E's new authority.
        reval_e11, ctx_e11 = e_context(11, 10, reservation_e)
        temporal_e11 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles_23,
            reservation_e,
            observed_cut=11,
            execution_started_at_cut=9,
        )
        completion, execution, finalization = resumed_e.complete(
            resume,
            treasury_e,
            proposal_e,
            auth_e,
            reservation_e,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles_23,
            supplied_temporal_intersection=temporal_e11,
            executor=worker_e,
            observed_cut=11,
            result_ref="result:060-resumed-complete",
            revalidation_context=ctx_e11,
        )
        assert execution["success"] is True
        assert finalization["status"] == "CONSUMED"
        assert completion["prior_progress_percent"] == 40
        assert completion["remaining_work_percent"] == 60
        assert completion["prior_work_measure"]["quantity"] == 12
        assert completion["new_work_counted_measure"]["quantity"] == 18
        assert completion["total_progress_percent"] == 100
        assert completion["prior_work_reexecuted"] is False
        assert completion["prior_work_double_counted"] is False
        assert completion["ownership_transfer"] is False
        assert completion["old_run_rewritten"] is False
        assert completion["settlement_authority"] == "none"

        final_state = resumed_e.state(resume["resume_id"])
        assert final_state["status"] == "COMPLETED"
        assert final_state["total_progress_percent"] == 100

        print({
            "simulation_passed": True,
            "source_run": {
                "guild": "guild:f",
                "reservation_measure": 30,
                "checkpoint_progress": 40,
                "checkpoint_measure": 12,
                "stopped": stop_f["reservation_status"],
            },
            "resume": {
                "guild": "guild:e",
                "bad_full_reservation_refused": bad_resume_refused,
                "new_reservation_measure": 18,
                "starts_at_total_progress": 40,
                "ownership_transfer": False,
            },
            "resumed_checkpoint": {
                "total_progress": 70,
                "new_work_progress": 30,
                "prior_work_reexecuted": False,
            },
            "completion": {
                "total_progress": 100,
                "prior_measure": 12,
                "new_measure": 18,
                "prior_work_double_counted": False,
                "service_complete": completion["service_complete"],
                "settlement_authority": completion["settlement_authority"],
            },
            "laws": [
                "RESUME != RESTART",
                "PARTIAL STATE != EXECUTION AUTHORITY",
                "MIGRATED CONTINUATION != OWNERSHIP TRANSFER",
                "OLD RUN != NEW RESOURCE AUTHORITY",
                "CHECKPOINT LINEAGE MUST SURVIVE MIGRATION",
                "RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK",
            ],
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
