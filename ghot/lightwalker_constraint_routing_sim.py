#!/usr/bin/env python3
"""Experiment 053 — Constraint-First Routing / Pareto Frontier."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_constraint_routing import (
    derive_pareto_frontier,
    evaluate_constraints,
    make_constraint_attestation,
    make_constraint_bound_reroute,
    make_constraint_policy,
    score_frontier,
    verify_constraint_attestation,
    verify_constraint_policy,
)
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
    verify_treasury_snapshot,
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
from lightwalker_route_policy import (
    make_owner_admission_response,
    make_route_policy,
)
from lightwalker_route_scoring import (
    make_route_measurement,
    make_scoring_policy,
    score_routes,
)
from relatte_identity import IdentityKey


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
        resource_ref="service:constraint-pareto-render-053",
        terms={
            "unit": "compute-minute",
            "quantity": 60,
            "capability": "render.verified",
        },
        evidence_policy="constraint-frontier-rerouted-completion",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref="consideration:constraint-pareto-053",
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
        guild_g = IdentityKey.load_or_create(root / "guild-g" / "body-p256.pem")

        worker_b = IdentityKey.load_or_create(root / "worker-b" / "body-p256.pem")
        worker_c = IdentityKey.load_or_create(root / "worker-c" / "body-p256.pem")
        worker_f = IdentityKey.load_or_create(root / "worker-f" / "body-p256.pem")
        customer = IdentityKey.load_or_create(root / "customer" / "body-p256.pem")
        route_probe = IdentityKey.load_or_create(
            root / "route-probe" / "body-p256.pem"
        )
        compliance_probe = IdentityKey.load_or_create(
            root / "compliance-probe" / "body-p256.pem"
        )

        treasury_b, entry_b = source_treasury(
            guild_id="guild:b", steward=guild_b, suffix="053"
        )
        treasury_c, entry_c = source_treasury(
            guild_id="guild:c", steward=guild_c, suffix="053"
        )
        treasury_d, entry_d = source_treasury(
            guild_id="guild:d", steward=guild_d, suffix="053"
        )
        treasury_e, entry_e = source_treasury(
            guild_id="guild:e", steward=guild_e, suffix="053"
        )
        treasury_f, entry_f = source_treasury(
            guild_id="guild:f", steward=guild_f, suffix="053"
        )
        treasury_g, entry_g = source_treasury(
            guild_id="guild:g", steward=guild_g, suffix="053"
        )
        for snapshot in (
            treasury_b,
            treasury_c,
            treasury_d,
            treasury_e,
            treasury_f,
            treasury_g,
        ):
            assert verify_treasury_snapshot(snapshot)

        proof_b = make_remote_capacity_proof(
            treasury_b,
            steward=guild_b,
            resource_entry_id=entry_b["entry_id"],
            observed_cut=1,
            valid_through_cut=10,
        )
        proof_c = make_remote_capacity_proof(
            treasury_c,
            steward=guild_c,
            resource_entry_id=entry_c["entry_id"],
            observed_cut=1,
            valid_through_cut=12,
        )
        proof_d = make_remote_capacity_proof(
            treasury_d,
            steward=guild_d,
            resource_entry_id=entry_d["entry_id"],
            observed_cut=4,
            valid_through_cut=12,
        )
        proof_e = make_remote_capacity_proof(
            treasury_e,
            steward=guild_e,
            resource_entry_id=entry_e["entry_id"],
            observed_cut=4,
            valid_through_cut=12,
        )
        proof_f = make_remote_capacity_proof(
            treasury_f,
            steward=guild_f,
            resource_entry_id=entry_f["entry_id"],
            observed_cut=3,
            valid_through_cut=14,
        )
        proof_g = make_remote_capacity_proof(
            treasury_g,
            steward=guild_g,
            resource_entry_id=entry_g["entry_id"],
            observed_cut=4,
            valid_through_cut=12,
        )

        original_sources = [
            {"snapshot": treasury_b, "proof": proof_b, "quantity": 30},
            {"snapshot": treasury_c, "proof": proof_c, "quantity": 30},
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
                "guild:g",
            ],
            required_capability="render.verified",
            max_proof_age_cuts=4,
            max_failover_hops=4,
            created_at_cut=2,
        )

        measurements = [
            make_route_measurement(
                treasury_d,
                proof_d,
                measurer=route_probe,
                latency_ms=1,
                reliability_ppm=1_000_000,
                energy_mwh_per_compute_minute=1,
                expected_completion_cuts=1,
                observed_cut=5,
            ),
            make_route_measurement(
                treasury_e,
                proof_e,
                measurer=route_probe,
                latency_ms=15,
                reliability_ppm=980_000,
                energy_mwh_per_compute_minute=60,
                expected_completion_cuts=2,
                observed_cut=5,
            ),
            make_route_measurement(
                treasury_f,
                proof_f,
                measurer=route_probe,
                latency_ms=30,
                reliability_ppm=999_000,
                energy_mwh_per_compute_minute=10,
                expected_completion_cuts=3,
                observed_cut=5,
            ),
            make_route_measurement(
                treasury_g,
                proof_g,
                measurer=route_probe,
                latency_ms=40,
                reliability_ppm=970_000,
                energy_mwh_per_compute_minute=80,
                expected_completion_cuts=4,
                observed_cut=5,
            ),
        ]

        candidates = [
            {"snapshot": treasury_b, "proof": proof_b},
            {"snapshot": treasury_d, "proof": proof_d},
            {"snapshot": treasury_e, "proof": proof_e},
            {"snapshot": treasury_f, "proof": proof_f},
            {"snapshot": treasury_g, "proof": proof_g},
        ]

        speed_policy = make_scoring_policy(
            promise,
            route_policy,
            promisor=guild_a,
            trusted_measurer_particular=route_probe.particular(),
            profile_name="latency-first",
            weights={
                "freshness": 1,
                "quantity_headroom": 0,
                "reliability": 1,
                "latency": 50,
                "energy": 1,
                "completion_window": 5,
            },
            max_measurement_age_cuts=2,
            created_at_cut=5,
        )
        efficiency_policy = make_scoring_policy(
            promise,
            route_policy,
            promisor=guild_a,
            trusted_measurer_particular=route_probe.particular(),
            profile_name="reliability-energy",
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

        # Without hard constraints, D's extreme performance dominates the
        # latency-first local preference.
        unrestricted = score_routes(
            promise,
            route_policy,
            speed_policy,
            candidates,
            measurements,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b"],
        )
        assert (
            unrestricted["selected_candidate"]["capacity_guild_id"]
            == "guild:d"
        )

        attestations = [
            make_constraint_attestation(
                treasury_d,
                proof_d,
                assessor=compliance_probe,
                jurisdiction="zone:blocked",
                privacy_class=1,
                renewable_evidence_present=False,
                sovereign_group="group:d",
                observed_cut=5,
            ),
            make_constraint_attestation(
                treasury_e,
                proof_e,
                assessor=compliance_probe,
                jurisdiction="zone:a",
                privacy_class=4,
                renewable_evidence_present=True,
                sovereign_group="group:e",
                observed_cut=5,
            ),
            make_constraint_attestation(
                treasury_f,
                proof_f,
                assessor=compliance_probe,
                jurisdiction="zone:b",
                privacy_class=5,
                renewable_evidence_present=True,
                sovereign_group="group:f",
                observed_cut=5,
            ),
            make_constraint_attestation(
                treasury_g,
                proof_g,
                assessor=compliance_probe,
                jurisdiction="zone:a",
                privacy_class=4,
                renewable_evidence_present=True,
                sovereign_group="group:g",
                observed_cut=5,
            ),
        ]
        for snapshot, proof, attestation in (
            (treasury_d, proof_d, attestations[0]),
            (treasury_e, proof_e, attestations[1]),
            (treasury_f, proof_f, attestations[2]),
            (treasury_g, proof_g, attestations[3]),
        ):
            assert verify_constraint_attestation(
                snapshot, proof, attestation
            )

        constraint_policy = make_constraint_policy(
            promise,
            route_policy,
            promisor=guild_a,
            trusted_assessor_particular=compliance_probe.particular(),
            trusted_measurer_particular=route_probe.particular(),
            allowed_jurisdictions=["zone:a", "zone:b"],
            min_privacy_class=3,
            require_renewable_evidence=True,
            max_expected_completion_cuts=4,
            forbidden_sovereign_groups=["group:forbidden"],
            max_attestation_age_cuts=2,
            created_at_cut=5,
        )
        assert verify_constraint_policy(
            promise, route_policy, constraint_policy
        )

        constrained = evaluate_constraints(
            promise,
            route_policy,
            constraint_policy,
            candidates,
            measurements,
            attestations,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b"],
        )
        rows = {
            row["capacity_guild_id"]: row
            for row in constrained["candidate_rows"]
        }
        assert rows["guild:d"]["constraint_status"] == "INELIGIBLE"
        assert "JURISDICTION_NOT_ALLOWED" in rows["guild:d"][
            "constraint_failures"
        ]
        assert "PRIVACY_CLASS_TOO_LOW" in rows["guild:d"][
            "constraint_failures"
        ]
        assert "RENEWABLE_EVIDENCE_REQUIRED" in rows["guild:d"][
            "constraint_failures"
        ]
        assert rows["guild:d"]["local_score"] is None
        assert rows["guild:e"]["constraint_status"] == "ELIGIBLE"
        assert rows["guild:f"]["constraint_status"] == "ELIGIBLE"
        assert rows["guild:g"]["constraint_status"] == "ELIGIBLE"
        assert constrained["winner"] is None

        frontier = derive_pareto_frontier(constrained)
        frontier_guilds = {
            row["capacity_guild_id"] for row in frontier["frontier"]
        }
        dominated_guilds = {
            row["capacity_guild_id"] for row in frontier["dominated"]
        }
        assert frontier_guilds == {"guild:e", "guild:f"}
        assert "guild:g" in dominated_guilds
        assert frontier["winner"] is None
        assert frontier["local_score"] is None

        frontier_speed = score_frontier(
            promise,
            route_policy,
            speed_policy,
            constrained,
            frontier,
            candidates,
            measurements,
            evaluation_cut=5,
        )
        frontier_efficiency = score_frontier(
            promise,
            route_policy,
            efficiency_policy,
            constrained,
            frontier,
            candidates,
            measurements,
            evaluation_cut=5,
        )
        assert (
            frontier_speed["selected_candidate"]["capacity_guild_id"]
            == "guild:e"
        )
        assert (
            frontier_efficiency["selected_candidate"]["capacity_guild_id"]
            == "guild:f"
        )
        assert frontier_speed["frontier_only"] is True
        assert frontier_efficiency["frontier_only"] is True

        # Create the original operational failure and retain C's reservation.
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
            treasury_b,
            proof_b,
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
            treasury_c,
            proof_c,
            request_c,
            capacity_steward=guild_c,
            executor_particular=worker_c.particular(),
            reservation_store=store_c,
            reserved_at_cut=3,
            expires_after_cut=9,
        )
        execution_b, final_b = store_b.execute_reserved(
            treasury_b,
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

        # F is selected only after hard constraints and Pareto filtering.
        admission_f = make_owner_admission_response(
            frontier_efficiency,
            treasury_f,
            proof_f,
            reservation_store=store_f,
            steward=guild_f,
            observed_cut=5,
        )
        assert admission_f["disposition"] == "ADMITTABLE"
        assert admission_f["reservation_created"] is False

        reroute, binding = make_constraint_bound_reroute(
            offer,
            acceptance,
            original_sources,
            promise,
            route_policy=route_policy,
            scoring_policy=efficiency_policy,
            constraint_evaluation=constrained,
            frontier=frontier,
            candidates=candidates,
            measurements=measurements,
            selection=frontier_efficiency,
            admission_response=admission_f,
            original_source_id=source_b["source_id"],
            original_snapshot=treasury_b,
            original_proof=proof_b,
            original_request=request_b,
            original_proposal=proposal_b,
            original_authorization=auth_b,
            original_reservation=reservation_b,
            original_grant=grant_b,
            original_finalization=final_b,
            substitute_snapshot=treasury_f,
            substitute_proof=proof_f,
            promisor=guild_a,
            rerouted_at_cut=5,
        )
        assert binding["selected_capacity_guild_id"] == "guild:f"
        assert binding["constraint_override_authority"] == "none"
        assert binding["reservation_authority"] == "none"
        assert json.dumps(promise, sort_keys=True) == frozen_promise

        substitute_request = make_substitute_request(
            offer,
            acceptance,
            promise,
            treasury_f,
            proof_f,
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
            treasury_f,
            proof_f,
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
            treasury_c,
            proposal_c,
            auth_c,
            reservation_c,
            executor=worker_c,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:053-c-success",
        )
        completion_c = make_source_completion(
            treasury_c,
            proof_c,
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
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            executor=worker_f,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:053-f-success",
        )
        completion_f = make_substitute_completion(
            treasury_f,
            proof_f,
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
            evidence_ref="evidence:053-customer-review",
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

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "unrestricted_scoring": {
                        "selected": "guild:d",
                        "meaning": "would win if hard constraints were treated as soft preferences",
                    },
                    "constraint_first": {
                        "guild_d_status": rows["guild:d"]["constraint_status"],
                        "guild_d_failures": rows["guild:d"]["constraint_failures"],
                        "guild_d_score": rows["guild:d"]["local_score"],
                        "eligible": ["guild:e", "guild:f", "guild:g"],
                        "winner": None,
                    },
                    "pareto": {
                        "frontier": sorted(frontier_guilds),
                        "dominated": sorted(dominated_guilds),
                        "winner": frontier["winner"],
                        "local_score": frontier["local_score"],
                    },
                    "local_preferences_after_frontier": {
                        "latency_first_selected": "guild:e",
                        "reliability_energy_selected": "guild:f",
                    },
                    "authority": {
                        "f_admission_created_reservation": False,
                        "constraint_override_authority": "none",
                        "reroute_reservation_authority": "none",
                    },
                    "completion": {
                        "selected_route": "guild:f",
                        "effective_backing": 60,
                        "aggregate": aggregate["status"],
                        "downstream_settlement": settlement["status"],
                        "promise_rewritten": False,
                    },
                    "laws": [
                        "CONSTRAINT != PREFERENCE",
                        "INELIGIBLE != LOW SCORE",
                        "PARETO FRONTIER != WINNER",
                        "TRADEOFF != COLLAPSE",
                        "LOCAL POLICY != UNIVERSAL OPTIMUM",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
