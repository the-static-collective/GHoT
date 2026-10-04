#!/usr/bin/env python3
"""Experiment 050 — Federated Reroute / Substitution."""

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
    make_reroute,
    make_reroute_crossing,
    make_substitute_completion,
    make_substitute_request,
    reserve_substitute,
    verify_reroute,
    verify_substitute_grant,
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
    verify_multi_source_promise,
    verify_source_grant,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


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
        resource_ref="service:reroutable-render-050",
        terms={
            "unit": "compute-minute",
            "quantity": 60,
            "capability": "render.verified",
        },
        evidence_policy="complete-rerouted-service",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref="consideration:reroute-050",
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
        valid_through_cut=16,
    )


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
        note=f"050 admit {name} as reroute evidence only",
    )
    return held, admitted


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
        worker_b = IdentityKey.load_or_create(
            root / "worker-b" / "body-p256.pem"
        )
        worker_c = IdentityKey.load_or_create(
            root / "worker-c" / "body-p256.pem"
        )
        worker_d = IdentityKey.load_or_create(
            root / "worker-d" / "body-p256.pem"
        )
        customer = IdentityKey.load_or_create(
            root / "customer" / "body-p256.pem"
        )

        inbox_a = StateParcelInbox(root / "inbox-a")
        inbox_d = StateParcelInbox(root / "inbox-d")
        observer = StateParcelInbox(root / "observer")

        treasury_b, entry_b = source_treasury(
            guild_id="guild:b",
            steward=guild_b,
            suffix="050",
        )
        treasury_c, entry_c = source_treasury(
            guild_id="guild:c",
            steward=guild_c,
            suffix="050",
        )
        treasury_d, entry_d = source_treasury(
            guild_id="guild:d",
            steward=guild_d,
            suffix="050",
        )
        assert verify_treasury_snapshot(treasury_b)
        assert verify_treasury_snapshot(treasury_c)
        assert verify_treasury_snapshot(treasury_d)

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
        assert verify_multi_source_promise(
            offer, original_sources, promise
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
        assert verify_source_grant(
            treasury_b,
            proof_b,
            request_b,
            proposal_b,
            auth_b,
            reservation_b,
            grant_b,
        )
        assert verify_source_grant(
            treasury_c,
            proof_c,
            request_c,
            proposal_c,
            auth_c,
            reservation_c,
            grant_c,
        )

        # Substitution cannot begin while B's old authority is still active.
        pre_failure_reroute_refused = refused(
            lambda: make_reroute(
                offer,
                acceptance,
                original_sources,
                promise,
                original_source_id=source_b["source_id"],
                original_snapshot=treasury_b,
                original_proof=proof_b,
                original_request=request_b,
                original_proposal=proposal_b,
                original_authorization=auth_b,
                original_reservation=reservation_b,
                original_grant=grant_b,
                original_finalization={},
                substitute_snapshot=treasury_d,
                substitute_proof=proof_d,
                promisor=guild_a,
                rerouted_at_cut=4,
            )
        )
        assert pre_failure_reroute_refused

        # B fails before consumption; its reservation is RELEASED.
        execution_b, final_b = store_b.execute_reserved(
            treasury_b,
            proposal_b,
            auth_b,
            reservation_b,
            executor=worker_b,
            observed_cut=4,
            simulate_success=False,
            error="simulation: guild B route failed before consumption",
        )
        assert execution_b["success"] is False
        assert execution_b["consumed_measure"] is None
        assert final_b["status"] == "RELEASED"

        b_state_after_failure = store_b.capacity_state(
            treasury_b,
            entry_b["entry_id"],
        )
        assert b_state_after_failure["reserved_quantity"] == 0
        assert b_state_after_failure["unencumbered_quantity"] == 60

        reroute = make_reroute(
            offer,
            acceptance,
            original_sources,
            promise,
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
            rerouted_at_cut=4,
        )
        assert verify_reroute(
            promise, treasury_d, proof_d, reroute
        )
        assert reroute["promise_rewritten"] is False
        assert reroute["old_authority_counts"] is False
        assert json.dumps(promise, sort_keys=True) == frozen_promise

        reroute_crossing = make_reroute_crossing(
            reroute,
            signer=guild_a,
            declared_kind="LIGHTWALKER_FEDERATED_REROUTE",
            destination_particular=guild_d.particular(),
        )
        held_reroute, admitted_reroute = parcel_cross(
            root=root,
            name="reroute",
            evidence=reroute,
            crossing=reroute_crossing,
            receiver=inbox_d,
        )
        assert held_reroute["kind"] == "HELD"
        assert admitted_reroute["kind"] == "ADMITTED"

        substitute_request = make_substitute_request(
            offer,
            acceptance,
            promise,
            treasury_d,
            proof_d,
            reroute,
            promisor=guild_a,
            requested_at_cut=5,
        )
        request_crossing = make_reroute_crossing(
            substitute_request,
            signer=guild_a,
            declared_kind="LIGHTWALKER_SUBSTITUTE_REQUEST",
            destination_particular=guild_d.particular(),
        )
        held_request, admitted_request = parcel_cross(
            root=root,
            name="substitute-request",
            evidence=substitute_request,
            crossing=request_crossing,
            receiver=inbox_d,
        )
        assert held_request["kind"] == "HELD"
        assert admitted_request["kind"] == "ADMITTED"

        backing_before_d = derive_rerouted_backing(
            promise,
            original_grants=[grant_b, grant_c],
            reroutes=[reroute],
            substitute_grants=[],
        )
        assert backing_before_d["status"] == "PARTIAL"
        assert backing_before_d["reserved_measure"]["quantity"] == 30
        assert grant_b["grant_id"] not in backing_before_d[
            "effective_grant_ids"
        ]

        (
            proposal_d,
            auth_d,
            reservation_d,
            grant_d,
        ) = reserve_substitute(
            treasury_d,
            proof_d,
            reroute,
            substitute_request,
            capacity_steward=guild_d,
            executor_particular=worker_d.particular(),
            reservation_store=store_d,
            reserved_at_cut=5,
            expires_after_cut=11,
        )
        assert verify_substitute_grant(
            treasury_d,
            proof_d,
            reroute,
            substitute_request,
            proposal_d,
            auth_d,
            reservation_d,
            grant_d,
        )

        backing_after_d = derive_rerouted_backing(
            promise,
            original_grants=[grant_b, grant_c],
            reroutes=[reroute],
            substitute_grants=[grant_d],
        )
        assert backing_after_d["status"] == "COMPLETE"
        assert backing_after_d["reserved_measure"]["quantity"] == 60
        assert grant_b["grant_id"] not in backing_after_d[
            "effective_grant_ids"
        ]
        assert grant_c["grant_id"] in backing_after_d[
            "effective_grant_ids"
        ]
        assert grant_d["grant_id"] in backing_after_d[
            "effective_grant_ids"
        ]

        # C succeeds on original route.
        execution_c, final_c = store_c.execute_reserved(
            treasury_c,
            proposal_c,
            auth_c,
            reservation_c,
            executor=worker_c,
            observed_cut=6,
            simulate_success=True,
            result_ref="result:original-c-success-050",
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

        partial_completion = derive_rerouted_completion(
            promise,
            original_completions=[completion_c],
            reroutes=[reroute],
            substitute_completions=[],
        )
        assert partial_completion["status"] == "PARTIAL"
        assert partial_completion["performed_measure"]["quantity"] == 30

        partial_performance_refused = refused(
            lambda: attest_rerouted_performance(
                offer,
                acceptance,
                promise,
                partial_completion,
                promisor=guild_a,
            )
        )
        assert partial_performance_refused

        # D fulfills B's original source slot.
        execution_d, final_d = store_d.execute_reserved(
            treasury_d,
            proposal_d,
            auth_d,
            reservation_d,
            executor=worker_d,
            observed_cut=6,
            simulate_success=True,
            result_ref="result:substitute-d-success-050",
        )
        completion_d = make_substitute_completion(
            treasury_d,
            proof_d,
            reroute,
            substitute_request,
            proposal_d,
            auth_d,
            reservation_d,
            grant_d,
            execution_d,
            final_d,
            capacity_steward=guild_d,
        )
        completion_crossing = make_reroute_crossing(
            completion_d,
            signer=guild_d,
            declared_kind="LIGHTWALKER_SUBSTITUTE_COMPLETION",
            destination_particular=guild_a.particular(),
        )
        held_completion, admitted_completion = parcel_cross(
            root=root,
            name="substitute-completion",
            evidence=completion_d,
            crossing=completion_crossing,
            receiver=inbox_a,
        )
        assert held_completion["kind"] == "HELD"
        assert admitted_completion["kind"] == "ADMITTED"

        aggregate = derive_rerouted_completion(
            promise,
            original_completions=[completion_c],
            reroutes=[reroute],
            substitute_completions=[completion_d],
        )
        assert aggregate["status"] == "COMPLETE"
        assert aggregate["performed_measure"]["quantity"] == 60
        assert aggregate["promise_rewritten"] is False

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
            evidence_ref="evidence:customer-reroute-review-050",
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
        assert witness["route_history_preserved"] is True

        witness_crossing = make_reroute_crossing(
            witness,
            signer=guild_a,
            declared_kind="LIGHTWALKER_REROUTED_SERVICE_SETTLEMENT",
            destination_particular=observer.signer.particular(),
        )
        held_witness, admitted_witness = parcel_cross(
            root=root,
            name="rerouted-service-settlement",
            evidence=witness,
            crossing=witness_crossing,
            receiver=observer,
        )
        assert held_witness["kind"] == "HELD"
        assert admitted_witness["kind"] == "ADMITTED"

        # The original B failure remains visible and B's released capacity
        # remains B-local; D's success did not consume B.
        b_final_state = store_b.capacity_state(
            treasury_b,
            entry_b["entry_id"],
        )
        assert b_final_state["unencumbered_quantity"] == 60
        d_final_state = store_d.capacity_state(
            treasury_d,
            entry_d["entry_id"],
        )
        assert d_final_state["reserved_quantity"] == 0

        duplicate_old_and_substitute_not_counted = (
            backing_after_d["reserved_measure"]["quantity"] == 60
            and len(backing_after_d["effective_grant_ids"]) == 2
        )
        assert duplicate_old_and_substitute_not_counted
        assert json.dumps(promise, sort_keys=True) == frozen_promise

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "original_promise": {
                        "declared_service": 60,
                        "original_sources": {
                            "guild_b": 30,
                            "guild_c": 30,
                        },
                        "promise_unchanged_after_reroute": True,
                    },
                    "failed_route": {
                        "guild_b_reserved": 30,
                        "guild_b_execution_success": False,
                        "guild_b_consumed": 0,
                        "guild_b_finalization": final_b["status"],
                        "guild_b_capacity_available_after_failure": 60,
                        "pre_failure_reroute_refused": (
                            pre_failure_reroute_refused
                        ),
                    },
                    "reroute": {
                        "original_slot": "guild_b:30",
                        "substitute": "guild_d:30",
                        "old_authority_counts": False,
                        "before_substitute_reservation": (
                            backing_before_d["status"]
                        ),
                        "after_substitute_reservation": (
                            backing_after_d["status"]
                        ),
                        "old_and_substitute_not_double_counted": (
                            duplicate_old_and_substitute_not_counted
                        ),
                    },
                    "completion": {
                        "guild_c_original_completion": 30,
                        "partial_status_before_d": (
                            partial_completion["status"]
                        ),
                        "partial_performance_refused": (
                            partial_performance_refused
                        ),
                        "guild_d_substitute_completion": 30,
                        "aggregate_status": aggregate["status"],
                        "performed": 60,
                        "downstream_settlement": settlement["status"],
                    },
                    "history": {
                        "guild_b_failure_preserved": True,
                        "guild_b_capacity_not_consumed_by_d": True,
                        "route_history_preserved": True,
                        "promise_rewritten": False,
                    },
                    "crossings": {
                        "reroute": [
                            held_reroute["kind"],
                            admitted_reroute["kind"],
                        ],
                        "substitute_request": [
                            held_request["kind"],
                            admitted_request["kind"],
                        ],
                        "substitute_completion": [
                            held_completion["kind"],
                            admitted_completion["kind"],
                        ],
                        "final_witness": [
                            held_witness["kind"],
                            admitted_witness["kind"],
                        ],
                    },
                    "laws": [
                        "SOURCE SUBSTITUTION != PROMISE REWRITE",
                        "FAILED SOURCE != FAILED SERVICE",
                        "REROUTE REQUIRES NEW EVIDENCE",
                        "OLD AUTHORITY MUST STOP COUNTING BEFORE SUBSTITUTE AUTHORITY COUNTS",
                        "SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE",
                        "ROUTE HISTORY != SERVICE SEMANTICS",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
