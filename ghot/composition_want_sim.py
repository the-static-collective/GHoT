#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 024."""

from __future__ import annotations

import copy
import json
import socket
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from composition_want import (
    CompositionWantStore,
    collect_observations,
    derive_want_id,
)
from grammar_exchange import (
    GrammarExchangeService,
    GrammarRequestInbox,
    GrammarShareStore,
)
from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from merge_plugin_parcel import MergePluginParcelInbox
from relatte_identity import IdentityKey
from state_merge import MERGE_CONTRACTS
from state_parcel import StateParcelExporter, StateParcelInbox, parcel_handler


WORK_PACKAGE_ID = "ghot.plugin.foreign-work-memory"
WORK_CONTRACT = "ghot.organ.work->foreign-work-catalog/v0"
OTHER_PACKAGE_ID = "ghot.plugin.other-shape"
OTHER_CONTRACT = "ghot.organ.presence-ish->other-catalog/v0"


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
        "node_id": "node-gap-source",
        "started_at": "2026-10-03T03:00:00Z",
        "updated_at": "2026-10-03T03:01:00Z",
        "cycle": 7,
        "body": {
            "node_id": "node-gap-source",
            "offers": [],
        },
        "field": {"bodies": []},
        "authorities": [],
        "work": {"status": "no-dispatch"},
        "services": {},
        "errors": [],
        "presence": {
            "boot_id": "boot-gap",
            "manifest_address": "sha256:" + "a" * 64,
            "startup_receipt_id": "startup-gap",
        },
    }


def admit_work_parcel(
    source_root: Path,
    receiver_root: Path,
) -> dict[str, Any]:
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
    admitted = inbox.decide(
        bundle["parcel"]["parcel_id"],
        "ADMIT",
        note="024 concrete composition gap",
    )
    assert admitted["kind"] == "ADMITTED"
    return bundle


def other_shape_package(package: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(package)
    value["package_id"] = OTHER_PACKAGE_ID
    value["contract"]["contract_id"] = OTHER_CONTRACT
    value["contract"]["title"] = "Other exact source shape"
    value["contract"]["source"]["selector"] = "/presence"
    value["contract"]["target"]["relative_path"] = (
        "knowledge/plugins/ghot.plugin.other-shape/other.v0.json"
    )
    value["contract"]["target"]["state_kind"] = "ghot.other-catalog"
    value["schemas"]["target"]["kind"] = "ghot.other-catalog"
    value["fixtures"][0]["local_before"]["kind"] = "ghot.other-catalog"
    value["fixtures"][0]["expected_after"]["kind"] = "ghot.other-catalog"
    return value


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    package_path = (
        repo_root
        / "examples"
        / "merge-plugins"
        / "foreign-work-memory.package.json"
    )
    work_package = json.loads(
        package_path.read_text(encoding="utf-8")
    )
    assert isinstance(work_package, dict)
    other_package = other_shape_package(work_package)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_root = base / "source"
        parcel_source_root = base / "parcel-source"
        requester_root = base / "requester"

        source_store = MergePluginStore(source_root)
        work_install = source_store.install(
            work_package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        other_install = source_store.install(
            other_package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        assert verify_install_receipt(work_install)
        assert verify_install_receipt(other_install)

        shares = GrammarShareStore(source_root)
        shares.share(WORK_PACKAGE_ID)
        shares.share(OTHER_PACKAGE_ID)

        exchange_port = free_tcp_port()
        discovery_port = free_udp_port()
        requester_parcel_port = free_tcp_port()

        service = GrammarExchangeService(
            root=source_root,
            host="127.0.0.1",
            port=exchange_port,
            discovery_port=discovery_port,
            parcel_port=7792,
        )
        service.start()

        porch, porch_thread = start_parcel_porch(
            requester_root,
            requester_parcel_port,
        )
        exchange_url = f"http://127.0.0.1:{exchange_port}"

        try:
            admitted_bundle = admit_work_parcel(
                parcel_source_root,
                requester_root,
            )
            parcel_id = admitted_bundle["parcel"]["parcel_id"]
            pantry = MergeContractPantry(requester_root)
            assert pantry.inspect(parcel_id)["compatible_contract_ids"] == []

            wants = CompositionWantStore(requester_root)

            # A — a gap is concrete and may be wanted even with no candidates.
            empty_gap = wants.inspect_gap(parcel_id)
            assert empty_gap["status"] == "gap"
            assert empty_gap["candidate_count"] == 0
            empty_want = wants.declare_want(
                parcel_id,
                note="the gap itself matters before a solution is observed",
            )
            assert empty_want["candidates"] == []
            assert empty_want["want_id"] == derive_want_id(empty_want)

            # B — observation finds exactly one structural candidate even though
            # the source advertises two packages.
            observations = collect_observations(
                exchange_urls=[exchange_url],
            )
            gap = wants.inspect_gap(
                parcel_id,
                observations=observations,
            )
            assert gap["status"] == "gap"
            assert gap["candidate_count"] == 1
            candidate = gap["candidates"][0]
            assert candidate["package_id"] == WORK_PACKAGE_ID
            assert candidate["contract_id"] == WORK_CONTRACT
            assert candidate["source"]["selector"] == "/work"
            assert candidate["match"] == "exact-source-shape"
            assert "rank" not in candidate
            assert "score" not in candidate
            assert "recommended" not in candidate

            want = wants.declare_want(
                parcel_id,
                observations=observations,
                note="operator wants a lawful /work merge grammar",
            )
            assert len(want["candidates"]) == 1
            assert want["want_id"] == derive_want_id(want)

            # One candidate still causes no request.
            source_requests = GrammarRequestInbox(source_root)
            assert source_requests.list() == []
            assert MergePluginParcelInbox(requester_root).list() == []
            assert MergePluginStore(requester_root).list_installed() == []

            # C — candidate is observation, not durable entitlement. If source
            # unshares it, REQUEST revalidation refuses.
            shares.unshare(WORK_PACKAGE_ID)
            stale_candidate_refused = False
            try:
                wants.request_candidate(
                    want["want_id"],
                    candidate["candidate_id"],
                    return_parcel_port=requester_parcel_port,
                )
            except ValueError:
                stale_candidate_refused = True
            assert stale_candidate_refused
            assert source_requests.list() == []

            # Restore explicit share for the actual request.
            shares.share(WORK_PACKAGE_ID)

            # D — explicit candidate-specific REQUEST uses 023 and still crosses
            # no package.
            requested = wants.request_candidate(
                want["want_id"],
                candidate["candidate_id"],
                return_parcel_port=requester_parcel_port,
            )
            outgoing = requested["outgoing_request"]
            link = requested["link"]
            assert outgoing["receipt"]["kind"] == "REQUESTED"
            assert (
                (outgoing["receipt"].get("extensions") or {})
                .get("package_crossed")
                is False
            )
            assert link["want_id"] == want["want_id"]
            assert link["candidate_id"] == candidate["candidate_id"]
            assert link["request_id"] == outgoing["request"]["request_id"]
            assert len(source_requests.list()) == 1
            assert MergePluginParcelInbox(requester_root).list() == []
            assert MergePluginStore(requester_root).list_installed() == []

            # E — 024 does not offer. The source must separately do the 023
            # owner-local OFFER.
            source_request_id = outgoing["request"]["request_id"]
            offer = source_requests.offer(
                source_request_id,
                note="source separately agrees to share this wanted grammar",
            )
            assert offer["installed_remotely"] is False
            held = MergePluginParcelInbox(requester_root).list()
            assert len(held) == 1
            assert held[0]["status"] == "HOLD"
            assert MergePluginStore(requester_root).list_installed() == []

            # F — requester remains owner of 022 validation/install.
            plugin_inbox = MergePluginParcelInbox(requester_root)
            plugin_inbox.validate_local(held[0]["parcel_id"])
            installed = plugin_inbox.install_local(
                held[0]["parcel_id"],
                note="requester explicitly installs the wanted grammar",
            )
            assert verify_install_receipt(installed["install_receipt"])

            satisfied = wants.inspect_gap(parcel_id)
            assert satisfied["status"] == "satisfied-local"
            assert WORK_CONTRACT in satisfied["local_compatible_contract_ids"]
            assert satisfied["candidate_count"] == 0

            # Once local state satisfies the gap, the old WANT cannot create
            # another request, even though its candidate snapshot remains.
            satisfied_gap_blocks_request = False
            try:
                wants.request_candidate(
                    want["want_id"],
                    candidate["candidate_id"],
                    return_parcel_port=requester_parcel_port,
                )
            except ValueError:
                satisfied_gap_blocks_request = True
            assert satisfied_gap_blocks_request

            # G — durable inspection keeps WANT separate from request history.
            shown = wants.show(want["want_id"])
            assert shown["want"]["want_id"] == want["want_id"]
            assert len(shown["request_links"]) == 1
            assert (
                shown["current_local_inspection"]["compatible_contract_ids"]
            )

            passed = all([
                empty_gap["candidate_count"] == 0,
                gap["candidate_count"] == 1,
                stale_candidate_refused,
                outgoing["receipt"]["kind"] == "REQUESTED",
                offer["installed_remotely"] is False,
                verify_install_receipt(installed["install_receipt"]),
                satisfied["status"] == "satisfied-local",
                satisfied_gap_blocks_request,
                len(shown["request_links"]) == 1,
            ])

            print(json.dumps({
                "simulation_passed": passed,
                "gap": {
                    "parcel_id": parcel_id,
                    "source": gap["source"],
                    "zero_candidate_want_valid": (
                        len(empty_want["candidates"]) == 0
                    ),
                },
                "matching": {
                    "source_advertised_packages": 2,
                    "exact_candidates": gap["candidate_count"],
                    "chosen_by_system": False,
                    "rank_present": "rank" in candidate,
                    "score_present": "score" in candidate,
                },
                "want": {
                    "want_id": want["want_id"],
                    "request_links_before_request": 0,
                    "candidate_count": len(want["candidates"]),
                },
                "revalidation": {
                    "unshare_blocks_request": stale_candidate_refused,
                    "local_satisfaction_blocks_repeat_request": (
                        satisfied_gap_blocks_request
                    ),
                },
                "request": {
                    "receipt_kind": outgoing["receipt"]["kind"],
                    "package_crossed": (
                        (outgoing["receipt"].get("extensions") or {})
                        .get("package_crossed")
                    ),
                    "durable_link": link["link_id"],
                },
                "offer": {
                    "separate_source_action": True,
                    "requester_status_after_offer": held[0]["status"],
                    "installed_remotely": offer["installed_remotely"],
                },
                "resolution": {
                    "explicit_install_verified": verify_install_receipt(
                        installed["install_receipt"]
                    ),
                    "gap_status_after_install": satisfied["status"],
                    "local_contracts": (
                        satisfied["local_compatible_contract_ids"]
                    ),
                },
            }, indent=2))
            return 0 if passed else 1
        finally:
            service.close()
            porch.shutdown()
            porch.server_close()
            porch_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
