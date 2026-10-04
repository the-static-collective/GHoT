#!/usr/bin/env python3
"""Experiment 048 — Federated Service Promise."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError
from lightwalker_federated_service import (
    attest_promisor_performance,
    derive_federated_service_settlement,
    make_federated_evidence_crossing,
    make_federated_service_promise,
    make_remote_capacity_proof,
    make_subcontract_completion,
    make_subcontract_failure,
    make_subcontract_request,
    reserve_federated_subcontract,
    verify_federated_service_promise,
    verify_remote_capacity_proof,
    verify_subcontract_completion,
    verify_subcontract_failure,
    verify_subcontract_grant,
    verify_subcontract_request,
)
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
        resource_ref=f"service:federated-render-{suffix}",
        terms={
            "unit": "compute-minute",
            "quantity": quantity,
            "capability": "render.verified",
        },
        evidence_policy="federated-subcontract-completion",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref=f"consideration:federated-{suffix}",
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
        valid_through_cut=12,
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
        note=f"048 admit {name} as federated evidence only",
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
        worker_b = IdentityKey.load_or_create(
            root / "worker-b" / "body-p256.pem"
        )
        customer_ok = IdentityKey.load_or_create(
            root / "customer-ok" / "body-p256.pem"
        )
        customer_fail = IdentityKey.load_or_create(
            root / "customer-fail" / "body-p256.pem"
        )

        inbox_a = StateParcelInbox(root / "inbox-a")
        inbox_b = StateParcelInbox(root / "inbox-b")
        observer = StateParcelInbox(root / "observer")

        # Guild B owns the operational capacity.
        capacity_entry = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref="capability:guild-b-render-pool-048",
            source_ref="ghot-node:guild-b-048",
            evidence_refs=["receipt:guild-b-capacity-probe-048"],
            native_measure={"unit": "compute-minute", "quantity": 60},
            metadata={"capability": "render.verified"},
        )
        treasury_b0 = make_treasury_snapshot(
            guild_id="guild:b",
            steward=guild_b,
            entries=[capacity_entry],
            sequence=0,
        )
        assert verify_treasury_snapshot(treasury_b0)
        frozen_treasury_b0 = json.dumps(treasury_b0, sort_keys=True)

        remote_proof0 = make_remote_capacity_proof(
            treasury_b0,
            steward=guild_b,
            resource_entry_id=capacity_entry["entry_id"],
            observed_cut=1,
            valid_through_cut=8,
        )
        assert verify_remote_capacity_proof(treasury_b0, remote_proof0)
        assert remote_proof0["capacity_reserved"] is False
        assert remote_proof0["execution_authority_granted"] is False

        wrong_proof_signer_refused = refused(
            lambda: make_remote_capacity_proof(
                treasury_b0,
                steward=guild_a,
                resource_entry_id=capacity_entry["entry_id"],
                observed_cut=1,
                valid_through_cut=8,
            )
        )
        assert wrong_proof_signer_refused

        proof_crossing = make_federated_evidence_crossing(
            remote_proof0,
            signer=guild_b,
            declared_kind="LIGHTWALKER_REMOTE_CAPACITY_PROOF",
            destination_particular=guild_a.particular(),
        )
        assert verify_crossing(proof_crossing)
        held_proof, admitted_proof = parcel_cross(
            root=root,
            name="remote-proof",
            evidence=remote_proof0,
            crossing=proof_crossing,
            receiver=inbox_a,
        )
        assert held_proof["kind"] == "HELD"
        assert admitted_proof["kind"] == "ADMITTED"

        wrong_crossing_signer_refused = refused(
            lambda: make_federated_evidence_crossing(
                remote_proof0,
                signer=guild_a,
                declared_kind="LIGHTWALKER_REMOTE_CAPACITY_PROOF",
                destination_particular=guild_a.particular(),
            )
        )
        assert wrong_crossing_signer_refused

        # SUCCESS PATH -----------------------------------------------------
        offer_ok = customer_offer(
            promisor=guild_a,
            customer=customer_ok,
            quantity=40,
            suffix="ok",
        )
        promise_ok = make_federated_service_promise(
            treasury_b0,
            offer_ok,
            remote_proof0,
            promisor=guild_a,
            promised_at_cut=2,
        )
        assert verify_federated_service_promise(
            treasury_b0, offer_ok, remote_proof0, promise_ok
        )
        assert promise_ok["capacity_reserved"] is False
        assert promise_ok["local_execution_authority"] is False

        acceptance_ok = accept_exchange_offer(
            offer_ok,
            acceptor_particular=customer_ok.particular(),
            accepted_at_cut=2,
        )
        request_ok = make_subcontract_request(
            treasury_b0,
            offer_ok,
            acceptance_ok,
            remote_proof0,
            promise_ok,
            promisor=guild_a,
            requested_at_cut=3,
        )
        assert verify_subcontract_request(
            treasury_b0,
            offer_ok,
            acceptance_ok,
            remote_proof0,
            promise_ok,
            request_ok,
        )
        assert request_ok["reservation_authority"] == "none"

        request_crossing = make_federated_evidence_crossing(
            request_ok,
            signer=guild_a,
            declared_kind="LIGHTWALKER_FEDERATED_SUBCONTRACT_REQUEST",
            destination_particular=guild_b.particular(),
        )
        held_request, admitted_request = parcel_cross(
            root=root,
            name="subcontract-request",
            evidence=request_ok,
            crossing=request_crossing,
            receiver=inbox_b,
        )
        assert held_request["kind"] == "HELD"
        assert admitted_request["kind"] == "ADMITTED"

        store_b = GuildReservationStore(
            root / "guild-b-reservations",
            steward=guild_b,
        )

        promisor_cannot_reserve_remote_refused = refused(
            lambda: reserve_federated_subcontract(
                treasury_b0,
                offer_ok,
                acceptance_ok,
                remote_proof0,
                promise_ok,
                request_ok,
                capacity_steward=guild_a,
                executor_particular=worker_b.particular(),
                reservation_store=store_b,
                reserved_at_cut=3,
                expires_after_cut=7,
            )
        )
        assert promisor_cannot_reserve_remote_refused

        (
            proposal_ok,
            authorization_ok,
            reservation_ok,
            grant_ok,
        ) = reserve_federated_subcontract(
            treasury_b0,
            offer_ok,
            acceptance_ok,
            remote_proof0,
            promise_ok,
            request_ok,
            capacity_steward=guild_b,
            executor_particular=worker_b.particular(),
            reservation_store=store_b,
            reserved_at_cut=3,
            expires_after_cut=7,
        )
        assert verify_subcontract_grant(
            treasury_b0,
            remote_proof0,
            request_ok,
            proposal_ok,
            authorization_ok,
            reservation_ok,
            grant_ok,
        )
        assert grant_ok["promisor_execution_authority"] is False
        assert grant_ok["ownership_transfer"] is False

        grant_crossing = make_federated_evidence_crossing(
            grant_ok,
            signer=guild_b,
            declared_kind="LIGHTWALKER_FEDERATED_SUBCONTRACT_GRANT",
            destination_particular=guild_a.particular(),
        )
        held_grant, admitted_grant = parcel_cross(
            root=root,
            name="subcontract-grant",
            evidence=grant_ok,
            crossing=grant_crossing,
            receiver=inbox_a,
        )
        assert held_grant["kind"] == "HELD"
        assert admitted_grant["kind"] == "ADMITTED"

        promisor_cannot_execute_remote_refused = refused(
            lambda: store_b.execute_reserved(
                treasury_b0,
                proposal_ok,
                authorization_ok,
                reservation_ok,
                executor=guild_a,
                observed_cut=4,
                simulate_success=True,
                result_ref="result:wrong-promisor-execution",
            )
        )
        assert promisor_cannot_execute_remote_refused

        execution_ok, finalization_ok = store_b.execute_reserved(
            treasury_b0,
            proposal_ok,
            authorization_ok,
            reservation_ok,
            executor=worker_b,
            observed_cut=4,
            simulate_success=True,
            result_ref="result:guild-b-render-success-048",
        )
        completion_ok = make_subcontract_completion(
            treasury_b0,
            remote_proof0,
            request_ok,
            proposal_ok,
            authorization_ok,
            reservation_ok,
            grant_ok,
            execution_ok,
            finalization_ok,
            capacity_steward=guild_b,
        )
        assert verify_subcontract_completion(grant_ok, completion_ok)
        assert completion_ok["downstream_settlement_created"] is False

        completion_crossing = make_federated_evidence_crossing(
            completion_ok,
            signer=guild_b,
            declared_kind="LIGHTWALKER_FEDERATED_SUBCONTRACT_COMPLETION",
            destination_particular=guild_a.particular(),
        )
        held_completion, admitted_completion = parcel_cross(
            root=root,
            name="subcontract-completion",
            evidence=completion_ok,
            crossing=completion_crossing,
            receiver=inbox_a,
        )
        assert held_completion["kind"] == "HELD"
        assert admitted_completion["kind"] == "ADMITTED"

        promisor_perf_ok = attest_promisor_performance(
            treasury_b0,
            offer_ok,
            acceptance_ok,
            remote_proof0,
            promise_ok,
            request_ok,
            grant_ok,
            completion_ok,
            promisor=guild_a,
        )
        assert promisor_perf_ok["evidence_ref"] == completion_ok["completion_id"]

        customer_perf_ok = sign_obligation_performance(
            offer_ok,
            acceptance_ok,
            role="ACCEPTOR",
            signer=customer_ok,
            evidence_ref="evidence:customer-ok-consideration-048",
        )
        settlement_ok = settle_exchange(
            offer_ok,
            acceptance_ok,
            [promisor_perf_ok, customer_perf_ok],
        )
        federated_witness = derive_federated_service_settlement(
            treasury_b0,
            offer_ok,
            acceptance_ok,
            remote_proof0,
            promise_ok,
            request_ok,
            proposal_ok,
            authorization_ok,
            reservation_ok,
            grant_ok,
            execution_ok,
            finalization_ok,
            completion_ok,
            promisor_perf_ok,
            customer_perf_ok,
            settlement_ok,
        )
        assert federated_witness["customer_service_performed"] is True
        assert federated_witness["capacity_ownership_transferred"] is False
        assert (
            federated_witness["promisor_remote_execution_authority"]
            is False
        )
        assert (
            federated_witness["payment_inferred_from_remote_execution"]
            is False
        )

        witness_crossing = make_federated_evidence_crossing(
            federated_witness,
            signer=guild_a,
            declared_kind="LIGHTWALKER_FEDERATED_SERVICE_SETTLEMENT",
            destination_particular=observer.signer.particular(),
        )
        held_witness, admitted_witness = parcel_cross(
            root=root,
            name="federated-service-settlement",
            evidence=federated_witness,
            crossing=witness_crossing,
            receiver=observer,
        )
        assert held_witness["kind"] == "HELD"
        assert admitted_witness["kind"] == "ADMITTED"

        # Remote successful execution creates B's successor Treasury.
        treasury_b1 = apply_execution_to_treasury(
            treasury_b0,
            proposal_ok,
            authorization_ok,
            execution_ok,
            steward=guild_b,
        )
        assert verify_treasury_snapshot(treasury_b1)
        capacity_entry1 = next(
            item
            for item in treasury_b1["entries"]
            if item["category"] == "capability"
            and item["position"] == "available"
            and item["subject_ref"] == capacity_entry["subject_ref"]
        )
        assert capacity_entry1["native_measure"]["quantity"] == 20
        assert json.dumps(treasury_b0, sort_keys=True) == frozen_treasury_b0

        stale_remote_proof_refused = refused(
            lambda: reserve_federated_subcontract(
                treasury_b1,
                offer_ok,
                acceptance_ok,
                remote_proof0,
                promise_ok,
                request_ok,
                capacity_steward=guild_b,
                executor_particular=worker_b.particular(),
                reservation_store=store_b,
                reserved_at_cut=5,
                expires_after_cut=7,
            )
        )
        assert stale_remote_proof_refused

        # FAILURE PATH -----------------------------------------------------
        remote_proof1 = make_remote_capacity_proof(
            treasury_b1,
            steward=guild_b,
            resource_entry_id=capacity_entry1["entry_id"],
            observed_cut=5,
            valid_through_cut=10,
        )
        offer_fail = customer_offer(
            promisor=guild_a,
            customer=customer_fail,
            quantity=20,
            suffix="fail",
        )
        promise_fail = make_federated_service_promise(
            treasury_b1,
            offer_fail,
            remote_proof1,
            promisor=guild_a,
            promised_at_cut=5,
        )
        acceptance_fail = accept_exchange_offer(
            offer_fail,
            acceptor_particular=customer_fail.particular(),
            accepted_at_cut=5,
        )
        request_fail = make_subcontract_request(
            treasury_b1,
            offer_fail,
            acceptance_fail,
            remote_proof1,
            promise_fail,
            promisor=guild_a,
            requested_at_cut=6,
        )
        (
            proposal_fail,
            authorization_fail,
            reservation_fail,
            grant_fail,
        ) = reserve_federated_subcontract(
            treasury_b1,
            offer_fail,
            acceptance_fail,
            remote_proof1,
            promise_fail,
            request_fail,
            capacity_steward=guild_b,
            executor_particular=worker_b.particular(),
            reservation_store=store_b,
            reserved_at_cut=6,
            expires_after_cut=9,
        )
        frozen_failure_promise = json.dumps(promise_fail, sort_keys=True)

        execution_fail, finalization_fail = store_b.execute_reserved(
            treasury_b1,
            proposal_fail,
            authorization_fail,
            reservation_fail,
            executor=worker_b,
            observed_cut=7,
            simulate_success=False,
            error="simulation: remote renderer failed before consumption",
        )
        assert execution_fail["success"] is False
        assert execution_fail["consumed_measure"] is None
        assert finalization_fail["status"] == "RELEASED"

        failure_notice = make_subcontract_failure(
            treasury_b1,
            remote_proof1,
            request_fail,
            proposal_fail,
            authorization_fail,
            reservation_fail,
            grant_fail,
            execution_fail,
            finalization_fail,
            capacity_steward=guild_b,
        )
        assert verify_subcontract_failure(grant_fail, failure_notice)
        assert failure_notice["capacity_released"] is True
        assert failure_notice["downstream_performance_proven"] is False

        failure_crossing = make_federated_evidence_crossing(
            failure_notice,
            signer=guild_b,
            declared_kind="LIGHTWALKER_FEDERATED_SUBCONTRACT_FAILURE",
            destination_particular=guild_a.particular(),
        )
        held_failure, admitted_failure = parcel_cross(
            root=root,
            name="subcontract-failure",
            evidence=failure_notice,
            crossing=failure_crossing,
            receiver=inbox_a,
        )
        assert held_failure["kind"] == "HELD"
        assert admitted_failure["kind"] == "ADMITTED"

        failed_downstream_performance_refused = refused(
            lambda: attest_promisor_performance(
                treasury_b1,
                offer_fail,
                acceptance_fail,
                remote_proof1,
                promise_fail,
                request_fail,
                grant_fail,
                failure_notice,
                promisor=guild_a,
            )
        )
        assert failed_downstream_performance_refused

        customer_perf_fail = sign_obligation_performance(
            offer_fail,
            acceptance_fail,
            role="ACCEPTOR",
            signer=customer_fail,
            evidence_ref="evidence:customer-fail-consideration-048",
        )
        failed_downstream_settlement_refused = refused(
            lambda: settle_exchange(
                offer_fail,
                acceptance_fail,
                [customer_perf_fail],
            )
        )
        assert failed_downstream_settlement_refused

        capacity_after_failure = store_b.capacity_state(
            treasury_b1,
            capacity_entry1["entry_id"],
        )
        assert capacity_after_failure["visible_quantity"] == 20
        assert capacity_after_failure["reserved_quantity"] == 0
        assert capacity_after_failure["unencumbered_quantity"] == 20
        assert json.dumps(promise_fail, sort_keys=True) == frozen_failure_promise

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "sovereignty": {
                        "promisor_guild": "guild:a",
                        "capacity_guild": "guild:b",
                        "same_sovereign": False,
                        "wrong_proof_signer_refused": (
                            wrong_proof_signer_refused
                        ),
                        "wrong_crossing_signer_refused": (
                            wrong_crossing_signer_refused
                        ),
                        "promisor_cannot_reserve_remote": (
                            promisor_cannot_reserve_remote_refused
                        ),
                        "promisor_cannot_execute_remote": (
                            promisor_cannot_execute_remote_refused
                        ),
                    },
                    "success_path": {
                        "remote_capacity_proven": 60,
                        "customer_promise": 40,
                        "remote_reservation": 40,
                        "remote_execution_success": True,
                        "completion_crossed_back": True,
                        "customer_settlement": settlement_ok["status"],
                        "capacity_ownership_transferred": False,
                        "payment_inferred_from_remote_execution": False,
                        "remote_successor_capacity": 20,
                        "stale_remote_proof_refused": stale_remote_proof_refused,
                    },
                    "failure_path": {
                        "remote_capacity_proven": 20,
                        "customer_promise": 20,
                        "remote_execution_success": False,
                        "remote_capacity_consumed": 0,
                        "capacity_released": True,
                        "failure_crossed_back": True,
                        "downstream_performance_refused": (
                            failed_downstream_performance_refused
                        ),
                        "downstream_settlement_refused": (
                            failed_downstream_settlement_refused
                        ),
                        "remote_capacity_available_after_failure": 20,
                        "promise_history_unchanged": True,
                    },
                    "crossings": {
                        "proof": [
                            held_proof["kind"],
                            admitted_proof["kind"],
                        ],
                        "request": [
                            held_request["kind"],
                            admitted_request["kind"],
                        ],
                        "grant": [
                            held_grant["kind"],
                            admitted_grant["kind"],
                        ],
                        "completion": [
                            held_completion["kind"],
                            admitted_completion["kind"],
                        ],
                        "failure": [
                            held_failure["kind"],
                            admitted_failure["kind"],
                        ],
                        "final_witness": [
                            held_witness["kind"],
                            admitted_witness["kind"],
                        ],
                    },
                    "laws": [
                        "PROMISOR != CAPACITY HOLDER",
                        "REMOTE CAPACITY PROOF != LOCAL AUTHORITY",
                        "SUBCONTRACT != OWNERSHIP TRANSFER",
                        "UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE",
                        "DOWNSTREAM FAILURE MUST PROPAGATE WITHOUT HISTORY REWRITE",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
