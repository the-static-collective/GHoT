#!/usr/bin/env python3
"""Deterministic cross-repo simulation for GHoT Experiment 030."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import tempfile
from pathlib import Path

from ice_cube import build_work, mine_ice_cube
from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from relatte_identity import verify_crossing, verify_receipt
from state_merge import MERGE_CONTRACTS, StateMergeEngine, verify_merge_receipt
from state_parcel import StateParcelExporter, StateParcelInbox


PACKAGE_ID = "ghot.plugin.verified-ice-cube"
CONTRACT_ID = "ghot.ice-cube-result->verified-ice-cube-catalog/v0"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dogram-repo",
        type=Path,
        required=True,
        help="checkout of Dogram branch impl/ice-cube-001",
    )
    parser.add_argument("--width", type=int, default=48)
    parser.add_argument("--height", type=int, default=48)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    package = json.loads(
        (
            repo_root
            / "examples"
            / "merge-plugins"
            / "verified-ice-cube.package.json"
        ).read_text(encoding="utf-8")
    )

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        worker_root = base / "worker"
        receiver_root = base / "receiver"

        receiver_inbox = StateParcelInbox(receiver_root)
        plugin_receipt = MergePluginStore(receiver_root).install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        assert verify_install_receipt(plugin_receipt)

        work = build_work(
            lucas_index=5,
            width=args.width,
            height=args.height,
            max_halley_iter=10,
        )
        mined = mine_ice_cube(
            worker_root=worker_root,
            dogram_repo=args.dogram_repo,
            work=work,
        )

        # Separate witnesses stay separate.
        assert verify_crossing(mined["work_crossing"])
        assert verify_receipt(mined["execution_receipt"])
        assert mined["dogram_receipt"]["status"] == "OK"
        assert mined["execution_receipt"]["receipt_id"] != mined[
            "dogram_receipt_address"
        ]

        # reLATTE-shaped GHoT state parcel carries the result without learning
        # Mandelbrot, Lucas, Halley, or mapping-torus semantics.
        exporter = StateParcelExporter(worker_root)
        bundle = exporter.export(
            mined["result_relative_path"],
            selector="$",
            target_particular=receiver_inbox.signer.particular(),
        )
        held = receiver_inbox.receive(bundle)
        parcel_id = bundle["parcel"]["parcel_id"]
        assert held["kind"] == "HELD"
        assert held["semantic_effect"] == "none"
        assert receiver_inbox.show(parcel_id)["queue"]["status"] == "HOLD"

        admitted = receiver_inbox.decide(
            parcel_id,
            "ADMIT",
            note="030 owner-local admission after bounded Dogram verification",
        )
        assert admitted["kind"] == "ADMITTED"
        assert receiver_inbox.show(parcel_id)["queue"]["status"] == "ADMIT"

        # Explicit local grammar selection then creates the pantry entry.
        pantry = MergeContractPantry(receiver_root)
        inspection = pantry.inspect(parcel_id)
        assert CONTRACT_ID in inspection["compatible_contract_ids"]
        selection = pantry.select(parcel_id, CONTRACT_ID)
        proposal = pantry.propose(selection["selection_id"])
        merge_receipt = StateMergeEngine(receiver_root).apply(
            proposal["plan"]["plan_id"],
            note="030 merge verified Ice Cube into local pantry",
        )
        assert verify_merge_receipt(merge_receipt)
        assert merge_receipt["disposition"] == "APPLY"

        catalog_path = (
            receiver_root
            / "knowledge"
            / "plugins"
            / PACKAGE_ID
            / "verified-ice-cubes.v0.json"
        )
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert catalog["kind"] == "ghot.verified-ice-cube-catalog"
        assert len(catalog["entries"]) == 1
        entry = catalog["entries"][0]
        assert entry["specimen_id"] == mined["specimen"]["specimen_id"]
        assert entry["dogram_status"] == "OK"

        # The parcel carried the actual frozen artifact, not merely a pointer.
        admitted_payload = receiver_inbox.show(parcel_id)["bundle"]["parcel"][
            "payload"
        ]["value"]
        returned_render = base64.b64decode(admitted_payload["render_base64"])
        returned_address = "sha256:" + hashlib.sha256(returned_render).hexdigest()
        assert returned_address == mined["specimen"]["render"]["address"]

        summary = {
            "simulation_passed": True,
            "math": {
                "lucas_index": work["lucas_index"],
                "lucas_value": mined["specimen"]["lucas_value"],
                "period": work["period"],
                "monodromy": mined["specimen"]["monodromy"],
                "mapping_torus": mined["specimen"]["mapping_torus"],
            },
            "witness_split": {
                "ghot_execution_receipt_verified": True,
                "dogram_status": mined["dogram_receipt"]["status"],
                "dogram_claim_scope": mined["dogram_receipt"]["result"][
                    "claim_scope"
                ],
                "relatte_work_crossing_verified": True,
            },
            "crossing": {
                "receive_disposition": held["kind"],
                "receive_semantic_effect": held["semantic_effect"],
                "owner_disposition": admitted["kind"],
            },
            "pantry": {
                "contract_id": CONTRACT_ID,
                "merge_receipt_verified": True,
                "entries": len(catalog["entries"]),
                "specimen_id": entry["specimen_id"],
            },
            "artifact": {
                "render_address": returned_address,
                "render_crossed_with_result": True,
            },
        }
        print(json.dumps(summary, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
