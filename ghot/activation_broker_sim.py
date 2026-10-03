#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 029."""

from __future__ import annotations

import json
import socket
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from activation_broker import (
    ActivationBroker,
    ActivationBrokerHTTPService,
    render_preview,
    render_result,
)
from activation_ticket import verify_execution_receipt
from activation_ticket_sim import PARCEL_PORT
from composition_want import CompositionWantStore, collect_observations
from curious_doors import CuriousDoorsSurface
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


def launch_for(root: Path, operation: str) -> dict[str, Any]:
    doors = CuriousDoorsSurface(root).snapshot().get("doors") or []
    assert len(doors) == 1
    matches = [
        item
        for item in (doors[0].get("launches") or [])
        if (item.get("destination") or {}).get("operation") == operation
    ]
    assert len(matches) == 1, (operation, matches)
    return matches[0]


def activation_ticket_count(root: Path) -> int:
    path = root / "activation-tickets" / "tickets"
    if not path.is_dir():
        return 0
    return len(list(path.glob("*.json")))


def http_get(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return (
            int(response.status),
            response.headers.get("Content-Type", ""),
            response.read().decode("utf-8"),
        )


def http_post_json(
    url: str,
    value: dict[str, Any],
    *,
    origin: str | None = None,
) -> tuple[int, str]:
    headers = {"Content-Type": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    request = urllib.request.Request(
        url,
        data=json.dumps(value).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return int(response.status), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8")


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
        source_install = source_store.install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        assert verify_install_receipt(source_install)
        shares = GrammarShareStore(source_root)
        shares.share(PACKAGE_ID)

        exchange_port = free_tcp_port()
        discovery_port = free_udp_port()
        exchange = GrammarExchangeService(
            root=source_root,
            host="127.0.0.1",
            port=exchange_port,
            discovery_port=discovery_port,
            parcel_port=PARCEL_PORT,
        )
        exchange.start()
        exchange_url = f"http://127.0.0.1:{exchange_port}"

        porch = None
        porch_thread = None
        broker_service = None

        try:
            porch, porch_thread = start_parcel_porch(
                requester_root,
                PARCEL_PORT,
            )

            parcel_id = admit_work_parcel(
                parcel_source_root,
                requester_root,
            )
            wants = CompositionWantStore(requester_root)
            want = wants.declare_want(
                parcel_id,
                note="029 broker ceremony trial",
            )
            observations = collect_observations(
                exchange_urls=[exchange_url],
            )
            refreshed = wants.refresh(
                want["want_id"],
                observations=observations,
            )
            assert len(refreshed["candidates"]) == 1

            request_launch = launch_for(
                requester_root,
                "request-candidate",
            )
            launch_id = request_launch["launch_id"]
            broker = ActivationBroker(requester_root)

            # A — preview is a read-only destination preflight, not consent.
            before_preview = file_snapshot(requester_root)
            preview = broker.preview(launch_id)
            after_preview = file_snapshot(requester_root)
            assert before_preview == after_preview
            assert preview["ready_to_act"] is True
            assert preview["required_phrase"] == "ACT"
            assert preview["preview_executes"] is False
            assert preview["broker_grants_consent"] is False
            assert preview["ui_click_grants_consent"] is False
            assert preview["proposal_address"].startswith("sha256:")
            assert activation_ticket_count(requester_root) == 0
            assert GrammarRequestInbox(source_root).list() == []

            preview_html = render_preview(preview)
            assert '<form method="post" action="/act">' in preview_html
            assert "<button" in preview_html.lower()
            assert "Type <code>ACT</code>" in preview_html
            assert "Issue one ticket and attempt once" in preview_html

            # B — wrong phrase and wrong proposal binding issue no ticket.
            wrong_phrase_refused = False
            try:
                broker.act(
                    launch_id=launch_id,
                    expected_proposal_address=preview["proposal_address"],
                    confirm="YES",
                )
            except ValueError:
                wrong_phrase_refused = True
            assert wrong_phrase_refused
            assert activation_ticket_count(requester_root) == 0

            wrong_binding_refused = False
            try:
                broker.act(
                    launch_id=launch_id,
                    expected_proposal_address="sha256:" + "0" * 64,
                    confirm="ACT",
                )
            except ValueError:
                wrong_binding_refused = True
            assert wrong_binding_refused
            assert activation_ticket_count(requester_root) == 0

            # C — exact preview becomes stale remotely before ACT.
            shares.unshare(PACKAGE_ID)
            stale_remote_refused = False
            try:
                broker.act(
                    launch_id=launch_id,
                    expected_proposal_address=preview["proposal_address"],
                    confirm="ACT",
                )
            except ValueError:
                stale_remote_refused = True
            assert stale_remote_refused
            assert activation_ticket_count(requester_root) == 0
            assert GrammarRequestInbox(source_root).list() == []

            shares.share(PACKAGE_ID)
            fresh_preview = broker.preview(launch_id)
            assert fresh_preview["ready_to_act"] is True

            # D — real HTTP preview is read-only. Browser ACT must be
            # same-origin; an unrelated origin cannot post consent.
            broker_port = free_tcp_port()
            broker_service = ActivationBrokerHTTPService(
                root=requester_root,
                host="127.0.0.1",
                port=broker_port,
            )
            broker_service.start()
            base_url = f"http://127.0.0.1:{broker_port}"
            preview_url = (
                base_url
                + "/preview?launch_id="
                + urllib.parse.quote(launch_id, safe="")
            )

            index_before = file_snapshot(requester_root)
            status, content_type, broker_index = http_get(base_url + "/")
            index_after = file_snapshot(requester_root)
            assert status == 200
            assert "text/html" in content_type
            assert index_before == index_after
            assert "selection only · no consent" in broker_index
            assert "/preview?launch_id=" in broker_index
            assert "<form" not in broker_index.lower()
            assert "<button" not in broker_index.lower()

            status, content_type, health_text = http_get(
                base_url + "/health"
            )
            assert status == 200
            assert "application/json" in content_type
            health = json.loads(health_text)
            assert health["preview_read_only"] is True
            assert health["click_grants_consent"] is False
            assert health["act_required"] is True
            assert health["browser_post_same_origin_required"] is True

            http_before = file_snapshot(requester_root)
            status, content_type, served_preview = http_get(preview_url)
            http_after = file_snapshot(requester_root)
            assert status == 200
            assert "text/html" in content_type
            assert http_before == http_after
            assert "Type <code>ACT</code>" in served_preview

            act_payload = {
                "launch_id": launch_id,
                "expected_proposal_address": fresh_preview[
                    "proposal_address"
                ],
                "confirm": "ACT",
                "ttl_seconds": 120,
            }

            status, body = http_post_json(
                base_url + "/act",
                act_payload,
                origin="https://unrelated.example",
            )
            assert status == 403
            assert activation_ticket_count(requester_root) == 0

            wrong_http = dict(act_payload)
            wrong_http["confirm"] = "CLICK"
            status, body = http_post_json(
                base_url + "/act",
                wrong_http,
                origin=base_url,
            )
            assert status == 409
            assert activation_ticket_count(requester_root) == 0

            # E — exact same-origin ACT coordinates one ticket + one attempt.
            status, body = http_post_json(
                base_url + "/act",
                act_payload,
                origin=base_url,
            )
            assert status == 200
            broker_result = json.loads(body)
            assert broker_result["receipt_verified"] is True
            assert broker_result["signed_status"] == "EXECUTED"
            assert broker_result["signed_success"] is True
            assert broker_result["verified_success"] is True
            assert broker_result["broker_inferred_success"] is False
            assert broker_result["success_claim_basis"] == (
                "verified-signed-execution-receipt"
            )
            receipt = broker_result["execution"]["receipt"]
            assert verify_execution_receipt(receipt)
            assert activation_ticket_count(requester_root) == 1

            source_requests = GrammarRequestInbox(source_root).list()
            assert len(source_requests) == 1

            # The same old launch is no longer current after the request, so a
            # second ACT cannot silently repeat it.
            status, body = http_post_json(
                base_url + "/act",
                act_payload,
                origin=base_url,
            )
            assert status == 409
            assert activation_ticket_count(requester_root) == 1
            assert len(GrammarRequestInbox(source_root).list()) == 1

            success_html = render_result(broker_result)
            assert (
                "Verified signed receipt reports EXECUTED with success=true."
                in success_html
            )
            assert "RESULT DISPLAY != SUCCESS CLAIM" in success_html

            failed_html = render_result({
                "receipt_verified": True,
                "signed_status": "FAILED",
                "signed_success": False,
                "verified_success": False,
            })
            assert "attempted operation that failed" in failed_html
            assert "EXECUTED with success=true" not in failed_html

            unverified_html = render_result({
                "receipt_verified": False,
                "signed_status": "EXECUTED",
                "signed_success": True,
                "verified_success": False,
            })
            assert "could not be verified" in unverified_html
            assert "EXECUTED with success=true" not in unverified_html

            # F — source still owns OFFER; broker later coordinates bounded
            # validate and install using their fresh current launches.
            request_id = broker_result["execution"]["result"][
                "outgoing_request"
            ]["request"]["request_id"]
            source_inbox = GrammarRequestInbox(source_root)
            offer = source_inbox.offer(
                request_id,
                note="029 source separately offers",
            )
            assert offer["installed_remotely"] is False
            plugin_rows = MergePluginParcelInbox(requester_root).list()
            assert len(plugin_rows) == 1
            assert plugin_rows[0]["status"] == "HOLD"

            validate_launch = launch_for(
                requester_root,
                "validate-parcel",
            )
            validate_preview = broker.preview(
                validate_launch["launch_id"]
            )
            validate_result = broker.act(
                launch_id=validate_launch["launch_id"],
                expected_proposal_address=validate_preview[
                    "proposal_address"
                ],
                confirm="ACT",
            )
            assert validate_result["verified_success"] is True
            assert (
                MergePluginParcelInbox(requester_root).list()[0]["status"]
                == "VALIDATED"
            )

            install_launch = launch_for(
                requester_root,
                "install-parcel",
            )
            install_preview = broker.preview(
                install_launch["launch_id"]
            )
            install_result = broker.act(
                launch_id=install_launch["launch_id"],
                expected_proposal_address=install_preview[
                    "proposal_address"
                ],
                confirm="ACT",
            )
            assert install_result["verified_success"] is True
            plugin_state = MergePluginParcelInbox(requester_root).list()[0]
            assert plugin_state["status"] == "INSTALLED"
            assert verify_install_receipt(
                install_result["execution"]["result"]["install_receipt"]
            )

            # G — resolved launch can be previewed/activated, but result truth
            # remains receipt-grounded.
            inspect_launch = launch_for(
                requester_root,
                "inspect-parcel",
            )
            inspect_preview = broker.preview(inspect_launch["launch_id"])
            inspect_result = broker.act(
                launch_id=inspect_launch["launch_id"],
                expected_proposal_address=inspect_preview[
                    "proposal_address"
                ],
                confirm="ACT",
            )
            assert inspect_result["verified_success"] is True
            assert CONTRACT_ID in inspect_result["execution"]["result"][
                "compatible_contract_ids"
            ]

            passed = all([
                before_preview == after_preview,
                wrong_phrase_refused,
                wrong_binding_refused,
                stale_remote_refused,
                index_before == index_after,
                http_before == http_after,
                broker_result["verified_success"] is True,
                validate_result["verified_success"] is True,
                install_result["verified_success"] is True,
                inspect_result["verified_success"] is True,
            ])

            print(json.dumps({
                "simulation_passed": passed,
                "preview": {
                    "read_only": before_preview == after_preview,
                    "ready": preview["ready_to_act"],
                    "click_grants_consent": (
                        preview["ui_click_grants_consent"]
                    ),
                    "proposal_address": preview["proposal_address"],
                },
                "refusals": {
                    "wrong_phrase": wrong_phrase_refused,
                    "wrong_proposal_binding": wrong_binding_refused,
                    "stale_remote_state": stale_remote_refused,
                    "cross_origin_http_status": 403,
                    "wrong_http_phrase_status": 409,
                },
                "http_surface": {
                    "index_read_only": index_before == index_after,
                    "preview_read_only": http_before == http_after,
                    "index_has_act_form": "<form" in broker_index.lower(),
                    "index_has_act_button": "<button" in broker_index.lower(),
                    "health_act_required": health["act_required"],
                    "same_origin_required": health[
                        "browser_post_same_origin_required"
                    ],
                },
                "request": {
                    "receipt_verified": broker_result[
                        "receipt_verified"
                    ],
                    "signed_status": broker_result["signed_status"],
                    "verified_success": broker_result[
                        "verified_success"
                    ],
                    "source_requests": len(source_requests),
                    "repeat_old_launch_refused": True,
                },
                "result_truth": {
                    "success_requires_verified_receipt": True,
                    "failed_display_claims_success": (
                        "EXECUTED with success=true" in failed_html
                    ),
                    "unverified_display_claims_success": (
                        "EXECUTED with success=true" in unverified_html
                    ),
                },
                "downstream": {
                    "validate_verified_success": validate_result[
                        "verified_success"
                    ],
                    "install_verified_success": install_result[
                        "verified_success"
                    ],
                    "plugin_status": plugin_state["status"],
                    "inspect_verified_success": inspect_result[
                        "verified_success"
                    ],
                },
            }, indent=2))
            return 0 if passed else 1

        finally:
            if broker_service is not None:
                broker_service.close()
            exchange.close()
            if porch is not None:
                porch.shutdown()
                porch.server_close()
            if porch_thread is not None:
                porch_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
