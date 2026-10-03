#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 027."""

from __future__ import annotations

import copy
import json
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from composition_want import CompositionWantStore, collect_observations
from curious_doors import (
    CuriousDoorsHTTPService,
    CuriousDoorsSurface,
    STATE_CANDIDATE,
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
from launch_descriptor import verify_launch_descriptor
from launch_preflight import preflight_launch
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


def only_door(surface: CuriousDoorsSurface) -> dict[str, Any]:
    doors = surface.snapshot().get("doors") or []
    assert len(doors) == 1
    return doors[0]


def launches(
    door: dict[str, Any],
    operation: str | None = None,
) -> list[dict[str, Any]]:
    rows = [
        item
        for item in (door.get("launches") or [])
        if isinstance(item, dict)
    ]
    if operation is None:
        return rows
    return [
        item
        for item in rows
        if (item.get("destination") or {}).get("operation") == operation
    ]


def assert_descriptor_inert(descriptor: dict[str, Any]) -> None:
    assert verify_launch_descriptor(descriptor)
    assert descriptor["executes"] is False
    assert descriptor["permission_transfer"] is False
    assert descriptor["consent_granted"] is False
    assert descriptor["requirements"]["explicit_user_selection"] is True
    assert descriptor["requirements"]["destination_revalidation"] is True
    assert descriptor["requirements"]["execution_revalidation"] is True
    for forbidden in (
        "argv",
        "href",
        "command",
        "display_command",
        "shell",
        "executable",
        "consent_token",
        "authorization",
    ):
        assert forbidden not in descriptor
        assert forbidden not in descriptor["destination"]


def assert_preflight_inert(result: dict[str, Any]) -> None:
    assert result["executes"] is False
    assert result["authorization_granted"] is False
    assert result["consent_granted"] is False
    assert result["permission_transfer"] is False
    assert result["execution_revalidation_required"] is True
    proposal = result.get("proposal")
    if proposal is not None:
        assert proposal["executes"] is False
        assert proposal["authorization_granted"] is False
        assert proposal["consent_granted"] is False
        assert proposal["requires_separate_operator_action"] is True
        assert proposal["execution_revalidation_required"] is True


def http_get_json(url: str) -> tuple[int, dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=5) as response:
        value = json.loads(response.read().decode("utf-8"))
        assert isinstance(value, dict)
        return int(response.status), value


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

        shares = GrammarShareStore(source_root)
        shares.share(PACKAGE_ID)

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

        surface_server: CuriousDoorsHTTPService | None = None

        try:
            parcel_id = admit_work_parcel(
                parcel_source_root,
                requester_root,
            )
            wants = CompositionWantStore(requester_root)
            want = wants.declare_want(
                parcel_id,
                note="027 typed launch descriptor witness",
            )
            surface = CuriousDoorsSurface(requester_root)

            # A — initial machine launch channel is separate from 026 navigation.
            open_door = only_door(surface)
            assert len(open_door["navigation"]) >= 2
            open_launches = launches(open_door)
            assert len(open_launches) == 2
            for descriptor in open_launches:
                assert_descriptor_inert(descriptor)

            show_descriptor = launches(open_door, "show-want")[0]
            refresh_descriptor = launches(
                open_door,
                "refresh-candidates",
            )[0]

            before_show = file_snapshot(requester_root)
            show_preflight = preflight_launch(
                show_descriptor,
                root=requester_root,
            )
            after_show = file_snapshot(requester_root)
            assert before_show == after_show
            assert show_preflight["status"] == "ready"
            assert_preflight_inert(show_preflight)
            assert show_preflight["network_read_performed"] is False

            before_refresh = file_snapshot(requester_root)
            refresh_preflight = preflight_launch(
                refresh_descriptor,
                root=requester_root,
            )
            after_refresh = file_snapshot(requester_root)
            assert before_refresh == after_refresh
            assert refresh_preflight["status"] == "ready"
            assert_preflight_inert(refresh_preflight)

            # B — explicit 024 refresh elsewhere makes a request launch.
            observations = collect_observations(
                exchange_urls=[exchange_url],
            )
            refreshed = wants.refresh(
                want["want_id"],
                observations=observations,
            )
            assert len(refreshed["candidates"]) == 1
            candidate = refreshed["candidates"][0]

            candidate_door = only_door(surface)
            assert candidate_door["state"] == STATE_CANDIDATE
            request_descriptor = launches(
                candidate_door,
                "request-candidate",
            )[0]
            assert_descriptor_inert(request_descriptor)
            assert (
                request_descriptor["context"]["candidate_id"]
                == candidate["candidate_id"]
            )

            # C — destination preflight performs fresh remote read but no request.
            source_requests = GrammarRequestInbox(source_root)
            assert source_requests.list() == []
            before_request_preflight = file_snapshot(requester_root)
            request_preflight = preflight_launch(
                request_descriptor,
                root=requester_root,
            )
            after_request_preflight = file_snapshot(requester_root)
            assert before_request_preflight == after_request_preflight
            assert request_preflight["status"] == "ready"
            assert request_preflight["network_read_performed"] is True
            assert_preflight_inert(request_preflight)
            assert source_requests.list() == []

            # D — observation context is not durable permission. UNSHARE makes
            # the exact same descriptor stale at its destination.
            shares.unshare(PACKAGE_ID)
            stale_before = file_snapshot(requester_root)
            stale_preflight = preflight_launch(
                request_descriptor,
                root=requester_root,
            )
            stale_after = file_snapshot(requester_root)
            assert stale_before == stale_after
            assert stale_preflight["status"] == "stale"
            assert_preflight_inert(stale_preflight)
            assert source_requests.list() == []

            # Restore share. Descriptor becomes ready again after fresh proof.
            shares.share(PACKAGE_ID)
            ready_again = preflight_launch(
                request_descriptor,
                root=requester_root,
            )
            assert ready_again["status"] == "ready"
            assert_preflight_inert(ready_again)

            # E — tamper is blocked before destination routing.
            tampered = copy.deepcopy(request_descriptor)
            tampered["context"]["candidate_id"] = "tampered"
            tampered_preflight = preflight_launch(
                tampered,
                root=requester_root,
            )
            assert tampered_preflight["status"] == "blocked"
            assert_preflight_inert(tampered_preflight)

            # F — actual 024 request still happens only in owning subsystem.
            requested = wants.request_candidate(
                want["want_id"],
                candidate["candidate_id"],
                return_parcel_port=parcel_port,
            )
            assert requested["outgoing_request"]["receipt"]["kind"] == (
                "REQUESTED"
            )
            requested_door = only_door(surface)
            assert requested_door["state"] == STATE_REQUESTED
            assert launches(requested_door, "validate-parcel") == []
            assert launches(requested_door, "install-parcel") == []

            # G — source OFFER creates HOLD; surface emits typed validate launch.
            request_id = requested["outgoing_request"]["request"]["request_id"]
            offer = source_requests.offer(
                request_id,
                note="027 source separately offers",
            )
            assert offer["installed_remotely"] is False

            held_rows = MergePluginParcelInbox(requester_root).list()
            assert len(held_rows) == 1
            held_id = held_rows[0]["parcel_id"]

            held_door = only_door(surface)
            validate_descriptor = launches(
                held_door,
                "validate-parcel",
            )[0]
            assert_descriptor_inert(validate_descriptor)
            assert (
                validate_descriptor["context"]["plugin_parcel_id"]
                == held_id
            )

            before_validate_preflight = file_snapshot(requester_root)
            validate_preflight = preflight_launch(
                validate_descriptor,
                root=requester_root,
            )
            after_validate_preflight = file_snapshot(requester_root)
            assert before_validate_preflight == after_validate_preflight
            assert validate_preflight["status"] == "ready"
            assert_preflight_inert(validate_preflight)

            # H — actual VALIDATE elsewhere makes old launch stale and produces
            # a new install launch.
            plugin_inbox = MergePluginParcelInbox(requester_root)
            plugin_inbox.validate_local(held_id)

            old_validate_after = preflight_launch(
                validate_descriptor,
                root=requester_root,
            )
            assert old_validate_after["status"] == "stale"
            assert_preflight_inert(old_validate_after)

            validated_door = only_door(surface)
            install_descriptor = launches(
                validated_door,
                "install-parcel",
            )[0]
            assert_descriptor_inert(install_descriptor)

            before_install_preflight = file_snapshot(requester_root)
            install_preflight = preflight_launch(
                install_descriptor,
                root=requester_root,
            )
            after_install_preflight = file_snapshot(requester_root)
            assert before_install_preflight == after_install_preflight
            assert install_preflight["status"] == "ready"
            assert_preflight_inert(install_preflight)

            # I — actual INSTALL elsewhere resolves gap; old install becomes
            # stale, resolved door emits only merge-pantry inspect launch.
            installed = plugin_inbox.install_local(
                held_id,
                note="027 explicit destination action",
            )
            assert verify_install_receipt(installed["install_receipt"])

            old_install_after = preflight_launch(
                install_descriptor,
                root=requester_root,
            )
            assert old_install_after["status"] == "stale"
            assert_preflight_inert(old_install_after)

            resolved_door = only_door(surface)
            assert resolved_door["state"] == STATE_RESOLVED
            assert CONTRACT_ID in (
                resolved_door["local_compatible_contract_ids"]
            )
            assert launches(resolved_door, "request-candidate") == []
            assert launches(resolved_door, "validate-parcel") == []
            assert launches(resolved_door, "install-parcel") == []

            inspect_descriptor = launches(
                resolved_door,
                "inspect-parcel",
            )[0]
            assert_descriptor_inert(inspect_descriptor)
            inspect_preflight = preflight_launch(
                inspect_descriptor,
                root=requester_root,
            )
            assert inspect_preflight["status"] == "ready"
            assert_preflight_inert(inspect_preflight)

            # J — a shell can fetch one descriptor by content id through the
            # read-only surface. Fetch does not route or execute it.
            surface_port = free_tcp_port()
            surface_server = CuriousDoorsHTTPService(
                root=requester_root,
                host="127.0.0.1",
                port=surface_port,
            )
            surface_server.start()
            launch_id = inspect_descriptor["launch_id"]
            launch_url = (
                f"http://127.0.0.1:{surface_port}/launch?launch_id="
                + urllib.parse.quote(launch_id, safe="")
            )
            http_before = file_snapshot(requester_root)
            status, fetched = http_get_json(launch_url)
            http_after = file_snapshot(requester_root)
            assert status == 200
            assert http_before == http_after
            assert fetched == inspect_descriptor
            assert verify_launch_descriptor(fetched)
            assert http_post_status(launch_url) == 405

            # K — preflight is not execution/authorization/consent.
            all_results = [
                show_preflight,
                refresh_preflight,
                request_preflight,
                stale_preflight,
                ready_again,
                tampered_preflight,
                validate_preflight,
                old_validate_after,
                install_preflight,
                old_install_after,
                inspect_preflight,
            ]
            for result in all_results:
                assert_preflight_inert(result)

            passed = all([
                before_show == after_show,
                before_refresh == after_refresh,
                before_request_preflight == after_request_preflight,
                stale_before == stale_after,
                before_validate_preflight == after_validate_preflight,
                before_install_preflight == after_install_preflight,
                http_before == http_after,
                request_preflight["status"] == "ready",
                stale_preflight["status"] == "stale",
                ready_again["status"] == "ready",
                tampered_preflight["status"] == "blocked",
                validate_preflight["status"] == "ready",
                old_validate_after["status"] == "stale",
                install_preflight["status"] == "ready",
                old_install_after["status"] == "stale",
                inspect_preflight["status"] == "ready",
            ])

            print(json.dumps({
                "simulation_passed": passed,
                "surface": {
                    "human_navigation_preserved": (
                        len(open_door["navigation"]) >= 2
                    ),
                    "typed_launches": len(open_launches),
                    "launch_fetch_read_only": http_before == http_after,
                },
                "descriptor": {
                    "verifies": verify_launch_descriptor(
                        request_descriptor
                    ),
                    "contains_argv": "argv" in request_descriptor,
                    "contains_href": "href" in request_descriptor,
                    "executes": request_descriptor["executes"],
                    "permission_transfer": (
                        request_descriptor["permission_transfer"]
                    ),
                    "consent_granted": (
                        request_descriptor["consent_granted"]
                    ),
                },
                "candidate_request": {
                    "ready_before_unshare": request_preflight["status"],
                    "stale_after_unshare": stale_preflight["status"],
                    "ready_after_reshare": ready_again["status"],
                    "network_read": (
                        request_preflight["network_read_performed"]
                    ),
                    "source_requests_after_preflight": 0,
                },
                "plugin_parcel": {
                    "validate_preflight": validate_preflight["status"],
                    "old_validate_after_actual_validate": (
                        old_validate_after["status"]
                    ),
                    "install_preflight": install_preflight["status"],
                    "old_install_after_actual_install": (
                        old_install_after["status"]
                    ),
                },
                "resolved": {
                    "state": resolved_door["state"],
                    "inspect_preflight": inspect_preflight["status"],
                    "local_contracts": (
                        resolved_door["local_compatible_contract_ids"]
                    ),
                },
                "authority": {
                    "all_preflights_execute": any(
                        result["executes"]
                        for result in all_results
                    ),
                    "any_authorization_granted": any(
                        result["authorization_granted"]
                        for result in all_results
                    ),
                    "any_consent_granted": any(
                        result["consent_granted"]
                        for result in all_results
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
