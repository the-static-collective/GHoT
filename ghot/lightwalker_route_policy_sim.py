#!/usr/bin/env python3
"""Experiment 051 — Route Selection / Failover Policy."""

from __future__ import annotations

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
    verify_reroute,
)
from lightwalker_federated_service import make_remote_capacity_proof
from lightwalker_guild_authorization import make_resource_proposal
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
    make_policy_bound_reroute,
    make_route_policy,
    select_route,
    verify_owner_admission_response,
    verify_route_policy,
    verify_route_selection,
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
    capability: str = "render.verified",
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
        metadata={"capability": capability},
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
        resource_ref="service:policy-routed-render-051",
        terms={
            "unit": "compute-minute",
            "quantity": 60,
            "capability": "render.verified",
        },
        evidence_policy="complete-policy-routed-service",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref="consideration:route-policy-051",
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
        worker_d = IdentityKey.load_or_create(
            root / "worker-d" / "body-p256.pem"
        )
        worker_e = IdentityKey.load_or_create(
            root / "worker-e" / "body-p256.pem"
        )
        customer = IdentityKey.load_or_create(
            root / "customer" / "body-p256.pem"
        )

        treasury_b, entry_b = source_treasury(
            guild_id="guild:b",
            steward=guild_b,
            suffix="051",
        )
        treasury_c, entry_c = source_treasury(
            guild_id="guild:c",
            steward=guild_c,
            suffix="051",
        )
        treasury_d, entry_d = source_treasury(
            guild_id="guild:d",
            steward=guild_d,
            suffix="051",
        )
        treasury_e, entry_e = source_treasury(
            guild_id="guild:e",
            steward=guild_e,
            suffix="051",
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

        policy = make_route_policy(
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
            max_failover_hops=2,
            created_at_cut=2,
        )
        assert verify_route_policy(promise, policy)
        assert policy["reservation_authority"] == "none"
        assert policy["execution_authority"] == "none"

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

        # B fails before consumption, opening the 050 reroute aperture.
        execution_b, final_b = store_b.execute_reserved(
            treasury_b,
            proposal_b,
            auth_b,
            reservation_b,
            executor=worker_b,
            observed_cut=4,
            simulate_success=False,
            error="simulation: preferred route B failed",
        )
        assert execution_b["success"] is False
        assert final_b["status"] == "RELEASED"

        # D's proof is still valid, but D has locally encumbered all 60 for
        # unrelated work after that proof was published.
        competing_proposal_d = make_resource_proposal(
            treasury_d,
            proposer=guild_d,
            resource_entry_id=entry_d["entry_id"],
            requested_quantity=60,
            requested_unit="compute-minute",
            purpose_ref="local:d-unrelated-priority-work",
            proposed_at_cut=4,
        )
        (
            competing_auth_d,
            competing_reservation_d,
        ) = store_d.reserve_and_authorize(
            treasury_d,
            competing_proposal_d,
            executor_particular=worker_d.particular(),
            authorized_at_cut=4,
            expires_after_cut=10,
        )
        assert competing_reservation_d["reserved_measure"]["quantity"] == 60

        candidates = [
            {"snapshot": treasury_b, "proof": proof_b},
            {"snapshot": treasury_d, "proof": proof_d},
            {"snapshot": treasury_e, "proof": proof_e},
        ]

        selection_d = select_route(
            promise,
            policy,
            candidates,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b"],
        )
        assert verify_route_selection(
            promise, policy, candidates, selection_d
        )
        assert selection_d["selection_status"] == "SELECTED"
        assert (
            selection_d["selected_candidate"]["capacity_guild_id"]
            == "guild:d"
        )
        assert selection_d["reservation_authority"] == "none"

        admission_d = make_owner_admission_response(
            selection_d,
            treasury_d,
            proof_d,
            reservation_store=store_d,
            steward=guild_d,
            observed_cut=5,
        )
        assert verify_owner_admission_response(
            selection_d, admission_d
        )
        assert admission_d["disposition"] == "REFUSED"
        assert (
            admission_d["reason"]
            == "INSUFFICIENT_UNENCUMBERED_CAPACITY"
        )
        assert admission_d["reservation_created"] is False

        guarantee_refused = refused(
            lambda: make_policy_bound_reroute(
                offer,
                acceptance,
                original_sources,
                promise,
                policy=policy,
                candidates=candidates,
                selection=selection_d,
                admission_response=admission_d,
                original_source_id=source_b["source_id"],
                original_snapshot=treasury_b,
                original_proof=proof_b,
                original_request=request_b,
                original_proposal=proposal_b,
                original_authorization=auth_b,
                original_reservation=reservation_b,
                original_grant=grant_b,
                original_finalization=final_b,
                substitute_snapshot=treasury_d,
                substitute_proof=proof_d,
                promisor=guild_a,
                rerouted_at_cut=5,
            )
        )
        assert guarantee_refused

        # Second policy evaluation excludes both failed B and owner-refused D.
        selection_e = select_route(
            promise,
            policy,
            candidates,
            evaluation_cut=5,
            excluded_guild_ids=["guild:b", "guild:d"],
            prior_selection_ids=[selection_d["selection_id"]],
        )
        assert verify_route_selection(
            promise, policy, candidates, selection_e
        )
        assert (
            selection_e["selected_candidate"]["capacity_guild_id"]
            == "guild:e"
        )
        assert selection_e["failover_index"] == 2

        admission_e = make_owner_admission_response(
            selection_e,
            treasury_e,
            proof_e,
            reservation_store=store_e,
            steward=guild_e,
            observed_cut=5,
        )
        assert verify_owner_admission_response(
            selection_e, admission_e
        )
        assert admission_e["disposition"] == "ADMITTABLE"
        assert admission_e["reservation_created"] is False

        reroute, binding = make_policy_bound_reroute(
            offer,
            acceptance,
            original_sources,
            promise,
            policy=policy,
            candidates=candidates,
            selection=selection_e,
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
        assert verify_reroute(
            promise, treasury_e, proof_e, reroute
        )
        assert binding["policy_id"] == policy["policy_id"]
        assert binding["selection_id"] == selection_e["selection_id"]
        assert (
            binding["owner_admission_response_id"]
            == admission_e["admission_response_id"]
        )
        assert binding["reservation_authority"] == "none"
        assert json.dumps(promise, sort_keys=True) == frozen_promise

        # Owner admission was still not a reservation.
        e_state_before_reservation = store_e.capacity_state(
            treasury_e, entry_e["entry_id"]
        )
        assert e_state_before_reservation["reserved_quantity"] == 0

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
        assert grant_b["grant_id"] not in backing["effective_grant_ids"]

        execution_c, final_c = store_c.execute_reserved(
            treasury_c,
            proposal_c,
            auth_c,
            reservation_c,
            executor=worker_c,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:051-c-success",
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
            result_ref="result:051-e-success",
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
        assert aggregate["performed_measure"]["quantity"] == 60

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
            evidence_ref="evidence:051-customer-review",
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

        # Policy depth is bounded; a third failover recommendation is refused.
        depth_refused = refused(
            lambda: select_route(
                promise,
                policy,
                candidates,
                evaluation_cut=5,
                excluded_guild_ids=["guild:b", "guild:d", "guild:e"],
                prior_selection_ids=[
                    selection_d["selection_id"],
                    selection_e["selection_id"],
                ],
            )
        )
        assert depth_refused

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "policy": {
                        "route_order": ["guild:b", "guild:d", "guild:e"],
                        "required_capability": "render.verified",
                        "max_proof_age_cuts": 4,
                        "max_failover_hops": 2,
                        "reservation_authority": "none",
                        "execution_authority": "none",
                    },
                    "first_selection": {
                        "selected": "guild:d",
                        "selection_status": selection_d["selection_status"],
                        "proof_was_eligible": True,
                        "owner_disposition": admission_d["disposition"],
                        "owner_reason": admission_d["reason"],
                        "selection_created_reservation": False,
                        "policy_guarantee_refused": guarantee_refused,
                    },
                    "second_selection": {
                        "selected": "guild:e",
                        "failover_index": selection_e["failover_index"],
                        "owner_disposition": admission_e["disposition"],
                        "admission_created_reservation": False,
                    },
                    "reroute": {
                        "selected_route_bound_to_reroute": True,
                        "policy_binding_id": binding["binding_id"],
                        "old_b_authority_counts": False,
                        "effective_backing": 60,
                        "promise_rewritten": False,
                    },
                    "completion": {
                        "guild_c_original": 30,
                        "guild_e_substitute": 30,
                        "aggregate": aggregate["status"],
                        "performed": 60,
                        "downstream_settlement": settlement["status"],
                    },
                    "bounds": {
                        "third_failover_refused": depth_refused,
                        "owner_local_admission_preserved": True,
                    },
                    "laws": [
                        "POLICY != AUTHORITY",
                        "RECOMMENDATION != RESERVATION",
                        "FAILOVER ORDER != GUARANTEE",
                        "SOURCE SELECTION MUST REMAIN EVIDENCE-BACKED",
                        "AUTOMATIC ROUTING MAY NOT ERASE OWNER-LOCAL ADMISSION",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
