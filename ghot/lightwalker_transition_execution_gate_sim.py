#!/usr/bin/env python3
"""Experiment 058 — Transition-Aware Execution Gate / Durable Enforcement."""

from __future__ import annotations

import json
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
from lightwalker_multi_source_service import make_multi_source_promise
from lightwalker_policy_composition import make_policy_fragment
from lightwalker_policy_transition import (
    derive_transition_decision,
    make_migration_receipt,
    make_policy_transition,
)
from lightwalker_policy_versioning import (
    derive_active_policy_set,
    derive_revalidation,
    make_policy_version,
)
from lightwalker_route_policy import make_route_policy
from lightwalker_route_scoring import make_route_measurement
from lightwalker_transition_composition import derive_temporal_intersection
from lightwalker_transition_execution_gate import (
    execute_with_transition_gate,
)
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
        subject_ref=f"capability:{guild_id}-render-058",
        source_ref=f"ghot-node:{guild_id}-058",
        evidence_refs=[f"receipt:{guild_id}-probe-058"],
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
    purpose: str,
) -> tuple[dict, dict, dict]:
    proposal = make_resource_proposal(
        snapshot,
        proposer=proposer,
        resource_entry_id=entry["entry_id"],
        requested_quantity=quantity,
        requested_unit="compute-minute",
        purpose_ref=purpose,
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
    v2_forbidden_groups: list[str],
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
        min_privacy_class=3,
        require_renewable_evidence=True,
        max_expected_completion_cuts=5,
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
        min_privacy_class=3,
        require_renewable_evidence=True,
        max_expected_completion_cuts=5,
        forbidden_sovereign_groups=v2_forbidden_groups,
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
        treasury_e, entry_e, proof_e = source_treasury("guild:e", guild_e)
        treasury_f, entry_f, proof_f = source_treasury("guild:f", guild_f)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:transition-gate-058",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="fresh-transition-execution-gate",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:058",
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
            policy_name="customer-execution-boundary",
            assessor=customer_assessor,
            measurer=measurer,
            v2_forbidden_groups=["group:never-used"],
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
            policy_name="promisor-execution-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
            v2_forbidden_groups=["group:also-unused"],
        )

        policies = [
            customer_v1,
            customer_v2,
            promisor_v1,
            promisor_v2,
        ]
        versions = [
            customer_version1,
            customer_version2,
            promisor_version1,
            promisor_version2,
        ]
        policy_set_v1 = derive_active_policy_set(
            promise,
            route_policy,
            policies,
            versions,
            observed_cut=6,
        )
        policy_set_v2_cut7 = derive_active_policy_set(
            promise,
            route_policy,
            policies,
            versions,
            observed_cut=7,
        )
        policy_set_v2_cut8 = derive_active_policy_set(
            promise,
            route_policy,
            policies,
            versions,
            observed_cut=8,
        )

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
        promisor_immediate = make_policy_transition(
            promise,
            route_policy,
            previous_version=promisor_version1,
            current_version=promisor_version2,
            issuer=guild_a,
            mode="IMMEDIATE_REVALIDATION",
            declared_at_cut=7,
        )
        customer_migrate = make_policy_transition(
            promise,
            route_policy,
            previous_version=customer_version1,
            current_version=customer_version2,
            issuer=customer,
            mode="MIGRATE_BEFORE_EXECUTION",
            declared_at_cut=7,
        )
        promisor_new_work = make_policy_transition(
            promise,
            route_policy,
            previous_version=promisor_version1,
            current_version=promisor_version2,
            issuer=guild_a,
            mode="NEW_WORK_ONLY",
            declared_at_cut=7,
        )
        promisor_finish = make_policy_transition(
            promise,
            route_policy,
            previous_version=promisor_version1,
            current_version=promisor_version2,
            issuer=guild_a,
            mode="FINISH_IN_FLIGHT_ONLY",
            declared_at_cut=7,
        )

        legacy_bundles = [
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
        ]
        revalidation_bundles = [
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
        ]
        migration_bundles = [
            bundle(
                "customer",
                customer_version1,
                customer_version2,
                customer_migrate,
            ),
            bundle(
                "promisor",
                promisor_version1,
                promisor_version2,
                promisor_new_work,
            ),
        ]
        conflict_bundles = [
            bundle(
                "customer",
                customer_version1,
                customer_version2,
                customer_migrate,
            ),
            bundle(
                "promisor",
                promisor_version1,
                promisor_version2,
                promisor_finish,
            ),
        ]

        # Shared current evidence used by revalidation.
        measurement_f = make_route_measurement(
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
        attestations_f = [
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
        candidate_f = {
            "snapshot": treasury_f,
            "proof": proof_f,
        }

        # A. Fresh legacy evidence is mandatory at the exact execution cut.
        store_legacy = GuildReservationStore(
            root / "legacy",
            steward=guild_f,
        )
        (
            proposal_legacy,
            auth_legacy,
            reservation_legacy,
        ) = reserve(
            store_legacy,
            treasury_f,
            entry_f,
            proposer=guild_f,
            executor=worker_f,
            quantity=10,
            authorized_at_cut=6,
            expires_after_cut=12,
            purpose="058-legacy",
        )
        stale_legacy = derive_temporal_intersection(
            promise,
            route_policy,
            legacy_bundles,
            reservation_legacy,
            observed_cut=7,
        )
        stale_legacy_refused = refused(
            lambda: execute_with_transition_gate(
                store_legacy,
                treasury_f,
                proposal_legacy,
                auth_legacy,
                reservation_legacy,
                promise=promise,
                route_policy=route_policy,
                bundles=legacy_bundles,
                transition_subject_reservation=reservation_legacy,
                supplied_temporal_intersection=stale_legacy,
                executor=worker_f,
                observed_cut=8,
                simulate_success=True,
                result_ref="result:058-stale-legacy-must-not-run",
            )
        )
        assert stale_legacy_refused
        fresh_legacy = derive_temporal_intersection(
            promise,
            route_policy,
            legacy_bundles,
            reservation_legacy,
            observed_cut=8,
        )
        assert fresh_legacy["aggregate_action"] == "LEGACY_PATH_OPEN"
        legacy_gate, legacy_execution, legacy_final = (
            execute_with_transition_gate(
                store_legacy,
                treasury_f,
                proposal_legacy,
                auth_legacy,
                reservation_legacy,
                promise=promise,
                route_policy=route_policy,
                bundles=legacy_bundles,
                transition_subject_reservation=reservation_legacy,
                supplied_temporal_intersection=fresh_legacy,
                executor=worker_f,
                observed_cut=8,
                simulate_success=True,
                result_ref="result:058-fresh-legacy",
            )
        )
        assert legacy_gate["evidence_path"] == "FRESH_LEGACY_PERMISSION"
        assert legacy_gate["source_evidence_recomputed"] is True
        assert legacy_execution["success"] is True
        assert legacy_final["status"] == "CONSUMED"

        # B. Revalidation path rejects missing and wrong evidence types.
        store_revalidation = GuildReservationStore(
            root / "revalidation",
            steward=guild_f,
        )
        (
            proposal_revalidation,
            auth_revalidation,
            reservation_revalidation,
        ) = reserve(
            store_revalidation,
            treasury_f,
            entry_f,
            proposer=guild_f,
            executor=worker_f,
            quantity=10,
            authorized_at_cut=6,
            expires_after_cut=12,
            purpose="058-revalidation",
        )
        temporal_revalidation = derive_temporal_intersection(
            promise,
            route_policy,
            revalidation_bundles,
            reservation_revalidation,
            observed_cut=7,
        )
        assert (
            temporal_revalidation["aggregate_action"]
            == "REVALIDATION_REQUIRED"
        )
        missing_revalidation_refused = refused(
            lambda: execute_with_transition_gate(
                store_revalidation,
                treasury_f,
                proposal_revalidation,
                auth_revalidation,
                reservation_revalidation,
                promise=promise,
                route_policy=route_policy,
                bundles=revalidation_bundles,
                transition_subject_reservation=reservation_revalidation,
                supplied_temporal_intersection=temporal_revalidation,
                executor=worker_f,
                observed_cut=7,
                simulate_success=True,
                result_ref="result:058-missing-revalidation",
            )
        )
        assert missing_revalidation_refused

        prior_binding_id = content_address(
            {"kind": "058-prior-binding", "case": "revalidation"}
        )
        prior_admission_id = content_address(
            {"kind": "058-prior-admission", "case": "revalidation"}
        )
        revalidation = derive_revalidation(
            promise,
            route_policy,
            previous_policy_set=policy_set_v1,
            current_policy_set=policy_set_v2_cut7,
            policies=policies,
            candidate=candidate_f,
            measurements=[measurement_f],
            attestations=attestations_f,
            reservation=reservation_revalidation,
            prior_binding_id=prior_binding_id,
            prior_admission_response_id=prior_admission_id,
            evaluation_cut=7,
        )
        assert revalidation["status"] == "COMPLIANT"
        revalidation_context = {
            "policies": policies,
            "versions": versions,
            "previous_policy_set": policy_set_v1,
            "current_policy_set": policy_set_v2_cut7,
            "candidate": candidate_f,
            "measurements": [measurement_f],
            "attestations": attestations_f,
            "prior_binding_id": prior_binding_id,
            "prior_admission_response_id": prior_admission_id,
            "revalidation": revalidation,
        }
        wrong_evidence_type_refused = refused(
            lambda: execute_with_transition_gate(
                store_revalidation,
                treasury_f,
                proposal_revalidation,
                auth_revalidation,
                reservation_revalidation,
                promise=promise,
                route_policy=route_policy,
                bundles=revalidation_bundles,
                transition_subject_reservation=reservation_revalidation,
                supplied_temporal_intersection=temporal_revalidation,
                executor=worker_f,
                observed_cut=7,
                simulate_success=True,
                revalidation_context=revalidation_context,
                migration_context={"not": "migration"},
                result_ref="result:058-mixed-evidence",
            )
        )
        assert wrong_evidence_type_refused

        revalidation_gate, revalidation_execution, revalidation_final = (
            execute_with_transition_gate(
                store_revalidation,
                treasury_f,
                proposal_revalidation,
                auth_revalidation,
                reservation_revalidation,
                promise=promise,
                route_policy=route_policy,
                bundles=revalidation_bundles,
                transition_subject_reservation=reservation_revalidation,
                supplied_temporal_intersection=temporal_revalidation,
                executor=worker_f,
                observed_cut=7,
                simulate_success=True,
                revalidation_context=revalidation_context,
                result_ref="result:058-current-revalidation",
            )
        )
        assert revalidation_gate["evidence_path"] == "CURRENT_REVALIDATION"
        assert revalidation_gate["revalidation_id"] == (
            revalidation["revalidation_id"]
        )
        assert revalidation_execution["success"] is True
        assert revalidation_final["status"] == "CONSUMED"

        # C. Migration path executes only a distinct new reservation after the
        # old owner explicitly releases the old one.
        store_old = GuildReservationStore(
            root / "migration-old",
            steward=guild_f,
        )
        proposal_old, auth_old, reservation_old = reserve(
            store_old,
            treasury_f,
            entry_f,
            proposer=guild_f,
            executor=worker_f,
            quantity=10,
            authorized_at_cut=6,
            expires_after_cut=12,
            purpose="058-migration-old",
        )
        temporal_migration = derive_temporal_intersection(
            promise,
            route_policy,
            migration_bundles,
            reservation_old,
            observed_cut=8,
        )
        assert temporal_migration["aggregate_action"] == "MIGRATION_REQUIRED"

        old_release = store_old.release(
            treasury_f,
            proposal_old,
            auth_old,
            reservation_old,
            observed_cut=7,
            reason="058_MIGRATION_REQUIRED",
        )
        store_new = GuildReservationStore(
            root / "migration-new",
            steward=guild_e,
        )
        proposal_new, auth_new, reservation_new = reserve(
            store_new,
            treasury_e,
            entry_e,
            proposer=guild_e,
            executor=worker_e,
            quantity=10,
            authorized_at_cut=8,
            expires_after_cut=13,
            purpose="058-migration-new",
        )
        migration_decision = derive_transition_decision(
            customer_migrate,
            reservation_old,
            observed_cut=8,
        )
        migration_receipt = make_migration_receipt(
            customer_migrate,
            migration_decision,
            old_reservation=reservation_old,
            old_finalization=old_release,
            new_reservation=reservation_new,
            current_policy_set_id=policy_set_v2_cut8["policy_set_id"],
        )
        migration_context = {
            "policies": policies,
            "versions": versions,
            "current_policy_set": policy_set_v2_cut8,
            "transition": customer_migrate,
            "old_finalization": old_release,
            "migration_receipt": migration_receipt,
        }

        old_reservation_execution_refused = refused(
            lambda: execute_with_transition_gate(
                store_old,
                treasury_f,
                proposal_old,
                auth_old,
                reservation_old,
                promise=promise,
                route_policy=route_policy,
                bundles=migration_bundles,
                transition_subject_reservation=reservation_old,
                supplied_temporal_intersection=temporal_migration,
                executor=worker_f,
                observed_cut=8,
                simulate_success=True,
                migration_context=migration_context,
                result_ref="result:058-old-reservation-must-not-run",
            )
        )
        assert old_reservation_execution_refused

        migration_gate, migration_execution, migration_final = (
            execute_with_transition_gate(
                store_new,
                treasury_e,
                proposal_new,
                auth_new,
                reservation_new,
                promise=promise,
                route_policy=route_policy,
                bundles=migration_bundles,
                transition_subject_reservation=reservation_old,
                supplied_temporal_intersection=temporal_migration,
                executor=worker_e,
                observed_cut=8,
                simulate_success=True,
                migration_context=migration_context,
                result_ref="result:058-verified-migration",
            )
        )
        assert migration_gate["evidence_path"] == "VERIFIED_MIGRATION"
        assert migration_gate["migration_id"] == migration_receipt["migration_id"]
        assert migration_gate["execution_reservation_id"] == (
            reservation_new["reservation_id"]
        )
        assert migration_execution["success"] is True
        assert migration_final["status"] == "CONSUMED"

        # D. No common temporal path is an unconditional hard stop.
        store_conflict = GuildReservationStore(
            root / "conflict",
            steward=guild_f,
        )
        proposal_conflict, auth_conflict, reservation_conflict = reserve(
            store_conflict,
            treasury_f,
            entry_f,
            proposer=guild_f,
            executor=worker_f,
            quantity=10,
            authorized_at_cut=6,
            expires_after_cut=12,
            purpose="058-no-common",
        )
        temporal_conflict = derive_temporal_intersection(
            promise,
            route_policy,
            conflict_bundles,
            reservation_conflict,
            observed_cut=7,
            execution_started_at_cut=6,
        )
        assert temporal_conflict["result"] == "NO_COMMON_TRANSITION_PATH"
        no_common_execution_refused = refused(
            lambda: execute_with_transition_gate(
                store_conflict,
                treasury_f,
                proposal_conflict,
                auth_conflict,
                reservation_conflict,
                promise=promise,
                route_policy=route_policy,
                bundles=conflict_bundles,
                transition_subject_reservation=reservation_conflict,
                supplied_temporal_intersection=temporal_conflict,
                executor=worker_f,
                observed_cut=7,
                execution_started_at_cut=6,
                simulate_success=True,
                result_ref="result:058-no-common-must-not-run",
            )
        )
        assert no_common_execution_refused
        assert store_conflict.capacity_state(
            treasury_f,
            entry_f["entry_id"],
        )["reserved_quantity"] == 10

        print(json.dumps({
            "simulation_passed": True,
            "legacy": {
                "stale_intersection_refused": stale_legacy_refused,
                "fresh_gate_path": legacy_gate["evidence_path"],
                "execution": legacy_execution["success"],
            },
            "revalidation": {
                "missing_receipt_refused": missing_revalidation_refused,
                "wrong_evidence_type_refused": wrong_evidence_type_refused,
                "gate_path": revalidation_gate["evidence_path"],
                "revalidation_status": revalidation["status"],
                "execution": revalidation_execution["success"],
            },
            "migration": {
                "old_reservation_execution_refused": (
                    old_reservation_execution_refused
                ),
                "gate_path": migration_gate["evidence_path"],
                "old_finalization": old_release["status"],
                "new_reservation_consumed": migration_final["status"],
                "execution": migration_execution["success"],
            },
            "no_common_path": {
                "execution_refused": no_common_execution_refused,
                "reservation_still_live": True,
            },
            "laws": [
                "DECISION != ENFORCEMENT",
                "STALE TEMPORAL INTERSECTION != CURRENT AUTHORITY",
                "LEGACY PERMISSION MUST BE PROVEN AT EXECUTION TIME",
                "REVALIDATION RECEIPT != MIGRATION RECEIPT",
                "NO COMMON PATH != EXECUTION AUTHORITY",
                "ENFORCEMENT MUST RECOMPUTE FROM SOURCE EVIDENCE",
            ],
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
