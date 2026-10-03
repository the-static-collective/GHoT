#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 026."""

from __future__ import annotations

import json
import socket
import tempfile
import threading
import urllib.error
import urllib.parse
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
)
from curious_doors_sim import (
    admit_work_parcel,
    free_tcp_port,
    free_udp_port,
    start_parcel_porch,
)
from grammar_exchange import (
    GrammarExchangeService,
    GrammarRequestInbox,
    GrammarShareStore,
)
from merge_plugin import MergePluginStore, verify_install_receipt
from merge_plugin_parcel import MergePluginParcelInbox
from state_merge import MERGE_CONTRACTS


PACKAGE_ID = "ghot.plugin.foreign-work-memory"
CONTRACT_ID = "ghot.organ.work->foreign-work-catalog/v0"


def file_snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root))] = path.read_bytes()
    return result


def http_get(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return (
            int(response.status),
            response.headers.get("Content-Type", ""),
            response.read().decode("utf-8"),
        )


def http_post_status(url: str) -> int:
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


def one_door(surface: CuriousDoorsSurface) -> dict[str, Any]:
    doors = surface.snapshot().get("doors") or []
    assert len(doors) == 1
    return doors[0]


def nav_kind(
    door: dict[str, Any],
    kind: str,
) -> list[dict[str, Any]]:
    return [
        item
        for item in (door.get("navigation") or [])
        if item.get("kind") == kind
    ]


def assert_navigation_inert(door: dict[str, Any]) -> None:
    for item in door.get("navigation") or []:
        assert item.get("executes") is False
        assert item.get("permission_transfer") is False
        if item.get("kind") == "evidence-link":
            assert item.get("method") == "GET"
            assert item.get("effect") == "none"
            href = item.get("href")
            assert isinstance(href, str) and href.startswith("/")
            assert "argv" not in item
        elif item.get("kind") == "command-intent":
            assert "href" not in item
            argv = item.get("argv")
            assert isinstance(argv, list) and argv
            assert all(isinstance(part, str) for part in argv)
            assert item.get("display_command")
            assert item.get("owner_contract")
        else:
            raise AssertionError("unknown navigation kind")


def find_intent(
    door: dict[str, Any],
    *,
    owner: str,
    command: str,
) -> dict[str, Any] | None:
    for item in nav_kind(door, "command-intent"):
        argv = item.get("argv") or []
        if (
            item.get("owner_contract") == owner
            and len(argv) >= 3
            and argv[1].endswith(command)
        ):
            return item
    return None


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

        # A — opening a surface on a pristine root creates nothing.
        empty_root = base / "empty"
        before_empty = file_snapshot(empty_root)
        empty_surface = CuriousDoorsSurface(empty_root)
        empty_snapshot = empty_surface.snapshot()
        after_empty = file_snapshot(empty_root)
        assert before_empty == after_empty == {}
        assert empty_snapshot["doors"] == []
        assert empty_snapshot["navigation_executes"] is False
        assert empty_snapshot["navigation_transfers_permission"] is False

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

        surface_port = free_tcp_port()
        surface_server: CuriousDoorsHTTPService | None = None

        try:
            parcel_id = admit_work_parcel(
                parcel_source_root,
                requester_root,
            )
            wants = CompositionWantStore(requester_root)
            want = wants.declare_want(
                parcel_id,
                note="026 navigate without acting",
            )
            surface = CuriousDoorsSurface(requester_root)

            # B — open gap: evidence link + inert inspect/refresh intents.
            open_before = file_snapshot(requester_root)
            open_door = one_door(surface)
            open_after = file_snapshot(requester_root)
            assert open_before == open_after
            assert open_door["state"] == STATE_OPEN
            assert_navigation_inert(open_door)

            evidence_links = nav_kind(open_door, "evidence-link")
            assert len(evidence_links) == 1
            assert evidence_links[0]["owner_contract"] == "ghot.curious-doors@1"

            show_intent = find_intent(
                open_door,
                owner="ghot.composition-wants@0",
                command="composition_want.py",
            )
            assert show_intent is not None
            refresh_intents = [
                item
                for item in nav_kind(open_door, "command-intent")
                if "refresh" in (item.get("argv") or [])
            ]
            assert len(refresh_intents) == 1
            assert refresh_intents[0]["effect_if_run"] == (
                "network-read+local-observation-write"
            )

            # C — explicit REFRESH elsewhere makes candidate request intent
            # visible, but surface still performs nothing.
            observations = collect_observations(
                exchange_urls=[exchange_url],
            )
            refreshed = wants.refresh(
                want["want_id"],
                observations=observations,
            )
            assert len(refreshed["candidates"]) == 1
            candidate = refreshed["candidates"][0]

            candidate_door = one_door(surface)
            assert candidate_door["state"] == STATE_CANDIDATE
            assert_navigation_inert(candidate_door)
            request_intents = [
                item
                for item in nav_kind(candidate_door, "command-intent")
                if "request" in (item.get("argv") or [])
            ]
            assert len(request_intents) == 1
            request_argv = request_intents[0]["argv"]
            assert request_argv[-2:] == [
                want["want_id"],
                candidate["candidate_id"],
            ]
            assert "href" not in request_intents[0]

            source_requests = GrammarRequestInbox(source_root)
            assert source_requests.list() == []

            # D — real local surface exposes evidence navigation as GET only.
            surface_server = CuriousDoorsHTTPService(
                root=requester_root,
                host="127.0.0.1",
                port=surface_port,
            )
            surface_server.start()
            base_url = f"http://127.0.0.1:{surface_port}"

            index_before = file_snapshot(requester_root)
            status, content_type, index_html = http_get(base_url + "/")
            index_after = file_snapshot(requester_root)
            assert status == 200
            assert "text/html" in content_type
            assert index_before == index_after
            assert '<a href="/door?want_id=' in index_html
            assert "<button" not in index_html.lower()
            assert "<form" not in index_html.lower()
            assert "<script" not in index_html.lower()
            assert "This surface does not execute it." in index_html

            href = evidence_links[0]["href"]
            evidence_before = file_snapshot(requester_root)
            status, content_type, detail_html = http_get(base_url + href)
            evidence_after = file_snapshot(requester_root)
            assert status == 200
            assert "text/html" in content_type
            assert evidence_before == evidence_after
            assert "Possible next places" in detail_html
            assert "<button" not in detail_html.lower()
            assert "<form" not in detail_html.lower()
            assert "<script" not in detail_html.lower()

            encoded_want = urllib.parse.quote(want["want_id"], safe="")
            status, content_type, evidence_json = http_get(
                base_url + "/evidence?want_id=" + encoded_want
            )
            assert status == 200
            assert "application/json" in content_type
            evidence = json.loads(evidence_json)
            assert evidence["want"]["want_id"] == want["want_id"]
            assert evidence["read_only"] is True
            assert http_post_status(
                base_url + "/door?want_id=" + encoded_want
            ) == 405
            assert http_post_status(
                base_url + "/evidence?want_id=" + encoded_want
            ) == 405

            # E — explicitly run the owning 024 request operation elsewhere.
            requested = wants.request_candidate(
                want["want_id"],
                candidate["candidate_id"],
                return_parcel_port=parcel_port,
            )
            assert requested["outgoing_request"]["receipt"]["kind"] == (
                "REQUESTED"
            )
            requested_door = one_door(surface)
            assert requested_door["state"] == STATE_REQUESTED
            assert_navigation_inert(requested_door)
            assert MergePluginParcelInbox(requester_root).list() == []

            # Before OFFER there is no validate/install intent because no
            # plugin parcel exists locally yet.
            argv_flat = [
                part
                for item in nav_kind(requested_door, "command-intent")
                for part in (item.get("argv") or [])
            ]
            assert "validate" not in argv_flat
            assert "install" not in argv_flat

            # F — source separately OFFERs. Surface notices local HOLD and
            # points to owning plugin-parcel subsystem with inert inspect +
            # validate intents.
            request_id = requested["outgoing_request"]["request"]["request_id"]
            offer = source_requests.offer(
                request_id,
                note="026 source separately offers",
            )
            assert offer["installed_remotely"] is False

            held_rows = MergePluginParcelInbox(requester_root).list()
            assert len(held_rows) == 1
            held_id = held_rows[0]["parcel_id"]

            held_door = one_door(surface)
            assert held_door["state"] == STATE_REQUESTED
            assert_navigation_inert(held_door)
            assert held_door["matching_plugin_parcels"][0]["status"] == "HOLD"

            held_intents = nav_kind(held_door, "command-intent")
            show_plugin = [
                item for item in held_intents
                if item.get("owner_contract") == "ghot.merge-plugin-parcel-inbox@0"
                and "show" in (item.get("argv") or [])
            ]
            validate_plugin = [
                item for item in held_intents
                if item.get("owner_contract") == "ghot.merge-plugin-parcel-inbox@0"
                and "validate" in (item.get("argv") or [])
            ]
            assert len(show_plugin) == 1
            assert len(validate_plugin) == 1
            assert validate_plugin[0]["argv"][-1] == held_id
            assert "href" not in validate_plugin[0]

            # G — explicit validation elsewhere changes which inert command the
            # surface displays; it still executes nothing.
            plugin_inbox = MergePluginParcelInbox(requester_root)
            plugin_inbox.validate_local(held_id)

            validated_door = one_door(surface)
            assert validated_door["state"] == STATE_REQUESTED
            assert_navigation_inert(validated_door)
            validated_intents = nav_kind(
                validated_door,
                "command-intent",
            )
            assert not any(
                "validate" in (item.get("argv") or [])
                for item in validated_intents
            )
            install_intents = [
                item
                for item in validated_intents
                if (
                    item.get("owner_contract")
                    == "ghot.merge-plugin-parcel-inbox@0"
                    and "install" in (item.get("argv") or [])
                )
            ]
            assert len(install_intents) == 1
            assert install_intents[0]["argv"][-1] == held_id
            assert install_intents[0]["executes"] is False

            # H — explicit install elsewhere resolves the gap. Surface points
            # only to read-only pantry inspection; no stale mutation intent.
            installed = plugin_inbox.install_local(
                held_id,
                note="026 operator follows owning subsystem",
            )
            assert verify_install_receipt(installed["install_receipt"])

            resolved_door = one_door(surface)
            assert resolved_door["state"] == STATE_RESOLVED
            assert CONTRACT_ID in (
                resolved_door["local_compatible_contract_ids"]
            )
            assert_navigation_inert(resolved_door)
            resolved_intents = nav_kind(
                resolved_door,
                "command-intent",
            )
            assert any(
                item.get("owner_contract") == "ghot.merge-contract-pantry@0"
                and "inspect" in (item.get("argv") or [])
                for item in resolved_intents
            )
            all_resolved_argv = [
                part
                for item in resolved_intents
                for part in (item.get("argv") or [])
            ]
            assert "request" not in all_resolved_argv
            assert "validate" not in all_resolved_argv
            assert "install" not in all_resolved_argv

            # I — navigation projection itself stays read-only at end.
            final_before = file_snapshot(requester_root)
            _ = surface.snapshot()
            _ = surface.evidence(want["want_id"])
            final_after = file_snapshot(requester_root)
            assert final_before == final_after

            passed = all([
                before_empty == after_empty,
                open_before == open_after,
                index_before == index_after,
                evidence_before == evidence_after,
                final_before == final_after,
                candidate_door["state"] == STATE_CANDIDATE,
                requested_door["state"] == STATE_REQUESTED,
                held_door["matching_plugin_parcels"][0]["status"] == "HOLD",
                resolved_door["state"] == STATE_RESOLVED,
            ])

            print(json.dumps({
                "simulation_passed": passed,
                "empty_root": {
                    "created_files": sorted(after_empty),
                    "read_only": before_empty == after_empty,
                },
                "states": [
                    open_door["state"],
                    candidate_door["state"],
                    requested_door["state"],
                    held_door["state"],
                    validated_door["state"],
                    resolved_door["state"],
                ],
                "navigation": {
                    "evidence_links_are_get_only": all(
                        item.get("method") == "GET"
                        and item.get("effect") == "none"
                        and item.get("executes") is False
                        for item in nav_kind(open_door, "evidence-link")
                    ),
                    "command_intents_have_no_href": all(
                        "href" not in item
                        and item.get("executes") is False
                        and item.get("permission_transfer") is False
                        for door in (
                            open_door,
                            candidate_door,
                            requested_door,
                            held_door,
                            validated_door,
                            resolved_door,
                        )
                        for item in nav_kind(door, "command-intent")
                    ),
                    "candidate_request_intents": len(request_intents),
                    "hold_validate_intents": len(validate_plugin),
                    "validated_install_intents": len(install_intents),
                },
                "http": {
                    "index_read_only": index_before == index_after,
                    "evidence_read_only": evidence_before == evidence_after,
                    "door_post_status": 405,
                    "evidence_post_status": 405,
                    "has_button": "<button" in index_html.lower(),
                    "has_form": "<form" in index_html.lower(),
                    "has_script": "<script" in index_html.lower(),
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
            if surface_server is not None:
                surface_server.close()
            exchange.close()
            porch.shutdown()
            porch.server_close()
            porch_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
