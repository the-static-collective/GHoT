#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 018."""

from __future__ import annotations

import copy
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from relatte_identity import IdentityKey, verify_receipt
from state_parcel import (
    StateParcelExporter,
    StateParcelInbox,
    parcel_handler,
    send_bundle,
    verify_bundle,
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def state(node: str) -> dict[str, Any]:
    return {
        "kind": "ghot.organ.state",
        "version": "1",
        "node_id": node,
        "started_at": "2026-10-02T12:00:00Z",
        "updated_at": "2026-10-02T12:01:00Z",
        "cycle": 9,
        "body": {
            "node_id": node,
            "offers": [
                {"capability": "system.echo", "available": True},
                {"capability": "media.probe", "available": True},
            ],
        },
        "field": {"bodies": []},
        "authorities": [],
        "work": {"status": "no-dispatch"},
        "services": {"body_http": {"state": "awake"}},
        "errors": [],
        "presence": {
            "boot_id": "boot-source",
            "manifest_address": "sha256:" + "a" * 64,
            "startup_receipt_id": "startup-source",
        },
    }


def run_server(root: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        parcel_handler(root),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_root = base / "source"
        receiver_root = base / "receiver"
        other_root = base / "other"

        source_state = state("node-source")
        source_path = source_root / "organ" / "state.v1.json"
        write_json(source_path, source_state)

        receiver_signer = IdentityKey.load_or_create(
            receiver_root / "identity" / "body-p256.pem"
        )
        receiver_particular = receiver_signer.particular()

        exporter = StateParcelExporter(source_root)
        bundle = exporter.export(
            "organ/state.v1.json",
            selector="/body/offers",
            target_particular=receiver_particular,
        )

        assert verify_bundle(bundle)
        parcel = bundle["parcel"]
        assert parcel["source"]["state_kind"] == "ghot.organ.state"
        assert parcel["source"]["state_version"] == "1"
        assert parcel["migration"]["current_known_version"] == "1"
        assert parcel["target"]["particular"] == receiver_particular
        assert parcel["payload"]["value"] == source_state["body"]["offers"]

        tampered = copy.deepcopy(bundle)
        tampered["parcel"]["payload"]["value"][0]["available"] = False
        assert not verify_bundle(tampered)

        # Receiver canonical state is intentionally unrelated and must stay unchanged.
        receiver_canonical = receiver_root / "organ" / "state.v1.json"
        receiver_live = state("node-receiver")
        write_json(receiver_canonical, receiver_live)
        receiver_before = receiver_canonical.read_bytes()

        server, thread = run_server(receiver_root)
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            hold = send_bundle(bundle, base_url)
            assert verify_receipt(hold)
            assert hold["kind"] == "HELD"
            assert hold["semantic_effect"] == "none"
            assert (hold.get("extensions") or {}).get("disposition") == "HOLD"

            receiver_inbox = StateParcelInbox(receiver_root)
            rows = receiver_inbox.list()
            assert len(rows) == 1
            assert rows[0]["status"] == "HOLD"
            assert receiver_canonical.read_bytes() == receiver_before

            duplicate = send_bundle(bundle, base_url)
            assert verify_receipt(duplicate)
            assert duplicate["kind"] == "HELD"
            assert (duplicate.get("extensions") or {}).get("duplicate_crossing") is True
            assert len(receiver_inbox.list()) == 1

            admitted = receiver_inbox.decide(
                parcel["parcel_id"],
                "ADMIT",
                note="accept into local parcel corpus",
            )
            assert verify_receipt(admitted)
            assert admitted["kind"] == "ADMITTED"
            assert admitted["semantic_effect"] == "local-state-change"
            assert (admitted.get("extensions") or {}).get("canonical_state_mutated") is False
            admitted_file = (
                receiver_root
                / "state-parcels"
                / "admitted"
                / (
                    parcel["parcel_id"]
                    .replace(":", "_")
                    .replace("/", "_")
                    + ".json"
                )
            )
            assert admitted_file.exists()
            assert receiver_canonical.read_bytes() == receiver_before

            terminal_refused = False
            try:
                receiver_inbox.decide(parcel["parcel_id"], "REJECT")
            except ValueError:
                terminal_refused = True
            assert terminal_refused

            # A second parcel can be rejected without being materialized.
            reject_bundle = exporter.export(
                "organ/state.v1.json",
                selector="/work",
                target_particular=receiver_particular,
            )
            reject_hold = send_bundle(reject_bundle, base_url)
            assert reject_hold["kind"] == "HELD"
            rejected = receiver_inbox.decide(
                reject_bundle["parcel"]["parcel_id"],
                "REJECT",
                note="not useful here",
            )
            assert verify_receipt(rejected)
            assert rejected["kind"] == "REJECTED"
            assert rejected["semantic_effect"] == "none"

            # A third parcel is kept as a scar: retained witness, not active state.
            scar_bundle = exporter.export(
                "organ/state.v1.json",
                selector="/presence",
                target_particular=receiver_particular,
            )
            scar_hold = send_bundle(scar_bundle, base_url)
            assert scar_hold["kind"] == "HELD"
            scarred = receiver_inbox.decide(
                scar_bundle["parcel"]["parcel_id"],
                "SCAR",
                note="retain as foreign-state witness",
            )
            assert verify_receipt(scarred)
            assert scarred["kind"] == "SCARRED"
            scar_file = (
                receiver_root
                / "state-parcels"
                / "scars"
                / (
                    scar_bundle["parcel"]["parcel_id"]
                    .replace(":", "_")
                    .replace("/", "_")
                    + ".json"
                )
            )
            assert scar_file.exists()
            scar = json.loads(scar_file.read_text(encoding="utf-8"))
            assert scar["active"] is False
            assert receiver_canonical.read_bytes() == receiver_before

            # A parcel addressed to another particular is cryptographically valid
            # but receives a signed REFUSED receipt and never enters the queue.
            other_signer = IdentityKey.load_or_create(
                other_root / "identity" / "body-p256.pem"
            )
            wrong_target_bundle = exporter.export(
                "organ/state.v1.json",
                selector="/services",
                target_particular=other_signer.particular(),
            )
            refused = send_bundle(wrong_target_bundle, base_url)
            assert verify_receipt(refused)
            assert refused["kind"] == "REFUSED"
            assert (
                (refused.get("extensions") or {}).get("reason")
                == "target-particular-mismatch"
            )
            assert all(
                row["parcel_id"] != wrong_target_bundle["parcel"]["parcel_id"]
                for row in receiver_inbox.list()
            )

            all_receipts = receiver_inbox.receipts()
            assert all(item["verified"] is True for item in all_receipts)

        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        passed = (
            verify_bundle(bundle)
            and not verify_bundle(tampered)
            and hold["kind"] == "HELD"
            and duplicate["kind"] == "HELD"
            and admitted["kind"] == "ADMITTED"
            and rejected["kind"] == "REJECTED"
            and scarred["kind"] == "SCARRED"
            and refused["kind"] == "REFUSED"
            and receiver_canonical.read_bytes() == receiver_before
            and terminal_refused
        )

        print(json.dumps({
            "simulation_passed": passed,
            "export": {
                "parcel_id": parcel["parcel_id"],
                "bundle_verified": verify_bundle(bundle),
                "tamper_rejected": not verify_bundle(tampered),
                "target_bound": parcel["target"]["particular"] == receiver_particular,
            },
            "crossing": {
                "first_receipt": hold["kind"],
                "duplicate_receipt": duplicate["kind"],
                "duplicate_queue_suppressed": len([
                    row for row in StateParcelInbox(receiver_root).list()
                    if row["parcel_id"] == parcel["parcel_id"]
                ]) == 1,
            },
            "owner_local": {
                "admit": admitted["kind"],
                "reject": rejected["kind"],
                "scar": scarred["kind"],
                "terminal_redecision_refused": terminal_refused,
                "canonical_state_unchanged": (
                    receiver_canonical.read_bytes() == receiver_before
                ),
            },
            "audience": {
                "wrong_target": refused["kind"],
            },
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
