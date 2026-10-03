#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 023."""

from __future__ import annotations

import copy
import json
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from grammar_exchange import (
    GrammarExchangeService,
    GrammarRequestInbox,
    GrammarShareStore,
    advert_is_fresh,
    discover_exchanges,
    fetch_exchange_advert,
    inventory,
    make_exchange_request,
    request_is_fresh,
    send_request,
    verify_exchange_advert,
    verify_exchange_request,
)
from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from merge_plugin_parcel import (
    MergePluginParcelExporter,
    MergePluginParcelInbox,
    sign_package_author,
    verify_package_author,
)
from relatte_identity import IdentityKey, verify_receipt
from state_parcel import parcel_handler


PLUGIN_PACKAGE_ID = "ghot.plugin.foreign-work-memory"
PLUGIN_CONTRACT = "ghot.organ.work->foreign-work-catalog/v0"


def free_tcp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def start_parcel_porch(root: Path, port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", port),
        parcel_handler(root),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def install_authored_package(
    *,
    package: dict[str, Any],
    author_root: Path,
    receiver_root: Path,
) -> dict[str, Any]:
    receiver = IdentityKey.load_or_create(
        receiver_root / "identity" / "body-p256.pem"
    )
    author_signer = IdentityKey.load_or_create(
        author_root / "identity" / "body-p256.pem"
    )
    author = sign_package_author(package, author_signer)
    assert verify_package_author(author, package) is True

    bundle = MergePluginParcelExporter(author_root).export(
        package,
        target_particular=receiver.particular(),
        author=author,
    )
    inbox = MergePluginParcelInbox(receiver_root)
    held = inbox.receive(bundle)
    assert held["kind"] == "HELD"
    validated = inbox.validate_local(bundle["parcel"]["parcel_id"])
    assert validated["receipt"]["kind"] == "VALIDATED"
    installed = inbox.install_local(
        bundle["parcel"]["parcel_id"],
        note="023 source inventory bootstrap",
    )
    assert verify_install_receipt(installed["install_receipt"])
    return {
        "author": author,
        "bundle": bundle,
        "install": installed,
    }


def post_json(url: str, value: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    raw = json.dumps(value).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            return int(response.status), body
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        return int(exc.code), body


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    package_path = (
        repo_root
        / "examples"
        / "merge-plugins"
        / "foreign-work-memory.package.json"
    )
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert isinstance(package, dict)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        author_root = base / "author"
        source_root = base / "source"
        requester_root = base / "requester"
        wrong_return_root = base / "wrong-return"

        bootstrap = install_authored_package(
            package=package,
            author_root=author_root,
            receiver_root=source_root,
        )
        author = bootstrap["author"]

        source_store = MergePluginStore(source_root)
        source_pantry = MergeContractPantry(source_root)
        source_shares = GrammarShareStore(source_root)

        assert len(source_store.list_installed()) == 1
        assert PLUGIN_CONTRACT in [
            item["contract_id"]
            for item in source_pantry.contracts()
        ]

        # A — installed is not shareable.
        pre_share_inventory = inventory(source_root)
        assert pre_share_inventory["active_shares"] == []
        assert pre_share_inventory["installed"][0]["shareable"] is False

        exchange_port = free_tcp_port()
        discovery_port = free_udp_port()
        requester_parcel_port = free_tcp_port()
        wrong_parcel_port = free_tcp_port()

        requester_porch, requester_thread = start_parcel_porch(
            requester_root,
            requester_parcel_port,
        )
        wrong_porch, wrong_thread = start_parcel_porch(
            wrong_return_root,
            wrong_parcel_port,
        )

        service = GrammarExchangeService(
            root=source_root,
            host="127.0.0.1",
            port=exchange_port,
            discovery_port=discovery_port,
            parcel_port=7792,
        )
        service.start()
        exchange_url = f"http://127.0.0.1:{exchange_port}"

        try:
            advert_before = fetch_exchange_advert(exchange_url)
            assert verify_exchange_advert(advert_before)
            assert advert_is_fresh(advert_before)
            assert advert_before["packages"] == []

            # B — explicit share makes only metadata discoverable.
            share_record = source_shares.share(PLUGIN_PACKAGE_ID)
            assert share_record["shareable"] is True
            advert = fetch_exchange_advert(exchange_url)
            assert verify_exchange_advert(advert)
            assert len(advert["packages"]) == 1
            advertised = advert["packages"][0]
            assert advertised["package_id"] == PLUGIN_PACKAGE_ID
            assert advertised["package_address"] == share_record["package_address"]
            assert advertised["author_particular"] == author["particular"]

            tampered_advert = copy.deepcopy(advert)
            tampered_advert["packages"][0]["title"] = "tampered"
            assert verify_exchange_advert(tampered_advert) is False

            # C — signed UDP discovery returns the same share metadata but causes
            # no request, crossing, or install.
            observations = discover_exchanges(
                1.5,
                port=discovery_port,
                host="127.0.0.1",
            )
            assert len(observations) == 1
            observed_advert = observations[0]["advert"]
            assert verify_exchange_advert(observed_advert)
            assert observed_advert["packages"][0]["package_address"] == (
                share_record["package_address"]
            )
            assert MergePluginStore(requester_root).list_installed() == []
            assert MergePluginParcelInbox(requester_root).list() == []

            # D — signed request is a request only.
            outgoing = send_request(
                source_url=exchange_url,
                package_id=PLUGIN_PACKAGE_ID,
                package_address=share_record["package_address"],
                root=requester_root,
                return_parcel_port=requester_parcel_port,
                ttl_seconds=300,
            )
            request = outgoing["request"]
            request_receipt = outgoing["receipt"]
            assert verify_exchange_request(request)
            assert request_is_fresh(request)
            assert verify_receipt(request_receipt)
            assert request_receipt["kind"] == "REQUESTED"
            assert (
                (request_receipt.get("extensions") or {}).get("package_crossed")
                is False
            )
            assert MergePluginParcelInbox(requester_root).list() == []
            assert MergePluginStore(requester_root).list_installed() == []

            source_requests = GrammarRequestInbox(source_root)
            rows = source_requests.list()
            assert len(rows) == 1
            first_request_id = request["request_id"]
            first_row = rows[0]
            assert first_row["status"] == "REQUESTED"
            assert first_row["requester_observed_ip"] == "127.0.0.1"

            # Replay exact request is duplicate request storage only.
            status, duplicate_receipt = post_json(
                exchange_url + "/grammar-request",
                request,
            )
            assert status == 202
            assert verify_receipt(duplicate_receipt)
            assert (
                (duplicate_receipt.get("extensions") or {})
                .get("duplicate_request")
                is True
            )
            assert MergePluginParcelInbox(requester_root).list() == []

            # E — local OFFER verifies the requester's current parcel porch
            # particular, then crosses one 022 parcel. The requester only HOLDs.
            offer = source_requests.offer(
                first_request_id,
                note="source explicitly offers requested grammar",
            )
            assert offer["installed_remotely"] is False
            assert offer["author_particular"] == author["particular"]
            requester_rows = MergePluginParcelInbox(requester_root).list()
            assert len(requester_rows) == 1
            held_row = requester_rows[0]
            assert held_row["status"] == "HOLD"
            assert held_row["package_address"] == share_record["package_address"]
            assert held_row["author_particular"] == author["particular"]
            assert MergePluginStore(requester_root).list_installed() == []

            # F — requester still owns validation/install.
            requester_inbox = MergePluginParcelInbox(requester_root)
            validated = requester_inbox.validate_local(held_row["parcel_id"])
            assert validated["receipt"]["kind"] == "VALIDATED"
            assert MergePluginStore(requester_root).list_installed() == []

            installed = requester_inbox.install_local(
                held_row["parcel_id"],
                note="requester explicitly installs offered grammar",
            )
            assert verify_install_receipt(installed["install_receipt"])
            assert PLUGIN_CONTRACT in [
                item["contract_id"]
                for item in MergeContractPantry(requester_root).contracts()
            ]

            # G — request made while shared can be invalidated by local unshare
            # before OFFER. Discovery also stops advertising it.
            second = send_request(
                source_url=exchange_url,
                package_id=PLUGIN_PACKAGE_ID,
                package_address=share_record["package_address"],
                root=requester_root,
                return_parcel_port=requester_parcel_port,
                ttl_seconds=300,
            )
            second_id = second["request"]["request_id"]
            assert source_shares.unshare(PLUGIN_PACKAGE_ID) is True
            advert_unshared = fetch_exchange_advert(exchange_url)
            assert advert_unshared["packages"] == []

            unshared_offer_refused = False
            try:
                source_requests.offer(second_id)
            except ValueError:
                unshared_offer_refused = True
            assert unshared_offer_refused

            unshared_request_refused = False
            try:
                send_request(
                    source_url=exchange_url,
                    package_id=PLUGIN_PACKAGE_ID,
                    package_address=share_record["package_address"],
                    root=requester_root,
                    return_parcel_port=requester_parcel_port,
                )
            except ValueError:
                unshared_request_refused = True
            assert unshared_request_refused

            # H — decline is terminal.
            source_shares.share(PLUGIN_PACKAGE_ID)
            third = send_request(
                source_url=exchange_url,
                package_id=PLUGIN_PACKAGE_ID,
                package_address=share_record["package_address"],
                root=requester_root,
                return_parcel_port=requester_parcel_port,
            )
            third_id = third["request"]["request_id"]
            declined = source_requests.decline(
                third_id,
                note="source declines this request",
            )
            assert declined["status"] == "DECLINED"

            declined_offer_refused = False
            try:
                source_requests.offer(third_id)
            except ValueError:
                declined_offer_refused = True
            assert declined_offer_refused

            # I — return road is not requester identity. A signed request may
            # name a port, but OFFER probes the porch and checks its particular.
            advert_now = fetch_exchange_advert(exchange_url)
            wrong_request = make_exchange_request(
                root=requester_root,
                advert=advert_now,
                package_id=PLUGIN_PACKAGE_ID,
                package_address=share_record["package_address"],
                return_parcel_port=wrong_parcel_port,
                ttl_seconds=300,
            )
            status, wrong_request_receipt = post_json(
                exchange_url + "/grammar-request",
                wrong_request,
            )
            assert status == 202
            assert verify_receipt(wrong_request_receipt)

            road_identity_refused = False
            try:
                source_requests.offer(wrong_request["request_id"])
            except ValueError:
                road_identity_refused = True
            assert road_identity_refused
            assert MergePluginParcelInbox(wrong_return_root).list() == []

            # J — tampered/stale requests do not enter useful offer flow.
            bad_request = copy.deepcopy(wrong_request)
            bad_request["package_address"] = "sha256:" + "f" * 64
            assert verify_exchange_request(bad_request) is False

            stale_check = request_is_fresh(
                wrong_request,
                at=time.time() + 4000,
            )
            assert stale_check is False

            final_inventory = inventory(source_root)
            assert final_inventory["active_shares"][0]["package_id"] == (
                PLUGIN_PACKAGE_ID
            )

            passed = all([
                verify_exchange_advert(advert),
                verify_exchange_request(request),
                verify_receipt(request_receipt),
                verify_install_receipt(installed["install_receipt"]),
                unshared_offer_refused,
                unshared_request_refused,
                declined_offer_refused,
                road_identity_refused,
                not verify_exchange_request(bad_request),
                not stale_check,
            ])

            print(json.dumps({
                "simulation_passed": passed,
                "sharing": {
                    "installed_before_share": True,
                    "advertised_before_share": len(advert_before["packages"]),
                    "advertised_after_share": len(advert["packages"]),
                    "author_particular": advertised["author_particular"],
                },
                "discovery": {
                    "observations": len(observations),
                    "signed_advert_verified": verify_exchange_advert(
                        observed_advert
                    ),
                    "requester_installed_after_discovery": (
                        len(MergePluginStore(requester_root).list_installed())
                    ),
                },
                "request": {
                    "receipt_kind": request_receipt["kind"],
                    "package_crossed": (
                        (request_receipt.get("extensions") or {})
                        .get("package_crossed")
                    ),
                    "duplicate_request_only": (
                        (duplicate_receipt.get("extensions") or {})
                        .get("duplicate_request")
                    ),
                },
                "offer": {
                    "parcel_status_after_offer": held_row["status"],
                    "installed_remotely": offer["installed_remotely"],
                    "author_preserved": (
                        offer["author_particular"] == author["particular"]
                    ),
                },
                "requester": {
                    "explicit_install_verified": verify_install_receipt(
                        installed["install_receipt"]
                    ),
                    "plugin_visible_after_install": (
                        PLUGIN_CONTRACT in [
                            item["contract_id"]
                            for item in MergeContractPantry(
                                requester_root
                            ).contracts()
                        ]
                    ),
                },
                "refusals": {
                    "unshare_blocks_offer": unshared_offer_refused,
                    "unshare_blocks_new_request": unshared_request_refused,
                    "decline_blocks_offer": declined_offer_refused,
                    "return_road_identity_mismatch": road_identity_refused,
                    "tampered_request_invalid": (
                        not verify_exchange_request(bad_request)
                    ),
                    "stale_request_invalid": not stale_check,
                },
            }, indent=2))
            return 0 if passed else 1
        finally:
            service.close()
            requester_porch.shutdown()
            requester_porch.server_close()
            requester_thread.join(timeout=2)
            wrong_porch.shutdown()
            wrong_porch.server_close()
            wrong_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
