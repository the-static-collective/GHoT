#!/usr/bin/env python3
"""Closed-loop FIELD COMMONS 001 proof."""

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
from field_commons import (
    FieldCommonsStore,
    accept_commons_offer,
    make_artifact_for_compute_offer,
    verify_artifact_access_grant,
)
from ice_cube import ICE_CUBE_CAPABILITY, build_work, execute_capability, mine_ice_cube
from ice_cube_return import IceCubeReturnInbox, make_return_bundle
from ice_field import IceFieldStore
from lan_node import send_json
from lightwalker_guild_authorization import (
    authorize_resource_proposal,
    make_resource_proposal,
    verify_execution_receipt,
)
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    verify_exchange_settlement,
)
from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from relatte_identity import IdentityKey
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
        "willingness_reasons": ["Field Commons 001 simulation"],
    }


def candidate(
    node_id: str,
    *,
    location: str,
    willingness: str,
    url: str | None,
) -> dict[str, Any]:
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
            "power": power(willingness),
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
        note="Field Commons verified cube enters local pantry",
    )
    assert verify_merge_receipt(receipt)


def admit_return(
    inbox: IceCubeReturnInbox,
    parcel_id: str,
    dogram_repo: Path,
    package: dict[str, Any],
) -> None:
    verified = inbox.verify_local(parcel_id, dogram_repo=dogram_repo)
    assert verified["status"] == "VERIFIED"
    admitted = inbox.admit_verified(
        parcel_id,
        note="Field Commons owner-local admission after independent Dogram",
    )
    assert admitted["admission_receipt"]["kind"] == "ADMITTED"
    install_and_merge(inbox.root, parcel_id, package)


def find_return_for_work(inbox: IceCubeReturnInbox, work_address: str) -> str:
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
            server_version = "GHoTFieldCommonsRemote/0"

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
                        raise ValueError("remote only accepts Ice Cube capability")
                    output = execute_capability(
                        incoming.get("input"),
                        worker_root=service.root,
                    )
                    task_id = f"task-{uuid.uuid4()}"
                    send_json(self, 200, {
                        "task": {
                            "kind": "ghot.task",
                            "version": "0",
                            "task_id": task_id,
                            "capability": ICE_CUBE_CAPABILITY,
                            "input": incoming.get("input"),
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
                    send_json(self, 400, {"error": f"{type(exc).__name__}: {exc}"})

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

        artifact_owner = IdentityKey.load_or_create(base / "keys" / "owner.pem")
        guild = IdentityKey.load_or_create(base / "keys" / "guild.pem")

        inbox = IceCubeReturnInbox(receiver_root)
        target_particular = inbox.signer.particular()

        # Seed the commons with one already admitted verified artifact.
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
        seed_held = inbox.receive(seed_bundle)
        assert seed_held["kind"] == "HELD"
        seed_parcel_id = seed_bundle["state_parcel_bundle"]["parcel"]["parcel_id"]
        admit_return(inbox, seed_parcel_id, dogram_repo, package)

        field = IceFieldStore(receiver_root)
        field.refresh()
        want = next(
            item for item in field.wants()
            if item["relation"] == "lucas-next"
        )

        # Voluntary heterogeneous exchange: verified artifact access for one
        # bounded compute service. There is no common scalar.
        artifact_ref = seed["specimen"]["render"]["address"]
        offer = make_artifact_for_compute_offer(
            artifact_owner=artifact_owner,
            guild_particular=guild.particular(),
            artifact_ref=artifact_ref,
            want=want,
            valid_through_cut=20,
        )
        acceptance = accept_commons_offer(
            offer,
            guild=guild,
            accepted_at_cut=2,
        )

        compute_entry = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref=f"ghot-capability:{ICE_CUBE_CAPABILITY}",
            source_ref="guild-declared-capacity:field-commons-001",
            evidence_refs=[offer["offer_id"]],
            native_measure={
                "unit": "ice-cube-job",
                "quantity": 2,
            },
            metadata={
                "scope": "Field Commons bounded mathematical work",
            },
        )
        treasury = make_treasury_snapshot(
            guild_id="guild:field-commons-001",
            steward=guild,
            entries=[compute_entry],
            sequence=0,
        )
        assert verify_treasury_snapshot(treasury)

        proposal = make_resource_proposal(
            treasury,
            proposer=artifact_owner,
            resource_entry_id=compute_entry["entry_id"],
            requested_quantity=1,
            requested_unit="ice-cube-job",
            purpose_ref=want["want_id"],
            proposed_at_cut=3,
        )
        authorization = authorize_resource_proposal(
            treasury,
            proposal,
            steward=guild,
            executor_particular=guild.particular(),
            authorized_at_cut=4,
            expires_after_cut=15,
        )

        porch = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            parcel_handler(receiver_root),
        )
        porch_thread = threading.Thread(target=porch.serve_forever, daemon=True)
        porch_thread.start()
        porch_url = f"http://127.0.0.1:{porch.server_port}"

        remote = RemoteTaskService(remote_worker)
        remote.start()

        commons = FieldCommonsStore(receiver_root)

        # Missing/invalid Guild authorization refuses before dispatch.
        rejected_without_authority = False
        try:
            commons.execute(
                field=field,
                want_id=want["want_id"],
                offer=offer,
                acceptance=acceptance,
                artifact_owner=artifact_owner,
                guild=guild,
                treasury_snapshot=treasury,
                proposal=proposal,
                authorization={},
                executor=guild,
                return_url=porch_url,
                return_particular=target_particular,
                observed_cut=5,
                timeout=0.01,
            )
        except Exception:
            rejected_without_authority = True
        assert rejected_without_authority
        assert not inbox.list()[1:]  # seed only; no child return was launched.

        original_gather = energy_scheduler.gather_candidates
        try:
            candidates = [
                candidate(
                    "commons-local-normal",
                    location="local",
                    willingness="normal",
                    url=None,
                ),
                candidate(
                    "commons-remote-surplus",
                    location="remote",
                    willingness="abundant",
                    url=remote.url,
                ),
            ]
            energy_scheduler.gather_candidates = lambda timeout: (
                candidates,
                {"policy": {"simulation": "field-commons-001"}},
            )

            record = commons.execute(
                field=field,
                want_id=want["want_id"],
                offer=offer,
                acceptance=acceptance,
                artifact_owner=artifact_owner,
                guild=guild,
                treasury_snapshot=treasury,
                proposal=proposal,
                authorization=authorization,
                executor=guild,
                return_url=porch_url,
                return_particular=target_particular,
                observed_cut=5,
                timeout=0.01,
                return_chunk_size=101,
            )
        finally:
            energy_scheduler.gather_candidates = original_gather
            remote.close()
            porch.shutdown()
            porch.server_close()
            porch_thread.join(timeout=2)

        assert record["status"] == "SETTLED"
        assert record["authority"] == "bilateral-evidence-only"
        assert verify_artifact_access_grant(record["artifact_access_grant"])
        assert verify_exchange_settlement(
            offer,
            acceptance,
            [
                record["offeror_performance"],
                record["acceptor_performance"],
            ],
            record["settlement"],
        )
        assert verify_execution_receipt(
            treasury,
            proposal,
            authorization,
            record["guild_execution"],
        )

        # The Guild's successful one-job authorization consumed exactly one
        # native job from its treasury, without inventing a money total.
        after = record["treasury_snapshot_after"]
        assert verify_treasury_snapshot(after)
        available = [
            item for item in after["entries"]
            if item["category"] == "capability"
            and item["position"] == "available"
            and item.get("native_measure", {}).get("unit") == "ice-cube-job"
        ]
        assert len(available) == 1
        assert available[0]["native_measure"]["quantity"] == 1

        dispatch_plan = record["dispatch"]["energy_plan"]
        assert dispatch_plan["action"] == "run_there"
        assert dispatch_plan["selected"]["node_id"] == "commons-remote-surplus"
        assert record["compute_evidence"]["worker_dogram_status"] == "OK"
        assert record["compute_evidence"]["return_disposition"] == "HELD"

        # Economic settlement did not admit the artifact.
        child_parcel_id = find_return_for_work(inbox, want["work_address"])
        before_admit = inbox.show(child_parcel_id)
        assert before_admit["status"]["verification_status"] == "UNVERIFIED"
        assert before_admit["state_parcel"]["queue"]["status"] == "HOLD"

        # Replaying the same Guild authorization is refused before a second job.
        replay_refused = False
        try:
            commons.execute(
                field=field,
                want_id=want["want_id"],
                offer=offer,
                acceptance=acceptance,
                artifact_owner=artifact_owner,
                guild=guild,
                treasury_snapshot=treasury,
                proposal=proposal,
                authorization=authorization,
                executor=guild,
                return_url="http://127.0.0.1:1",
                return_particular=target_particular,
                observed_cut=6,
                timeout=0.01,
            )
        except Exception:
            replay_refused = True
        assert replay_refused

        # Only now does the requester independently verify, ADMIT, and merge.
        admit_return(inbox, child_parcel_id, dogram_repo, package)
        refreshed = field.refresh()
        completed = field.load(want["want_id"])
        assert completed["status"] == "satisfied"

        catalog = json.loads(field.catalog_path.read_text(encoding="utf-8"))
        assert len(catalog["entries"]) == 2

        second_generation = [
            item for item in field.wants()
            if item["parent_specimen_id"]
            == record["dispatch"]["execution"]["receipt"]["output"]["specimen_id"]
        ]
        assert second_generation

        summary = {
            "simulation_passed": True,
            "commons_exchange": {
                "offeror_obligation": offer["offeror_obligation"]["obligation_type"],
                "acceptor_obligation": offer["acceptor_obligation"]["obligation_type"],
                "common_unit": None,
                "settlement_status": record["settlement"]["status"],
                "authority": record["settlement"]["authority"],
            },
            "guild": {
                "authorization_required": rejected_without_authority,
                "authorization_replay_refused": replay_refused,
                "compute_before": 2,
                "compute_after": 1,
                "unit": "ice-cube-job",
            },
            "placement": {
                "decision": dispatch_plan["action"],
                "selected_node": dispatch_plan["selected"]["node_id"],
                "worker_dogram_status": record["compute_evidence"]["worker_dogram_status"],
            },
            "return_boundary": {
                "settled_while_artifact_still_hold": True,
                "receiver_local_verification_later": True,
                "owner_local_admission_later": True,
            },
            "commons_growth": {
                "completed_want": completed["status"],
                "verified_pantry_entries": len(catalog["entries"]),
                "second_generation_wants": len(second_generation),
            },
        }
        print(json.dumps(summary, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
