#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 022."""

from __future__ import annotations

import copy
import json
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from merge_plugin_parcel import (
    MergePluginParcelExporter,
    MergePluginParcelInbox,
    send_bundle,
    sign_package_author,
    verify_bundle,
    verify_package_author,
)
from relatte_identity import IdentityKey, verify_receipt
from state_parcel import parcel_handler


PLUGIN_CONTRACT = "ghot.organ.work->foreign-work-catalog/v0"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_server(root: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        parcel_handler(root),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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
        relay_root = base / "relay"
        receiver_root = base / "receiver"
        unsigned_root = base / "unsigned-receiver"
        wrong_root = base / "wrong-target"

        author_signer = IdentityKey.load_or_create(
            author_root / "identity" / "body-p256.pem"
        )
        author = sign_package_author(package, author_signer)
        assert verify_package_author(author, package) is True

        receiver_signer = IdentityKey.load_or_create(
            receiver_root / "identity" / "body-p256.pem"
        )
        receiver_particular = receiver_signer.particular()

        # A — author and transport sender are independent.
        relay_exporter = MergePluginParcelExporter(relay_root)
        signed_bundle = relay_exporter.export(
            package,
            target_particular=receiver_particular,
            author=author,
        )
        assert verify_bundle(signed_bundle)
        assert (
            signed_bundle["parcel"]["author"]["particular"]
            == author_signer.particular()
        )
        assert (
            signed_bundle["parcel"]["source"]["particular"]
            != author_signer.particular()
        )
        assert (
            signed_bundle["crossing"]["source_particular"]
            == signed_bundle["parcel"]["source"]["particular"]
        )

        tampered = copy.deepcopy(signed_bundle)
        tampered["parcel"]["package"]["contract"]["title"] = "tampered"
        assert not verify_bundle(tampered)

        bad_author = copy.deepcopy(signed_bundle)
        bad_author["parcel"]["author"]["signing"]["signature"] = (
            "A" + bad_author["parcel"]["author"]["signing"]["signature"][1:]
        )
        assert not verify_bundle(bad_author)

        server, thread = run_server(receiver_root)
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            # B — real HTTP crossing may only HOLD.
            held = send_bundle(signed_bundle, base_url)
            assert verify_receipt(held)
            assert held["kind"] == "HELD"
            assert held["semantic_effect"] == "none"
            assert (held.get("extensions") or {}).get("network_install") is False

            inbox = MergePluginParcelInbox(receiver_root)
            rows = inbox.list()
            assert len(rows) == 1
            assert rows[0]["status"] == "HOLD"
            assert rows[0]["author_signature_status"] == "verified"

            store = MergePluginStore(receiver_root)
            pantry = MergeContractPantry(receiver_root)
            assert store.list_installed() == []
            assert PLUGIN_CONTRACT not in [
                item["contract_id"]
                for item in pantry.contracts()
            ]

            duplicate = send_bundle(signed_bundle, base_url)
            assert verify_receipt(duplicate)
            assert duplicate["kind"] == "HELD"
            assert (duplicate.get("extensions") or {}).get(
                "duplicate_crossing"
            ) is True
            assert store.list_installed() == []

            # There is no remote validate/install route.
            request = urllib.request.Request(
                base_url + "/merge-plugin-install",
                data=json.dumps({"parcel_id": "x"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            remote_install_absent = False
            try:
                urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as exc:
                remote_install_absent = exc.code == 404
            assert remote_install_absent

            # C — local VALIDATE runs package conformance but still installs
            # nothing and exposes no pantry grammar.
            parcel_id = signed_bundle["parcel"]["parcel_id"]
            validated = inbox.validate_local(parcel_id)
            assert verify_receipt(validated["receipt"])
            assert validated["receipt"]["kind"] == "VALIDATED"
            assert validated["validation"]["installable"] is True
            assert validated["validation"]["conformance"]["passed"] is True
            assert store.list_installed() == []
            assert PLUGIN_CONTRACT not in [
                item["contract_id"]
                for item in pantry.contracts()
            ]

            # D — only explicit local INSTALL activates the 021 plugin.
            installed = inbox.install_local(
                parcel_id,
                note="receiver explicitly accepts this grammar",
            )
            assert verify_install_receipt(installed["install_receipt"])
            assert verify_receipt(installed["parcel_receipt"])
            assert installed["parcel_receipt"]["kind"] == "INSTALLED"
            assert (
                (installed["parcel_receipt"].get("extensions") or {})
                .get("install_receipt_id")
                == installed["install_receipt"]["receipt_id"]
            )
            assert PLUGIN_CONTRACT in [
                item["contract_id"]
                for item in pantry.contracts()
            ]
            assert len(store.list_installed()) == 1

        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        # E — validation report drift blocks installation.
        drift_bundle = MergePluginParcelExporter(relay_root).export(
            package,
            target_particular=receiver_particular,
            author=author,
        )
        drift_inbox = MergePluginParcelInbox(receiver_root)
        drift_held = drift_inbox.receive(drift_bundle)
        assert drift_held["kind"] == "HELD"
        drift_id = drift_bundle["parcel"]["parcel_id"]
        drift_inbox.validate_local(drift_id)
        validation_path = (
            receiver_root
            / "merge-plugin-parcels"
            / "validation"
            / (
                drift_id.replace(":", "_").replace("/", "_")
                + ".json"
            )
        )
        report = json.loads(validation_path.read_text(encoding="utf-8"))
        report["installable"] = False
        write_json(validation_path, report)
        validation_drift_refused = False
        try:
            drift_inbox.install_local(drift_id)
        except ValueError:
            validation_drift_refused = True
        assert validation_drift_refused

        # F — local REJECT is terminal and never installs.
        reject_bundle = MergePluginParcelExporter(relay_root).export(
            package,
            target_particular=receiver_particular,
            author=author,
        )
        reject_id = reject_bundle["parcel"]["parcel_id"]
        reject_inbox = MergePluginParcelInbox(receiver_root)
        assert reject_inbox.receive(reject_bundle)["kind"] == "HELD"
        rejected = reject_inbox.reject_local(
            reject_id,
            note="receiver declines this package",
        )
        assert verify_receipt(rejected)
        assert rejected["kind"] == "REJECTED"
        reject_install_refused = False
        try:
            reject_inbox.install_local(reject_id)
        except ValueError:
            reject_install_refused = True
        assert reject_install_refused

        # G — wrong-target package is signed REFUSED and never enters inbox.
        wrong_signer = IdentityKey.load_or_create(
            wrong_root / "identity" / "body-p256.pem"
        )
        wrong_bundle = MergePluginParcelExporter(relay_root).export(
            package,
            target_particular=wrong_signer.particular(),
            author=author,
        )
        wrong_receipt = MergePluginParcelInbox(receiver_root).receive(
            wrong_bundle
        )
        assert verify_receipt(wrong_receipt)
        assert wrong_receipt["kind"] == "REFUSED"
        assert all(
            row["parcel_id"] != wrong_bundle["parcel"]["parcel_id"]
            for row in MergePluginParcelInbox(receiver_root).list()
        )

        # H — author signatures are optional. An unsigned parcel may still be
        # explicitly validated + installed by another receiver.
        unsigned_signer = IdentityKey.load_or_create(
            unsigned_root / "identity" / "body-p256.pem"
        )
        unsigned_bundle = MergePluginParcelExporter(relay_root).export(
            package,
            target_particular=unsigned_signer.particular(),
        )
        assert verify_bundle(unsigned_bundle)
        assert unsigned_bundle["parcel"]["author"] is None
        unsigned_inbox = MergePluginParcelInbox(unsigned_root)
        unsigned_hold = unsigned_inbox.receive(unsigned_bundle)
        assert unsigned_hold["kind"] == "HELD"
        unsigned_id = unsigned_bundle["parcel"]["parcel_id"]
        unsigned_validation = unsigned_inbox.validate_local(unsigned_id)
        assert (
            unsigned_validation["validation"]["author_signature_status"]
            == "unsigned"
        )
        unsigned_install = unsigned_inbox.install_local(
            unsigned_id,
            note="explicit local install of unsigned package",
        )
        assert verify_install_receipt(unsigned_install["install_receipt"])
        assert PLUGIN_CONTRACT in [
            item["contract_id"]
            for item in MergeContractPantry(unsigned_root).contracts()
        ]

        # I — persisted receiver receipts all remain verifiable.
        all_receipts = MergePluginParcelInbox(receiver_root).receipts()
        assert all(item["verified"] is True for item in all_receipts)

        passed = all([
            verify_package_author(author, package) is True,
            verify_bundle(signed_bundle),
            not verify_bundle(tampered),
            not verify_bundle(bad_author),
            remote_install_absent,
            validation_drift_refused,
            reject_install_refused,
            verify_receipt(wrong_receipt),
            verify_install_receipt(unsigned_install["install_receipt"]),
            all(item["verified"] is True for item in all_receipts),
        ])

        print(json.dumps({
            "simulation_passed": passed,
            "authorship": {
                "author_verified": verify_package_author(author, package),
                "author_particular": author_signer.particular(),
                "transport_particular": (
                    signed_bundle["parcel"]["source"]["particular"]
                ),
                "author_independent_from_transport": (
                    author_signer.particular()
                    != signed_bundle["parcel"]["source"]["particular"]
                ),
                "tampered_package_rejected": not verify_bundle(tampered),
                "tampered_author_signature_rejected": (
                    not verify_bundle(bad_author)
                ),
            },
            "network": {
                "first_disposition": held["kind"],
                "duplicate_disposition": duplicate["kind"],
                "remote_install_route_absent": remote_install_absent,
                "network_install": (
                    (held.get("extensions") or {}).get("network_install")
                ),
            },
            "local_lifecycle": {
                "validated_without_install": (
                    validated["receipt"]["kind"] == "VALIDATED"
                ),
                "install_receipt_verified": verify_install_receipt(
                    installed["install_receipt"]
                ),
                "plugin_visible_after_explicit_install": (
                    PLUGIN_CONTRACT in [
                        item["contract_id"]
                        for item in pantry.contracts()
                    ]
                ),
                "validation_drift_refused": validation_drift_refused,
                "reject_install_refused": reject_install_refused,
            },
            "targeting": {
                "wrong_target": wrong_receipt["kind"],
            },
            "unsigned": {
                "author_status": (
                    unsigned_validation["validation"][
                        "author_signature_status"
                    ]
                ),
                "explicit_install_verified": verify_install_receipt(
                    unsigned_install["install_receipt"]
                ),
            },
            "receipts_verified": all(
                item["verified"] is True for item in all_receipts
            ),
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
