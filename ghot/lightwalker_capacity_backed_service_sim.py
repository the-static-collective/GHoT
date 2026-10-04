#!/usr/bin/env python3
"""Experiment 047 — Capacity-Backed Future Service."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_capacity_backed_service import (
    attest_successful_service_performance,
    derive_capacity_backed_service_settlement,
    make_capacity_backed_service_crossing,
    make_capacity_backed_service_promise,
    reserve_accepted_service,
    verify_capacity_backed_service_promise,
    verify_service_encumbrance,
)
from lightwalker_economy import LightwalkerEconomyError, content_address
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
from lightwalker_metabolic_exchange import (
    acquisition_to_treasury_entry,
    make_settled_capacity_acquisition,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def service_offer(
    *,
    guild: IdentityKey,
    customer: IdentityKey,
    quantity: int,
    suffix: str,
) -> dict:
    service = make_obligation(
        obligation_type="future-compute-service",
        resource_ref=f"service:render-{suffix}",
        terms={
            "unit": "compute-minute",
            "quantity": quantity,
            "capability": "render.verified",
        },
        evidence_policy="guild-execution-receipt",
    )
    consideration = make_obligation(
        obligation_type="service-consideration",
        resource_ref=f"consideration:{suffix}",
        terms={
            "deliverable": "one signed review note",
            "for_customer": customer.particular(),
        },
        evidence_policy="signed-counterparty-performance",
    )
    return make_exchange_offer(
        offeror_particular=guild.particular(),
        offeror_obligation=service,
        acceptor_obligation=consideration,
        orientation_refs=[],
        valid_through_cut=12,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        upstream = IdentityKey.load_or_create(
            root / "upstream" / "body-p256.pem"
        )
        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        customer_a = IdentityKey.load_or_create(
            root / "customer-a" / "body-p256.pem"
        )
        customer_b = IdentityKey.load_or_create(
            root / "customer-b" / "body-p256.pem"
        )
        customer_c = IdentityKey.load_or_create(
            root / "customer-c" / "body-p256.pem"
        )
        executor = IdentityKey.load_or_create(
            root / "executor" / "body-p256.pem"
        )

        # Close the 046 -> 047 loop: acquire 60 compute-minutes through a real
        # heterogeneous settlement, then admit it into Treasury.
        upstream_capacity = make_obligation(
            obligation_type="compute-capacity-delivery",
            resource_ref="compute:upstream-047",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="signed-provider-capacity-delivery",
        )
        upstream_consideration = make_obligation(
            obligation_type="documentation-service",
            resource_ref="guild:source-consideration-047",
            terms={"scope": "one documentation pass"},
            evidence_policy="signed-documentation-output",
        )
        source_offer = make_exchange_offer(
            offeror_particular=upstream.particular(),
            offeror_obligation=upstream_capacity,
            acceptor_obligation=upstream_consideration,
            orientation_refs=[],
            valid_through_cut=5,
        )
        source_acceptance = accept_exchange_offer(
            source_offer,
            acceptor_particular=guild.particular(),
            accepted_at_cut=1,
        )
        upstream_perf = sign_obligation_performance(
            source_offer,
            source_acceptance,
            role="OFFEROR",
            signer=upstream,
            evidence_ref="evidence:upstream-capacity-047",
        )
        guild_source_perf = sign_obligation_performance(
            source_offer,
            source_acceptance,
            role="ACCEPTOR",
            signer=guild,
            evidence_ref="evidence:guild-documentation-047",
        )
        source_attestations = [upstream_perf, guild_source_perf]
        source_settlement = settle_exchange(
            source_offer,
            source_acceptance,
            source_attestations,
        )
        source_acquisition = make_settled_capacity_acquisition(
            source_offer,
            source_acceptance,
            source_attestations,
            source_settlement,
            steward=guild,
            guild_id="guild:lantern-forge",
            capacity_subject_ref="capability:acquired-compute-047",
            admitted_at_cut=2,
        )
        capacity_entry = acquisition_to_treasury_entry(source_acquisition)
        source_receipt_entry = make_treasury_entry(
            category="receipt",
            position="evidence",
            subject_ref="source-settlement:" + source_settlement["settlement_id"],
            source_ref=source_settlement["settlement_id"],
            evidence_refs=[
                source_settlement["settlement_id"],
                source_acquisition["acquisition_id"],
            ],
            metadata={
                "source_for_future_service": True,
                "execution_authority": False,
            },
        )
        treasury0 = make_treasury_snapshot(
            guild_id="guild:lantern-forge",
            steward=guild,
            entries=[capacity_entry, source_receipt_entry],
            sequence=0,
        )
        assert verify_treasury_snapshot(treasury0)
        frozen_treasury0 = json.dumps(treasury0, sort_keys=True)

        # Two independently valid promises reference the same visible 60.
        offer_a = service_offer(
            guild=guild,
            customer=customer_a,
            quantity=40,
            suffix="a",
        )
        offer_b = service_offer(
            guild=guild,
            customer=customer_b,
            quantity=40,
            suffix="b",
        )
        promise_a = make_capacity_backed_service_promise(
            treasury0,
            offer_a,
            steward=guild,
            resource_entry_id=capacity_entry["entry_id"],
            executor_particular=executor.particular(),
            promised_at_cut=2,
        )
        promise_b = make_capacity_backed_service_promise(
            treasury0,
            offer_b,
            steward=guild,
            resource_entry_id=capacity_entry["entry_id"],
            executor_particular=executor.particular(),
            promised_at_cut=2,
        )
        assert verify_capacity_backed_service_promise(
            treasury0, offer_a, promise_a
        )
        assert verify_capacity_backed_service_promise(
            treasury0, offer_b, promise_b
        )
        assert promise_a["capacity_encumbered"] is False
        assert promise_b["capacity_encumbered"] is False

        # Promise alone does not alter the Treasury or reserve anything.
        assert json.dumps(treasury0, sort_keys=True) == frozen_treasury0

        acceptance_a = accept_exchange_offer(
            offer_a,
            acceptor_particular=customer_a.particular(),
            accepted_at_cut=3,
        )
        acceptance_b = accept_exchange_offer(
            offer_b,
            acceptor_particular=customer_b.particular(),
            accepted_at_cut=3,
        )

        store = GuildReservationStore(
            root / "service-reservations",
            steward=guild,
        )
        (
            proposal_a,
            authorization_a,
            reservation_a,
            encumbrance_a,
        ) = reserve_accepted_service(
            treasury0,
            offer_a,
            acceptance_a,
            promise_a,
            steward=guild,
            reservation_store=store,
            reserved_at_cut=3,
            expires_after_cut=7,
        )
        assert verify_service_encumbrance(
            treasury0,
            offer_a,
            acceptance_a,
            promise_a,
            proposal_a,
            authorization_a,
            reservation_a,
            encumbrance_a,
        )
        state_after_a = store.capacity_state(
            treasury0, capacity_entry["entry_id"]
        )
        assert state_after_a["visible_quantity"] == 60
        assert state_after_a["reserved_quantity"] == 40
        assert state_after_a["unencumbered_quantity"] == 20

        competing_promise_reservation_refused = refused(
            lambda: reserve_accepted_service(
                treasury0,
                offer_b,
                acceptance_b,
                promise_b,
                steward=guild,
                reservation_store=store,
                reserved_at_cut=3,
                expires_after_cut=7,
            )
        )
        assert competing_promise_reservation_refused

        # Successful performance path.
        execution_a, finalization_a = store.execute_reserved(
            treasury0,
            proposal_a,
            authorization_a,
            reservation_a,
            executor=executor,
            observed_cut=4,
            simulate_success=True,
            result_ref=content_address(
                {
                    "kind": "render-service-result",
                    "customer": customer_a.particular(),
                    "quantity": 40,
                }
            ),
        )
        service_perf_a = attest_successful_service_performance(
            treasury0,
            offer_a,
            acceptance_a,
            promise_a,
            proposal_a,
            authorization_a,
            reservation_a,
            encumbrance_a,
            execution_a,
            finalization_a,
            steward=guild,
        )
        customer_perf_a = sign_obligation_performance(
            offer_a,
            acceptance_a,
            role="ACCEPTOR",
            signer=customer_a,
            evidence_ref="evidence:customer-a-review-note",
        )
        settlement_a = settle_exchange(
            offer_a,
            acceptance_a,
            [service_perf_a, customer_perf_a],
        )
        service_witness_a = derive_capacity_backed_service_settlement(
            treasury0,
            offer_a,
            acceptance_a,
            promise_a,
            proposal_a,
            authorization_a,
            reservation_a,
            encumbrance_a,
            execution_a,
            finalization_a,
            service_perf_a,
            customer_perf_a,
            settlement_a,
        )
        assert service_witness_a["service_performed"] is True
        assert service_witness_a["payment_inferred"] is False

        # Consumption becomes a new Treasury history, not an edit to the old one.
        treasury1 = apply_execution_to_treasury(
            treasury0,
            proposal_a,
            authorization_a,
            execution_a,
            steward=guild,
        )
        assert verify_treasury_snapshot(treasury1)
        capacity_entry1 = next(
            item
            for item in treasury1["entries"]
            if item["category"] == "capability"
            and item["position"] == "available"
            and item["subject_ref"] == capacity_entry["subject_ref"]
        )
        assert capacity_entry1["native_measure"]["quantity"] == 20
        assert json.dumps(treasury0, sort_keys=True) == frozen_treasury0

        # The old B promise is still valid history against snapshot0, but it
        # cannot be used as if it were a promise against the successor snapshot.
        stale_promise_refused = refused(
            lambda: reserve_accepted_service(
                treasury1,
                offer_b,
                acceptance_b,
                promise_b,
                steward=guild,
                reservation_store=GuildReservationStore(
                    root / "stale-promise-store",
                    steward=guild,
                ),
                reserved_at_cut=5,
                expires_after_cut=8,
            )
        )
        assert stale_promise_refused

        # Failure path on the 20-unit successor capacity.
        offer_c = service_offer(
            guild=guild,
            customer=customer_c,
            quantity=20,
            suffix="c",
        )
        promise_c = make_capacity_backed_service_promise(
            treasury1,
            offer_c,
            steward=guild,
            resource_entry_id=capacity_entry1["entry_id"],
            executor_particular=executor.particular(),
            promised_at_cut=5,
        )
        acceptance_c = accept_exchange_offer(
            offer_c,
            acceptor_particular=customer_c.particular(),
            accepted_at_cut=5,
        )
        failure_store = GuildReservationStore(
            root / "failure-reservations",
            steward=guild,
        )
        (
            proposal_c,
            authorization_c,
            reservation_c,
            encumbrance_c,
        ) = reserve_accepted_service(
            treasury1,
            offer_c,
            acceptance_c,
            promise_c,
            steward=guild,
            reservation_store=failure_store,
            reserved_at_cut=5,
            expires_after_cut=8,
        )
        execution_c, finalization_c = failure_store.execute_reserved(
            treasury1,
            proposal_c,
            authorization_c,
            reservation_c,
            executor=executor,
            observed_cut=6,
            simulate_success=False,
            error="simulation: render service failed before consumption",
        )
        assert execution_c["success"] is False
        assert execution_c["consumed_measure"] is None
        assert finalization_c["status"] == "RELEASED"

        failed_service_attestation_refused = refused(
            lambda: attest_successful_service_performance(
                treasury1,
                offer_c,
                acceptance_c,
                promise_c,
                proposal_c,
                authorization_c,
                reservation_c,
                encumbrance_c,
                execution_c,
                finalization_c,
                steward=guild,
            )
        )
        assert failed_service_attestation_refused

        customer_perf_c = sign_obligation_performance(
            offer_c,
            acceptance_c,
            role="ACCEPTOR",
            signer=customer_c,
            evidence_ref="evidence:customer-c-review-note",
        )
        failed_settlement_refused = refused(
            lambda: settle_exchange(
                offer_c,
                acceptance_c,
                [customer_perf_c],
            )
        )
        assert failed_settlement_refused

        failure_capacity = failure_store.capacity_state(
            treasury1, capacity_entry1["entry_id"]
        )
        assert failure_capacity["visible_quantity"] == 20
        assert failure_capacity["reserved_quantity"] == 0
        assert failure_capacity["unencumbered_quantity"] == 20

        crossing = make_capacity_backed_service_crossing(
            service_witness_a,
            signer=guild,
        )
        assert verify_crossing(crossing)
        assert (
            crossing["requested_effect"]["automatic_execution_requested"]
            is False
        )
        assert (
            crossing["requested_effect"]["payment_inference_requested"]
            is False
        )
        assert (
            crossing["requested_effect"]["ownership_transfer_requested"]
            is False
        )

        source = root / "service-source"
        payload = source / "service-settlement.json"
        source.mkdir(parents=True, exist_ok=True)
        payload.write_text(
            json.dumps(
                {
                    "promise": promise_a,
                    "encumbrance": encumbrance_a,
                    "execution": execution_a,
                    "settlement": settlement_a,
                    "witness": service_witness_a,
                    "crossing": crossing,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        receiver = StateParcelInbox(root / "service-receiver")
        bundle = StateParcelExporter(source).export(
            str(payload.relative_to(source)),
            selector="$",
            target_particular=receiver.signer.particular(),
        )
        held = receiver.receive(bundle)
        assert held["kind"] == "HELD"
        assert held["semantic_effect"] == "none"
        admitted = receiver.decide(
            bundle["parcel"]["parcel_id"],
            "ADMIT",
            note=(
                "047 admit service-settlement audit as evidence only; "
                "do not infer payment, ownership, or execution authority"
            ),
        )
        assert admitted["kind"] == "ADMITTED"

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "source_capacity": {
                        "origin": "046-style heterogeneous acquisition",
                        "quantity": 60,
                    },
                    "promises": {
                        "promise_a": 40,
                        "promise_b": 40,
                        "both_valid_before_reservation": True,
                        "capacity_encumbered_by_promise": False,
                    },
                    "reservation": {
                        "a_reserved": 40,
                        "unencumbered_after_a": 20,
                        "competing_b_reservation_refused": (
                            competing_promise_reservation_refused
                        ),
                    },
                    "success": {
                        "a_execution_success": True,
                        "a_service_performance_bound_to_execution": True,
                        "a_settlement_status": settlement_a["status"],
                        "payment_inferred": False,
                        "successor_capacity": 20,
                        "stale_b_promise_refused_on_successor": (
                            stale_promise_refused
                        ),
                    },
                    "failure": {
                        "c_reserved": 20,
                        "c_execution_success": False,
                        "c_consumed": 0,
                        "reservation_released": True,
                        "service_attestation_refused": (
                            failed_service_attestation_refused
                        ),
                        "settlement_refused": failed_settlement_refused,
                        "capacity_available_after_failure": 20,
                    },
                    "crossing": {
                        "first_disposition": held["kind"],
                        "owner_disposition": admitted["kind"],
                        "automatic_execution_requested": False,
                        "payment_inference_requested": False,
                        "ownership_transfer_requested": False,
                    },
                    "laws": [
                        "CAPACITY PROOF != PROMISE",
                        "PROMISE != RESERVATION",
                        "RESERVATION != PERFORMANCE",
                        "PERFORMANCE != PAYMENT",
                        "FUTURE SERVICE OFFER MUST NAME ITS AUTHORITY SOURCE",
                        "ECONOMIC COMMITMENT MAY ENCUMBER CAPACITY WITHOUT CONSUMING IT",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
