#!/usr/bin/env python3
"""Experiment 034 — The Market Without the Coin."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from dogram_contribution_bridge import run_contribution_field
from ice_cube import build_work, mine_ice_cube
from lightwalker_market import (
    accept_offer,
    make_acceptance_crossing,
    make_offer,
    make_offer_crossing,
    make_settlement_crossing,
    settle,
    sign_performance,
    verify_acceptance,
    verify_offer,
    verify_settlement,
)
from lightwalker_temporal_economy import (
    ASSAY_LENS_KIND,
    ASSAY_LENS_VERSION,
    project_measurement,
)
from lightwalker_economy import LightwalkerEconomyError, content_address
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dogram-ice-repo", type=Path, required=True)
    parser.add_argument("--dogram-contribution-repo", type=Path, required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        worker_root = root / "worker"
        market_receiver_root = root / "market-receiver"

        seller = IdentityKey.load_or_create(root / "seller" / "body-p256.pem")
        buyer = IdentityKey.load_or_create(root / "buyer" / "body-p256.pem")

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
        contribution_root = result["specimen_address"]
        first_descendant = "artifact-use:" + result["render_address"]
        second_descendant = "derived-study:" + result["specimen_address"]

        events = [
            {
                "event_id": "e-ice-birth",
                "relation_kind": "CREATED",
                "source_ref": seller.particular(),
                "subject_ref": contribution_root,
                "evidence_ref": result["dogram_receipt_address"],
                "evidence_status": "complete",
                "available_from": 0,
            },
            {
                "event_id": "e-render-enabled-use",
                "relation_kind": "ENABLED",
                "source_ref": contribution_root,
                "subject_ref": first_descendant,
                "evidence_ref": result["execution_receipt_id"],
                "evidence_status": "complete",
                "available_from": 1,
            },
            {
                "event_id": "e-use-carried-study",
                "relation_kind": "CARRIED",
                "source_ref": first_descendant,
                "subject_ref": second_descendant,
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
                "Projection is an input to negotiation, not a mandatory sale price.",
            ],
        }
        projection = project_measurement(workmark, measurement, lens)
        assert projection["quantity"] == 13

        frozen_workmark = json.dumps(workmark, sort_keys=True)
        frozen_projection = json.dumps(projection, sort_keys=True)

        offer = make_offer(
            projection,
            offeror_particular=seller.particular(),
            deliverable_ref="license:" + result["render_address"],
            asking_unit="lumen",
            asking_quantity=11,
            valid_through_cut=3,
        )
        assert verify_offer(offer)
        assert offer["consideration"]["quantity"] == 11
        assert offer["consideration"]["quantity"] != projection["quantity"]
        frozen_offer = json.dumps(offer, sort_keys=True)

        offer_crossing = make_offer_crossing(
            offer,
            signer=seller,
            node_id="lightwalker-market-034-seller",
        )
        assert verify_crossing(offer_crossing)
        assert offer_crossing["requested_effect"]["automatic_acceptance_requested"] is False
        assert offer_crossing["requested_effect"]["automatic_settlement_requested"] is False

        acceptance = accept_offer(
            offer,
            acceptor_particular=buyer.particular(),
            accepted_at_cut=2,
        )
        assert verify_acceptance(offer, acceptance)
        frozen_acceptance = json.dumps(acceptance, sort_keys=True)
        acceptance_crossing = make_acceptance_crossing(
            offer,
            acceptance,
            signer=buyer,
            node_id="lightwalker-market-034-buyer",
        )
        assert verify_crossing(acceptance_crossing)
        assert acceptance_crossing["requested_effect"]["automatic_settlement_requested"] is False

        delivery_evidence = content_address(
            {
                "kind": "simulation.delivery-evidence",
                "acceptance_id": acceptance["acceptance_id"],
                "deliverable_ref": offer["deliverable_ref"],
                "render_address": result["render_address"],
            }
        )
        consideration_evidence = content_address(
            {
                "kind": "simulation.consideration-evidence",
                "acceptance_id": acceptance["acceptance_id"],
                "realm_id": offer["consideration"]["realm_id"],
                "unit": offer["consideration"]["unit"],
                "quantity": offer["consideration"]["quantity"],
            }
        )

        delivery = sign_performance(
            offer,
            acceptance,
            role="DELIVERY",
            signer=seller,
            evidence_ref=delivery_evidence,
        )

        unilateral_refused = False
        try:
            settle(offer, acceptance, [delivery])
        except LightwalkerEconomyError:
            unilateral_refused = True
        assert unilateral_refused

        consideration = sign_performance(
            offer,
            acceptance,
            role="CONSIDERATION",
            signer=buyer,
            evidence_ref=consideration_evidence,
        )
        settlement = settle(
            offer,
            acceptance,
            [delivery, consideration],
        )
        assert verify_settlement(
            offer,
            acceptance,
            [delivery, consideration],
            settlement,
        )

        settlement_crossing = make_settlement_crossing(
            settlement,
            signer=seller,
            node_id="lightwalker-market-034-settlement",
        )
        assert verify_crossing(settlement_crossing)
        assert settlement_crossing["requested_effect"]["mint_authority_requested"] is False
        assert settlement_crossing["requested_effect"]["balance_mutation_requested"] is False
        assert settlement_crossing["requested_effect"]["ownership_transfer_inferred"] is False

        assert json.dumps(workmark, sort_keys=True) == frozen_workmark
        assert json.dumps(projection, sort_keys=True) == frozen_projection
        assert json.dumps(offer, sort_keys=True) == frozen_offer
        assert json.dumps(acceptance, sort_keys=True) == frozen_acceptance

        packet_path = worker_root / "lightwalker" / "market-034.v0.json"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps(
                {
                    "workmark": workmark,
                    "projection": projection,
                    "offer": offer,
                    "offer_crossing": offer_crossing,
                    "acceptance": acceptance,
                    "acceptance_crossing": acceptance_crossing,
                    "delivery_attestation": delivery,
                    "consideration_attestation": consideration,
                    "settlement": settlement,
                    "settlement_crossing": settlement_crossing,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        inbox = StateParcelInbox(market_receiver_root)
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
            note="034 admit bilateral settlement evidence; no balance or ownership mutation inferred",
        )
        assert admitted["kind"] == "ADMITTED"

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "projection": {
                        "quantity": projection["quantity"],
                        "unit": projection["unit"],
                    },
                    "offer": {
                        "quantity": offer["consideration"]["quantity"],
                        "unit": offer["consideration"]["unit"],
                        "differs_from_projection": True,
                    },
                    "acceptance": {
                        "status": acceptance["status"],
                        "settlement_implied": False,
                    },
                    "performance": {
                        "unilateral_settlement_refused": unilateral_refused,
                        "delivery_signed_by_offeror": True,
                        "consideration_signed_by_acceptor": True,
                    },
                    "settlement": {
                        "settlement_id": settlement["settlement_id"],
                        "status": settlement["status"],
                        "authority": settlement["authority"],
                        "mint_authority_requested": False,
                        "balance_mutation_requested": False,
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
                        "VALUATION != OFFER",
                        "OFFER != ACCEPTANCE",
                        "ACCEPTANCE != PERFORMANCE",
                        "PERFORMANCE != SETTLEMENT",
                        "SETTLEMENT != WORKMARK",
                        "SETTLEMENT DOES NOT CREATE UNIVERSAL MONEY",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
