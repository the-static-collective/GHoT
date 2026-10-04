#!/usr/bin/env python3
"""Deterministic Lightwalker Economy 001 vertical-slice simulation."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from ice_cube import build_work, mine_ice_cube
from lightwalker_economy import (
    LENS_KIND,
    LENS_VERSION,
    make_projection_crossing,
    mint_workmark_from_ice_cube,
    project_workmark,
    verify_workmark,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dogram-repo",
        type=Path,
        required=True,
        help="checkout of Dogram branch impl/ice-cube-001",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        worker_root = root / "worker"
        receiver_root = root / "receiver"

        work = build_work(
            lucas_index=5,
            width=24,
            height=24,
            max_halley_iter=8,
        )
        mined = mine_ice_cube(
            worker_root=worker_root,
            dogram_repo=args.dogram_repo,
            work=work,
        )

        workmark = mint_workmark_from_ice_cube(mined["result"])
        assert verify_workmark(workmark)
        original_workmark = json.dumps(workmark, sort_keys=True)

        lantern_lens = {
            "kind": LENS_KIND,
            "version": LENS_VERSION,
            "realm_id": "realm:lantern",
            "unit": "lumen",
            "policy": {
                "basis": "fixed-per-verified-workmark",
                "amount": 7,
            },
            "assumptions": [
                "This Realm rewards one bounded verified artifact as one participation event.",
                "The quantity is local policy, not a Dogram measurement.",
            ],
        }
        forge_lens = {
            "kind": LENS_KIND,
            "version": LENS_VERSION,
            "realm_id": "realm:forge",
            "unit": "compute-credit",
            "policy": {
                "basis": "fixed-per-verified-workmark",
                "amount": 96,
            },
            "assumptions": [
                "This Realm uses a different exchange policy over the same history.",
            ],
        }
        witness_only_lens = {
            "kind": LENS_KIND,
            "version": LENS_VERSION,
            "realm_id": "realm:witness",
            "unit": None,
            "policy": {
                "basis": "no-economic-interpretation",
            },
            "assumptions": [
                "This Realm records the Workmark without assigning economic quantity.",
            ],
        }

        lantern = project_workmark(workmark, lantern_lens)
        forge = project_workmark(workmark, forge_lens)
        witness_only = project_workmark(workmark, witness_only_lens)

        assert lantern["workmark_id"] == forge["workmark_id"] == workmark["workmark_id"]
        assert witness_only["workmark_id"] == workmark["workmark_id"]
        assert lantern["projection_id"] != forge["projection_id"]
        assert lantern["unit"] == "lumen" and lantern["quantity"] == 7
        assert forge["unit"] == "compute-credit" and forge["quantity"] == 96
        assert witness_only["status"] == "NO_ECONOMIC_INTERPRETATION"
        assert witness_only["quantity"] is None
        assert json.dumps(workmark, sort_keys=True) == original_workmark

        realm_signer = IdentityKey.load_or_create(
            root / "realm-identity" / "body-p256.pem"
        )
        crossing = make_projection_crossing(
            lantern,
            signer=realm_signer,
            node_id="lightwalker-economy-032",
        )
        assert verify_crossing(crossing)
        assert crossing["requested_effect"]["mint_authority_requested"] is False

        bundle_path = worker_root / "lightwalker" / "projection-bundle.v0.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(
            json.dumps(
                {
                    "workmark": workmark,
                    "lens": lantern_lens,
                    "projection": lantern,
                    "projection_crossing": crossing,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        inbox = StateParcelInbox(receiver_root)
        exporter = StateParcelExporter(worker_root)
        parcel_bundle = exporter.export(
            str(bundle_path.relative_to(worker_root)),
            selector="$",
            target_particular=inbox.signer.particular(),
        )
        held = inbox.receive(parcel_bundle)
        assert held["kind"] == "HELD"
        assert held["semantic_effect"] == "none"

        parcel_id = parcel_bundle["parcel"]["parcel_id"]
        admitted = inbox.decide(
            parcel_id,
            "ADMIT",
            note="032 admit economic projection as local information, not automatic payment",
        )
        assert admitted["kind"] == "ADMITTED"

        summary = {
            "simulation_passed": True,
            "workmark": {
                "workmark_id": workmark["workmark_id"],
                "authority": workmark["authority"],
                "dogram_status": workmark["declared_facts"]["dogram_status"],
                "money_field_present": "money" in workmark,
                "score_field_present": "score" in workmark,
            },
            "realm_projections": [
                {
                    "realm_id": lantern["realm_id"],
                    "projection_id": lantern["projection_id"],
                    "unit": lantern["unit"],
                    "quantity": lantern["quantity"],
                },
                {
                    "realm_id": forge["realm_id"],
                    "projection_id": forge["projection_id"],
                    "unit": forge["unit"],
                    "quantity": forge["quantity"],
                },
                {
                    "realm_id": witness_only["realm_id"],
                    "projection_id": witness_only["projection_id"],
                    "status": witness_only["status"],
                    "unit": witness_only["unit"],
                    "quantity": witness_only["quantity"],
                },
            ],
            "crossing": {
                "verified": True,
                "declared_kind": crossing["declared_kind"],
                "requested_effect": crossing["requested_effect"],
                "receiver_first_disposition": held["kind"],
                "receiver_local_disposition": admitted["kind"],
            },
            "laws": [
                "ACT != WORKMARK",
                "WORKMARK != MONEY",
                "VERIFICATION != VALUATION",
                "SAME WORKMARK MAY HAVE MANY REALM-LOCAL PROJECTIONS",
                "PROJECTION MAY NOT REWRITE WORKMARK",
                "DELIVERY != PAYMENT",
            ],
        }
        print(json.dumps(summary, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
