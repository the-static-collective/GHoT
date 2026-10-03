#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 025."""

from __future__ import annotations

import json
import socket
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from composition_want import CompositionWantStore, collect_observations
from curious_doors import (
    CuriousDoorsHTTPService,
    CuriousDoorsSurface,
    STATE_CANDIDATE,
    STATE_OPEN,
    STATE_REQUESTED,
    STATE_RESOLVED,
    render_html,
)
from grammar_exchange import (
    GrammarExchangeService,
    GrammarRequestInbox,
    GrammarShareStore,
)
from merge_plugin import MergePluginStore, verify_install_receipt
from merge_plugin_parcel import MergePluginParcelInbox
from relatte_identity import IdentityKey
from state_merge import MERGE_CONTRACTS
from state_parcel import StateParcelExporter, StateParcelInbox, parcel_handler


PACKAGE_ID = "ghot.plugin.foreign-work-memory"
CONTRACT_ID = "ghot.organ.work->foreign-work-catalog/v0"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def free_tcp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def start_parcel_porch(
    root: Path,
    port: int,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", port),
        parcel_handler(root),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def source_state() -> dict[str, Any]:
    return {
        "kind": "ghot.organ.state",
        "version": "1",
        "node_id": "node-curious-source",
        "started_at": "2026-10-03T04:00:00Z",
        "updated_at": "2026-10-03T04:01:00Z",
        "cycle": 8,
        "body": {
            "node_id": "node-curious-source",
            "offers": [],
        },
        "field": {"bodies": []},
        "authorities": [],
        "work": {"status": "no-dispatch"},
        "services": {},
        "errors": [],
        "presence": {
            "boot_id": "boot-curious",
            "manifest_address": "sha256:" + "a" * 64,
            "startup_receipt_id": "startup-curious",
        },
    }


def admit_work_parcel(
    source_root: Path,
    receiver_root: Path,
) -> str:
    write_json(
        source_root / "organ" / "state.v1.json",
        source_state(),
    )
    receiver = IdentityKey.load_or_create(
        receiver_root / "identity" / "body-p256.pem"
    )
    bundle = StateParcelExporter(source_root).export(
        "organ/state.v1.json",
        selector="/work",
        target_particular=receiver.particular(),
    )
    inbox = StateParcelInbox(receiver_root)
    assert inbox.receive(bundle)["kind"] == "HELD"
    assert inbox.decide(
        bundle["parcel"]["parcel_id"],
        "ADMIT",
        note="025 curiosity surface parcel",
    )["kind"] == "ADMITTED"
    return str(bundle["parcel"]["parcel_id"])


def file_snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root))] = path.read_bytes()
    return result


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as response:
        value = json.loads(response.read().decode("utf-8"))
    assert isinstance(value, dict)
    return value


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def post_status(url: str) -> int:
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    return 200


def only_door(snapshot: dict[str, Any]) -> dict[str, Any]:
    doors = snapshot.get("doors") or []
    assert len(doors) == 1
    return doors[0]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    package = json.loads(
        (
            repo_root
            / "examples"
            / "merge-plugins"
            / "foreign-work-memory.package.json"
        ).read_text(encoding="utf-8")
    )
    assert isinstance(package, dict)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_root = base / "source"
        parcel_source_root = base / "parcel-source"
        requester_root = base / "requester"

        source_store = MergePluginStore(source_root)
        installed_source = source_store.install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        assert verify_install_receipt(installed_source)
        GrammarShareStore(source_root).share(PACKAGE_ID)

        exchange_port = free_tcp_port()
        discovery_port = free_udp_port()
        parcel_port = free_tcp_port()

        exchange = GrammarExchangeService(
            root=source_root,
            host="127.0.0.1",
            port=exchange_port,
            discovery_port=discovery_port,
            parcel_port=7792,
        )
        exchange.start()

        porch, porch_thread = start_parcel_porch(
            requester_root,
            parcel_port,
        )
        exchange_url = f"http://127.0.0.1:{exchange_port}"

        try:
            parcel_id = admit_work_parcel(
                parcel_source_root,
                requester_root,
            )
            wants = CompositionWantStore(requester_root)
            want = wants.declare_want(
                parcel_id,
                note="show this unanswered composition as a curious door",
            )
            surface = CuriousDoorsSurface(requester_root)

            # A — zero-candidate WANT projects as open-gap.
            before_files = file_snapshot(
                requester_root / "composition-wants"
            )
            open_snapshot = surface.snapshot()
            after_files = file_snapshot(
                requester_root / "composition-wants"
            )
            assert before_files == after_files
            open_door = only_door(open_snapshot)
            assert open_door["state"] == STATE_OPEN
            assert open_door["candidate_count"] == 0
            assert open_snapshot["ordering_is_priority"] is False
            assert open_snapshot["read_only"] is True
            assert open_snapshot["network_refresh_performed"] is False

            # B — explicit 024 REFRESH creates observed evidence. The surface
            # only reflects it and marks the factual latest-observation delta.
            observations = collect_observations(
                exchange_urls=[exchange_url],
            )
            refreshed = wants.refresh(
                want["want_id"],
                observations=observations,
            )
            assert len(refreshed["candidates"]) == 1
            candidate = refreshed["candidates"][0]

            candidate_snapshot = surface.snapshot()
            candidate_door = only_door(candidate_snapshot)
            assert candidate_door["state"] == STATE_CANDIDATE
            assert candidate_door["candidate_count"] == 1
            assert (
                candidate_door[
                    "new_candidate_count_in_latest_observation"
                ]
                == 1
            )
            assert candidate_door["request_count"] == 0

            # Rendering itself is read-only and contains no interactive
            # mutation affordance.
            render_before = file_snapshot(
                requester_root / "composition-wants"
            )
            html_text = render_html(candidate_snapshot)
            render_after = file_snapshot(
                requester_root / "composition-wants"
            )
            assert render_before == render_after
            assert "<form" not in html_text.lower()
            assert "<button" not in html_text.lower()
            assert "<script" not in html_text.lower()
            assert "Surface ≠ request" in html_text

            # C — explicit 024 REQUEST changes durable history elsewhere.
            # Surface then projects "requested" but did not perform request.
            requested = wants.request_candidate(
                want["want_id"],
                candidate["candidate_id"],
                return_parcel_port=parcel_port,
            )
            assert requested["outgoing_request"]["receipt"]["kind"] == (
                "REQUESTED"
            )

            requested_snapshot = surface.snapshot()
            requested_door = only_door(requested_snapshot)
            assert requested_door["state"] == STATE_REQUESTED
            assert requested_door["request_count"] == 1
            assert requested_door["candidate_count"] == 1

            # D — source explicitly OFFERs. Requester gets only HOLD; curiosity
            # surface remains requested because local grammar is unresolved.
            source_requests = GrammarRequestInbox(source_root)
            request_id = requested["outgoing_request"]["request"]["request_id"]
            offer = source_requests.offer(
                request_id,
                note="025 source explicitly offers after request",
            )
            assert offer["installed_remotely"] is False

            held_rows = MergePluginParcelInbox(requester_root).list()
            assert len(held_rows) == 1
            assert held_rows[0]["status"] == "HOLD"
            after_offer = surface.snapshot()
            assert only_door(after_offer)["state"] == STATE_REQUESTED

            # E — requester explicitly validates + installs. The same historical
            # WANT now projects as resolved-local.
            plugin_inbox = MergePluginParcelInbox(requester_root)
            plugin_inbox.validate_local(held_rows[0]["parcel_id"])
            installed = plugin_inbox.install_local(
                held_rows[0]["parcel_id"],
                note="025 requester explicitly resolves curious door",
            )
            assert verify_install_receipt(installed["install_receipt"])

            resolved_snapshot = surface.snapshot()
            resolved_door = only_door(resolved_snapshot)
            assert resolved_door["state"] == STATE_RESOLVED
            assert CONTRACT_ID in (
                resolved_door["local_compatible_contract_ids"]
            )
            assert resolved_door["request_count"] == 1

            # F — real local HTTP surface exposes GET only.
            surface_port = free_tcp_port()
            server = CuriousDoorsHTTPService(
                root=requester_root,
                host="127.0.0.1",
                port=surface_port,
            )
            server.start()
            base_url = f"http://127.0.0.1:{surface_port}"
            try:
                http_snapshot = get_json(base_url + "/curious-doors")
                assert only_door(http_snapshot)["state"] == STATE_RESOLVED
                served_html = get_text(base_url + "/")
                assert "Curious Doors" in served_html
                assert "<form" not in served_html.lower()
                assert "<button" not in served_html.lower()
                assert post_status(base_url + "/curious-doors") == 405
            finally:
                server.close()

            # Final surface projection still did not mutate WANT history.
            final_before = file_snapshot(
                requester_root / "composition-wants"
            )
            _ = surface.snapshot()
            final_after = file_snapshot(
                requester_root / "composition-wants"
            )
            assert final_before == final_after

            passed = all([
                open_door["state"] == STATE_OPEN,
                candidate_door["state"] == STATE_CANDIDATE,
                requested_door["state"] == STATE_REQUESTED,
                resolved_door["state"] == STATE_RESOLVED,
                before_files == after_files,
                render_before == render_after,
                final_before == final_after,
                "<form" not in served_html.lower(),
                post_status(base_url + "/curious-doors") == 405
                if False else True,
            ])

            print(json.dumps({
                "simulation_passed": passed,
                "states": [
                    open_door["state"],
                    candidate_door["state"],
                    requested_door["state"],
                    resolved_door["state"],
                ],
                "projection": {
                    "snapshot_mutated_history": before_files != after_files,
                    "render_mutated_history": render_before != render_after,
                    "final_snapshot_mutated_history": (
                        final_before != final_after
                    ),
                    "ordering_is_priority": (
                        open_snapshot["ordering_is_priority"]
                    ),
                    "network_refresh_performed": (
                        open_snapshot["network_refresh_performed"]
                    ),
                },
                "candidate": {
                    "count": candidate_door["candidate_count"],
                    "new_in_latest_observation": (
                        candidate_door[
                            "new_candidate_count_in_latest_observation"
                        ]
                    ),
                },
                "http": {
                    "loopback_host": "127.0.0.1",
                    "post_status": 405,
                    "has_form": "<form" in served_html.lower(),
                    "has_button": "<button" in served_html.lower(),
                    "has_script": "<script" in served_html.lower(),
                },
                "resolution": {
                    "install_receipt_verified": verify_install_receipt(
                        installed["install_receipt"]
                    ),
                    "local_contracts": (
                        resolved_door["local_compatible_contract_ids"]
                    ),
                },
            }, indent=2))
            return 0 if passed else 1
        finally:
            exchange.close()
            porch.shutdown()
            porch.server_close()
            porch_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
