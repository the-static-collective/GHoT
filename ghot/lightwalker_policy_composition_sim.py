#!/usr/bin/env python3
"""Experiment 054 — Policy Composition / Constraint Intersection."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_constraint_routing import make_constraint_attestation
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
from lightwalker_guild_reservation import GuildReservationStore
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
    verify_policy_fragment,
)
from lightwalker_route_policy import (
    make_owner_admission_response,
    make_route_policy,
)
from lightwalker_route_scoring import (
    make_route_measurement,
    make_scoring_policy,
)
from lightwalker_economy import LightwalkerEconomyError
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
        resource_ref="service:multi-policy-render-054",
        terms={
            "unit": "compute-minute",
            "quantity": 60,
            "capability": "render.verified",
        },
        evidence_policy="all-composed-policies-and-service-completion",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref="consideration:multi-policy-054",
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
        guild_d = IdentityKey.load_or_create(root / "guild-d" / "body-p256.pem")
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
        worker_f = IdentityKey.load_or_create(root / "worker-f" / "body-p256.pem")

        treasuries = {}
        entries = {}
        stewards = {
            "guild:b": guild_b,
            "guild:c": guild_c,
            "guild:d": guild_d,
            "guild:e": guild_e,
            "guild:f": guild_f,
            "guild:h": guild_h,
        }
        for guild_id, steward in stewards.items():
            snapshot, entry = source_treasury(
                guild_id=guild_id,
                steward=steward,
                suffix="054",
            )
            treasuries[guild_id] = snapshot
            entries[guild_id] = entry

        proofs = {}
        proof_specs = {
            "guild:b": (1, 10),
            "guild:c": (1, 12),
            "guild:d": (4, 12),
            "guild:e": (4, 12),
            "guild:f": (3, 14),
            "guild:h": (4, 12),
        }
        for guild_id, (observed, valid) in proof_specs.items():
            proofs[guild_id] = make_remote_capacity_proof(
                treasuries[guild_id],
                steward=stewards[guild_id],
                resource_entry_id=entries[guild_id]["entry_id"],
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
        offer = customer_offer(promisor=guild_a, customer=customer)
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
            row for row in promise["sources"]
            if row["capacity_guild_id"] == "guild:b"
        )
        source_c = next(
            row for row in promise["sources"]
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
                "guild:d",
                "guild:e",
                "guild:f",
                "guild:h",
            ],
            required_capability="render.verified",
            max_proof_age_cuts=4,
            max_failover_hops=4,
            created_at_cut=2,
        )

        candidate_ids = ["guild:d", "guild:e", "guild:f", "guild:h"]
        candidates = [
            {
                "snapshot": treasuries[guild_id],
                "proof": proofs[guild_id],
            }
            for guild_id in ["guild:b", *candidate_ids]
        ]

        metric_specs = {
            "guild:d": dict(
                latency_ms=4,
                reliability_ppm=995_000,
                energy_mwh_per_compute_minute=15,
                expected_completion_cuts=1,
            ),
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
                **metric_specs[guild_id],
            )
            for guild_id in candidate_ids
        ]

        customer_policy = make_policy_fragment(
            promise,
            route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-privacy-boundary",
            trusted_assessor_particular=customer_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:a", "zone:b"],
            min_privacy_class=3,
            require_renewable_evidence=False,
            max_expected_completion_cuts=4,
            forbidden_sovereign_groups=["group:x"],
            max_attestation_age_cuts=2,
            created_at_cut=5,
        )
        promisor_policy = make_policy_fragment(
            promise,
            route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-operational-boundary",
            trusted_assessor_particular=promisor_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:b", "zone:c"],
            min_privacy_class=4,
            require_renewable_evidence=True,
            max_expected_completion_cuts=5,
            forbidden_sovereign_groups=[],
            max_attestation_age_cuts=2,
            created_at_cut=5,
        )
        project_policy = make_policy_fragment(
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
            forbidden_sovereign_groups=["group:blocked"],
            max_attestation_age_cuts=2,
            created_at_cut=5,
        )
        policies = [customer_policy, promisor_policy, project_policy]
        for policy in policies:
            assert verify_policy_fragment(
                promise, route_policy, policy
            )
        frozen_policies = [
            json.dumps(policy, sort_keys=True) for policy in policies
        ]

        facts = {
            "guild:d": dict(
                jurisdiction="zone:a",
                privacy_class=5,
                renewable_evidence_present=True,
                sovereign_group="group:d",
            ),
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
        assessor_map = {
            customer_assessor.particular(): customer_assessor,
            promisor_assessor.particular(): promisor_assessor,
            project_assessor.particular(): project_assessor,
        }
        attestations = []
        for guild_id in candidate_ids:
            for assessor in assessor_map.values():
                attestations.append(
                    make_constraint_attestation(
                        treasuries[guild_id],
                        proofs[guild_id],
                        assessor=assessor,
                        observed_cut=5,
                        **facts[guild_id],
                    )
                )

        intersection = compose_policy_intersection(
            promise, route_policy, policies
        )
        assert intersection["status"] == "COMPOSABLE"
        assert intersection["effective_summary"] == {
            "allowed_jurisdictions": ["zone:b"],
            "min_privacy_class": 4,
            "require_renewable_evidence": True,
            "max_expected_completion_cuts": 4,
            "forbidden_sovereign_groups": [
                "group:blocked",
                "group:x",
            ],
        }
        assert intersection["source_policies_rewritten"] is False
        assert intersection["override_authority"] == "none"

        evaluation = evaluate_policy_intersection(
            promise,
            route_policy,
            policies,
            intersection,
            candidates,
            measurements,
            attestations,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b"],
        )
        rows = {
            row["capacity_guild_id"]: row
            for row in evaluation["candidate_rows"]
        }
        assert rows["guild:d"]["intersection_status"] == "INELIGIBLE"
        d_verdicts = {
            row["issuer_role"]: row
            for row in rows["guild:d"]["policy_verdicts"]
        }
        assert d_verdicts["customer"]["status"] == "PASS"
        assert d_verdicts["promisor"]["status"] == "FAIL"
        assert d_verdicts["project"]["status"] == "FAIL"
        assert rows["guild:e"]["intersection_status"] == "ELIGIBLE"
        assert rows["guild:f"]["intersection_status"] == "ELIGIBLE"
        assert rows["guild:h"]["intersection_status"] == "ELIGIBLE"
        assert evaluation["result"] == "SATISFYING_ROUTES"
        assert evaluation["winner"] is None

        frontier = derive_composed_frontier(evaluation)
        frontier_guilds = {
            row["capacity_guild_id"] for row in frontier["frontier"]
        }
        dominated_guilds = {
            row["capacity_guild_id"] for row in frontier["dominated"]
        }
        assert frontier_guilds == {"guild:e", "guild:f"}
        assert "guild:h" in dominated_guilds
        assert frontier["winner"] is None
        assert len(frontier["policy_provenance"]) == 3

        efficiency_policy = make_scoring_policy(
            promise,
            route_policy,
            promisor=guild_a,
            trusted_measurer_particular=route_probe.particular(),
            profile_name="reliability-energy-after-intersection",
            weights={
                "freshness": 1,
                "quantity_headroom": 0,
                "reliability": 5,
                "latency": 1,
                "energy": 20,
                "completion_window": 1,
            },
            max_measurement_age_cuts=2,
            created_at_cut=5,
        )
        selection = score_composed_frontier(
            promise,
            route_policy,
            efficiency_policy,
            evaluation,
            frontier,
            candidates,
            measurements,
            evaluation_cut=5,
        )
        assert (
            selection["selected_candidate"]["capacity_guild_id"]
            == "guild:f"
        )
        assert len(selection["policy_provenance"]) == 3

        # Conflict specimen: both policies are individually valid, but their
        # allowed-jurisdiction sets have empty intersection.
        conflict_customer = make_policy_fragment(
            promise,
            route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="conflict-customer-zone-a-only",
            trusted_assessor_particular=customer_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:a"],
            min_privacy_class=0,
            require_renewable_evidence=False,
            max_expected_completion_cuts=10,
            forbidden_sovereign_groups=[],
            max_attestation_age_cuts=2,
            created_at_cut=5,
        )
        conflict_project = make_policy_fragment(
            promise,
            route_policy,
            issuer=project_authority,
            issuer_role="project",
            policy_name="conflict-project-zone-b-only",
            trusted_assessor_particular=project_assessor.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:b"],
            min_privacy_class=0,
            require_renewable_evidence=False,
            max_expected_completion_cuts=10,
            forbidden_sovereign_groups=[],
            max_attestation_age_cuts=2,
            created_at_cut=5,
        )
        conflict_policies = [conflict_customer, conflict_project]
        conflict_intersection = compose_policy_intersection(
            promise, route_policy, conflict_policies
        )
        assert conflict_intersection["status"] == "CONFLICT"
        assert (
            "ALLOWED_JURISDICTIONS_DISJOINT"
            in conflict_intersection["static_conflicts"]
        )
        assert conflict_intersection["relaxation_authority"] == "none"
        conflict_evaluation = evaluate_policy_intersection(
            promise,
            route_policy,
            conflict_policies,
            conflict_intersection,
            candidates,
            measurements,
            attestations,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b"],
        )
        assert conflict_evaluation["result"] == "NO_SATISFYING_ROUTE"
        assert conflict_evaluation["eligible_remote_proof_ids"] == []
        assert conflict_evaluation["override_authority"] == "none"
        assert conflict_evaluation["relaxation_authority"] == "none"
        frontier_relaxation_refused = refused(
            lambda: derive_composed_frontier(
                conflict_evaluation
            )
        )
        assert frontier_relaxation_refused

        # Build the operational success path through F.
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
            expires_after_cut=9,
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
            selection,
            treasuries["guild:f"],
            proofs["guild:f"],
            reservation_store=store_f,
            steward=guild_f,
            observed_cut=5,
        )
        assert admission_f["disposition"] == "ADMITTABLE"
        assert admission_f["reservation_created"] is False

        reroute, binding = make_composed_policy_bound_reroute(
            offer,
            acceptance,
            original_sources,
            promise,
            route_policy=route_policy,
            scoring_policy=efficiency_policy,
            evaluation=evaluation,
            frontier=frontier,
            candidates=candidates,
            measurements=measurements,
            selection=selection,
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
            rerouted_at_cut=5,
        )
        assert binding["selected_capacity_guild_id"] == "guild:f"
        assert binding["source_policies_rewritten"] is False
        assert binding["override_authority"] == "none"
        assert binding["relaxation_authority"] == "none"
        assert len(binding["policy_provenance"]) == 3

        substitute_request = make_substitute_request(
            offer,
            acceptance,
            promise,
            treasuries["guild:f"],
            proofs["guild:f"],
            reroute,
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
            reroute,
            substitute_request,
            capacity_steward=guild_f,
            executor_particular=worker_f.particular(),
            reservation_store=store_f,
            reserved_at_cut=6,
            expires_after_cut=12,
        )
        backing = derive_rerouted_backing(
            promise,
            original_grants=[grant_b, grant_c],
            reroutes=[reroute],
            substitute_grants=[grant_f],
        )
        assert backing["status"] == "COMPLETE"

        execution_c, final_c = store_c.execute_reserved(
            treasuries["guild:c"],
            proposal_c,
            auth_c,
            reservation_c,
            executor=worker_c,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:054-c-success",
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
        execution_f, final_f = store_f.execute_reserved(
            treasuries["guild:f"],
            proposal_f,
            auth_f,
            reservation_f,
            executor=worker_f,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:054-f-success",
        )
        completion_f = make_substitute_completion(
            treasuries["guild:f"],
            proofs["guild:f"],
            reroute,
            substitute_request,
            proposal_f,
            auth_f,
            reservation_f,
            grant_f,
            execution_f,
            final_f,
            capacity_steward=guild_f,
        )
        aggregate = derive_rerouted_completion(
            promise,
            original_completions=[completion_c],
            reroutes=[reroute],
            substitute_completions=[completion_f],
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
            evidence_ref="evidence:054-customer-review",
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

        assert json.dumps(promise, sort_keys=True) == frozen_promise
        assert [
            json.dumps(policy, sort_keys=True) for policy in policies
        ] == frozen_policies

        print(json.dumps({
            "simulation_passed": True,
            "policies": {
                "count": 3,
                "roles": ["customer", "promisor", "project"],
                "source_policies_rewritten": False,
                "intersection_summary": intersection["effective_summary"],
            },
            "intersection": {
                "guild_d_customer": d_verdicts["customer"]["status"],
                "guild_d_promisor": d_verdicts["promisor"]["status"],
                "guild_d_project": d_verdicts["project"]["status"],
                "eligible": ["guild:e", "guild:f", "guild:h"],
                "winner": None,
            },
            "pareto": {
                "frontier": sorted(frontier_guilds),
                "dominated": sorted(dominated_guilds),
                "selected_after_local_preference": "guild:f",
            },
            "conflict": {
                "status": conflict_intersection["status"],
                "reason": "ALLOWED_JURISDICTIONS_DISJOINT",
                "result": conflict_evaluation["result"],
                "override_authority": "none",
                "relaxation_authority": "none",
                "frontier_relaxation_refused": frontier_relaxation_refused,
            },
            "authority": {
                "admission_created_reservation": False,
                "binding_override_authority": "none",
                "binding_relaxation_authority": "none",
                "policy_provenance_count": len(
                    binding["policy_provenance"]
                ),
            },
            "completion": {
                "selected_route": "guild:f",
                "effective_backing": 60,
                "aggregate": aggregate["status"],
                "settlement": settlement["status"],
                "promise_rewritten": False,
            },
            "laws": [
                "POLICY A != POLICY B",
                "INTERSECTION != POLICY REWRITE",
                "CONFLICT != AUTOMATIC OVERRIDE",
                "MORE RESTRICTIVE != MORE AUTHORITATIVE",
                "NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS",
                "POLICY PROVENANCE MUST SURVIVE COMPOSITION",
            ],
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
