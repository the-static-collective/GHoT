#!/usr/bin/env python3
"""End-to-end Ice Field ecology proof for Experiment 033."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import energy_scheduler
import reference_node
from ice_cube import ICE_CUBE_CAPABILITY, build_work, execute_capability, mine_ice_cube
from ice_cube_return import IceCubeReturnInbox, make_return_bundle
from ice_field import IceFieldStore
from lan_node import send_json
from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from state_merge import MERGE_CONTRACTS, StateMergeEngine, verify_merge_receipt
from state_parcel import parcel_handler


PACKAGE_ID = "ghot.plugin.verified-ice-cube"
CONTRACT_ID = "ghot.ice-cube-result->verified-ice-cube-catalog/v0"


def power(willingness: str) -> dict[str, Any]:
    abundant = willingness == "abundant"
    return {
        "source": "solar" if abundant else "battery",
        "battery_percent": 95 if abundant else 80,
        "charging": abundant,
        "renewable_surplus": abundant,
        "temperature_c": 42,
        "thermal_state": "normal",
        "load_per_cpu_1m": 0.05,
        "willingness": willingness,
        "willingness_reasons": ["033 simulation"],
    }


def body_candidate(
    node_id: str,
    *,
    location: str,
    willingness: str,
    url: str | None,
) -> dict[str, Any]:
    abundant = willingness == "abundant"
    return {
        "node_id": node_id,
        "location": location,
        "url": url,
        "field_state": "awake",
        "body": {
            "kind": "ghot.body",
            "version": "0",
            "node_id": node_id,
            "identity": {
                "available": True,
                "particular": f"particular:{node_id}",
                "public_key": {},
                "profile": "relatte.identity-signature/v0",
            },
            "power": {
                **power(willingness),
                "charging": abundant,
            },
            "offers": [{
                "kind": "ghot.offer",
                "version": "0",
                "capability": ICE_CUBE_CAPABILITY,
                "available": True,
                "executor": "ghot.ice-cube",
                "power": {
                    "class": "heavy",
                    "willingness": willingness,
                    "policy_reasons": [],
                },
            }],
        },
    }


def install_and_merge(root: Path, parcel_id: str, package: dict[str, Any]) -> None:
    install = MergePluginStore(root).install(
        package,
        builtin_contract_ids=set(MERGE_CONTRACTS),
    )
    assert verify_install_receipt(install)
    pantry = MergeContractPantry(root)
    inspection = pantry.inspect(parcel_id)
    assert CONTRACT_ID in inspection["compatible_contract_ids"]
    selection = pantry.select(parcel_id, CONTRACT_ID)
    proposal = pantry.propose(selection["selection_id"])
    receipt = StateMergeEngine(root).apply(
        proposal["plan"]["plan_id"],
        note="033 Ice Field specimen enters local verified pantry",
    )
    assert verify_merge_receipt(receipt)


def admit_return(
    inbox: IceCubeReturnInbox,
    parcel_id: str,
    dogram_repo: Path,
    package: dict[str, Any],
) -> dict[str, Any]:
    verified = inbox.verify_local(parcel_id, dogram_repo=dogram_repo)
    assert verified["status"] == "VERIFIED"
    admitted = inbox.admit_verified(
        parcel_id,
        note="033 owner-local admission after receiver Dogram verification",
    )
    assert admitted["admission_receipt"]["kind"] == "ADMITTED"
    install_and_merge(inbox.root, parcel_id, package)
    return admitted


def find_return_for_work(
    inbox: IceCubeReturnInbox,
    work_address: str,
) -> str:
    for row in inbox.list():
        parcel_id = str(row["parcel_id"])
        shown = inbox.show(parcel_id)
        result = shown["return_bundle"]["state_parcel_bundle"]["parcel"]["payload"]["value"]
        if result.get("work_address") == work_address:
            return parcel_id
    raise AssertionError(f"no returned parcel for work {work_address}")


class RemoteTaskService:
    def __init__(self, root: Path) -> None:
        self.root = root
        service = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "GHoTIceFieldRemote/0"

            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def do_POST(self) -> None:
                if self.path != "/task":
                    send_json(self, 404, {"error": "not found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    incoming = json.loads(self.rfile.read(length).decode("utf-8"))
                    if incoming.get("capability") != ICE_CUBE_CAPABILITY:
                        raise ValueError("033 remote only accepts Ice Cube capability")
                    payload = incoming.get("input")
                    output = execute_capability(payload, worker_root=service.root)
                    task_id = f"task-{uuid.uuid4()}"
                    send_json(self, 200, {
                        "task": {
                            "kind": "ghot.task",
                            "version": "0",
                            "task_id": task_id,
                            "capability": ICE_CUBE_CAPABILITY,
                            "input": payload,
                            "constraints": incoming.get("constraints") or {},
                        },
                        "receipt": {
                            "kind": "ghot.receipt",
                            "version": "0",
                            "receipt_id": f"receipt-{uuid.uuid4()}",
                            "task_id": task_id,
                            "capability": ICE_CUBE_CAPABILITY,
                            "status": "ok",
                            "output": output,
                            "error": None,
                        },
                    })
                except Exception as exc:
                    send_json(self, 400, {
                        "error": f"{type(exc).__name__}: {exc}",
                    })

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dogram-repo", type=Path, required=True)
    args = parser.parse_args()
    dogram_repo = args.dogram_repo.resolve()

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
        receiver_root = base / "receiver"
        seed_worker = base / "seed-worker"
        remote_worker = base / "remote-worker"

        os.environ["GHOT_DOGRAM_REPO"] = str(dogram_repo)

        inbox = IceCubeReturnInbox(receiver_root)
        target_particular = inbox.signer.particular()

        # Seed one verified cube and explicitly bring it into the pantry.
        seed = mine_ice_cube(
            worker_root=seed_worker,
            dogram_repo=dogram_repo,
            work=build_work(
                lucas_index=2,
                width=24,
                height=24,
                max_halley_iter=8,
            ),
        )
        seed_bundle = make_return_bundle(
            seed_worker,
            seed["result_path"],
            target_particular=target_particular,
            chunk_size=97,
        )
        held = inbox.receive(seed_bundle)
        assert held["kind"] == "HELD"
        seed_parcel_id = seed_bundle["state_parcel_bundle"]["parcel"]["parcel_id"]
        admit_return(inbox, seed_parcel_id, dogram_repo, package)

        field = IceFieldStore(receiver_root)
        first_refresh = field.refresh()
        first_wants = field.wants()
        assert first_refresh["pantry_entries"] == 1
        assert len(first_wants) == 5
        assert {item["relation"] for item in first_wants} == {
            "lucas-next",
            "c-real-minus",
            "c-real-plus",
            "c-imag-minus",
            "c-imag-plus",
        }

        want = next(item for item in first_wants if item["relation"] == "lucas-next")
        expected_work_address = want["work_address"]

        # Receiver porch for the child to come home through 032.
        porch = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            parcel_handler(receiver_root),
        )
        porch_thread = threading.Thread(target=porch.serve_forever, daemon=True)
        porch_thread.start()
        porch_url = f"http://127.0.0.1:{porch.server_port}"

        remote = RemoteTaskService(remote_worker)
        remote.start()

        original_gather = energy_scheduler.gather_candidates
        try:
            candidates = [
                body_candidate(
                    "node-local-normal",
                    location="local",
                    willingness="normal",
                    url=None,
                ),
                body_candidate(
                    "node-remote-surplus",
                    location="remote",
                    willingness="abundant",
                    url=remote.url,
                ),
            ]
            energy_scheduler.gather_candidates = lambda timeout: (
                candidates,
                {"policy": {"simulation": "033"}},
            )

            dispatched = field.dispatch(
                want["want_id"],
                return_url=porch_url,
                return_particular=target_particular,
                timeout=0.01,
                return_chunk_size=101,
            )
        finally:
            energy_scheduler.gather_candidates = original_gather
            remote.close()
            porch.shutdown()
            porch.server_close()
            porch_thread.join(timeout=2)

        assert dispatched["status"] == "ok"
        plan = dispatched["energy_plan"]
        assert plan["action"] == "run_there"
        assert plan["selected"]["node_id"] == "node-remote-surplus"
        output = dispatched["execution"]["receipt"]["output"]
        assert output["work_address"] == expected_work_address
        assert output["dogram_status"] == "OK"
        assert output["verified_return"]["receiver_disposition"] == "HELD"
        assert output["verified_return"]["receiver_semantic_effect"] == "none"

        child_parcel_id = find_return_for_work(inbox, expected_work_address)
        child_before = inbox.show(child_parcel_id)
        assert child_before["status"]["verification_status"] == "UNVERIFIED"
        assert child_before["state_parcel"]["queue"]["status"] == "HOLD"

        admit_return(inbox, child_parcel_id, dogram_repo, package)

        second_refresh = field.refresh()
        refreshed_want = field.load(want["want_id"])
        assert refreshed_want["status"] == "satisfied"
        assert want["want_id"] in second_refresh["newly_satisfied"]

        catalog = json.loads(field.catalog_path.read_text(encoding="utf-8"))
        assert len(catalog["entries"]) == 2
        all_wants = field.wants()
        child_specimen_id = output["specimen_id"]
        second_generation = [
            item for item in all_wants
            if item.get("parent_specimen_id") == child_specimen_id
        ]
        assert second_generation

        summary = {
            "simulation_passed": True,
            "seed": {
                "specimen_id": seed["specimen"]["specimen_id"],
                "first_generation_wants": len(first_wants),
                "relations": sorted(item["relation"] for item in first_wants),
            },
            "selection": {
                "local_power": "normal",
                "remote_power": "abundant",
                "decision": plan["action"],
                "selected_node_id": plan["selected"]["node_id"],
                "selected_relation": want["relation"],
            },
            "remote_mining": {
                "work_address": output["work_address"],
                "dogram_status": output["dogram_status"],
                "return_disposition": output["verified_return"]["receiver_disposition"],
            },
            "home": {
                "receiver_reverified": True,
                "owner_admitted": True,
                "pantry_entries": len(catalog["entries"]),
            },
            "field_growth": {
                "completed_want_status": refreshed_want["status"],
                "total_wants": len(all_wants),
                "second_generation_wants": len(second_generation),
            },
        }
        print(json.dumps(summary, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
