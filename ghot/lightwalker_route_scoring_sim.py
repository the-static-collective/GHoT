#!/usr/bin/env python3
"""Experiment 052 — Route Scoring / Multi-Factor Selection."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

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
    make_scored_policy_bound_reroute,
    make_scoring_policy,
    score_routes,
    verify_route_measurement,
    verify_scored_selection,
    verify_scoring_policy,
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
        resource_ref="service:scored-route-render-052",
        terms={
            "unit": "compute-minute",
            "quantity": 60,
            "capability": "render.verified",
        },
        evidence_policy="complete-scored-rerouted-service",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref="consideration:route-score-052",
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
        valid_through_cut=18,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild_a = IdentityKey.load_or_create(
            root / "guild-a" / "body-p256.pem"
        )
        guild_b = IdentityKey.load_or_create(
            root / "guild-b" / "body-p256.pem"
        )
        guild_c = IdentityKey.load_or_create(
            root / "guild-c" / "body-p256.pem"
        )
        guild_d = IdentityKey.load_or_create(
            root / "guild-d" / "body-p256.pem"
        )
        guild_e = IdentityKey.load_or_create(
            root / "guild-e" / "body-p256.pem"
        )
        worker_b = IdentityKey.load_or_create(
            root / "worker-b" / "body-p256.pem"
        )
        worker_c = IdentityKey.load_or_create(
            root / "worker-c" / "body-p256.pem"
        )
        worker_e = IdentityKey.load_or_create(
            root / "worker-e" / "body-p256.pem"
        )
        customer = IdentityKey.load_or_create(
            root / "customer" / "body-p256.pem"
        )
        probe = IdentityKey.load_or_create(
            root / "route-probe" / "body-p256.pem"
        )
        untrusted_probe = IdentityKey.load_or_create(
            root / "untrusted-probe" / "body-p256.pem"
        )

        treasury_b, entry_b = source_treasury(
            guild_id="guild:b",
            steward=guild_b,
            suffix="052",
        )
        treasury_c, entry_c = source_treasury(
            guild_id="guild:c",
            steward=guild_c,
            suffix="052",
        )
        treasury_d, entry_d = source_treasury(
            guild_id="guild:d",
            steward=guild_d,
            suffix="052",
        )
        treasury_e, entry_e = source_treasury(
            guild_id="guild:e",
            steward=guild_e,
            suffix="052",
        )
        for snapshot in (
            treasury_b,
            treasury_c,
            treasury_d,
            treasury_e,
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
            observed_cut=2,
            valid_through_cut=14,
        )

        original_sources = [
            {
                "snapshot": treasury_b,
                "proof": proof_b,
                "quantity": 30,
            },
            {
                "snapshot": treasury_c,
                "proof": proof_c,
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
                "guild:d",
                "guild:e",
            ],
            required_capability="render.verified",
            max_proof_age_cuts=4,
            max_failover_hops=3,
            created_at_cut=2,
        )

        measurement_d = make_route_measurement(
            treasury_d,
            proof_d,
            measurer=probe,
            latency_ms=10,
            reliability_ppm=970_000,
            energy_mwh_per_compute_minute=80,
            expected_completion_cuts=2,
            observed_cut=5,
        )
        measurement_e = make_route_measurement(
            treasury_e,
            proof_e,
            measurer=probe,
            latency_ms=35,
            reliability_ppm=999_000,
            energy_mwh_per_compute_minute=20,
            expected_completion_cuts=3,
            observed_cut=5,
        )
        assert verify_route_measurement(
            treasury_d, proof_d, measurement_d
        )
        assert verify_route_measurement(
            treasury_e, proof_e, measurement_e
        )
        measurements = [measurement_d, measurement_e]

        speed_policy = make_scoring_policy(
            promise,
            route_policy,
            promisor=guild_a,
            trusted_measurer_particular=probe.particular(),
            profile_name="speed-first",
            weights={
                "freshness": 10,
                "quantity_headroom": 0,
                "reliability": 1,
                "latency": 20,
                "energy": 0,
                "completion_window": 0,
            },
            max_measurement_age_cuts=2,
            created_at_cut=5,
        )
        efficiency_policy = make_scoring_policy(
            promise,
            route_policy,
            promisor=guild_a,
            trusted_measurer_particular=probe.particular(),
            profile_name="efficiency-reliability",
            weights={
                "freshness": 1,
                "quantity_headroom": 0,
                "reliability": 2,
                "latency": 1,
                "energy": 10,
                "completion_window": 1,
            },
            max_measurement_age_cuts=2,
            created_at_cut=5,
        )
        assert verify_scoring_policy(
            promise, route_policy, speed_policy
        )
        assert verify_scoring_policy(
            promise, route_policy, efficiency_policy
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
            root / "reservations-b",
            steward=guild_b,
        )
        store_c = GuildReservationStore(
            root / "reservations-c",
            steward=guild_c,
        )
        store_d = GuildReservationStore(
            root / "reservations-d",
            steward=guild_d,
        )
        store_e = GuildReservationStore(
            root / "reservations-e",
            steward=guild_e,
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

        candidates = [
            {"snapshot": treasury_b, "proof": proof_b},
            {"snapshot": treasury_d, "proof": proof_d},
            {"snapshot": treasury_e, "proof": proof_e},
        ]

        speed_selection = score_routes(
            promise,
            route_policy,
            speed_policy,
            candidates,
            measurements,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b"],
        )
        efficiency_selection = score_routes(
            promise,
            route_policy,
            efficiency_policy,
            candidates,
            measurements,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b"],
        )
        assert verify_scored_selection(
            promise,
            route_policy,
            speed_policy,
            candidates,
            measurements,
            speed_selection,
        )
        assert verify_scored_selection(
            promise,
            route_policy,
            efficiency_policy,
            candidates,
            measurements,
            efficiency_selection,
        )
        assert (
            speed_selection["selected_candidate"]["capacity_guild_id"]
            == "guild:d"
        )
        assert (
            efficiency_selection["selected_candidate"]["capacity_guild_id"]
            == "guild:e"
        )
        assert speed_selection["reservation_authority"] == "none"
        assert efficiency_selection["value_authority"] == "none"

        speed_scores = {
            row["capacity_guild_id"]: row["local_score"]
            for row in speed_selection["candidate_rows"]
            if row["score_eligible"]
        }
        efficiency_scores = {
            row["capacity_guild_id"]: row["local_score"]
            for row in efficiency_selection["candidate_rows"]
            if row["score_eligible"]
        }
        assert speed_scores["guild:d"] > speed_scores["guild:e"]
        assert efficiency_scores["guild:e"] > efficiency_scores["guild:d"]

        # The same raw measurements have not changed.
        assert measurement_d["score"] is None
        assert measurement_e["score"] is None

        # A score still creates no remote reservation. D may admit the route,
        # but A is free not to act on that recommendation.
        admission_d = make_owner_admission_response(
            speed_selection,
            treasury_d,
            proof_d,
            reservation_store=store_d,
            steward=guild_d,
            observed_cut=5,
        )
        assert admission_d["disposition"] == "ADMITTABLE"
        assert admission_d["reservation_created"] is False
        d_state = store_d.capacity_state(
            treasury_d, entry_d["entry_id"]
        )
        assert d_state["reserved_quantity"] == 0

        # Preference tampering and untrusted measurement evidence are refused.
        tampered = copy.deepcopy(measurement_d)
        tampered["metrics"]["latency_ms"] = 1
        tampered_measurement_refused = refused(
            lambda: score_routes(
                promise,
                route_policy,
                speed_policy,
                candidates,
                [tampered, measurement_e],
                evaluation_cut=5,
                excluded_guild_ids=["guild:b"],
            )
        )
        assert tampered_measurement_refused

        untrusted_measurement_e = make_route_measurement(
            treasury_e,
            proof_e,
            measurer=untrusted_probe,
            latency_ms=35,
            reliability_ppm=999_000,
            energy_mwh_per_compute_minute=20,
            expected_completion_cuts=3,
            observed_cut=5,
        )
        untrusted_measurement_refused = refused(
            lambda: score_routes(
                promise,
                route_policy,
                efficiency_policy,
                candidates,
                [measurement_d, untrusted_measurement_e],
                evaluation_cut=5,
                excluded_guild_ids=["guild:b"],
            )
        )
        assert untrusted_measurement_refused

        # Act on the efficiency policy's E recommendation.
        admission_e = make_owner_admission_response(
            efficiency_selection,
            treasury_e,
            proof_e,
            reservation_store=store_e,
            steward=guild_e,
            observed_cut=5,
        )
        assert admission_e["disposition"] == "ADMITTABLE"
        assert admission_e["reservation_created"] is False

        reroute, binding = make_scored_policy_bound_reroute(
            offer,
            acceptance,
            original_sources,
            promise,
            route_policy=route_policy,
            scoring_policy=efficiency_policy,
            candidates=candidates,
            measurements=measurements,
            selection=efficiency_selection,
            admission_response=admission_e,
            original_source_id=source_b["source_id"],
            original_snapshot=treasury_b,
            original_proof=proof_b,
            original_request=request_b,
            original_proposal=proposal_b,
            original_authorization=auth_b,
            original_reservation=reservation_b,
            original_grant=grant_b,
            original_finalization=final_b,
            substitute_snapshot=treasury_e,
            substitute_proof=proof_e,
            promisor=guild_a,
            rerouted_at_cut=5,
        )
        assert binding["selected_capacity_guild_id"] == "guild:e"
        assert binding["value_authority"] == "none"
        assert binding["reservation_authority"] == "none"
        assert json.dumps(promise, sort_keys=True) == frozen_promise

        substitute_request = make_substitute_request(
            offer,
            acceptance,
            promise,
            treasury_e,
            proof_e,
            reroute,
            promisor=guild_a,
            requested_at_cut=6,
        )
        (
            proposal_e,
            auth_e,
            reservation_e,
            grant_e,
        ) = reserve_substitute(
            treasury_e,
            proof_e,
            reroute,
            substitute_request,
            capacity_steward=guild_e,
            executor_particular=worker_e.particular(),
            reservation_store=store_e,
            reserved_at_cut=6,
            expires_after_cut=12,
        )
        backing = derive_rerouted_backing(
            promise,
            original_grants=[grant_b, grant_c],
            reroutes=[reroute],
            substitute_grants=[grant_e],
        )
        assert backing["status"] == "COMPLETE"
        assert backing["reserved_measure"]["quantity"] == 60

        execution_c, final_c = store_c.execute_reserved(
            treasury_c,
            proposal_c,
            auth_c,
            reservation_c,
            executor=worker_c,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:052-c-success",
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
        execution_e, final_e = store_e.execute_reserved(
            treasury_e,
            proposal_e,
            auth_e,
            reservation_e,
            executor=worker_e,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:052-e-success",
        )
        completion_e = make_substitute_completion(
            treasury_e,
            proof_e,
            reroute,
            substitute_request,
            proposal_e,
            auth_e,
            reservation_e,
            grant_e,
            execution_e,
            final_e,
            capacity_steward=guild_e,
        )
        aggregate = derive_rerouted_completion(
            promise,
            original_completions=[completion_c],
            reroutes=[reroute],
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
            evidence_ref="evidence:052-customer-review",
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
        assert witness["promise_rewritten"] is False

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "same_measurements": {
                        "guild_d": measurement_d["metrics"],
                        "guild_e": measurement_e["metrics"],
                        "measurements_contain_score": False,
                    },
                    "speed_profile": {
                        "weights": speed_policy["weights"],
                        "scores": speed_scores,
                        "selected": "guild:d",
                    },
                    "efficiency_profile": {
                        "weights": efficiency_policy["weights"],
                        "scores": efficiency_scores,
                        "selected": "guild:e",
                    },
                    "authority": {
                        "d_score_created_reservation": False,
                        "d_owner_disposition": admission_d["disposition"],
                        "e_owner_disposition": admission_e["disposition"],
                        "scored_binding_value_authority": "none",
                        "scored_binding_reservation_authority": "none",
                    },
                    "hostile_controls": {
                        "tampered_measurement_refused": (
                            tampered_measurement_refused
                        ),
                        "untrusted_measurement_refused": (
                            untrusted_measurement_refused
                        ),
                    },
                    "completion": {
                        "selected_route": "guild:e",
                        "effective_backing": 60,
                        "aggregate": aggregate["status"],
                        "downstream_settlement": settlement["status"],
                        "promise_rewritten": False,
                    },
                    "laws": [
                        "SCORE != VALUE",
                        "SCORE != AUTHORITY",
                        "MEASUREMENT != PREFERENCE",
                        "PREFERENCE != ADMISSION",
                        "LOWER COST != UNIVERSALLY BETTER",
                        "POLICY WEIGHTS ARE LOCAL",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
