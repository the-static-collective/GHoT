#!/usr/bin/env python3
"""GHoT declared durable-state migrations — Experiment 017.

V0 policy:
- only exact registered kind/version/path migrations may run;
- source state is never edited in place;
- a canonical backup is written before target state;
- target state is atomically written and re-read;
- the BODY P-256 key signs before/after semantic content addresses;
- unknown versions remain blocked.

First real migration:
    ghot.organ.state / 0 -> 1
    .ghot/organ/state.v0.json -> .ghot/organ/state.v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
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


PLAN_KIND = "ghot.state.migration.plan"
PLAN_VERSION = "0"
RECEIPT_KIND = "ghot.state.migration.receipt"
RECEIPT_VERSION = "0"
RECEIPT_ID_DOMAIN = b"GHoT-StateMigrationReceipt-v0|"
RECEIPT_SIGNATURE_DOMAIN = b"GHoT-StateMigrationReceiptSignature-v0|"
RECEIPT_SIGNING_DOMAIN = "ghot.state-migration-receipt-signature/v0"

CURRENT_STATE = {
    "ghot.organ.state": "1",
    "ghot.field": "0",
}

MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


def semantic_address(value: Any) -> str:
    normalized = identity_safe(value)
    return "sha256:" + hashlib.sha256(jcs_bytes(normalized)).hexdigest()


def migrate_organ_state_v0_to_v1(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("kind") != "ghot.organ.state" or value.get("version") != "0":
        raise ValueError("migration requires ghot.organ.state version 0")
    migrated = dict(value)
    migrated["version"] = "1"
    migrated["presence"] = {
        "boot_id": None,
        "manifest_address": None,
        "startup_receipt_id": None,
    }
    return identity_safe(migrated)


MIGRATIONS: dict[str, dict[str, Any]] = {
    "ghot.organ.state/0->1": {
        "migration_id": "ghot.organ.state/0->1",
        "kind": "ghot.organ.state",
        "from_version": "0",
        "to_version": "1",
        "source_rel": "organ/state.v0.json",
        "target_rel": "organ/state.v1.json",
        "apply": migrate_organ_state_v0_to_v1,
    },
}


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"state file must contain a JSON object: {path}")
    return value


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    signing = receipt.get("signing") or {}
    return {
        "kind": receipt.get("kind"),
        "version": receipt.get("version"),
        "migration_id": receipt.get("migration_id"),
        "state_kind": receipt.get("state_kind"),
        "from_version": receipt.get("from_version"),
        "to_version": receipt.get("to_version"),
        "source_path": receipt.get("source_path"),
        "target_path": receipt.get("target_path"),
        "backup_path": receipt.get("backup_path"),
        "before_address": receipt.get("before_address"),
        "after_address": receipt.get("after_address"),
        "applied_at": receipt.get("applied_at"),
        "particular": receipt.get("particular"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    }


def derive_migration_receipt_id(receipt: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        RECEIPT_ID_DOMAIN + jcs_bytes(identity_safe(_receipt_body(receipt)))
    ).hexdigest()
    return "ghot-state-migration-receipt-v0:" + digest


def migration_receipt_signature_bytes(receipt: dict[str, Any]) -> bytes:
    body = identity_safe(_receipt_body(receipt))
    return RECEIPT_SIGNATURE_DOMAIN + jcs_bytes({
        "receipt_id": derive_migration_receipt_id(receipt),
        **body,
    })


def sign_migration_receipt(
    *,
    plan: dict[str, Any],
    before_address: str,
    after_address: str,
    backup_path: Path,
    signer: IdentityKey,
) -> dict[str, Any]:
    receipt = {
        "kind": RECEIPT_KIND,
        "version": RECEIPT_VERSION,
        "receipt_id": "",
        "migration_id": plan["migration_id"],
        "state_kind": plan["state_kind"],
        "from_version": plan["from_version"],
        "to_version": plan["to_version"],
        "source_path": plan["source_path"],
        "target_path": plan["target_path"],
        "backup_path": str(backup_path),
        "before_address": before_address,
        "after_address": after_address,
        "applied_at": timestamp_now(),
        "particular": signer.particular(),
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": RECEIPT_SIGNING_DOMAIN,
        },
    }
    receipt["receipt_id"] = derive_migration_receipt_id(receipt)
    receipt["signing"]["signature"] = signer.sign(
        migration_receipt_signature_bytes(receipt)
    )
    return receipt


def verify_migration_receipt(receipt: dict[str, Any]) -> bool:
    try:
        signing = receipt.get("signing") or {}
        if receipt.get("kind") != RECEIPT_KIND or receipt.get("version") != RECEIPT_VERSION:
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != RECEIPT_SIGNING_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        if receipt.get("particular") != particular_for_public_key(public_key):
            return False
        if receipt.get("receipt_id") != derive_migration_receipt_id(receipt):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            migration_receipt_signature_bytes(receipt),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


class StateMigrator:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.migration_root = self.root / "migrations"
        self.backups_dir = self.migration_root / "backups"
        self.receipts_dir = self.migration_root / "receipts"

    def _plan_for(self, spec: dict[str, Any]) -> dict[str, Any] | None:
        source = self.root / spec["source_rel"]
        target = self.root / spec["target_rel"]

        if target.exists():
            try:
                current = _read_object(target)
            except Exception:
                return None
            if (
                current.get("kind") == spec["kind"]
                and current.get("version") == spec["to_version"]
            ):
                return None
            return None

        if not source.exists():
            return None
        try:
            value = _read_object(source)
        except Exception:
            return None
        if (
            value.get("kind") != spec["kind"]
            or value.get("version") != spec["from_version"]
        ):
            return None

        migrated = spec["apply"](value)
        return {
            "kind": PLAN_KIND,
            "version": PLAN_VERSION,
            "migration_id": spec["migration_id"],
            "state_kind": spec["kind"],
            "from_version": spec["from_version"],
            "to_version": spec["to_version"],
            "source_path": str(source),
            "target_path": str(target),
            "before_address": semantic_address(value),
            "proposed_after_address": semantic_address(migrated),
            "available": True,
        }

    def plans(self) -> list[dict[str, Any]]:
        plans = []
        for migration_id in sorted(MIGRATIONS):
            plan = self._plan_for(MIGRATIONS[migration_id])
            if plan is not None:
                plans.append(plan)
        return plans

    def inspect(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        migration_required = False
        available = self.plans()
        available_by_source = {
            plan["source_path"]: plan
            for plan in available
        }

        organ_v1 = self.root / "organ" / "state.v1.json"
        organ_v0 = self.root / "organ" / "state.v0.json"

        if organ_v1.exists():
            try:
                value = _read_object(organ_v1)
                supported = (
                    value.get("kind") == "ghot.organ.state"
                    and value.get("version") == "1"
                )
                checks.append({
                    "path": str(organ_v1),
                    "status": "compatible" if supported else "migration-required",
                    "kind": value.get("kind"),
                    "version": value.get("version"),
                    "canonical": True,
                })
                if not supported:
                    migration_required = True
            except Exception as exc:
                checks.append({
                    "path": str(organ_v1),
                    "status": "invalid",
                    "kind": None,
                    "version": None,
                    "canonical": True,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                migration_required = True

            if organ_v0.exists():
                checks.append({
                    "path": str(organ_v0),
                    "status": "legacy-source-preserved",
                    "kind": "ghot.organ.state",
                    "version": "0",
                    "canonical": False,
                })
        elif organ_v0.exists():
            try:
                value = _read_object(organ_v0)
                path_key = str(organ_v0)
                plan = available_by_source.get(path_key)
                if plan is not None:
                    checks.append({
                        "path": path_key,
                        "status": "migration-available",
                        "kind": value.get("kind"),
                        "version": value.get("version"),
                        "canonical": False,
                        "migration_id": plan["migration_id"],
                        "target_path": plan["target_path"],
                    })
                else:
                    checks.append({
                        "path": path_key,
                        "status": "migration-required",
                        "kind": value.get("kind"),
                        "version": value.get("version"),
                        "canonical": False,
                    })
                migration_required = True
            except Exception as exc:
                checks.append({
                    "path": str(organ_v0),
                    "status": "invalid",
                    "kind": None,
                    "version": None,
                    "canonical": False,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                migration_required = True
        else:
            checks.append({
                "path": str(organ_v1),
                "status": "absent",
                "kind": None,
                "version": None,
                "canonical": True,
            })

        field_path = self.root / "field.v0.json"
        if not field_path.exists():
            checks.append({
                "path": str(field_path),
                "status": "absent",
                "kind": None,
                "version": None,
                "canonical": True,
            })
        else:
            try:
                field = _read_object(field_path)
                supported = (
                    field.get("kind") == "ghot.field"
                    and field.get("version") == "0"
                )
                checks.append({
                    "path": str(field_path),
                    "status": "compatible" if supported else "migration-required",
                    "kind": field.get("kind"),
                    "version": field.get("version"),
                    "canonical": True,
                })
                if not supported:
                    migration_required = True
            except Exception as exc:
                checks.append({
                    "path": str(field_path),
                    "status": "invalid",
                    "kind": None,
                    "version": None,
                    "canonical": True,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                migration_required = True

        return {
            "status": "migration-required" if migration_required else "compatible",
            "migration_required": migration_required,
            "checks": checks,
            "available_migrations": available,
            "automatic_migrations_applied": [],
        }

    def _backup_path(
        self,
        migration_id: str,
        before_address: str,
    ) -> Path:
        safe_id = migration_id.replace("/", "_").replace("->", "_to_")
        digest = before_address.split(":", 1)[-1]
        return self.backups_dir / safe_id / f"{digest}.json"

    def _receipt_path(self, receipt_id: str) -> Path:
        safe = receipt_id.replace(":", "_")
        return self.receipts_dir / f"{safe}.json"

    def apply_plan(
        self,
        plan: dict[str, Any],
        *,
        signer: IdentityKey,
    ) -> dict[str, Any]:
        migration_id = str(plan.get("migration_id") or "")
        spec = MIGRATIONS.get(migration_id)
        if spec is None:
            raise ValueError(f"unregistered migration: {migration_id}")

        source = Path(str(plan["source_path"]))
        target = Path(str(plan["target_path"]))
        expected_source = self.root / spec["source_rel"]
        expected_target = self.root / spec["target_rel"]
        if source != expected_source or target != expected_target:
            raise ValueError("migration plan paths do not match registry")

        before = _read_object(source)
        if (
            before.get("kind") != spec["kind"]
            or before.get("version") != spec["from_version"]
        ):
            raise ValueError("source state no longer matches migration precondition")

        before_address = semantic_address(before)
        if before_address != plan.get("before_address"):
            raise ValueError("source content changed after migration plan")

        after = spec["apply"](before)
        after_address = semantic_address(after)
        if after_address != plan.get("proposed_after_address"):
            raise ValueError("migration output changed after plan")
        if (
            after.get("kind") != spec["kind"]
            or after.get("version") != spec["to_version"]
        ):
            raise ValueError("migration did not produce declared target kind/version")

        backup_path = self._backup_path(migration_id, before_address)
        if not backup_path.exists():
            _write_atomic(backup_path, identity_safe(before))

        _write_atomic(target, identity_safe(after))
        persisted = _read_object(target)
        if semantic_address(persisted) != after_address:
            raise RuntimeError("persisted migration target failed after-address verification")

        receipt = sign_migration_receipt(
            plan=plan,
            before_address=before_address,
            after_address=after_address,
            backup_path=backup_path,
            signer=signer,
        )
        if not verify_migration_receipt(receipt):
            raise RuntimeError("migration receipt failed local signature verification")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(self._receipt_path(receipt["receipt_id"]), receipt)

        return {
            "status": "applied",
            "plan": plan,
            "receipt": receipt,
            "target": persisted,
        }

    def apply_available(
        self,
        *,
        signer: IdentityKey,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for plan in self.plans():
            results.append(self.apply_plan(plan, signer=signer))
        after = self.inspect()
        return {
            "kind": "ghot.state.migration.run",
            "version": "0",
            "applied": results,
            "state": after,
        }

    def receipts(self) -> list[dict[str, Any]]:
        if not self.receipts_dir.is_dir():
            return []
        results = []
        for path in sorted(self.receipts_dir.glob("*.json")):
            try:
                value = _read_object(path)
            except Exception:
                continue
            results.append({
                **value,
                "verified": verify_migration_receipt(value),
            })
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect/apply declared GHoT state migrations.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    sub.add_parser("plan")
    sub.add_parser("apply")
    sub.add_parser("receipts")
    args = parser.parse_args()

    migrator = StateMigrator()

    if args.command == "inspect":
        print(json.dumps(migrator.inspect(), indent=2))
        return 0

    if args.command == "plan":
        print(json.dumps(migrator.plans(), indent=2))
        return 0

    if args.command == "apply":
        signer = IdentityKey.load_or_create(ROOT / "identity" / "body-p256.pem")
        result = migrator.apply_available(signer=signer)
        print(json.dumps(result, indent=2))
        return 0 if result["state"]["migration_required"] is False else 1

    if args.command == "receipts":
        print(json.dumps(migrator.receipts(), indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
