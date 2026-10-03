#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 028."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any

from activation_ticket import (
    ActivationStore,
    ticket_is_fresh,
    verify_activation_ticket,
    verify_execution_receipt,
)
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
PARCEL_PORT = 7792


def one_door(root: Path) -> dict[str, Any]:
    doors = CuriousDoorsSurface(root).snapshot().get("doors") or []
    assert len(doors) == 1
    return doors[0]


def launch_for(
    root: Path,
    operation: str,
) -> dict[str, Any]:
    matches = [
        item
        for item in one_door(root).get("launches") or []
        if (item.get("destination") or {}).get("operation") == operation
    ]
    assert len(matches) == 1, (operation, matches)
    return matches[0]


class FailingActivationStore(ActivationStore):
    def _dispatch(
        self,
        descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        raise RuntimeError("simulated destination failure after revalidation")


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
                note="028 explicit activation ticket trial",
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
            activation = ActivationStore(requester_root)

            # A — ACT must be explicit and exact.
            wrong_phrase_refused = False
            try:
                activation.issue(
                    request_launch,
                    consent_phrase="YES",
                )
            except ValueError:
                wrong_phrase_refused = True
            assert wrong_phrase_refused

            issued_stale = activation.issue(
                request_launch,
                consent_phrase="ACT",
                ttl_seconds=120,
            )
            stale_ticket = issued_stale["ticket"]
            assert verify_activation_ticket(stale_ticket)
            assert ticket_is_fresh(stale_ticket)
            assert stale_ticket["human_identity_proven"] is False
            assert stale_ticket["one_operation"] is True
            assert issued_stale["preflight"]["status"] == "ready"

            tampered_ticket = copy.deepcopy(stale_ticket)
            tampered_ticket["ttl_seconds"] = 121
            assert verify_activation_ticket(tampered_ticket) is False

            # Synthetic expiry check without sleeping.
            issued_epoch = __import__("datetime").datetime.fromisoformat(
                stale_ticket["issued_at"].replace("Z", "+00:00")
            ).timestamp()
            assert ticket_is_fresh(
                stale_ticket,
                at=issued_epoch + 121,
            ) is False

            # B — context goes stale after consent. Execution claims/spends the
            # ticket, revalidates, refuses, signs receipt, and sends no request.
            shares.unshare(PACKAGE_ID)
            stale_execution = activation.execute(
                stale_ticket["ticket_id"]
            )
            stale_receipt = stale_execution["receipt"]
            assert stale_receipt["status"] == "REFUSED_STALE"
            assert stale_receipt["ticket_spent"] is True
            assert stale_receipt["operation_attempted"] is False
            assert stale_receipt["success"] is False
            assert verify_execution_receipt(stale_receipt)
            assert GrammarRequestInbox(source_root).list() == []

            stale_replay_refused = False
            try:
                activation.execute(stale_ticket["ticket_id"])
            except ValueError:
                stale_replay_refused = True
            assert stale_replay_refused

            # C — fresh consent after source re-shares can execute exactly one
            # real 024 request. The ticket cannot be replayed.
            shares.share(PACKAGE_ID)
            fresh_request_launch = launch_for(
                requester_root,
                "request-candidate",
            )
            issued_request = activation.issue(
                fresh_request_launch,
                consent_phrase="ACT",
            )
            request_ticket = issued_request["ticket"]
            request_execution = activation.execute(
                request_ticket["ticket_id"]
            )
            request_receipt = request_execution["receipt"]
            assert request_receipt["status"] == "EXECUTED"
            assert request_receipt["operation_attempted"] is True
            assert request_receipt["success"] is True
            assert verify_execution_receipt(request_receipt)

            source_requests = GrammarRequestInbox(source_root).list()
            assert len(source_requests) == 1
            assert MergePluginParcelInbox(requester_root).list() == []

            request_replay_refused = False
            try:
                activation.execute(request_ticket["ticket_id"])
            except ValueError:
                request_replay_refused = True
            assert request_replay_refused

            # D — source still separately owns OFFER.
            request_id = request_execution["result"]["outgoing_request"][
                "request"
            ]["request_id"]
            source_inbox = GrammarRequestInbox(source_root)
            offer = source_inbox.offer(
                request_id,
                note="028 source separately offers after activated request",
            )
            assert offer["installed_remotely"] is False

            plugin_rows = MergePluginParcelInbox(requester_root).list()
            assert len(plugin_rows) == 1
            plugin_parcel_id = plugin_rows[0]["parcel_id"]
            assert plugin_rows[0]["status"] == "HOLD"

            # E — fresh one-operation ticket performs real local VALIDATE.
            validate_launch = launch_for(
                requester_root,
                "validate-parcel",
            )
            issued_validate = activation.issue(
                validate_launch,
                consent_phrase="ACT",
            )
            validate_execution = activation.execute(
                issued_validate["ticket"]["ticket_id"]
            )
            validate_receipt = validate_execution["receipt"]
            assert validate_receipt["status"] == "EXECUTED"
            assert validate_receipt["success"] is True
            assert verify_execution_receipt(validate_receipt)

            validated_rows = MergePluginParcelInbox(requester_root).list()
            assert validated_rows[0]["status"] == "VALIDATED"

            # F — prove EXECUTION != SUCCESS. Issue a valid install ticket,
            # revalidate READY, then simulate destination failure after that
            # boundary. The ticket is spent and signed FAILED; state stays
            # VALIDATED, allowing a new explicit ACT later.
            install_launch = launch_for(
                requester_root,
                "install-parcel",
            )
            failing = FailingActivationStore(requester_root)
            issued_failure = failing.issue(
                install_launch,
                consent_phrase="ACT",
            )
            failed_execution = failing.execute(
                issued_failure["ticket"]["ticket_id"]
            )
            failed_receipt = failed_execution["receipt"]
            assert failed_receipt["status"] == "FAILED"
            assert failed_receipt["operation_attempted"] is True
            assert failed_receipt["ticket_spent"] is True
            assert failed_receipt["success"] is False
            assert failed_receipt["error"]["type"] == "RuntimeError"
            assert verify_execution_receipt(failed_receipt)
            assert (
                MergePluginParcelInbox(requester_root).list()[0]["status"]
                == "VALIDATED"
            )

            failed_replay_refused = False
            try:
                failing.execute(
                    issued_failure["ticket"]["ticket_id"]
                )
            except ValueError:
                failed_replay_refused = True
            assert failed_replay_refused

            # G — a new ACT creates a new ticket and may perform INSTALL once.
            fresh_install_launch = launch_for(
                requester_root,
                "install-parcel",
            )
            issued_install = activation.issue(
                fresh_install_launch,
                consent_phrase="ACT",
            )
            install_execution = activation.execute(
                issued_install["ticket"]["ticket_id"]
            )
            install_receipt = install_execution["receipt"]
            assert install_receipt["status"] == "EXECUTED"
            assert install_receipt["success"] is True
            assert verify_execution_receipt(install_receipt)

            plugin_state = MergePluginParcelInbox(requester_root).list()[0]
            assert plugin_state["status"] == "INSTALLED"
            underlying_install = install_execution["result"][
                "install_receipt"
            ]
            assert verify_install_receipt(underlying_install)

            # H — old install ticket is impossible to replay, and the resolved
            # door exposes only read-only pantry inspection.
            install_replay_refused = False
            try:
                activation.execute(
                    issued_install["ticket"]["ticket_id"]
                )
            except ValueError:
                install_replay_refused = True
            assert install_replay_refused

            resolved_door = one_door(requester_root)
            assert resolved_door["state"] == "resolved-local"
            resolved_operations = {
                (item.get("destination") or {}).get("operation")
                for item in resolved_door.get("launches") or []
            }
            assert "request-candidate" not in resolved_operations
            assert "validate-parcel" not in resolved_operations
            assert "install-parcel" not in resolved_operations
            assert "inspect-parcel" in resolved_operations

            # I — read-only launch can also be activated as one bounded action.
            inspect_launch = launch_for(
                requester_root,
                "inspect-parcel",
            )
            issued_inspect = activation.issue(
                inspect_launch,
                consent_phrase="ACT",
            )
            inspect_execution = activation.execute(
                issued_inspect["ticket"]["ticket_id"]
            )
            assert inspect_execution["receipt"]["status"] == "EXECUTED"
            assert inspect_execution["receipt"]["success"] is True
            assert CONTRACT_ID in inspect_execution["result"][
                "compatible_contract_ids"
            ]
            assert verify_execution_receipt(
                inspect_execution["receipt"]
            )

            passed = all([
                wrong_phrase_refused,
                verify_activation_ticket(stale_ticket),
                verify_execution_receipt(stale_receipt),
                stale_replay_refused,
                verify_execution_receipt(request_receipt),
                request_replay_refused,
                verify_execution_receipt(validate_receipt),
                verify_execution_receipt(failed_receipt),
                failed_replay_refused,
                verify_execution_receipt(install_receipt),
                install_replay_refused,
                verify_execution_receipt(
                    inspect_execution["receipt"]
                ),
            ])

            print(json.dumps({
                "simulation_passed": passed,
                "consent": {
                    "wrong_phrase_refused": wrong_phrase_refused,
                    "ticket_verifies": verify_activation_ticket(
                        stale_ticket
                    ),
                    "human_identity_proven": (
                        stale_ticket["human_identity_proven"]
                    ),
                    "one_operation": stale_ticket["one_operation"],
                    "synthetic_expiry_verified": (
                        not ticket_is_fresh(
                            stale_ticket,
                            at=issued_epoch + 121,
                        )
                    ),
                },
                "stale": {
                    "status": stale_receipt["status"],
                    "ticket_spent": stale_receipt["ticket_spent"],
                    "operation_attempted": (
                        stale_receipt["operation_attempted"]
                    ),
                    "replay_refused": stale_replay_refused,
                    "source_requests": len(
                        GrammarRequestInbox(source_root).list()
                    ),
                },
                "request": {
                    "status": request_receipt["status"],
                    "receipt_verified": verify_execution_receipt(
                        request_receipt
                    ),
                    "replay_refused": request_replay_refused,
                    "source_request_created": len(source_requests) == 1,
                    "package_crossed_by_request": False,
                },
                "validate": {
                    "status": validate_receipt["status"],
                    "plugin_status": validated_rows[0]["status"],
                },
                "failure": {
                    "status": failed_receipt["status"],
                    "ticket_spent": failed_receipt["ticket_spent"],
                    "success": failed_receipt["success"],
                    "plugin_status_after_failure": (
                        "VALIDATED"
                    ),
                    "replay_refused": failed_replay_refused,
                },
                "install": {
                    "status": install_receipt["status"],
                    "underlying_install_receipt_verified": (
                        verify_install_receipt(underlying_install)
                    ),
                    "plugin_status": plugin_state["status"],
                    "replay_refused": install_replay_refused,
                },
                "resolved": {
                    "door_state": resolved_door["state"],
                    "operations": sorted(
                        str(value)
                        for value in resolved_operations
                        if value is not None
                    ),
                },
            }, indent=2))
            return 0 if passed else 1

        finally:
            exchange.close()
            if porch is not None:
                porch.shutdown()
                porch.server_close()
            if porch_thread is not None:
                porch_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
