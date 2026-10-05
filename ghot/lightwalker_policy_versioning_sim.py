#!/usr/bin/env python3
"""Experiment 055 — Policy Versioning / Mid-Flight Change."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_constraint_routing import make_constraint_attestation
from lightwalker_economy import LightwalkerEconomyError
from lightwalker_federated_reroute import (
    attest_rerouted_performance,
    derive_rerouted_backing,
    derive_rerouted_completion,
    derive_rerouted_settlement,
    make_substitute_completion,
    make_substitute_request,
    reserve_substitute,
)
from lightwalker_federated_service import make_remote_capacity_proof
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_reservation,
)
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    accept_exchange_offer,
    make_exchange_offer,
    make_obligation,
    settle_exchange,
    sign_obligation_performance,
)
from lightwalker_multi_source_service import (
    make_multi_source_promise,
    make_source_completion,
    make_source_request,
    reserve_source,
)
from lightwalker_policy_composition import (
    compose_policy_intersection,
    derive_composed_frontier,
    evaluate_policy_intersection,
    make_composed_policy_bound_reroute,
    make_policy_fragment,
    score_composed_frontier,
)
from lightwalker_policy_versioning import (
    active_policy_fragments,
    bind_route_to_policy_set,
    derive_active_policy_set,
    derive_revalidation,
    execute_reserved_with_revalidation,
    make_policy_version,
    policy_lineage_id,
    verify_policy_version,
    verify_revalidation,
)
from lightwalker_route_policy import (
    make_owner_admission_response,
    make_route_policy,
    verify_owner_admission_response,
)
from lightwalker_route_scoring import (
    make_route_measurement,
    make_scoring_policy,
)
from relatte_identity import IdentityKey


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def source_treasury(
    *,
    guild_id: str,
    steward: IdentityKey,
    suffix: str,
    quantity: int = 60,
) -> tuple[dict, dict]:
    entry = make_treasury_entry(
        category="capability",
        position="available",
        subject_ref=f"capability:{guild_id}-render-{suffix}",
        source_ref=f"ghot-node:{guild_id}-{suffix}",
        evidence_refs=[f"receipt:{guild_id}-probe-{suffix}"],
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
    return snapshot, entry


def customer_offer(
    *,
    promisor: IdentityKey,
    customer: IdentityKey,
) -> dict:
    service = make_obligation(
        obligation_type="future-compute-service",
        resource_ref="service:adaptive-policy-render-055",
        terms={
            "unit": "compute-minute",
            "quantity": 60,
            "capability": "render.verified",
        },
        evidence_policy="current-policy-version-and-service-completion",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref="consideration:adaptive-policy-055",
        terms={
            "deliverable": "one signed review note",
            "customer": customer.particular(),
        },
        evidence_policy="signed-counterparty-performance",
    )
    return make_exchange_offer(
        offeror_particular=promisor.particular(),
        offeror_obligation=service,
        acceptor_obligation=consideration,
        orientation_refs=[],
        valid_through_cut=20,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild_a = IdentityKey.load_or_create(root / "guild-a" / "body-p256.pem")
        guild_b = IdentityKey.load_or_create(root / "guild-b" / "body-p256.pem")
        guild_c = IdentityKey.load_or_create(root / "guild-c" / "body-p256.pem")
        guild_e = IdentityKey.load_or_create(root / "guild-e" / "body-p256.pem")
        guild_f = IdentityKey.load_or_create(root / "guild-f" / "body-p256.pem")
        guild_h = IdentityKey.load_or_create(root / "guild-h" / "body-p256.pem")

        customer = IdentityKey.load_or_create(
            root / "customer" / "body-p256.pem"
        )
        project_authority = IdentityKey.load_or_create(
            root / "project-authority" / "body-p256.pem"
        )
        customer_assessor = IdentityKey.load_or_create(
            root / "customer-assessor" / "body-p256.pem"
        )
        promisor_assessor = IdentityKey.load_or_create(
            root / "promisor-assessor" / "body-p256.pem"
        )
        project_assessor = IdentityKey.load_or_create(
            root / "project-assessor" / "body-p256.pem"
        )
        route_probe = IdentityKey.load_or_create(
            root / "route-probe" / "body-p256.pem"
        )

        worker_b = IdentityKey.load_or_create(root / "worker-b" / "body-p256.pem")
        worker_c = IdentityKey.load_or_create(root / "worker-c" / "body-p256.pem")
        worker_e = IdentityKey.load_or_create(root / "worker-e" / "body-p256.pem")
        worker_f = IdentityKey.load_or_create(root / "worker-f" / "body-p256.pem")

        stewards = {
            "guild:b": guild_b,
            "guild:c": guild_c,
            "guild:e": guild_e,
            "guild:f": guild_f,
            "guild:h": guild_h,
        }
        treasuries = {}
        entries = {}
        proofs = {}
        proof_specs = {
            "guild:b": (1, 10),
            "guild:c": (1, 12),
            "guild:e": (4, 14),
            "guild:f": (3, 14),
            "guild:h": (4, 14),
        }
        for guild_id, steward in stewards.items():
            snapshot, entry = source_treasury(
                guild_id=guild_id,
                steward=steward,
                suffix="055",
            )
            treasuries[guild_id] = snapshot
            entries[guild_id] = entry
            observed, valid = proof_specs[guild_id]
            proofs[guild_id] = make_remote_capacity_proof(
                snapshot,
                steward=steward,
                resource_entry_id=entry["entry_id"],
                observed_cut=observed,
                valid_through_cut=valid,
            )

        original_sources = [
            {
                "snapshot": treasuries["guild:b"],
                "proof": proofs["guild:b"],
                "quantity": 30,
            },
            {
                "snapshot": treasuries["guild:c"],
                "proof": proofs["guild:c"],
                "quantity": 30,
            },
        ]
        offer = customer_offer(
            promisor=guild_a,
            customer=customer,
        )
        promise = make_multi_source_promise(
            offer,
            original_sources,
            promisor=guild_a,
            promised_at_cut=2,
        )
        frozen_promise = json.dumps(promise, sort_keys=True)
        acceptance = accept_exchange_offer(
            offer,
            acceptor_particular=customer.particular(),
            accepted_at_cut=2,
        )
        source_b = next(
            row
            for row in promise["sources"]
            if row["capacity_guild_id"] == "guild:b"
        )
        source_c = next(
            row
            for row in promise["sources"]
            if row["capacity_guild_id"] == "guild:c"
        )

        route_policy = make_route_policy(
            offer,
            original_sources,
            promise,
            source_slot_id=source_b["source_id"],
            promisor=guild_a,
            ordered_guild_ids=[
                "guild:b",
                "guild:e",
                "guild:f",
                "guild:h",
            ],
            required_capability="render.verified",
            max_proof_age_cuts=5,
            max_failover_hops=4,
            created_at_cut=2,
        )

        candidates = [
            {
                "snapshot": treasuries[guild_id],
                "proof": proofs[guild_id],
            }
            for guild_id in ["guild:b", "guild:e", "guild:f", "guild:h"]
        ]
        metrics = {
            "guild:e": dict(
                latency_ms=15,
                reliability_ppm=980_000,
                energy_mwh_per_compute_minute=60,
                expected_completion_cuts=2,
            ),
            "guild:f": dict(
                latency_ms=30,
                reliability_ppm=999_000,
                energy_mwh_per_compute_minute=10,
                expected_completion_cuts=3,
            ),
            "guild:h": dict(
                latency_ms=40,
                reliability_ppm=970_000,
                energy_mwh_per_compute_minute=80,
                expected_completion_cuts=4,
            ),
        }
        measurements = [
            make_route_measurement(
                treasuries[guild_id],
                proofs[guild_id],
                measurer=route_probe,
                observed_cut=5,
                **metrics[guild_id],
            )
            for guild_id in ["guild:e", "guild:f", "guild:h"]
        ]

        customer_v1 = make_policy_fragment(
            promise,
            route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-privacy-boundary",
            trusted_assessor_particular=customer_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:b"],
            min_privacy_class=3,
            require_renewable_evidence=False,
            max_expected_completion_cuts=4,
            forbidden_sovereign_groups=["group:x"],
            max_attestation_age_cuts=3,
            created_at_cut=5,
        )
        promisor_v1 = make_policy_fragment(
            promise,
            route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-operational-boundary",
            trusted_assessor_particular=promisor_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:b"],
            min_privacy_class=4,
            require_renewable_evidence=True,
            max_expected_completion_cuts=5,
            forbidden_sovereign_groups=[],
            max_attestation_age_cuts=3,
            created_at_cut=5,
        )
        project_v1 = make_policy_fragment(
            promise,
            route_policy,
            issuer=project_authority,
            issuer_role="project",
            policy_name="project-delivery-boundary",
            trusted_assessor_particular=project_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:b"],
            min_privacy_class=2,
            require_renewable_evidence=False,
            max_expected_completion_cuts=4,
            forbidden_sovereign_groups=[],
            max_attestation_age_cuts=3,
            created_at_cut=5,
        )

        # Customer v2 keeps the same policy identity but changes its immutable
        # fragment: group:f is no longer permitted.
        customer_v2 = make_policy_fragment(
            promise,
            route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-privacy-boundary",
            trusted_assessor_particular=customer_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:b"],
            min_privacy_class=3,
            require_renewable_evidence=False,
            max_expected_completion_cuts=4,
            forbidden_sovereign_groups=["group:x", "group:f"],
            max_attestation_age_cuts=3,
            created_at_cut=7,
        )

        customer_version_1 = make_policy_version(
            promise,
            route_policy,
            customer_v1,
            issuer=customer,
            version_number=1,
            effective_from_cut=5,
            declared_at_cut=5,
        )
        customer_version_2 = make_policy_version(
            promise,
            route_policy,
            customer_v2,
            issuer=customer,
            version_number=2,
            effective_from_cut=7,
            declared_at_cut=7,
            previous_version=customer_version_1,
        )
        promisor_version_1 = make_policy_version(
            promise,
            route_policy,
            promisor_v1,
            issuer=guild_a,
            version_number=1,
            effective_from_cut=5,
            declared_at_cut=5,
        )
        project_version_1 = make_policy_version(
            promise,
            route_policy,
            project_v1,
            issuer=project_authority,
            version_number=1,
            effective_from_cut=5,
            declared_at_cut=5,
        )
        all_policies = [
            customer_v1,
            customer_v2,
            promisor_v1,
            project_v1,
        ]
        all_versions = [
            customer_version_1,
            customer_version_2,
            promisor_version_1,
            project_version_1,
        ]
        for policy, version in (
            (customer_v1, customer_version_1),
            (customer_v2, customer_version_2),
            (promisor_v1, promisor_version_1),
            (project_v1, project_version_1),
        ):
            assert verify_policy_version(
                promise, route_policy, policy, version
            )

        assert policy_lineage_id(customer_v1) == policy_lineage_id(
            customer_v2
        )
        assert customer_v1["policy_id"] != customer_v2["policy_id"]
        assert (
            customer_version_1["policy_version_id"]
            != customer_version_2["policy_version_id"]
        )

        frozen_v1 = json.dumps(customer_v1, sort_keys=True)
        frozen_v2 = json.dumps(customer_v2, sort_keys=True)

        facts = {
            "guild:e": dict(
                jurisdiction="zone:b",
                privacy_class=4,
                renewable_evidence_present=True,
                sovereign_group="group:e",
            ),
            "guild:f": dict(
                jurisdiction="zone:b",
                privacy_class=5,
                renewable_evidence_present=True,
                sovereign_group="group:f",
            ),
            "guild:h": dict(
                jurisdiction="zone:b",
                privacy_class=4,
                renewable_evidence_present=True,
                sovereign_group="group:h",
            ),
        }
        assessors = [
            customer_assessor,
            promisor_assessor,
            project_assessor,
        ]
        attestations = []
        for guild_id in ["guild:e", "guild:f", "guild:h"]:
            for assessor in assessors:
                attestations.append(
                    make_constraint_attestation(
                        treasuries[guild_id],
                        proofs[guild_id],
                        assessor=assessor,
                        observed_cut=5,
                        **facts[guild_id],
                    )
                )

        scoring_policy = make_scoring_policy(
            promise,
            route_policy,
            promisor=guild_a,
            trusted_measurer_particular=route_probe.particular(),
            profile_name="reliability-energy-adaptive",
            weights={
                "freshness": 1,
                "quantity_headroom": 0,
                "reliability": 5,
                "latency": 1,
                "energy": 20,
                "completion_window": 1,
            },
            max_measurement_age_cuts=3,
            created_at_cut=5,
        )

        policy_set_v1 = derive_active_policy_set(
            promise,
            route_policy,
            all_policies,
            all_versions,
            observed_cut=6,
        )
        active_v1 = active_policy_fragments(
            policy_set_v1, all_policies
        )
        assert {p["policy_id"] for p in active_v1} == {
            customer_v1["policy_id"],
            promisor_v1["policy_id"],
            project_v1["policy_id"],
        }
        assert customer_version_2["policy_version_id"] not in {
            row["policy_version_id"]
            for row in policy_set_v1["active_versions"]
        }

        intersection_v1 = compose_policy_intersection(
            promise, route_policy, active_v1
        )
        evaluation_v1 = evaluate_policy_intersection(
            promise,
            route_policy,
            active_v1,
            intersection_v1,
            candidates,
            measurements,
            attestations,
            evaluation_cut=6,
            excluded_guild_ids=["guild:b"],
        )
        frontier_v1 = derive_composed_frontier(
            evaluation_v1
        )
        selection_v1 = score_composed_frontier(
            promise,
            route_policy,
            scoring_policy,
            evaluation_v1,
            frontier_v1,
            candidates,
            measurements,
            evaluation_cut=6,
        )
        assert (
            selection_v1["selected_candidate"]["capacity_guild_id"]
            == "guild:f"
        )

        request_b = make_source_request(
            offer,
            acceptance,
            original_sources,
            promise,
            source_id=source_b["source_id"],
            promisor=guild_a,
            requested_at_cut=3,
        )
        request_c = make_source_request(
            offer,
            acceptance,
            original_sources,
            promise,
            source_id=source_c["source_id"],
            promisor=guild_a,
            requested_at_cut=3,
        )

        store_b = GuildReservationStore(
            root / "reservations-b", steward=guild_b
        )
        store_c = GuildReservationStore(
            root / "reservations-c", steward=guild_c
        )
        store_e = GuildReservationStore(
            root / "reservations-e", steward=guild_e
        )
        store_f = GuildReservationStore(
            root / "reservations-f", steward=guild_f
        )

        (
            proposal_b,
            auth_b,
            reservation_b,
            grant_b,
        ) = reserve_source(
            treasuries["guild:b"],
            proofs["guild:b"],
            request_b,
            capacity_steward=guild_b,
            executor_particular=worker_b.particular(),
            reservation_store=store_b,
            reserved_at_cut=3,
            expires_after_cut=8,
        )
        (
            proposal_c,
            auth_c,
            reservation_c,
            grant_c,
        ) = reserve_source(
            treasuries["guild:c"],
            proofs["guild:c"],
            request_c,
            capacity_steward=guild_c,
            executor_particular=worker_c.particular(),
            reservation_store=store_c,
            reserved_at_cut=3,
            expires_after_cut=12,
        )
        execution_b, final_b = store_b.execute_reserved(
            treasuries["guild:b"],
            proposal_b,
            auth_b,
            reservation_b,
            executor=worker_b,
            observed_cut=4,
            simulate_success=False,
            error="simulation: original B route failed",
        )
        assert execution_b["success"] is False
        assert final_b["status"] == "RELEASED"

        admission_f = make_owner_admission_response(
            selection_v1,
            treasuries["guild:f"],
            proofs["guild:f"],
            reservation_store=store_f,
            steward=guild_f,
            observed_cut=6,
        )
        assert admission_f["disposition"] == "ADMITTABLE"

        reroute_f, binding_f = make_composed_policy_bound_reroute(
            offer,
            acceptance,
            original_sources,
            promise,
            route_policy=route_policy,
            scoring_policy=scoring_policy,
            evaluation=evaluation_v1,
            frontier=frontier_v1,
            candidates=candidates,
            measurements=measurements,
            selection=selection_v1,
            admission_response=admission_f,
            original_source_id=source_b["source_id"],
            original_snapshot=treasuries["guild:b"],
            original_proof=proofs["guild:b"],
            original_request=request_b,
            original_proposal=proposal_b,
            original_authorization=auth_b,
            original_reservation=reservation_b,
            original_grant=grant_b,
            original_finalization=final_b,
            substitute_snapshot=treasuries["guild:f"],
            substitute_proof=proofs["guild:f"],
            promisor=guild_a,
            rerouted_at_cut=6,
        )
        request_f = make_substitute_request(
            offer,
            acceptance,
            promise,
            treasuries["guild:f"],
            proofs["guild:f"],
            reroute_f,
            promisor=guild_a,
            requested_at_cut=6,
        )
        (
            proposal_f,
            auth_f,
            reservation_f,
            grant_f,
        ) = reserve_substitute(
            treasuries["guild:f"],
            proofs["guild:f"],
            reroute_f,
            request_f,
            capacity_steward=guild_f,
            executor_particular=worker_f.particular(),
            reservation_store=store_f,
            reserved_at_cut=6,
            expires_after_cut=12,
        )
        versioned_binding_f = bind_route_to_policy_set(
            policy_set_v1,
            route_binding_id=binding_f["binding_id"],
            reservation_id=reservation_f["reservation_id"],
            admission_response_id=admission_f["admission_response_id"],
        )
        assert versioned_binding_f["bound_at_cut"] == 6
        assert store_f.capacity_state(
            treasuries["guild:f"],
            entries["guild:f"]["entry_id"],
        )["reserved_quantity"] == 30

        # Customer v2 becomes active at cut 7. The old artifacts remain
        # cryptographically valid history, but future authority must be checked.
        policy_set_v2 = derive_active_policy_set(
            promise,
            route_policy,
            all_policies,
            all_versions,
            observed_cut=7,
        )
        assert customer_version_1["policy_version_id"] in (
            policy_set_v2["superseded_policy_version_ids"]
        )
        assert customer_version_2["policy_version_id"] in {
            row["policy_version_id"]
            for row in policy_set_v2["active_versions"]
        }
        assert verify_owner_admission_response(
            selection_v1, admission_f
        )
        assert verify_reservation(
            treasuries["guild:f"],
            proposal_f,
            auth_f,
            reservation_f,
        )

        candidate_f = next(
            item
            for item in candidates
            if item["proof"]["capacity_guild_id"] == "guild:f"
        )
        revalidation_f = derive_revalidation(
            promise,
            route_policy,
            previous_policy_set=policy_set_v1,
            current_policy_set=policy_set_v2,
            policies=all_policies,
            candidate=candidate_f,
            measurements=measurements,
            attestations=attestations,
            reservation=reservation_f,
            prior_binding_id=versioned_binding_f[
                "versioned_binding_id"
            ],
            prior_admission_response_id=admission_f[
                "admission_response_id"
            ],
            evaluation_cut=7,
        )
        assert verify_revalidation(
            promise,
            route_policy,
            previous_policy_set=policy_set_v1,
            current_policy_set=policy_set_v2,
            policies=all_policies,
            candidate=candidate_f,
            measurements=measurements,
            attestations=attestations,
            reservation=reservation_f,
            prior_binding_id=versioned_binding_f[
                "versioned_binding_id"
            ],
            prior_admission_response_id=admission_f[
                "admission_response_id"
            ],
            revalidation=revalidation_f,
        )
        assert revalidation_f["status"] == "NONCOMPLIANT"
        assert revalidation_f["future_execution_permitted"] is False
        customer_v2_verdict = next(
            row
            for row in revalidation_f["policy_failures"]
            if row["policy_id"] == customer_v2["policy_id"]
        )
        assert customer_v2_verdict["status"] == "FAIL"
        assert (
            "SOVEREIGN_GROUP_FORBIDDEN"
            in customer_v2_verdict["failures"]
        )

        missing_revalidation_refused = refused(
            lambda: execute_reserved_with_revalidation(
                store_f,
                treasuries["guild:f"],
                proposal_f,
                auth_f,
                reservation_f,
                promise=promise,
                route_policy=route_policy,
                previous_policy_set=policy_set_v1,
                current_policy_set=policy_set_v2,
                policies=all_policies,
                candidate=candidate_f,
                measurements=measurements,
                attestations=attestations,
                prior_binding_id=versioned_binding_f[
                    "versioned_binding_id"
                ],
                prior_admission_response_id=admission_f[
                    "admission_response_id"
                ],
                revalidation=None,
                executor=worker_f,
                observed_cut=7,
                simulate_success=True,
                result_ref="result:055-f-illegal-no-revalidation",
            )
        )
        assert missing_revalidation_refused

        failed_revalidation_refused = refused(
            lambda: execute_reserved_with_revalidation(
                store_f,
                treasuries["guild:f"],
                proposal_f,
                auth_f,
                reservation_f,
                promise=promise,
                route_policy=route_policy,
                previous_policy_set=policy_set_v1,
                current_policy_set=policy_set_v2,
                policies=all_policies,
                candidate=candidate_f,
                measurements=measurements,
                attestations=attestations,
                prior_binding_id=versioned_binding_f[
                    "versioned_binding_id"
                ],
                prior_admission_response_id=admission_f[
                    "admission_response_id"
                ],
                revalidation=revalidation_f,
                executor=worker_f,
                observed_cut=7,
                simulate_success=True,
                result_ref="result:055-f-illegal-noncompliant",
            )
        )
        assert failed_revalidation_refused

        release_f = store_f.release(
            treasuries["guild:f"],
            proposal_f,
            auth_f,
            reservation_f,
            observed_cut=7,
            reason="POLICY_V2_REVALIDATION_FAILED",
        )
        assert release_f["status"] == "RELEASED"
        assert store_f.capacity_state(
            treasuries["guild:f"],
            entries["guild:f"]["entry_id"],
        )["reserved_quantity"] == 0

        # Recompute with the current v2 policy set. F is now ineligible and E
        # becomes the sole non-dominated route.
        active_v2 = active_policy_fragments(
            policy_set_v2, all_policies
        )
        intersection_v2 = compose_policy_intersection(
            promise, route_policy, active_v2
        )
        evaluation_v2 = evaluate_policy_intersection(
            promise,
            route_policy,
            active_v2,
            intersection_v2,
            candidates,
            measurements,
            attestations,
            evaluation_cut=7,
            excluded_guild_ids=["guild:b"],
        )
        rows_v2 = {
            row["capacity_guild_id"]: row
            for row in evaluation_v2["candidate_rows"]
        }
        assert rows_v2["guild:f"]["intersection_status"] == "INELIGIBLE"
        assert rows_v2["guild:e"]["intersection_status"] == "ELIGIBLE"

        frontier_v2 = derive_composed_frontier(
            evaluation_v2
        )
        assert {
            row["capacity_guild_id"]
            for row in frontier_v2["frontier"]
        } == {"guild:e"}
        selection_v2 = score_composed_frontier(
            promise,
            route_policy,
            scoring_policy,
            evaluation_v2,
            frontier_v2,
            candidates,
            measurements,
            evaluation_cut=7,
        )
        assert (
            selection_v2["selected_candidate"]["capacity_guild_id"]
            == "guild:e"
        )

        admission_e = make_owner_admission_response(
            selection_v2,
            treasuries["guild:e"],
            proofs["guild:e"],
            reservation_store=store_e,
            steward=guild_e,
            observed_cut=7,
        )
        reroute_e, binding_e = make_composed_policy_bound_reroute(
            offer,
            acceptance,
            original_sources,
            promise,
            route_policy=route_policy,
            scoring_policy=scoring_policy,
            evaluation=evaluation_v2,
            frontier=frontier_v2,
            candidates=candidates,
            measurements=measurements,
            selection=selection_v2,
            admission_response=admission_e,
            original_source_id=source_b["source_id"],
            original_snapshot=treasuries["guild:b"],
            original_proof=proofs["guild:b"],
            original_request=request_b,
            original_proposal=proposal_b,
            original_authorization=auth_b,
            original_reservation=reservation_b,
            original_grant=grant_b,
            original_finalization=final_b,
            substitute_snapshot=treasuries["guild:e"],
            substitute_proof=proofs["guild:e"],
            promisor=guild_a,
            rerouted_at_cut=7,
        )
        request_e = make_substitute_request(
            offer,
            acceptance,
            promise,
            treasuries["guild:e"],
            proofs["guild:e"],
            reroute_e,
            promisor=guild_a,
            requested_at_cut=8,
        )
        (
            proposal_e,
            auth_e,
            reservation_e,
            grant_e,
        ) = reserve_substitute(
            treasuries["guild:e"],
            proofs["guild:e"],
            reroute_e,
            request_e,
            capacity_steward=guild_e,
            executor_particular=worker_e.particular(),
            reservation_store=store_e,
            reserved_at_cut=8,
            expires_after_cut=13,
        )
        versioned_binding_e = bind_route_to_policy_set(
            policy_set_v2,
            route_binding_id=binding_e["binding_id"],
            reservation_id=reservation_e["reservation_id"],
            admission_response_id=admission_e["admission_response_id"],
        )
        assert versioned_binding_e["policy_set_id"] == (
            policy_set_v2["policy_set_id"]
        )

        execution_e, final_e = store_e.execute_reserved(
            treasuries["guild:e"],
            proposal_e,
            auth_e,
            reservation_e,
            executor=worker_e,
            observed_cut=8,
            simulate_success=True,
            result_ref="result:055-e-success-under-v2",
        )
        completion_e = make_substitute_completion(
            treasuries["guild:e"],
            proofs["guild:e"],
            reroute_e,
            request_e,
            proposal_e,
            auth_e,
            reservation_e,
            grant_e,
            execution_e,
            final_e,
            capacity_steward=guild_e,
        )

        execution_c, final_c = store_c.execute_reserved(
            treasuries["guild:c"],
            proposal_c,
            auth_c,
            reservation_c,
            executor=worker_c,
            observed_cut=8,
            simulate_success=True,
            result_ref="result:055-c-success",
        )
        completion_c = make_source_completion(
            treasuries["guild:c"],
            proofs["guild:c"],
            request_c,
            proposal_c,
            auth_c,
            reservation_c,
            grant_c,
            execution_c,
            final_c,
            capacity_steward=guild_c,
        )
        backing = derive_rerouted_backing(
            promise,
            original_grants=[grant_b, grant_c],
            reroutes=[reroute_e],
            substitute_grants=[grant_e],
        )
        assert backing["status"] == "COMPLETE"
        aggregate = derive_rerouted_completion(
            promise,
            original_completions=[completion_c],
            reroutes=[reroute_e],
            substitute_completions=[completion_e],
        )
        assert aggregate["status"] == "COMPLETE"

        promisor_perf = attest_rerouted_performance(
            offer,
            acceptance,
            promise,
            aggregate,
            promisor=guild_a,
        )
        customer_perf = sign_obligation_performance(
            offer,
            acceptance,
            role="ACCEPTOR",
            signer=customer,
            evidence_ref="evidence:055-customer-review",
        )
        settlement = settle_exchange(
            offer,
            acceptance,
            [promisor_perf, customer_perf],
        )
        witness = derive_rerouted_settlement(
            offer,
            acceptance,
            promise,
            aggregate,
            promisor_perf,
            customer_perf,
            settlement,
        )
        assert witness["customer_service_performed"] is True

        # Policy and historical artifacts are not rewritten by the update.
        assert json.dumps(customer_v1, sort_keys=True) == frozen_v1
        assert json.dumps(customer_v2, sort_keys=True) == frozen_v2
        assert json.dumps(promise, sort_keys=True) == frozen_promise
        assert admission_f["disposition"] == "ADMITTABLE"
        assert reservation_f["status"] == "ACTIVE"
        assert revalidation_f["old_admission_rewritten"] is False
        assert revalidation_f["reservation_rewritten"] is False
        assert revalidation_f["history_erased"] is False

        print(json.dumps({
            "simulation_passed": True,
            "policy_lineage": {
                "same_lineage": True,
                "v1_fragment_id": customer_v1["policy_id"],
                "v2_fragment_id": customer_v2["policy_id"],
                "v1_version_id": customer_version_1["policy_version_id"],
                "v2_version_id": customer_version_2["policy_version_id"],
                "v1_effective_from": 5,
                "v2_effective_from": 7,
            },
            "v1_route": {
                "selected": "guild:f",
                "admission": admission_f["disposition"],
                "reservation_created": True,
                "versioned_binding_id": versioned_binding_f[
                    "versioned_binding_id"
                ],
            },
            "v2_revalidation": {
                "status": revalidation_f["status"],
                "failure": "SOVEREIGN_GROUP_FORBIDDEN",
                "missing_revalidation_execution_refused": (
                    missing_revalidation_refused
                ),
                "failed_revalidation_execution_refused": (
                    failed_revalidation_refused
                ),
                "f_reservation_finalized": release_f["status"],
            },
            "history": {
                "old_admission_still_verifies": True,
                "old_reservation_object_still_verifies": True,
                "old_admission_rewritten": False,
                "reservation_rewritten": False,
                "history_erased": False,
            },
            "adaptation": {
                "v2_selected": "guild:e",
                "v2_versioned_binding_id": versioned_binding_e[
                    "versioned_binding_id"
                ],
                "effective_backing": 60,
                "aggregate": aggregate["status"],
                "settlement": settlement["status"],
            },
            "laws": [
                "NEW POLICY != RETROACTIVE REWRITE",
                "POLICY VERSION != POLICY IDENTITY",
                "OLD ADMISSION != NEW COMPLIANCE",
                "RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2",
                "POLICY CHANGE MAY REQUIRE REVALIDATION",
                "REVALIDATION != HISTORY ERASURE",
            ],
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
