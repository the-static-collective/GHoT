#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 017."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from boot_presence import PresenceStore
from relatte_identity import IdentityKey
from state_migration import (
    MIGRATIONS,
    StateMigrator,
    migrate_organ_state_v0_to_v1,
    semantic_address,
    verify_migration_receipt,
)


def legacy_state(node: str = "node-migrate") -> dict[str, Any]:
    return {
        "kind": "ghot.organ.state",
        "version": "0",
        "node_id": node,
        "started_at": "2026-10-02T12:00:00+00:00",
        "updated_at": "2026-10-02T12:01:00+00:00",
        "cycle": 7,
        "body": {"node_id": node},
        "field": {"kind": "ghot.field.snapshot", "bodies": []},
        "authorities": [],
        "work": {"status": "no-dispatch"},
        "services": {"body_http": {"state": "awake"}},
        "errors": [],
    }


def body_record(root: Path, node: str) -> dict[str, Any]:
    signer = IdentityKey.load_or_create(root / "identity" / "body-p256.pem")
    return {
        "kind": "ghot.body",
        "version": "0",
        "node_id": node,
        "identity": {
            "available": True,
            "profile": "relatte.identity-signature/v0",
            "algorithm": "ECDSA-P256-SHA256",
            "particular": signer.particular(),
            "public_key": signer.public_jwk(),
        },
        "power": {
            "source": "ac",
            "battery_percent": None,
            "charging": True,
            "renewable_surplus": False,
            "willingness": "normal",
        },
        "offers": [],
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # A — normal real migration.
        root = base / "normal"
        source = root / "organ" / "state.v0.json"
        legacy = legacy_state()
        write_json(source, legacy)
        original_bytes = source.read_bytes()

        signer = IdentityKey.load_or_create(root / "identity" / "body-p256.pem")
        migrator = StateMigrator(root)
        before = migrator.inspect()
        plans = migrator.plans()
        assert before["migration_required"] is True
        assert len(plans) == 1
        assert plans[0]["mode"] == "apply"
        assert plans[0]["migration_id"] == "ghot.organ.state/0->1"

        run = migrator.apply_available(signer=signer)
        assert len(run["applied"]) == 1
        applied = run["applied"][0]
        receipt = applied["receipt"]
        target = root / "organ" / "state.v1.json"
        migrated = json.loads(target.read_text(encoding="utf-8"))

        assert migrated["kind"] == "ghot.organ.state"
        assert migrated["version"] == "1"
        assert migrated["presence"] == {
            "boot_id": None,
            "manifest_address": None,
            "startup_receipt_id": None,
        }
        assert verify_migration_receipt(receipt)
        assert receipt["before_address"] == semantic_address(legacy)
        assert receipt["after_address"] == semantic_address(migrated)
        backup = Path(receipt["backup_path"])
        assert backup.read_bytes() == original_bytes
        assert source.read_bytes() == original_bytes
        assert run["state"]["migration_required"] is False

        # Presence manifest must witness the migration receipt from this wake.
        repo = base / "repo"
        (repo / "ghot").mkdir(parents=True)
        (repo / "ghot" / "organ.py").write_text("# simulated organ\n", encoding="utf-8")
        presence = PresenceStore(root)
        manifest, startup_receipt = presence.wake(
            repo_root=repo,
            body_record=body_record(root, "node-migrate"),
            migration_run=run,
        )
        assert startup_receipt is not None
        witnessed = manifest["state"]["automatic_migrations_applied"]
        assert len(witnessed) == 1
        assert witnessed[0]["receipt_id"] == receipt["receipt_id"]
        assert presence.health()["status"] == "healthy"

        # B — idempotence: current v1 + valid receipt produces no new migration.
        second = migrator.apply_available(signer=signer)
        assert second["applied"] == []
        assert second["state"]["migration_required"] is False

        # C — interrupted migration: target exists, receipt does not.
        crash_root = base / "interrupted"
        crash_source = crash_root / "organ" / "state.v0.json"
        crash_legacy = legacy_state("node-crash")
        write_json(crash_source, crash_legacy)
        crash_target = crash_root / "organ" / "state.v1.json"
        write_json(crash_target, migrate_organ_state_v0_to_v1(crash_legacy))
        crash_signer = IdentityKey.load_or_create(
            crash_root / "identity" / "body-p256.pem"
        )
        crash_migrator = StateMigrator(crash_root)
        crash_inspect = crash_migrator.inspect()
        crash_plans = crash_migrator.plans()
        assert crash_inspect["migration_required"] is True
        assert len(crash_plans) == 1
        assert crash_plans[0]["mode"] == "reconcile-receipt"
        target_before = crash_target.read_bytes()
        reconciled = crash_migrator.apply_available(signer=crash_signer)
        assert len(reconciled["applied"]) == 1
        assert verify_migration_receipt(reconciled["applied"][0]["receipt"])
        assert crash_target.read_bytes() == target_before
        assert reconciled["state"]["migration_required"] is False

        # D — plan/source race: stale plan cannot mutate target.
        race_root = base / "race"
        race_source = race_root / "organ" / "state.v0.json"
        write_json(race_source, legacy_state("node-race"))
        race_signer = IdentityKey.load_or_create(
            race_root / "identity" / "body-p256.pem"
        )
        race_migrator = StateMigrator(race_root)
        stale_plan = race_migrator.plans()[0]
        changed = legacy_state("node-race")
        changed["cycle"] = 999
        write_json(race_source, changed)
        race_refused = False
        try:
            race_migrator.apply_plan(stale_plan, signer=race_signer)
        except ValueError:
            race_refused = True
        assert race_refused
        assert not (race_root / "organ" / "state.v1.json").exists()

        # E — unknown version has no migration and remains blocked.
        unknown_root = base / "unknown"
        unknown = legacy_state("node-unknown")
        unknown["version"] = "99"
        write_json(unknown_root / "organ" / "state.v0.json", unknown)
        unknown_migrator = StateMigrator(unknown_root)
        unknown_inspect = unknown_migrator.inspect()
        assert unknown_migrator.plans() == []
        assert unknown_inspect["migration_required"] is True

        passed = (
            verify_migration_receipt(receipt)
            and run["state"]["migration_required"] is False
            and second["applied"] == []
            and reconciled["state"]["migration_required"] is False
            and race_refused
            and unknown_inspect["migration_required"] is True
            and presence.health()["status"] == "healthy"
        )

        print(json.dumps({
            "simulation_passed": passed,
            "normal": {
                "migration_id": receipt["migration_id"],
                "before_address": receipt["before_address"],
                "after_address": receipt["after_address"],
                "receipt_verified": verify_migration_receipt(receipt),
                "backup_exact_bytes": backup.read_bytes() == original_bytes,
                "legacy_source_preserved": source.read_bytes() == original_bytes,
                "startup_manifest_witnessed_receipt": (
                    witnessed[0]["receipt_id"] == receipt["receipt_id"]
                ),
            },
            "idempotent_second_boot": second["applied"] == [],
            "interrupted_write": {
                "mode": crash_plans[0]["mode"],
                "receipt_reconciled": (
                    reconciled["state"]["migration_required"] is False
                ),
                "target_not_rewritten": crash_target.read_bytes() == target_before,
            },
            "stale_plan_refused": race_refused,
            "unknown_version_blocked": unknown_inspect["migration_required"],
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
