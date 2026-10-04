#!/usr/bin/env python3
"""End-to-end return-home proof for GHoT Experiment 032."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from ice_cube import build_work, content_address, mine_ice_cube
from ice_cube_return import (
    IceCubeReturnInbox,
    make_return_bundle,
    send_return_bundle,
    verify_return_bundle,
)
from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from relatte_identity import verify_receipt
from state_merge import MERGE_CONTRACTS, StateMergeEngine, verify_merge_receipt
from state_parcel import parcel_handler


PACKAGE_ID = "ghot.plugin.verified-ice-cube"
CONTRACT_ID = "ghot.ice-cube-result->verified-ice-cube-catalog/v0"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dogram-repo", type=Path, required=True)
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

        receiver = IceCubeReturnInbox(receiver_root)
        target_particular = receiver.signer.particular()

        work = build_work(
            lucas_index=3,
            width=32,
            height=32,
            max_halley_iter=9,
        )
        mined = mine_ice_cube(
            worker_root=worker_root,
            dogram_repo=args.dogram_repo,
            work=work,
        )
        assert mined["dogram_receipt"]["status"] == "OK"

        bundle = make_return_bundle(
            worker_root,
            mined["result_path"],
            target_particular=target_particular,
            chunk_size=113,
        )
        assert verify_return_bundle(bundle)
        parcel_id = bundle["state_parcel_bundle"]["parcel"]["parcel_id"]
        assert len(bundle["chunks"]) > 1

        # A mutated chunk cannot ride the valid manifest/crossing.
        damaged = copy.deepcopy(bundle)
        first = damaged["chunks"][0]
        raw = bytearray(base64.b64decode(first["data"]))
        raw[0] ^= 0x01
        first["data"] = base64.b64encode(bytes(raw)).decode("ascii")
        assert not verify_return_bundle(damaged)

        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            parcel_handler(receiver_root),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"

        try:
            # Network arrival proves only HOLD.
            held = send_return_bundle(bundle, base_url)
            assert held["kind"] == "HELD"
            assert held["semantic_effect"] == "none"
            state = receiver.show(parcel_id)
            assert state["state_parcel"]["queue"]["status"] == "HOLD"
            assert state["status"]["verification_status"] == "UNVERIFIED"

            # Local ADMIT is gated on receiver-local verification.
            blocked_before_verify = False
            try:
                receiver.admit_verified(parcel_id)
            except ValueError:
                blocked_before_verify = True
            assert blocked_before_verify
            assert receiver.show(parcel_id)["state_parcel"]["queue"]["status"] == "HOLD"

            # Receiver independently replays Dogram against the returned bytes.
            verified = receiver.verify_local(
                parcel_id,
                dogram_repo=args.dogram_repo,
            )
            assert verified["status"] == "VERIFIED"
            assert verified["dogram_receipt"]["status"] == "OK"
            assert verify_receipt(verified["verification_receipt"])
            extensions = verified["verification_receipt"]["extensions"]
            assert extensions["independent_reverification"] is True
            assert extensions["worker_verification_is_not_authority"] is True
            assert extensions["verification_is_not_admission"] is True

            # Verification still leaves the State Parcel in HOLD.
            assert receiver.show(parcel_id)["state_parcel"]["queue"]["status"] == "HOLD"

            admitted = receiver.admit_verified(
                parcel_id,
                note="032 owner admits independently reverified returned cube",
            )
            admission_receipt = admitted["admission_receipt"]
            assert admission_receipt["kind"] == "ADMITTED"
            assert verify_receipt(admission_receipt)

            render_path = Path(admitted["render_path"])
            result_path = Path(admitted["result_path"])
            assert render_path.is_file()
            assert result_path.is_file()
            returned_result = json.loads(result_path.read_text(encoding="utf-8"))
            returned_render_address = (
                "sha256:" + hashlib.sha256(render_path.read_bytes()).hexdigest()
            )
            assert returned_render_address == returned_result["render_address"]
            assert content_address(returned_result["specimen"]) == returned_result[
                "specimen_address"
            ]

            # Because the return is still an ordinary ADMITTED State Parcel,
            # 030's explicit pantry grammar composes without a new authority path.
            install = MergePluginStore(receiver_root).install(
                package,
                builtin_contract_ids=set(MERGE_CONTRACTS),
            )
            assert verify_install_receipt(install)

            pantry = MergeContractPantry(receiver_root)
            inspection = pantry.inspect(parcel_id)
            assert CONTRACT_ID in inspection["compatible_contract_ids"]
            selection = pantry.select(parcel_id, CONTRACT_ID)
            proposal = pantry.propose(selection["selection_id"])
            merge_receipt = StateMergeEngine(receiver_root).apply(
                proposal["plan"]["plan_id"],
                note="032 merge returned verified cube into pantry",
            )
            assert verify_merge_receipt(merge_receipt)

            catalog_path = (
                receiver_root
                / "knowledge"
                / "plugins"
                / PACKAGE_ID
                / "verified-ice-cubes.v0.json"
            )
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            assert len(catalog["entries"]) == 1
            entry = catalog["entries"][0]
            assert entry["specimen_id"] == mined["specimen"]["specimen_id"]
            assert entry["render_address"] == returned_render_address
            assert entry["dogram_status"] == "OK"

            summary = {
                "simulation_passed": True,
                "return_transport": {
                    "chunked": True,
                    "chunk_count": len(bundle["chunks"]),
                    "state_parcel_crossing_verified": True,
                    "tampered_chunk_refused": True,
                },
                "network": {
                    "arrival_disposition": held["kind"],
                    "semantic_effect": held["semantic_effect"],
                },
                "receiver_gate": {
                    "admit_before_verify_blocked": blocked_before_verify,
                    "local_dogram_status": verified["dogram_receipt"]["status"],
                    "verification_receipt_verified": True,
                    "still_hold_after_verify": True,
                    "owner_disposition": admission_receipt["kind"],
                },
                "artifact": {
                    "specimen_id": entry["specimen_id"],
                    "render_address": returned_render_address,
                    "materialized_on_requester": True,
                },
                "pantry": {
                    "merge_receipt_verified": True,
                    "entries": len(catalog["entries"]),
                    "contract_id": CONTRACT_ID,
                },
            }
            print(json.dumps(summary, indent=2))
            return 0
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
