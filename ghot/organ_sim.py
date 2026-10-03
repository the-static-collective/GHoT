#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 014."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from organ import OrganDaemon


def make_body(node: str, willingness: str = "normal") -> dict[str, Any]:
    return {
        "kind": "ghot.body",
        "version": "0",
        "node_id": node,
        "identity": {
            "available": True,
            "profile": "relatte.identity-signature/v0",
            "particular": f"particular:{node}",
        },
        "power": {
            "source": "battery",
            "battery_percent": 80 if willingness == "normal" else 12,
            "charging": False,
            "renewable_surplus": False,
            "willingness": willingness,
        },
        "offers": [{
            "kind": "ghot.offer",
            "version": "0",
            "capability": "system.echo",
            "available": willingness != "critical",
            "power": {
                "class": "essential",
            },
        }],
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        peer_calls = {"count": 0}
        authority_calls = {"count": 0}
        work_calls = {"count": 0}
        body_calls = {"count": 0}

        def body_probe() -> dict[str, Any]:
            body_calls["count"] += 1
            willingness = "normal" if body_calls["count"] < 3 else "critical"
            return make_body("node-local", willingness)

        def peer_discoverer(timeout: float) -> list[dict[str, Any]]:
            peer_calls["count"] += 1
            if peer_calls["count"] == 1:
                return [{
                    "node_id": "node-peer",
                    "url": "http://10.0.0.20:7788",
                    "address": "10.0.0.20",
                    "body": make_body("node-peer"),
                }]
            if peer_calls["count"] == 2:
                raise RuntimeError("simulated discovery failure")
            return []

        def authority_resolver(timeout: float) -> list[dict[str, Any]]:
            authority_calls["count"] += 1
            if authority_calls["count"] == 2:
                raise RuntimeError("simulated porch discovery failure")
            return [{
                "advert": {
                    "authority_id": "authority-one",
                    "particular": "particular:authority-one",
                },
                "authority_url": "http://10.0.0.5:7790",
                "trust": "remembered",
            }]

        def work_runner(
            urls: list[str],
            *,
            worker_id: str,
            lease_seconds: float,
        ) -> dict[str, Any]:
            work_calls["count"] += 1
            if work_calls["count"] == 2:
                raise RuntimeError("simulated lease worker failure")
            if not urls:
                return {
                    "status": "no-trusted-authority",
                    "worker_id": worker_id,
                }
            if work_calls["count"] == 3:
                return {
                    "status": "completed",
                    "worker_id": worker_id,
                    "authority_particular": "particular:authority-one",
                    "authority_receipt": {
                        "receipt_id": "receipt-organ-sim",
                    },
                }
            return {
                "status": "no-dispatch",
                "worker_id": worker_id,
                "authority_count": len(urls),
            }

        daemon = OrganDaemon(
            root=root,
            body_probe=body_probe,
            peer_discoverer=peer_discoverer,
            authority_resolver=authority_resolver,
            work_runner=work_runner,
            discovery_timeout=0.01,
            authority_timeout=0.01,
            lease_seconds=30,
        )
        daemon.service_state["body_http"] = {"state": "awake", "port": 7788}
        daemon.service_state["body_discovery"] = {"state": "awake", "port": 47888}

        first = daemon.cycle(at=100.0)
        assert first["cycle"] == 1
        assert first["errors"] == []
        assert first["work"]["status"] == "no-dispatch"
        first_peer = next(
            item for item in first["field"]["bodies"]
            if item["node_id"] == "node-peer"
        )
        assert first_peer["state"] == "awake"

        second = daemon.cycle(at=106.0)
        assert second["cycle"] == 2
        failed_subsystems = {item["subsystem"] for item in second["errors"]}
        assert failed_subsystems == {
            "body-discovery",
            "authority-discovery",
            "lease-worker",
        }
        assert second["node_id"] == "node-local"

        third = daemon.cycle(at=170.0)
        assert third["cycle"] == 3
        assert third["errors"] == []
        assert third["body"]["power"]["willingness"] == "critical"
        assert third["work"]["status"] == "completed"
        third_peer = next(
            item for item in third["field"]["bodies"]
            if item["node_id"] == "node-peer"
        )
        assert third_peer["state"] == "departed"

        persisted = json.loads(
            (root / "organ" / "state.v0.json").read_text(encoding="utf-8")
        )
        assert persisted["cycle"] == 3
        assert persisted["work"]["status"] == "completed"

        events = list((root / "records").glob("*-organ-event-*.json"))
        assert events

        passed = (
            first["work"]["status"] == "no-dispatch"
            and len(second["errors"]) == 3
            and third["work"]["status"] == "completed"
            and third_peer["state"] == "departed"
            and persisted["cycle"] == 3
            and bool(events)
        )

        print(json.dumps({
            "simulation_passed": passed,
            "cycle_1": {
                "work": first["work"]["status"],
                "peer": first_peer["state"],
            },
            "cycle_2": {
                "survived": second["node_id"] == "node-local",
                "errors": sorted(failed_subsystems),
            },
            "cycle_3": {
                "power": third["body"]["power"]["willingness"],
                "work": third["work"]["status"],
                "peer": third_peer["state"],
            },
            "durable_state_cycle": persisted["cycle"],
            "durable_event_count": len(events),
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
