#!/usr/bin/env python3
"""Installable declarative merge-contract packages — Experiment 021.

Packages contain no executable Python. A package declares:
- merge-contract descriptor metadata;
- a bounded operation from the local merge DSL;
- inline schema declarations for the target state family;
- deterministic conformance fixtures.

Installation validates the package and fixtures, then stores the exact manifest
under GHOT_HOME and writes a BODY-signed install receipt. The pantry discovers
only installed packages whose manifest address still matches a verified receipt.

V0 DSL operation:
    catalog-object-snapshot/v0

It maps fields from an admitted object payload/source envelope into a local
catalog entry, keyed by declared entry fields. No eval/import/shell/network/file
operation is available to the package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable

from reference_node import ROOT
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    jcs_bytes,
    particular_for_public_key,
    timestamp_now,
    unb64url,
    verify_p256,
)
from state_migration import semantic_address


PACKAGE_KIND = "ghot.merge-plugin.package"
PACKAGE_VERSION = "0"
INSTALL_RECEIPT_KIND = "ghot.merge-plugin.install-receipt"
INSTALL_RECEIPT_VERSION = "0"
INSTALL_RECEIPT_ID_DOMAIN = b"GHoT-MergePluginInstallReceipt-v0|"
INSTALL_RECEIPT_SIGNATURE_DOMAIN = b"GHoT-MergePluginInstallReceiptSignature-v0|"
INSTALL_RECEIPT_SIGNING_DOMAIN = "ghot.merge-plugin-install-receipt-signature/v0"

SUPPORTED_OPERATIONS = {"catalog-object-snapshot/v0"}
MAX_PACKAGE_BYTES = 256 * 1024
MAX_FIXTURES = 32
MAX_ENTRY_FIELDS = 64


def _safe_name(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def package_address(package: dict[str, Any]) -> str:
    return semantic_address(identity_safe(package))


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _resolve_expression(
    expression: str,
    *,
    parcel: dict[str, Any],
    payload: dict[str, Any],
) -> Any:
    if expression == "source.particular":
        return parcel["source"]["particular"]
    if expression == "source.node_id":
        return parcel["source"]["node_id"]
    if expression == "parcel.id":
        return parcel["parcel_id"]
    if expression == "parcel.address":
        return parcel["parcel_address"]
    if expression == "payload.address":
        return parcel["payload"]["address"]
    if expression.startswith("payload."):
        key = expression[len("payload."):]
        if not key or "." in key or "/" in key:
            raise ValueError("payload field expression must name one direct key")
        if key not in payload:
            raise ValueError(f"payload field missing: {key}")
        return payload[key]
    raise ValueError(f"unsupported merge expression: {expression}")


def validate_package(package: dict[str, Any]) -> dict[str, Any]:
    normalized = identity_safe(package)
    encoded = jcs_bytes(normalized)
    if len(encoded) > MAX_PACKAGE_BYTES:
        raise ValueError(f"merge plugin exceeds {MAX_PACKAGE_BYTES} bytes")

    if normalized.get("kind") != PACKAGE_KIND:
        raise ValueError("invalid merge plugin package kind")
    if normalized.get("version") != PACKAGE_VERSION:
        raise ValueError("unsupported merge plugin package version")

    package_id = _require_text(normalized.get("package_id"), "package_id")
    package_version = _require_text(
        normalized.get("package_version"),
        "package_version",
    )
    contract = normalized.get("contract")
    operation = normalized.get("operation")
    schemas = normalized.get("schemas")
    fixtures = normalized.get("fixtures")

    if not isinstance(contract, dict):
        raise ValueError("contract must be an object")
    if not isinstance(operation, dict):
        raise ValueError("operation must be an object")
    if not isinstance(schemas, dict):
        raise ValueError("schemas must be an object")
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be an array")
    if len(fixtures) < 1 or len(fixtures) > MAX_FIXTURES:
        raise ValueError("package must contain 1..32 conformance fixtures")

    contract_id = _require_text(contract.get("contract_id"), "contract.contract_id")
    _require_text(contract.get("title"), "contract.title")
    _require_text(contract.get("description"), "contract.description")
    _require_text(contract.get("category"), "contract.category")

    source = contract.get("source")
    target = contract.get("target")
    if not isinstance(source, dict) or not isinstance(target, dict):
        raise ValueError("contract source/target must be objects")

    _require_text(source.get("state_kind"), "contract.source.state_kind")
    _require_text(source.get("state_version"), "contract.source.state_version")
    selector = source.get("selector")
    if not isinstance(selector, str):
        raise ValueError("contract.source.selector must be a string")
    payload_type = _require_text(
        source.get("payload_type"),
        "contract.source.payload_type",
    )
    if payload_type != "object":
        raise ValueError("021 plugin DSL currently accepts object payloads only")

    rel = _require_text(target.get("relative_path"), "contract.target.relative_path")
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ValueError("plugin target path must be relative and non-traversing")
    _require_text(target.get("state_kind"), "contract.target.state_kind")
    _require_text(target.get("state_version"), "contract.target.state_version")

    if contract.get("authority_effect") != "none":
        raise ValueError("plugin authority_effect must be none")
    if contract.get("freshness_effect") != "none":
        raise ValueError("plugin freshness_effect must be none")
    if _require_bool(
        contract.get("selection_required"),
        "contract.selection_required",
    ) is not True:
        raise ValueError("plugin contracts must require explicit selection")

    op_kind = operation.get("kind")
    if op_kind not in SUPPORTED_OPERATIONS:
        raise ValueError(f"unsupported merge plugin operation: {op_kind}")

    entry_fields = operation.get("entry_fields")
    key_fields = operation.get("key_fields")
    if not isinstance(entry_fields, dict):
        raise ValueError("operation.entry_fields must be an object")
    if not 1 <= len(entry_fields) <= MAX_ENTRY_FIELDS:
        raise ValueError("operation.entry_fields must contain 1..64 fields")
    if not isinstance(key_fields, list) or not key_fields:
        raise ValueError("operation.key_fields must be a non-empty array")

    for output_name, expression in entry_fields.items():
        _require_text(output_name, "operation entry output name")
        expr = _require_text(expression, f"operation.entry_fields.{output_name}")
        # Validate grammar without requiring a real payload.
        if expr not in {
            "source.particular",
            "source.node_id",
            "parcel.id",
            "parcel.address",
            "payload.address",
        } and not expr.startswith("payload."):
            raise ValueError(f"unsupported merge expression: {expr}")
    for field in key_fields:
        field_name = _require_text(field, "operation key field")
        if field_name not in entry_fields:
            raise ValueError("every key_field must be produced by entry_fields")

    target_schema = schemas.get("target")
    if not isinstance(target_schema, dict):
        raise ValueError("schemas.target must be an object")
    if target_schema.get("kind") != target.get("state_kind"):
        raise ValueError("target schema kind must match contract target kind")
    if target_schema.get("version") != target.get("state_version"):
        raise ValueError("target schema version must match contract target version")
    if target_schema.get("shape") != "catalog":
        raise ValueError("021 target schema shape must be catalog")

    seen_names: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise ValueError("fixture must be an object")
        name = _require_text(fixture.get("name"), "fixture.name")
        if name in seen_names:
            raise ValueError("fixture names must be unique")
        seen_names.add(name)
        for field in ("local_before", "parcel", "expected_after"):
            if not isinstance(fixture.get(field), dict):
                raise ValueError(f"fixture.{field} must be an object")

    return {
        "package_id": package_id,
        "package_version": package_version,
        "contract_id": contract_id,
        "package_address": package_address(normalized),
        "normalized": normalized,
    }


def _initial_for(package: dict[str, Any]) -> dict[str, Any]:
    target = package["contract"]["target"]
    return {
        "kind": target["state_kind"],
        "version": target["state_version"],
        "entries": [],
        "merged_parcels": [],
    }


def compile_package(
    package: dict[str, Any],
) -> tuple[dict[str, Any], Callable[[], dict[str, Any]], Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]]:
    checked = validate_package(package)
    normalized = checked["normalized"]
    contract = normalized["contract"]
    operation = normalized["operation"]
    target = contract["target"]

    def initial() -> dict[str, Any]:
        return identity_safe(_initial_for(normalized))

    def apply(
        local_state: dict[str, Any],
        admitted_context: dict[str, Any],
    ) -> dict[str, Any]:
        if (
            local_state.get("kind") != target["state_kind"]
            or local_state.get("version") != target["state_version"]
        ):
            raise ValueError("plugin local target kind/version mismatch")

        parcel = admitted_context.get("parcel")
        if not isinstance(parcel, dict):
            raise ValueError("plugin merge requires admitted parcel context")
        payload = (parcel.get("payload") or {}).get("value")
        if not isinstance(payload, dict):
            raise ValueError("plugin merge payload must be an object")

        entry: dict[str, Any] = {}
        for output_name, expression in operation["entry_fields"].items():
            entry[output_name] = _resolve_expression(
                expression,
                parcel=parcel,
                payload=payload,
            )
        entry = identity_safe(entry)

        key_fields = list(operation["key_fields"])

        def key_for(value: dict[str, Any]) -> tuple[str, ...]:
            parts = []
            for field in key_fields:
                if field not in value:
                    raise ValueError(f"catalog entry missing key field: {field}")
                parts.append(json.dumps(value[field], sort_keys=True, separators=(",", ":")))
            return tuple(parts)

        entries_by_key: dict[tuple[str, ...], dict[str, Any]] = {}
        for raw in local_state.get("entries") or []:
            if not isinstance(raw, dict):
                raise ValueError("plugin catalog entries must be objects")
            safe = identity_safe(raw)
            entries_by_key[key_for(safe)] = safe
        entries_by_key[key_for(entry)] = entry

        entries = [
            entries_by_key[key]
            for key in sorted(entries_by_key)
        ]
        merged_parcels = sorted(set(
            [
                str(item)
                for item in (local_state.get("merged_parcels") or [])
                if isinstance(item, str)
            ]
            + [str(parcel["parcel_id"])]
        ))

        return identity_safe({
            "kind": target["state_kind"],
            "version": target["state_version"],
            "entries": entries,
            "merged_parcels": merged_parcels,
        })

    spec = {
        "contract_id": contract["contract_id"],
        "title": contract["title"],
        "description": contract["description"],
        "category": contract["category"],
        "parcel_state_kind": contract["source"]["state_kind"],
        "parcel_state_version": contract["source"]["state_version"],
        "parcel_selector": contract["source"]["selector"],
        "payload_type": contract["source"]["payload_type"],
        "local_rel": contract["target"]["relative_path"],
        "local_kind": contract["target"]["state_kind"],
        "local_version": contract["target"]["state_version"],
        "authority_effect": "none",
        "freshness_effect": "none",
        "selection_required": True,
        "plugin_package_id": checked["package_id"],
        "plugin_package_version": checked["package_version"],
        "plugin_package_address": checked["package_address"],
        "operation_kind": operation["kind"],
        "initial": initial,
        "apply": apply,
    }
    return spec, initial, apply


def run_conformance(package: dict[str, Any]) -> dict[str, Any]:
    checked = validate_package(package)
    _spec, _initial, apply = compile_package(checked["normalized"])
    results = []
    for fixture in checked["normalized"]["fixtures"]:
        local_before = identity_safe(fixture["local_before"])
        parcel = identity_safe(fixture["parcel"])
        expected = identity_safe(fixture["expected_after"])
        actual = apply(
            local_before,
            {
                "parcel": parcel,
                "admitted": {},
                "admitted_ref": "sha256:" + "0" * 64,
            },
        )
        passed = actual == expected
        results.append({
            "name": fixture["name"],
            "passed": passed,
            "expected_address": semantic_address(expected),
            "actual_address": semantic_address(actual),
        })
        if not passed:
            raise ValueError(
                f"merge plugin fixture failed: {fixture['name']}"
            )
    return {
        "package_id": checked["package_id"],
        "package_address": checked["package_address"],
        "fixtures": results,
        "passed": all(item["passed"] for item in results),
    }


def _install_receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    signing = receipt.get("signing") or {}
    return {
        "kind": receipt.get("kind"),
        "version": receipt.get("version"),
        "receipt_id": None,
        "package_id": receipt.get("package_id"),
        "package_version": receipt.get("package_version"),
        "package_address": receipt.get("package_address"),
        "contract_id": receipt.get("contract_id"),
        "installed_path": receipt.get("installed_path"),
        "installed_at": receipt.get("installed_at"),
        "particular": receipt.get("particular"),
        "conformance": receipt.get("conformance"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    }


def derive_install_receipt_id(receipt: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        INSTALL_RECEIPT_ID_DOMAIN
        + jcs_bytes(identity_safe(_install_receipt_body(receipt)))
    ).hexdigest()
    return "ghot-merge-plugin-install-receipt-v0:" + digest


def install_receipt_signature_bytes(receipt: dict[str, Any]) -> bytes:
    body = identity_safe(_install_receipt_body(receipt))
    return INSTALL_RECEIPT_SIGNATURE_DOMAIN + jcs_bytes({
        "receipt_id": derive_install_receipt_id(receipt),
        **body,
    })


def sign_install_receipt(
    *,
    checked: dict[str, Any],
    installed_path: Path,
    conformance: dict[str, Any],
    signer: IdentityKey,
) -> dict[str, Any]:
    receipt = {
        "kind": INSTALL_RECEIPT_KIND,
        "version": INSTALL_RECEIPT_VERSION,
        "receipt_id": "",
        "package_id": checked["package_id"],
        "package_version": checked["package_version"],
        "package_address": checked["package_address"],
        "contract_id": checked["contract_id"],
        "installed_path": str(installed_path),
        "installed_at": timestamp_now(),
        "particular": signer.particular(),
        "conformance": {
            "passed": conformance["passed"],
            "fixture_count": len(conformance["fixtures"]),
        },
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": INSTALL_RECEIPT_SIGNING_DOMAIN,
        },
    }
    receipt["receipt_id"] = derive_install_receipt_id(receipt)
    receipt["signing"]["signature"] = signer.sign(
        install_receipt_signature_bytes(receipt)
    )
    return receipt


def verify_install_receipt(receipt: dict[str, Any]) -> bool:
    try:
        if (
            receipt.get("kind") != INSTALL_RECEIPT_KIND
            or receipt.get("version") != INSTALL_RECEIPT_VERSION
        ):
            return False
        signing = receipt.get("signing") or {}
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != INSTALL_RECEIPT_SIGNING_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        if receipt.get("particular") != particular_for_public_key(public_key):
            return False
        if receipt.get("receipt_id") != derive_install_receipt_id(receipt):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            install_receipt_signature_bytes(receipt),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


class MergePluginStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.base = self.root / "merge-plugins"
        self.packages_dir = self.base / "packages"
        self.receipts_dir = self.base / "receipts"
        self.disabled_dir = self.base / "disabled"
        self.signer = IdentityKey.load_or_create(
            self.root / "identity" / "body-p256.pem"
        )

    def _package_dir(self, package_id: str) -> Path:
        return self.packages_dir / _safe_name(package_id)

    def _manifest_path(self, package_id: str) -> Path:
        return self._package_dir(package_id) / "manifest.v0.json"

    def _receipt_path(self, package_id: str) -> Path:
        return self.receipts_dir / f"{_safe_name(package_id)}.json"

    def install(
        self,
        package: dict[str, Any],
        *,
        builtin_contract_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        checked = validate_package(package)
        contract_id = checked["contract_id"]
        if builtin_contract_ids and contract_id in builtin_contract_ids:
            raise ValueError("plugin contract_id collides with built-in contract")

        for item in self.list_installed(include_invalid=True):
            if (
                item.get("status") == "installed"
                and item.get("contract_id") == contract_id
                and item.get("package_id") != checked["package_id"]
            ):
                raise ValueError("plugin contract_id collides with installed contract")

        conformance = run_conformance(checked["normalized"])
        manifest_path = self._manifest_path(checked["package_id"])
        receipt_path = self._receipt_path(checked["package_id"])

        if manifest_path.exists():
            current = _read_object(manifest_path)
            if package_address(current) != checked["package_address"]:
                raise ValueError(
                    "package_id already installed with different content; remove first"
                )
            if receipt_path.exists():
                existing = _read_object(receipt_path)
                if (
                    verify_install_receipt(existing)
                    and existing.get("package_address") == checked["package_address"]
                ):
                    return existing

        _write_atomic(manifest_path, checked["normalized"])
        receipt = sign_install_receipt(
            checked=checked,
            installed_path=manifest_path,
            conformance=conformance,
            signer=self.signer,
        )
        if not verify_install_receipt(receipt):
            raise RuntimeError("new merge plugin install receipt failed verification")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(receipt_path, receipt)
        return receipt

    def remove(self, package_id: str) -> dict[str, Any]:
        package_dir = self._package_dir(package_id)
        if not package_dir.exists():
            raise ValueError("merge plugin is not installed")
        disabled = self.disabled_dir / f"{_safe_name(package_id)}-{uuid.uuid4()}"
        disabled.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(package_dir), str(disabled))
        return {
            "package_id": package_id,
            "removed": True,
            "preserved_at": str(disabled),
            "receipt_preserved": self._receipt_path(package_id).exists(),
        }

    def _status_for(self, manifest_path: Path) -> dict[str, Any]:
        try:
            package = _read_object(manifest_path)
            checked = validate_package(package)
        except Exception as exc:
            return {
                "status": "invalid",
                "manifest_path": str(manifest_path),
                "error": f"{type(exc).__name__}: {exc}",
            }
        receipt_path = self._receipt_path(checked["package_id"])
        if not receipt_path.exists():
            return {
                "status": "invalid",
                "package_id": checked["package_id"],
                "contract_id": checked["contract_id"],
                "manifest_path": str(manifest_path),
                "package_address": checked["package_address"],
                "error": "install receipt missing",
            }
        try:
            receipt = _read_object(receipt_path)
        except Exception as exc:
            return {
                "status": "invalid",
                "package_id": checked["package_id"],
                "contract_id": checked["contract_id"],
                "manifest_path": str(manifest_path),
                "package_address": checked["package_address"],
                "error": f"install receipt unreadable: {type(exc).__name__}: {exc}",
            }
        if not verify_install_receipt(receipt):
            return {
                "status": "invalid",
                "package_id": checked["package_id"],
                "contract_id": checked["contract_id"],
                "manifest_path": str(manifest_path),
                "package_address": checked["package_address"],
                "error": "install receipt failed signature verification",
            }
        if receipt.get("package_address") != checked["package_address"]:
            return {
                "status": "invalid",
                "package_id": checked["package_id"],
                "contract_id": checked["contract_id"],
                "manifest_path": str(manifest_path),
                "package_address": checked["package_address"],
                "error": "manifest address no longer matches install receipt",
            }
        return {
            "status": "installed",
            "package_id": checked["package_id"],
            "package_version": checked["package_version"],
            "contract_id": checked["contract_id"],
            "package_address": checked["package_address"],
            "manifest_path": str(manifest_path),
            "receipt_id": receipt.get("receipt_id"),
            "receipt_verified": True,
            "package": checked["normalized"],
        }

    def list_installed(
        self,
        *,
        include_invalid: bool = False,
    ) -> list[dict[str, Any]]:
        if not self.packages_dir.is_dir():
            return []
        result = []
        for path in sorted(self.packages_dir.glob("*/manifest.v0.json")):
            item = self._status_for(path)
            if include_invalid or item.get("status") == "installed":
                result.append(item)
        return result

    def contract_specs(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in self.list_installed():
            package = item.get("package")
            if not isinstance(package, dict):
                continue
            spec, _initial, _apply = compile_package(package)
            contract_id = spec["contract_id"]
            if contract_id in result:
                raise ValueError("duplicate installed plugin contract id")
            result[contract_id] = spec
        return result


def installed_contract_specs(root: Path) -> dict[str, dict[str, Any]]:
    return MergePluginStore(root).contract_specs()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and install declarative GHoT merge-contract plugins."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("package_file")

    install = sub.add_parser("install")
    install.add_argument("package_file")

    sub.add_parser("list")

    remove = sub.add_parser("remove")
    remove.add_argument("package_id")

    args = parser.parse_args()
    store = MergePluginStore()

    if args.command in {"validate", "install"}:
        path = Path(args.package_file).expanduser()
        package = _read_object(path)
        checked = validate_package(package)
        conformance = run_conformance(package)
        if args.command == "validate":
            print(json.dumps({
                "valid": True,
                "package_id": checked["package_id"],
                "contract_id": checked["contract_id"],
                "package_address": checked["package_address"],
                "conformance": conformance,
            }, indent=2))
            return 0

        # Import lazily to avoid state_merge <-> merge_plugin import cycle.
        from state_merge import MERGE_CONTRACTS

        receipt = store.install(
            package,
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        print(json.dumps(receipt, indent=2))
        return 0

    if args.command == "list":
        print(json.dumps(store.list_installed(include_invalid=True), indent=2))
        return 0

    if args.command == "remove":
        print(json.dumps(store.remove(args.package_id), indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
