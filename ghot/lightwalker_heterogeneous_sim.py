#!/usr/bin/env python3
"""Experiment 035 — Heterogeneous exchange without a common scalar."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from dogram_contribution_bridge import run_contribution_field
from ice_cube import build_work, mine_ice_cube
from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_heterogeneous_exchange import (
    accept_exchange_offer,
    make_acceptance_crossing,
    make_exchange_offer,
    make_obligation,
    make_offer_crossing,
    make_settlement_crossing,
    settle_exchange,
    sign_obligation_performance,
    verify_exchange_acceptance,
    verify_exchange_offer,
    verify_exchange_settlement,
)
from lightwalker_temporal_economy import (
    ASSAY_LENS_KIND,
    ASSAY_LENS_VERSION,
    project_measurement,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def _expect_refusal(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dogram-ice-repo", type=Path, required=True)
    parser.add_argument("--dogram-contribution-repo", type=Path, required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        worker_root = root / "worker"
        receiver_root = root / "receiver"

        artist = IdentityKey.load_or_create(root / "artist" / "body-p256.pem")
        compute_host = IdentityKey.load_or_create(
            root / "compute-host" / "body-p256.pem"
        )

        mined = mine_ice_cube(
            worker_root=worker_root,
            dogram_repo=args.dogram_ice_repo,
            work=build_work(
                lucas_index=5,
                width=24,
                height=24,
                max_halley_iter=8,
            ),
        )
        result = mined["result"]

        root_ref = result["specimen_address"]
        descendant_a = "artifact-use:" + result["render_address"]
        descendant_b = "derived-study:" + result["specimen_address"]
        events = [
            {
                "event_id": "e-ice-birth",
                "relation_kind": "CREATED",
                "source_ref": artist.particular(),
                "subject_ref": root_ref,
                "evidence_ref": result["dogram_receipt_address"],
                "evidence_status": "complete",
                "available_from": 0,
            },
            {
                "event_id": "e-render-enabled-use",
                "relation_kind": "ENABLED",
                "source_ref": root_ref,
                "subject_ref": descendant_a,
                "evidence_ref": result["execution_receipt_id"],
                "evidence_status": "complete",
                "available_from": 1,
            },
            {
                "event_id": "e-use-carried-study",
                "relation_kind": "CARRIED",
                "source_ref": descendant_a,
                "subject_ref": descendant_b,
                "evidence_ref": result["work_crossing_id"],
                "evidence_status": "complete",
                "available_from": 1,
            },
        ]
        field = run_contribution_field(
            args.dogram_contribution_repo,
            events=events,
            declared_relation_kinds=("CREATED", "ENABLED", "CARRIED"),
            birth_event_id="e-ice-birth",
            birth_cut=0,
            before_cut=0,
            after_cut=1,
        )
        workmark = field["workmark"]
        measurement = field["after"]

        lens = {
            "kind": ASSAY_LENS_KIND,
            "version": ASSAY_LENS_VERSION,
            "realm_id": "realm:lantern",
            "unit": "lumen",
            "policy": {
                "basis": "base-plus-descendants",
                "base_amount": 7,
                "per_descendant": 3,
            },
            "assumptions": [
                "This projection is orientation only; it does not price the barter.",
            ],
        }
        projection = project_measurement(workmark, measurement, lens)
        assert projection["quantity"] == 13

        artifact_access = make_obligation(
            obligation_type="artifact-access",
            resource_ref="license:" + result["render_address"],
            terms={
                "scope": "non-exclusive-read-and-derive",
                "artifact_ref": result["render_address"],
                "revocation": "none-for-frozen-specimen",
            },
            evidence_policy="signed-license-grant-reference",
        )
        compute_service = make_obligation(
            obligation_type="compute-service",
            resource_ref="ghot-capability:ice-cube/v0",
            terms={
                "work_family": result["family"],
                "requested_width": 48,
                "requested_height": 48,
                "verification": "dogram-required",
            },
            evidence_policy="verified-result-plus-execution-receipt",
        )

        offer = make_exchange_offer(
            offeror_particular=artist.particular(),
            offeror_obligation=artifact_access,
            acceptor_obligation=compute_service,
            orientation_refs=[projection["projection_id"]],
            valid_through_cut=4,
        )
        assert verify_exchange_offer(offer)
        assert "price" not in offer
        assert "exchange_rate" not in offer
        assert "common_unit" not in offer

        frozen_workmark = json.dumps(workmark, sort_keys=True)
        frozen_projection = json.dumps(projection, sort_keys=True)
        frozen_offer = json.dumps(offer, sort_keys=True)

        offer_crossing = make_offer_crossing(
            offer,
            signer=artist,
            node_id="lightwalker-heterogeneous-035-artist",
        )
        assert verify_crossing(offer_crossing)
        assert (
            offer_crossing["requested_effect"]["automatic_conversion_requested"]
            is False
        )

        acceptance = accept_exchange_offer(
            offer,
            acceptor_particular=compute_host.particular(),
            accepted_at_cut=2,
        )
        assert verify_exchange_acceptance(offer, acceptance)
        frozen_acceptance = json.dumps(acceptance, sort_keys=True)

        acceptance_crossing = make_acceptance_crossing(
            offer,
            acceptance,
            signer=compute_host,
            node_id="lightwalker-heterogeneous-035-host",
        )
        assert verify_crossing(acceptance_crossing)
        assert (
            acceptance_crossing["requested_effect"]["automatic_conversion_requested"]
            is False
        )

        tampered_offer = json.loads(json.dumps(offer))
        tampered_offer["acceptor_obligation"]["terms"]["requested_width"] = 96
        tampered_offer["acceptor_obligation"]["obligation_id"] = content_address(
            {
                key: value
                for key, value in tampered_offer["acceptor_obligation"].items()
                if key != "obligation_id"
            }
        )
        tampered_offer["offer_id"] = content_address(
            {
                key: value
                for key, value in tampered_offer.items()
                if key != "offer_id"
            }
        )
        assert not verify_exchange_acceptance(tampered_offer, acceptance)

        grant_evidence = content_address(
            {
                "kind": "simulation.artifact-access-grant",
                "acceptance_id": acceptance["acceptance_id"],
                "resource_ref": artifact_access["resource_ref"],
                "granted_to": compute_host.particular(),
            }
        )
        compute_evidence = content_address(
            {
                "kind": "simulation.compute-service-result",
                "acceptance_id": acceptance["acceptance_id"],
                "capability": compute_service["resource_ref"],
                "result_family": result["family"],
                "dogram_required": True,
            }
        )

        artist_performance = sign_obligation_performance(
            offer,
            acceptance,
            role="OFFEROR",
            signer=artist,
            evidence_ref=grant_evidence,
        )
        unilateral_refused = _expect_refusal(
            lambda: settle_exchange(
                offer,
                acceptance,
                [artist_performance],
            )
        )
        assert unilateral_refused

        host_performance = sign_obligation_performance(
            offer,
            acceptance,
            role="ACCEPTOR",
            signer=compute_host,
            evidence_ref=compute_evidence,
        )
        settlement = settle_exchange(
            offer,
            acceptance,
            [artist_performance, host_performance],
        )
        assert verify_exchange_settlement(
            offer,
            acceptance,
            [artist_performance, host_performance],
            settlement,
        )

        forbidden_in_settlement = {
            "price",
            "exchange_rate",
            "common_unit",
            "currency",
            "monetary_amount",
            "equivalent_value",
            "conversion_rate",
        }
        assert forbidden_in_settlement.isdisjoint(settlement)

        settlement_crossing = make_settlement_crossing(
            settlement,
            signer=artist,
            node_id="lightwalker-heterogeneous-035-settlement",
        )
        assert verify_crossing(settlement_crossing)
        effect = settlement_crossing["requested_effect"]
        assert effect["conversion_rate_requested"] is False
        assert effect["common_unit_requested"] is False
        assert effect["mint_authority_requested"] is False
        assert effect["balance_mutation_requested"] is False

        # Second specimen proves the protocol is not special-cased to the
        # artifact/compute pair and does not require a valuation projection.
        storage = make_obligation(
            obligation_type="hosting-service",
            resource_ref="host:content-addressed-bundle",
            terms={
                "availability_window": "declared-72h-window",
                "integrity_check": "sha256",
            },
            evidence_policy="uptime-log-plus-integrity-receipt",
        )
        labor_writ = make_obligation(
            obligation_type="future-labor-writ",
            resource_ref="labor:documentation-pass",
            terms={
                "scope": "one-bounded-documentation-pass",
                "acceptance_test": "owner-local-review",
            },
            evidence_policy="signed-completion-receipt",
        )
        second_offer = make_exchange_offer(
            offeror_particular=artist.particular(),
            offeror_obligation=storage,
            acceptor_obligation=labor_writ,
            orientation_refs=[],
            valid_through_cut=7,
        )
        assert verify_exchange_offer(second_offer)
        assert second_offer["orientation_refs"] == []
        assert second_offer["offeror_obligation"]["obligation_type"] != (
            second_offer["acceptor_obligation"]["obligation_type"]
        )

        assert json.dumps(workmark, sort_keys=True) == frozen_workmark
        assert json.dumps(projection, sort_keys=True) == frozen_projection
        assert json.dumps(offer, sort_keys=True) == frozen_offer
        assert json.dumps(acceptance, sort_keys=True) == frozen_acceptance

        packet_path = (
            worker_root
            / "lightwalker"
            / "heterogeneous-exchange-035.v0.json"
        )
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps(
                {
                    "workmark": workmark,
                    "orientation_projection": projection,
                    "offer": offer,
                    "offer_crossing": offer_crossing,
                    "acceptance": acceptance,
                    "acceptance_crossing": acceptance_crossing,
                    "offeror_performance": artist_performance,
                    "acceptor_performance": host_performance,
                    "settlement": settlement,
                    "settlement_crossing": settlement_crossing,
                    "second_unpriced_offer": second_offer,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        inbox = StateParcelInbox(receiver_root)
        exporter = StateParcelExporter(worker_root)
        bundle = exporter.export(
            str(packet_path.relative_to(worker_root)),
            selector="$",
            target_particular=inbox.signer.particular(),
        )
        held = inbox.receive(bundle)
        assert held["kind"] == "HELD"
        assert held["semantic_effect"] == "none"
        parcel_id = bundle["parcel"]["parcel_id"]
        admitted = inbox.decide(
            parcel_id,
            "ADMIT",
            note=(
                "035 admit heterogeneous settlement evidence; "
                "no conversion, balance mutation, or ownership inference"
            ),
        )
        assert admitted["kind"] == "ADMITTED"

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "orientation": {
                        "projection_quantity": projection["quantity"],
                        "projection_unit": projection["unit"],
                        "used_as_price": False,
                    },
                    "exchange": {
                        "offeror_obligation": artifact_access[
                            "obligation_type"
                        ],
                        "acceptor_obligation": compute_service[
                            "obligation_type"
                        ],
                        "shared_scalar_required": False,
                        "unilateral_settlement_refused": unilateral_refused,
                    },
                    "anti_tamper": {
                        "post_acceptance_term_change_refused": True,
                    },
                    "settlement": {
                        "settlement_id": settlement["settlement_id"],
                        "status": settlement["status"],
                        "authority": settlement["authority"],
                        "conversion_rate_present": False,
                        "common_unit_present": False,
                        "balance_mutation_requested": False,
                    },
                    "generality": {
                        "second_offer_pair": [
                            storage["obligation_type"],
                            labor_writ["obligation_type"],
                        ],
                        "second_offer_has_orientation_projection": False,
                    },
                    "history": {
                        "workmark_unchanged": True,
                        "projection_unchanged": True,
                        "offer_unchanged": True,
                        "acceptance_unchanged": True,
                    },
                    "crossing": {
                        "held_first": held["kind"],
                        "owner_disposition": admitted["kind"],
                    },
                    "laws": [
                        "OBLIGATION A != OBLIGATION B",
                        "ORIENTATION != PRICE",
                        "NO COMMON UNIT REQUIRED",
                        "SETTLEMENT != CONVERSION",
                        "EXCHANGE CAN BE COMPOSED BEFORE CURRENCY IS STANDARDIZED",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
