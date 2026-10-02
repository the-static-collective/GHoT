#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 006."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from liveness_field import LivenessField


def observation(node_id: str) -> dict:
    return {
        "node_id": node_id,
        "url": f"http://{node_id}.invalid:7788",
        "body": {
            "kind": "ghot.body",
            "version": "0",
            "node_id": node_id,
            "system": {"hostname": node_id},
            "offers": [
                {
                    "kind": "ghot.offer",
                    "version": "0",
                    "capability": "system.echo",
                    "available": True,
                }
            ],
        },
    }


def main() -> int:
    events: list[dict] = []

    with tempfile.TemporaryDirectory() as tmp:
        field = LivenessField(
            Path(tmp) / "field.json",
            awake_ttl_seconds=10,
            depart_after_seconds=30,
            failure_threshold=3,
            quarantine_seconds=20,
            event_sink=events.append,
        )

        # Arrival.
        arrived = field.observe(observation("body-a"), at=100.0)
        assert arrived["state"] == "awake"

        # Silence changes state without deleting memory.
        stale = field.sweep(at=111.0)
        assert stale["bodies"][0]["state"] == "stale"

        departed = field.sweep(at=131.0)
        assert departed["bodies"][0]["state"] == "departed"

        # Same identity can return.
        returned = field.observe(observation("body-a"), at=132.0)
        assert returned["state"] == "awake"

        # Repeated crossing failures trip a bounded circuit breaker.
        field.record_failure("body-a", "simulated failure 1", at=133.0)
        field.record_failure("body-a", "simulated failure 2", at=134.0)
        quarantined = field.record_failure("body-a", "simulated failure 3", at=135.0)
        assert quarantined["state"] == "quarantined"

        # Heartbeat while quarantined refreshes presence but does not restore eligibility.
        still_quarantined = field.observe(observation("body-a"), at=150.0)
        assert still_quarantined["state"] == "quarantined"

        # Once quarantine expires, recent heartbeat allows return to awake.
        recovered = field.sweep(at=156.0)
        assert recovered["bodies"][0]["state"] == "awake"

        event_types = [event["event_type"] for event in events]
        required = {
            "body.arrived",
            "body.stale",
            "body.departed",
            "body.returned",
            "body.quarantined",
            "body.quarantine_expired",
        }
        passed = required.issubset(set(event_types))

        result = {
            "simulation_passed": passed,
            "final_state": recovered["bodies"][0]["state"],
            "event_types": event_types,
            "remembered_after_departure": True,
        }
        print(json.dumps(result, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
