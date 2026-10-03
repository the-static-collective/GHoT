#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 021."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any

from merge_contract_pantry import MergeContractPantry
from merge_plugin import (
    MergePluginStore,
    package_address,
    run_conformance,
    validate_package,
    verify_install_receipt,
)
from relatte_identity import IdentityKey
from state_merge import MERGE_CONTRACTS, StateMergeEngine, verify_merge_receipt
from state_parcel import StateParcelExporter, StateParcelInbox


PLUGIN_CONTRACT = "ghot.organ.work->foreign-work-catalog/v0"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_state(status: str) -> dict[str, Any]:
    return {
        "kind": "ghot.organ.state",
        "version": "1",
        "node_id": "node-source",
        "started_at": "2026-10-03T02:00:00Z",
        "updated_at": "2026-10-03T02:01:00Z",
        "cycle": 4,
        "body": {
            "node_id": "node-source",
            "offers": [],
        },
        "field": {"bodies": []},
        "authorities": [],
        "work": {"status": status},
        "services": {},
        "errors": [],
        "presence": {
            "boot_id": "boot-plugin",
            "manifest_address": "sha256:" + "a" * 64,
            "startup_receipt_id": "startup-plugin",
        },
    }


def admit_work(
    source_root: Path,
    receiver_root: Path,
    *,
    status: str,
) -> dict[str, Any]:
    write_json(
        source_root / "organ" / "state.v1.json",
        source_state(status),
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
    held = inbox.receive(bundle)
    assert held["kind"] == "HELD"
    admitted = inbox.decide(
        bundle["parcel"]["parcel_id"],
        "ADMIT",
        note="021 plugin simulation admission",
    )
    assert admitted["kind"] == "ADMITTED"
    return bundle


def variant(
    package: dict[str, Any],
    *,
    package_id: str,
    contract_id: str,
) -> dict[str, Any]:
    value = copy.deepcopy(package)
    value["package_id"] = package_id
    value["contract"]["contract_id"] = contract_id
    value["contract"]["target"]["relative_path"] = (
        f"knowledge/plugins/{package_id}/catalog.v0.json"
    )
    return value


def expect_install_refused(
    store: MergePluginStore,
    package: dict[str, Any],
) -> bool:
    try:
        store.install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
    except ValueError:
        return True
    return False


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

    checked = validate_package(package)
    conformance = run_conformance(package)
    assert checked["contract_id"] == PLUGIN_CONTRACT
    assert conformance["passed"] is True

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_root = base / "source"
        receiver_root = base / "receiver"
        pantry = MergeContractPantry(receiver_root)
        engine = StateMergeEngine(receiver_root)
        store = MergePluginStore(receiver_root)

        # A — /work has no built-in grammar before local installation.
        work_bundle = admit_work(
            source_root,
            receiver_root,
            status="no-dispatch",
        )
        work_id = work_bundle["parcel"]["parcel_id"]
        before_install = pantry.inspect(work_id)
        assert before_install["compatible_contract_ids"] == []
        assert PLUGIN_CONTRACT not in [
            item["contract_id"]
            for item in pantry.contracts()
        ]

        # B — install only after validation + fixture conformance.
        install_receipt = store.install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        assert verify_install_receipt(install_receipt)
        assert install_receipt["package_address"] == package_address(package)
        assert install_receipt["conformance"]["passed"] is True
        assert install_receipt["conformance"]["fixture_count"] == 1

        # Same exact install is idempotent.
        install_again = store.install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        assert install_again["receipt_id"] == install_receipt["receipt_id"]

        installed = store.list_installed()
        assert len(installed) == 1
        assert installed[0]["status"] == "installed"
        assert installed[0]["receipt_verified"] is True

        contracts = pantry.contracts()
        ids = [item["contract_id"] for item in contracts]
        assert PLUGIN_CONTRACT in ids
        plugin_descriptor = next(
            item for item in contracts
            if item["contract_id"] == PLUGIN_CONTRACT
        )
        assert plugin_descriptor["origin"]["kind"] == "plugin"
        assert (
            plugin_descriptor["origin"]["package_id"]
            == package["package_id"]
        )
        assert (
            plugin_descriptor["origin"]["package_address"]
            == package_address(package)
        )
        assert (
            plugin_descriptor["origin"]["operation_kind"]
            == "catalog-object-snapshot/v0"
        )

        after_install = pantry.inspect(work_id)
        assert after_install["compatible_contract_ids"] == [PLUGIN_CONTRACT]

        # C — normal 020 selection + proposal + 019 APPLY works with the
        # dynamically installed contract.
        selection = pantry.select(work_id, PLUGIN_CONTRACT)
        proposal = pantry.propose(selection["selection_id"])
        plan = proposal["plan"]
        assert plan["contract_id"] == PLUGIN_CONTRACT

        target = (
            receiver_root
            / "knowledge"
            / "plugins"
            / "ghot.plugin.foreign-work-memory"
            / "foreign-work.v0.json"
        )
        assert not target.exists()
        merge_receipt = engine.apply(
            plan["plan_id"],
            note="021 installed plugin merge",
        )
        assert verify_merge_receipt(merge_receipt)
        assert target.exists()

        catalog = json.loads(target.read_text(encoding="utf-8"))
        assert catalog["kind"] == "ghot.foreign-work-catalog"
        assert catalog["version"] == "0"
        assert catalog["entries"][0]["status"] == "no-dispatch"
        assert (
            catalog["entries"][0]["source_particular"]
            == work_bundle["parcel"]["source"]["particular"]
        )

        # D — remove package after SELECT: proposal must fail because selection
        # cannot keep executing a grammar that is no longer locally installed.
        second_bundle = admit_work(
            source_root,
            receiver_root,
            status="completed",
        )
        second_id = second_bundle["parcel"]["parcel_id"]
        second_selection = pantry.select(second_id, PLUGIN_CONTRACT)
        removed = store.remove(package["package_id"])
        assert removed["removed"] is True
        assert PLUGIN_CONTRACT not in [
            item["contract_id"]
            for item in pantry.contracts()
        ]

        removed_selection_refused = False
        try:
            pantry.propose(second_selection["selection_id"])
        except ValueError:
            removed_selection_refused = True
        assert removed_selection_refused

        # Reinstall exact package to continue.
        reinstall = store.install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        assert verify_install_receipt(reinstall)
        assert PLUGIN_CONTRACT in [
            item["contract_id"]
            for item in pantry.contracts()
        ]

        # E — tampering with installed manifest invalidates discovery because
        # the signed install receipt witnesses the original package address.
        manifest_path = Path(reinstall["installed_path"])
        original_manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        tampered_manifest = copy.deepcopy(original_manifest)
        tampered_manifest["contract"]["title"] = "tampered title"
        write_json(manifest_path, tampered_manifest)

        all_status = store.list_installed(include_invalid=True)
        assert len(all_status) == 1
        assert all_status[0]["status"] == "invalid"
        assert "manifest address" in all_status[0]["error"]
        assert PLUGIN_CONTRACT not in [
            item["contract_id"]
            for item in pantry.contracts()
        ]

        # Restoring exact manifest restores receipt-valid discovery.
        write_json(manifest_path, original_manifest)
        assert store.list_installed()[0]["status"] == "installed"

        # F — invalid package classes are rejected before installation.
        unknown_operation = variant(
            package,
            package_id="ghot.plugin.unknown-operation",
            contract_id="ghot.test.unknown-operation/v0",
        )
        unknown_operation["operation"]["kind"] = "python.eval/v0"
        unknown_operation_refused = expect_install_refused(
            store,
            unknown_operation,
        )
        assert unknown_operation_refused

        bad_fixture = variant(
            package,
            package_id="ghot.plugin.bad-fixture",
            contract_id="ghot.test.bad-fixture/v0",
        )
        bad_fixture["fixtures"][0]["expected_after"]["entries"][0]["status"] = (
            "not-the-output"
        )
        bad_fixture_refused = expect_install_refused(store, bad_fixture)
        assert bad_fixture_refused

        path_traversal = variant(
            package,
            package_id="ghot.plugin.path-traversal",
            contract_id="ghot.test.path/v0",
        )
        path_traversal["contract"]["target"]["relative_path"] = (
            "../outside.json"
        )
        path_traversal_refused = expect_install_refused(
            store,
            path_traversal,
        )
        assert path_traversal_refused

        authority_claim = variant(
            package,
            package_id="ghot.plugin.authority",
            contract_id="ghot.test.authority/v0",
        )
        authority_claim["contract"]["authority_effect"] = "grant"
        authority_claim_refused = expect_install_refused(
            store,
            authority_claim,
        )
        assert authority_claim_refused

        built_in_collision = variant(
            package,
            package_id="ghot.plugin.collision",
            contract_id=next(iter(MERGE_CONTRACTS)),
        )
        collision_refused = expect_install_refused(
            store,
            built_in_collision,
        )
        assert collision_refused

        # G — package bytes cannot smuggle arbitrary source paths or nested
        # expression traversal through the bounded DSL.
        bad_expression = variant(
            package,
            package_id="ghot.plugin.bad-expression",
            contract_id="ghot.test.expression/v0",
        )
        bad_expression["operation"]["entry_fields"]["status"] = (
            "payload.__class__.__mro__"
        )
        bad_expression_refused = expect_install_refused(
            store,
            bad_expression,
        )
        assert bad_expression_refused

        passed = all([
            conformance["passed"],
            verify_install_receipt(install_receipt),
            verify_merge_receipt(merge_receipt),
            removed_selection_refused,
            unknown_operation_refused,
            bad_fixture_refused,
            path_traversal_refused,
            authority_claim_refused,
            collision_refused,
            bad_expression_refused,
        ])

        print(json.dumps({
            "simulation_passed": passed,
            "pre_install": {
                "work_compatible_contracts": (
                    before_install["compatible_contract_ids"]
                ),
            },
            "install": {
                "receipt_verified": verify_install_receipt(install_receipt),
                "fixture_passed": conformance["passed"],
                "idempotent": (
                    install_again["receipt_id"]
                    == install_receipt["receipt_id"]
                ),
                "plugin_visible_in_pantry": PLUGIN_CONTRACT in ids,
                "origin": plugin_descriptor["origin"],
            },
            "merge": {
                "contract_id": plan["contract_id"],
                "receipt_verified": verify_merge_receipt(merge_receipt),
                "target_kind": catalog["kind"],
                "remembered_status": catalog["entries"][0]["status"],
            },
            "lifecycle": {
                "remove_invalidates_selection": removed_selection_refused,
                "tamper_invalidates_discovery": all_status[0]["status"] == "invalid",
                "restore_recovers_discovery": (
                    store.list_installed()[0]["status"] == "installed"
                ),
            },
            "refusals": {
                "unknown_operation": unknown_operation_refused,
                "bad_fixture": bad_fixture_refused,
                "path_traversal": path_traversal_refused,
                "authority_claim": authority_claim_refused,
                "built_in_collision": collision_refused,
                "bad_expression": bad_expression_refused,
            },
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
