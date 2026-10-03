#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 016."""

from __future__ import annotations

import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from boot_presence import (
    PresenceStore,
    verify_boot_manifest,
    verify_startup_receipt,
)
from organ import PresenceHTTPService
from relatte_identity import IdentityKey


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
        "offers": [{
            "kind": "ghot.offer",
            "version": "0",
            "capability": "system.echo",
            "available": True,
            "power": {"class": "essential"},
        }],
    }


class FakeDaemon:
    def __init__(self) -> None:
        self.service_state: dict[str, Any] = {}

    def _event(self, event_type: str, detail: dict[str, Any]) -> None:
        return


def read_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=3) as response:
        value = json.loads(response.read().decode("utf-8"))
    assert isinstance(value, dict)
    return value


def main() -> int:
    old_surface = os.environ.get("GHOT_BOOT_SURFACE")
    old_instance = os.environ.get("GHOT_BOOT_INSTANCE")
    os.environ["GHOT_BOOT_SURFACE"] = "simulation"
    os.environ["GHOT_BOOT_INSTANCE"] = "presence-sim"

    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "state"
            repo = Path(tmp) / "repo"
            (repo / "ghot").mkdir(parents=True)
            (repo / "ghot" / "organ.py").write_text(
                "# simulated organ\n",
                encoding="utf-8",
            )

            record = body_record(root, "node-presence")
            store = PresenceStore(root)
            manifest, receipt = store.wake(
                repo_root=repo,
                body_record=record,
            )

            assert receipt is not None
            assert manifest["boot_surface"]["surface"] == "simulation"
            assert manifest["boot_surface"]["instance"] == "presence-sim"
            assert verify_boot_manifest(manifest)
            assert verify_startup_receipt(receipt)
            assert receipt["manifest_address"] == manifest["manifest_address"]
            assert receipt["particular"] == record["identity"]["particular"]

            runtime_path = root / "organ" / "state.v0.json"
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_state = {
                "kind": "ghot.organ.state",
                "version": "0",
                "node_id": "node-presence",
                "cycle": 1,
                "services": {
                    "body_http": {"state": "awake"},
                    "body_discovery": {"state": "awake"},
                    "presence_http": {"state": "awake"},
                },
                "errors": [],
            }
            runtime_path.write_text(
                json.dumps(runtime_state) + "\n",
                encoding="utf-8",
            )

            healthy = store.health()
            assert healthy["status"] == "healthy"

            daemon = FakeDaemon()
            service = PresenceHTTPService(
                daemon,
                store,
                host="127.0.0.1",
                port=0,
            )
            service.start()
            assert service.server is not None
            port = service.server.server_port
            http_health = read_json(f"http://127.0.0.1:{port}/health")
            http_presence = read_json(f"http://127.0.0.1:{port}/presence")
            service.close()

            assert http_health["status"] == "healthy"
            assert (
                http_presence["startup_receipt"]["receipt_id"]
                == receipt["receipt_id"]
            )

            runtime_state["services"]["body_discovery"] = {
                "state": "failed",
                "error": "simulated responder failure",
            }
            runtime_path.write_text(
                json.dumps(runtime_state) + "\n",
                encoding="utf-8",
            )
            degraded = store.health()
            assert degraded["status"] == "degraded"
            assert any(
                item.get("kind") == "service-failed"
                for item in degraded["reasons"]
            )

            # Restore healthy runtime before testing persisted manifest integrity.
            runtime_state["services"]["body_discovery"] = {"state": "awake"}
            runtime_path.write_text(
                json.dumps(runtime_state) + "\n",
                encoding="utf-8",
            )

            manifest_path = root / "startup" / "manifest.v0.json"
            tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered["code"]["entrypoint"] = "/tampered/organ.py"
            manifest_path.write_text(
                json.dumps(tampered) + "\n",
                encoding="utf-8",
            )
            blocked_tamper = store.health()
            assert blocked_tamper["status"] == "blocked"
            assert any(
                item.get("kind") == "boot-manifest-invalid"
                for item in blocked_tamper["reasons"]
            )

            # A fresh startup over an unsupported durable state version must
            # report migration-required rather than silently rewriting it.
            old_root = Path(tmp) / "old-state"
            (old_root / "organ").mkdir(parents=True)
            (old_root / "organ" / "state.v0.json").write_text(
                json.dumps({
                    "kind": "ghot.organ.state",
                    "version": "99",
                    "node_id": "node-old",
                }) + "\n",
                encoding="utf-8",
            )
            old_record = body_record(old_root, "node-old")
            old_store = PresenceStore(old_root)
            old_manifest, old_receipt = old_store.wake(
                repo_root=repo,
                body_record=old_record,
            )
            assert old_receipt is not None
            assert old_manifest["state"]["migration_required"] is True
            migration_health = old_store.health()
            assert migration_health["status"] == "blocked"
            assert any(
                item.get("kind") == "state-migration-required"
                for item in migration_health["reasons"]
            )

            passed = (
                healthy["status"] == "healthy"
                and http_health["status"] == "healthy"
                and degraded["status"] == "degraded"
                and blocked_tamper["status"] == "blocked"
                and migration_health["status"] == "blocked"
                and verify_startup_receipt(receipt)
            )

            print(json.dumps({
                "simulation_passed": passed,
                "boot": {
                    "surface": manifest["boot_surface"]["surface"],
                    "instance": manifest["boot_surface"]["instance"],
                    "manifest_verified": verify_boot_manifest(manifest),
                    "startup_receipt_verified": verify_startup_receipt(receipt),
                },
                "health_endpoint": http_health["status"],
                "presence_receipt_match": (
                    http_presence["startup_receipt"]["receipt_id"]
                    == receipt["receipt_id"]
                ),
                "runtime_failure": degraded["status"],
                "manifest_tamper": blocked_tamper["status"],
                "old_state": {
                    "migration_required": old_manifest["state"]["migration_required"],
                    "health": migration_health["status"],
                },
            }, indent=2))
            return 0 if passed else 1
    finally:
        if old_surface is None:
            os.environ.pop("GHOT_BOOT_SURFACE", None)
        else:
            os.environ["GHOT_BOOT_SURFACE"] = old_surface
        if old_instance is None:
            os.environ.pop("GHOT_BOOT_INSTANCE", None)
        else:
            os.environ["GHOT_BOOT_INSTANCE"] = old_instance


if __name__ == "__main__":
    raise SystemExit(main())
