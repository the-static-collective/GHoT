#!/usr/bin/env python3
"""Experiment 033 — later consequences re-project without rewriting history."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from dogram_contribution_bridge import run_contribution_field
from ice_cube import build_work, mine_ice_cube
from lightwalker_temporal_economy import (
    ASSAY_LENS_KIND,
    ASSAY_LENS_VERSION,
    make_assay_projection_crossing,
    project_measurement,
    verify_dogram_measurement,
    verify_dogram_workmark,
)
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
        receiver_root = root / "realm-receiver"

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
        worker_particular = mined["execution_receipt"]["receiver_particular"]
        first_descendant = "artifact-use:" + result["render_address"]
        second_descendant = "derived-study:" + result["specimen_address"]

        events = [
            {
                "event_id": "e-ice-birth",
                "relation_kind": "CREATED",
                "source_ref": worker_particular,
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
            {
                "event_id": "e-root-challenged",
                "relation_kind": "CHALLENGED",
                "source_ref": "realm:independent-reviewer",
                "subject_ref": contribution_root,
                "evidence_ref": result["dogram_receipt_address"],
                "evidence_status": "complete",
                "available_from": 1,
            },
        ]

        field = run_contribution_field(
            args.dogram_contribution_repo,
            events=events,
            declared_relation_kinds=("CREATED", "ENABLED", "CARRIED", "CHALLENGED"),
            birth_event_id="e-ice-birth",
            birth_cut=0,
            before_cut=0,
            after_cut=1,
        )
        workmark = field["workmark"]
        before = field["before"]
        after = field["after"]
        delta = field["delta"]

        assert verify_dogram_workmark(workmark)
        assert verify_dogram_measurement(before)
        assert verify_dogram_measurement(after)
        assert before["workmark"] == after["workmark"] == workmark
        assert before["measurements"]["descendant_count"] == 0
        assert after["measurements"]["descendant_count"] == 2
        assert delta["descendant_count_delta"] == 2

        frozen_birth = json.dumps(workmark, sort_keys=True)

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
                "The Realm chooses descendant count as one bounded economic input.",
                "Dogram does not endorse this exchange policy.",
                "A new cut creates a new projection rather than rewriting an old one.",
            ],
        }

        projection_t0 = project_measurement(workmark, before, lens)
        frozen_projection_t0 = json.dumps(projection_t0, sort_keys=True)
        projection_t1 = project_measurement(workmark, after, lens)

        assert projection_t0["quantity"] == 7
        assert projection_t1["quantity"] == 13
        assert projection_t0["workmark_id"] == projection_t1["workmark_id"]
        assert projection_t0["lens_id"] == projection_t1["lens_id"]
        assert projection_t0["projection_id"] != projection_t1["projection_id"]
        assert json.dumps(workmark, sort_keys=True) == frozen_birth
        assert json.dumps(projection_t0, sort_keys=True) == frozen_projection_t0

        realm_signer = IdentityKey.load_or_create(
            root / "realm-identity" / "body-p256.pem"
        )
        crossing = make_assay_projection_crossing(
            projection_t1,
            signer=realm_signer,
            node_id="lightwalker-time-assay-033",
        )
        assert verify_crossing(crossing)
        assert crossing["requested_effect"]["mint_authority_requested"] is False
        assert (
            crossing["requested_effect"]["retroactive_repricing_requested"] is False
        )

        packet_path = worker_root / "lightwalker" / "assay-033.v0.json"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps(
                {
                    "workmark": workmark,
                    "measurement_before": before,
                    "measurement_after": after,
                    "delta": delta,
                    "lens": lens,
                    "projection_t0": projection_t0,
                    "projection_t1": projection_t1,
                    "projection_t1_crossing": crossing,
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
            note="033 admit later assay projection as local information, not retroactive payment",
        )
        assert admitted["kind"] == "ADMITTED"

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "workmark": {
                        "workmark_id": workmark["workmark_id"],
                        "birth_unchanged": True,
                        "contribution_root": workmark["contribution_root"],
                    },
                    "time_assay": {
                        "before_cut": before["cut"],
                        "after_cut": after["cut"],
                        "descendants_before": before["measurements"][
                            "descendant_count"
                        ],
                        "descendants_after": after["measurements"][
                            "descendant_count"
                        ],
                        "delta": delta["descendant_count_delta"],
                    },
                    "realm_projection": {
                        "lens_same": projection_t0["lens_id"]
                        == projection_t1["lens_id"],
                        "t0": {
                            "projection_id": projection_t0["projection_id"],
                            "quantity": projection_t0["quantity"],
                            "unit": projection_t0["unit"],
                        },
                        "t1": {
                            "projection_id": projection_t1["projection_id"],
                            "quantity": projection_t1["quantity"],
                            "unit": projection_t1["unit"],
                        },
                        "t0_unchanged_after_t1": True,
                    },
                    "crossing": {
                        "verified": True,
                        "held_first": held["kind"],
                        "owner_disposition": admitted["kind"],
                        "mint_authority_requested": False,
                        "retroactive_repricing_requested": False,
                    },
                    "laws": [
                        "WORKMARK != MEASUREMENT != VALUATION",
                        "LATER HISTORY MAY ENRICH THE FIELD",
                        "LATER HISTORY MAY NOT REWRITE BIRTH",
                        "NEW MEASUREMENT MAY CREATE NEW PROJECTION",
                        "NEW PROJECTION MAY NOT REWRITE OLD PROJECTION",
                        "TIME ASSAYS THE ORE; THE REALM NAMES ITS EXCHANGE RATE",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
