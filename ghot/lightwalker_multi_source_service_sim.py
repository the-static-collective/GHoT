#!/usr/bin/env python3
"""Experiment 049 — Multi-Source Federated Service."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError
from lightwalker_federated_service import make_remote_capacity_proof
from lightwalker_guild_authorization import apply_execution_to_treasury
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
    attest_multi_source_performance,
    derive_backing_view,
    derive_multi_source_completion,
    derive_multi_source_settlement,
    make_multi_source_crossing,
    make_multi_source_promise,
    make_source_completion,
    make_source_failure,
    make_source_request,
    reserve_source,
    verify_multi_source_promise,
    verify_source_grant,
    verify_source_request,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def customer_offer(
    *,
    promisor: IdentityKey,
    customer: IdentityKey,
    quantity: int,
    suffix: str,
) -> dict:
    service = make_obligation(
        obligation_type="future-compute-service",
        resource_ref=f"service:multi-source-{suffix}",
        terms={
            "unit": "compute-minute",
            "quantity": quantity,
            "capability": "render.verified",
        },
        evidence_policy="all-required-source-completions",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref=f"consideration:multi-source-{suffix}",
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
        valid_through_cut=14,
    )


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


def parcel_cross(
    *,
    root: Path,
    name: str,
    evidence: dict,
    crossing: dict,
    receiver: StateParcelInbox,
) -> tuple[dict, dict]:
    source = root / f"source-{name}"
    payload = source / f"{name}.json"
    source.mkdir(parents=True, exist_ok=True)
    payload.write_text(
        json.dumps(
            {"evidence": evidence, "crossing": crossing},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    bundle = StateParcelExporter(source).export(
        str(payload.relative_to(source)),
        selector="$",
        target_particular=receiver.signer.particular(),
    )
    held = receiver.receive(bundle)
    admitted = receiver.decide(
        bundle["parcel"]["parcel_id"],
        "ADMIT",
        note=f"049 admit {name} as multi-source evidence only",
    )
    return held, admitted


def make_sources(
    snapshot_b: dict,
    proof_b: dict,
    snapshot_c: dict,
    proof_c: dict,
    *,
    quantity: int,
) -> list[dict]:
    return [
        {
            "snapshot": snapshot_b,
            "proof": proof_b,
            "quantity": quantity,
        },
        {
            "snapshot": snapshot_c,
            "proof": proof_c,
            "quantity": quantity,
        },
    ]


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
        worker_b = IdentityKey.load_or_create(
            root / "worker-b" / "body-p256.pem"
        )
        worker_c = IdentityKey.load_or_create(
            root / "worker-c" / "body-p256.pem"
        )
        customer_ok = IdentityKey.load_or_create(
            root / "customer-ok" / "body-p256.pem"
        )
        customer_fail = IdentityKey.load_or_create(
            root / "customer-fail" / "body-p256.pem"
        )

        inbox_b = StateParcelInbox(root / "inbox-b")
        inbox_c = StateParcelInbox(root / "inbox-c")
        inbox_a = StateParcelInbox(root / "inbox-a")
        observer = StateParcelInbox(root / "observer")

        treasury_b0, entry_b0 = source_treasury(
            guild_id="guild:b",
            steward=guild_b,
            suffix="049",
        )
        treasury_c0, entry_c0 = source_treasury(
            guild_id="guild:c",
            steward=guild_c,
            suffix="049",
        )
        assert verify_treasury_snapshot(treasury_b0)
        assert verify_treasury_snapshot(treasury_c0)

        proof_b0 = make_remote_capacity_proof(
            treasury_b0,
            steward=guild_b,
            resource_entry_id=entry_b0["entry_id"],
            observed_cut=1,
            valid_through_cut=10,
        )
        proof_c0 = make_remote_capacity_proof(
            treasury_c0,
            steward=guild_c,
            resource_entry_id=entry_c0["entry_id"],
            observed_cut=1,
            valid_through_cut=10,
        )
        sources0 = make_sources(
            treasury_b0,
            proof_b0,
            treasury_c0,
            proof_c0,
            quantity=30,
        )

        # SUCCESS PATH -----------------------------------------------------
        offer_ok = customer_offer(
            promisor=guild_a,
            customer=customer_ok,
            quantity=60,
            suffix="success",
        )
        promise_ok = make_multi_source_promise(
            offer_ok,
            sources0,
            promisor=guild_a,
            promised_at_cut=2,
        )
        assert verify_multi_source_promise(
            offer_ok, sources0, promise_ok
        )
        assert promise_ok["promised_measure"]["quantity"] == 60
        assert len(promise_ok["sources"]) == 2
        assert promise_ok["full_backing_proven"] is False
        assert promise_ok["ownership_aggregated"] is False

        wrong_sum_refused = refused(
            lambda: make_multi_source_promise(
                offer_ok,
                make_sources(
                    treasury_b0,
                    proof_b0,
                    treasury_c0,
                    proof_c0,
                    quantity=20,
                ),
                promisor=guild_a,
                promised_at_cut=2,
            )
        )
        assert wrong_sum_refused

        acceptance_ok = accept_exchange_offer(
            offer_ok,
            acceptor_particular=customer_ok.particular(),
            accepted_at_cut=2,
        )

        source_b = next(
            row
            for row in promise_ok["sources"]
            if row["capacity_guild_id"] == "guild:b"
        )
        source_c = next(
            row
            for row in promise_ok["sources"]
            if row["capacity_guild_id"] == "guild:c"
        )

        request_b = make_source_request(
            offer_ok,
            acceptance_ok,
            sources0,
            promise_ok,
            source_id=source_b["source_id"],
            promisor=guild_a,
            requested_at_cut=3,
        )
        request_c = make_source_request(
            offer_ok,
            acceptance_ok,
            sources0,
            promise_ok,
            source_id=source_c["source_id"],
            promisor=guild_a,
            requested_at_cut=3,
        )
        assert verify_source_request(
            offer_ok, acceptance_ok, sources0, promise_ok, request_b
        )
        assert verify_source_request(
            offer_ok, acceptance_ok, sources0, promise_ok, request_c
        )

        request_b_crossing = make_multi_source_crossing(
            request_b,
            signer=guild_a,
            declared_kind="LIGHTWALKER_MULTI_SOURCE_REQUEST",
            destination_particular=guild_b.particular(),
        )
        request_c_crossing = make_multi_source_crossing(
            request_c,
            signer=guild_a,
            declared_kind="LIGHTWALKER_MULTI_SOURCE_REQUEST",
            destination_particular=guild_c.particular(),
        )
        held_request_b, admitted_request_b = parcel_cross(
            root=root,
            name="request-b",
            evidence=request_b,
            crossing=request_b_crossing,
            receiver=inbox_b,
        )
        held_request_c, admitted_request_c = parcel_cross(
            root=root,
            name="request-c",
            evidence=request_c,
            crossing=request_c_crossing,
            receiver=inbox_c,
        )
        assert held_request_b["kind"] == "HELD"
        assert admitted_request_b["kind"] == "ADMITTED"
        assert held_request_c["kind"] == "HELD"
        assert admitted_request_c["kind"] == "ADMITTED"

        store_b = GuildReservationStore(
            root / "reservations-b",
            steward=guild_b,
        )
        store_c = GuildReservationStore(
            root / "reservations-c",
            steward=guild_c,
        )

        proposal_b, auth_b, reservation_b, grant_b = reserve_source(
            treasury_b0,
            proof_b0,
            request_b,
            capacity_steward=guild_b,
            executor_particular=worker_b.particular(),
            reservation_store=store_b,
            reserved_at_cut=3,
            expires_after_cut=8,
        )
        assert verify_source_grant(
            treasury_b0,
            proof_b0,
            request_b,
            proposal_b,
            auth_b,
            reservation_b,
            grant_b,
        )

        partial_backing = derive_backing_view(
            promise_ok, [grant_b]
        )
        assert partial_backing["status"] == "PARTIAL"
        assert partial_backing["reserved_measure"]["quantity"] == 30
        assert len(partial_backing["missing_source_ids"]) == 1

        proposal_c, auth_c, reservation_c, grant_c = reserve_source(
            treasury_c0,
            proof_c0,
            request_c,
            capacity_steward=guild_c,
            executor_particular=worker_c.particular(),
            reservation_store=store_c,
            reserved_at_cut=3,
            expires_after_cut=8,
        )
        assert verify_source_grant(
            treasury_c0,
            proof_c0,
            request_c,
            proposal_c,
            auth_c,
            reservation_c,
            grant_c,
        )

        complete_backing = derive_backing_view(
            promise_ok, [grant_b, grant_c]
        )
        assert complete_backing["status"] == "COMPLETE"
        assert complete_backing["reserved_measure"]["quantity"] == 60
        assert complete_backing["ownership_aggregated"] is False

        execution_b, final_b = store_b.execute_reserved(
            treasury_b0,
            proposal_b,
            auth_b,
            reservation_b,
            executor=worker_b,
            observed_cut=4,
            simulate_success=True,
            result_ref="result:multi-source-b-success",
        )
        completion_b = make_source_completion(
            treasury_b0,
            proof_b0,
            request_b,
            proposal_b,
            auth_b,
            reservation_b,
            grant_b,
            execution_b,
            final_b,
            capacity_steward=guild_b,
        )

        partial_completion = derive_multi_source_completion(
            promise_ok, [completion_b]
        )
        assert partial_completion["status"] == "PARTIAL"
        assert partial_completion["performed_measure"]["quantity"] == 30

        partial_performance_refused = refused(
            lambda: attest_multi_source_performance(
                offer_ok,
                acceptance_ok,
                sources0,
                promise_ok,
                partial_completion,
                promisor=guild_a,
            )
        )
        assert partial_performance_refused

        execution_c, final_c = store_c.execute_reserved(
            treasury_c0,
            proposal_c,
            auth_c,
            reservation_c,
            executor=worker_c,
            observed_cut=4,
            simulate_success=True,
            result_ref="result:multi-source-c-success",
        )
        completion_c = make_source_completion(
            treasury_c0,
            proof_c0,
            request_c,
            proposal_c,
            auth_c,
            reservation_c,
            grant_c,
            execution_c,
            final_c,
            capacity_steward=guild_c,
        )

        aggregate_ok = derive_multi_source_completion(
            promise_ok, [completion_b, completion_c]
        )
        assert aggregate_ok["status"] == "COMPLETE"
        assert aggregate_ok["performed_measure"]["quantity"] == 60
        assert aggregate_ok["ownership_aggregated"] is False

        promisor_perf_ok = attest_multi_source_performance(
            offer_ok,
            acceptance_ok,
            sources0,
            promise_ok,
            aggregate_ok,
            promisor=guild_a,
        )
        assert promisor_perf_ok["evidence_ref"] == aggregate_ok["aggregate_id"]

        customer_perf_ok = sign_obligation_performance(
            offer_ok,
            acceptance_ok,
            role="ACCEPTOR",
            signer=customer_ok,
            evidence_ref="evidence:customer-ok-multi-source",
        )
        settlement_ok = settle_exchange(
            offer_ok,
            acceptance_ok,
            [promisor_perf_ok, customer_perf_ok],
        )
        witness_ok = derive_multi_source_settlement(
            offer_ok,
            acceptance_ok,
            promise_ok,
            aggregate_ok,
            promisor_perf_ok,
            customer_perf_ok,
            settlement_ok,
        )
        assert witness_ok["customer_service_performed"] is True
        assert witness_ok["source_ownership_aggregated"] is False
        assert (
            witness_ok["promisor_remote_execution_authority"]
            is False
        )

        witness_crossing = make_multi_source_crossing(
            witness_ok,
            signer=guild_a,
            declared_kind="LIGHTWALKER_MULTI_SOURCE_SETTLEMENT",
            destination_particular=observer.signer.particular(),
        )
        held_witness, admitted_witness = parcel_cross(
            root=root,
            name="multi-source-witness",
            evidence=witness_ok,
            crossing=witness_crossing,
            receiver=observer,
        )
        assert held_witness["kind"] == "HELD"
        assert admitted_witness["kind"] == "ADMITTED"

        # Success consumes 30 from each sovereign source independently.
        treasury_b1 = apply_execution_to_treasury(
            treasury_b0,
            proposal_b,
            auth_b,
            execution_b,
            steward=guild_b,
        )
        treasury_c1 = apply_execution_to_treasury(
            treasury_c0,
            proposal_c,
            auth_c,
            execution_c,
            steward=guild_c,
        )
        entry_b1 = next(
            item
            for item in treasury_b1["entries"]
            if item["category"] == "capability"
            and item["position"] == "available"
        )
        entry_c1 = next(
            item
            for item in treasury_c1["entries"]
            if item["category"] == "capability"
            and item["position"] == "available"
        )
        assert entry_b1["native_measure"]["quantity"] == 30
        assert entry_c1["native_measure"]["quantity"] == 30

        # FAILURE PATH -----------------------------------------------------
        proof_b1 = make_remote_capacity_proof(
            treasury_b1,
            steward=guild_b,
            resource_entry_id=entry_b1["entry_id"],
            observed_cut=5,
            valid_through_cut=12,
        )
        proof_c1 = make_remote_capacity_proof(
            treasury_c1,
            steward=guild_c,
            resource_entry_id=entry_c1["entry_id"],
            observed_cut=5,
            valid_through_cut=12,
        )
        sources1 = make_sources(
            treasury_b1,
            proof_b1,
            treasury_c1,
            proof_c1,
            quantity=30,
        )
        offer_fail = customer_offer(
            promisor=guild_a,
            customer=customer_fail,
            quantity=60,
            suffix="failure",
        )
        promise_fail = make_multi_source_promise(
            offer_fail,
            sources1,
            promisor=guild_a,
            promised_at_cut=5,
        )
        acceptance_fail = accept_exchange_offer(
            offer_fail,
            acceptor_particular=customer_fail.particular(),
            accepted_at_cut=5,
        )
        fail_b = next(
            row
            for row in promise_fail["sources"]
            if row["capacity_guild_id"] == "guild:b"
        )
        fail_c = next(
            row
            for row in promise_fail["sources"]
            if row["capacity_guild_id"] == "guild:c"
        )
        request_fail_b = make_source_request(
            offer_fail,
            acceptance_fail,
            sources1,
            promise_fail,
            source_id=fail_b["source_id"],
            promisor=guild_a,
            requested_at_cut=6,
        )
        request_fail_c = make_source_request(
            offer_fail,
            acceptance_fail,
            sources1,
            promise_fail,
            source_id=fail_c["source_id"],
            promisor=guild_a,
            requested_at_cut=6,
        )

        fail_store_b = GuildReservationStore(
            root / "failure-reservations-b",
            steward=guild_b,
        )
        fail_store_c = GuildReservationStore(
            root / "failure-reservations-c",
            steward=guild_c,
        )
        (
            proposal_fail_b,
            auth_fail_b,
            reservation_fail_b,
            grant_fail_b,
        ) = reserve_source(
            treasury_b1,
            proof_b1,
            request_fail_b,
            capacity_steward=guild_b,
            executor_particular=worker_b.particular(),
            reservation_store=fail_store_b,
            reserved_at_cut=6,
            expires_after_cut=10,
        )
        (
            proposal_fail_c,
            auth_fail_c,
            reservation_fail_c,
            grant_fail_c,
        ) = reserve_source(
            treasury_c1,
            proof_c1,
            request_fail_c,
            capacity_steward=guild_c,
            executor_particular=worker_c.particular(),
            reservation_store=fail_store_c,
            reserved_at_cut=6,
            expires_after_cut=10,
        )
        backing_fail = derive_backing_view(
            promise_fail, [grant_fail_b, grant_fail_c]
        )
        assert backing_fail["status"] == "COMPLETE"

        execution_fail_b, final_fail_b = fail_store_b.execute_reserved(
            treasury_b1,
            proposal_fail_b,
            auth_fail_b,
            reservation_fail_b,
            executor=worker_b,
            observed_cut=7,
            simulate_success=True,
            result_ref="result:failure-case-b-success",
        )
        completion_fail_b = make_source_completion(
            treasury_b1,
            proof_b1,
            request_fail_b,
            proposal_fail_b,
            auth_fail_b,
            reservation_fail_b,
            grant_fail_b,
            execution_fail_b,
            final_fail_b,
            capacity_steward=guild_b,
        )

        execution_fail_c, final_fail_c = fail_store_c.execute_reserved(
            treasury_c1,
            proposal_fail_c,
            auth_fail_c,
            reservation_fail_c,
            executor=worker_c,
            observed_cut=7,
            simulate_success=False,
            error="simulation: source C failed before consumption",
        )
        failure_c = make_source_failure(
            treasury_c1,
            proof_c1,
            request_fail_c,
            proposal_fail_c,
            auth_fail_c,
            reservation_fail_c,
            grant_fail_c,
            execution_fail_c,
            final_fail_c,
            capacity_steward=guild_c,
        )

        aggregate_fail = derive_multi_source_completion(
            promise_fail,
            [completion_fail_b],
            [failure_c],
        )
        assert aggregate_fail["status"] == "FAILED"
        assert aggregate_fail["performed_measure"]["quantity"] == 30

        failed_performance_refused = refused(
            lambda: attest_multi_source_performance(
                offer_fail,
                acceptance_fail,
                sources1,
                promise_fail,
                aggregate_fail,
                promisor=guild_a,
            )
        )
        assert failed_performance_refused

        customer_perf_fail = sign_obligation_performance(
            offer_fail,
            acceptance_fail,
            role="ACCEPTOR",
            signer=customer_fail,
            evidence_ref="evidence:customer-fail-multi-source",
        )
        failed_settlement_refused = refused(
            lambda: settle_exchange(
                offer_fail,
                acceptance_fail,
                [customer_perf_fail],
            )
        )
        assert failed_settlement_refused

        # B's source was consumed; C's failed source is released.
        treasury_b2 = apply_execution_to_treasury(
            treasury_b1,
            proposal_fail_b,
            auth_fail_b,
            execution_fail_b,
            steward=guild_b,
        )
        entry_b2 = next(
            item
            for item in treasury_b2["entries"]
            if item["category"] == "capability"
            and item["position"] == "available"
        )
        assert entry_b2["native_measure"]["quantity"] == 0

        c_state_after_failure = fail_store_c.capacity_state(
            treasury_c1,
            entry_c1["entry_id"],
        )
        assert c_state_after_failure["visible_quantity"] == 30
        assert c_state_after_failure["reserved_quantity"] == 0
        assert c_state_after_failure["unencumbered_quantity"] == 30

        failure_crossing = make_multi_source_crossing(
            failure_c,
            signer=guild_c,
            declared_kind="LIGHTWALKER_MULTI_SOURCE_FAILURE",
            destination_particular=guild_a.particular(),
        )
        held_failure, admitted_failure = parcel_cross(
            root=root,
            name="source-c-failure",
            evidence=failure_c,
            crossing=failure_crossing,
            receiver=inbox_a,
        )
        assert held_failure["kind"] == "HELD"
        assert admitted_failure["kind"] == "ADMITTED"

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "source_plan": {
                        "guild_b": 30,
                        "guild_c": 30,
                        "promised": 60,
                        "wrong_sum_refused": wrong_sum_refused,
                    },
                    "backing": {
                        "after_b_only": partial_backing["status"],
                        "after_b_and_c": complete_backing["status"],
                        "partial_reserved": 30,
                        "full_reserved": 60,
                        "ownership_aggregated": False,
                    },
                    "success": {
                        "after_b_completion": partial_completion["status"],
                        "partial_performance_refused": (
                            partial_performance_refused
                        ),
                        "after_b_and_c_completion": aggregate_ok["status"],
                        "downstream_settlement": settlement_ok["status"],
                        "source_b_remaining": 30,
                        "source_c_remaining": 30,
                    },
                    "failure": {
                        "source_b_status": "FULFILLED",
                        "source_c_status": "FAILED",
                        "aggregate_status": aggregate_fail["status"],
                        "performed_before_failure": 30,
                        "customer_performance_refused": (
                            failed_performance_refused
                        ),
                        "downstream_settlement_refused": (
                            failed_settlement_refused
                        ),
                        "source_b_remaining": 0,
                        "source_c_released_remaining": 30,
                    },
                    "crossings": {
                        "request_b": [
                            held_request_b["kind"],
                            admitted_request_b["kind"],
                        ],
                        "request_c": [
                            held_request_c["kind"],
                            admitted_request_c["kind"],
                        ],
                        "failure_c": [
                            held_failure["kind"],
                            admitted_failure["kind"],
                        ],
                        "final_witness": [
                            held_witness["kind"],
                            admitted_witness["kind"],
                        ],
                    },
                    "laws": [
                        "ONE PROMISE MAY DEPEND ON MULTIPLE SOVEREIGN SOURCES",
                        "PARTIAL RESERVATION != FULL BACKING",
                        "PARTIAL COMPLETION != CUSTOMER PERFORMANCE",
                        "SOURCE FAILURE RELEASES ONLY ITS OWN AUTHORITY",
                        "AGGREGATION != OWNERSHIP",
                        "ALL REQUIRED SUBCONTRACTS MUST COMPLETE BEFORE DOWNSTREAM PERFORMANCE",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
