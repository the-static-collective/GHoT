#!/usr/bin/env python3
"""GHoT Liveness Field — Experiment 006.

Maintains a durable, revisable picture of known bodies.

A body can be remembered without being eligible for work. V0 states:
    awake -> stale -> departed
and independently:
    quarantined after repeated failures

Periodic discovery sweeps act as heartbeat probes. Offer freshness inherits the
body observation freshness in V0.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from reference_node import ROOT, now, persist

DEFAULT_AWAKE_TTL_SECONDS = 15.0
DEFAULT_DEPART_AFTER_SECONDS = 60.0
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_QUARANTINE_SECONDS = 30.0

EventSink = Callable[[dict[str, Any]], None]


def _iso_from_epoch(value: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _default_event_sink(event: dict[str, Any]) -> None:
    persist("event", event)


class LivenessField:
    def __init__(
        self,
        state_path: Path | None = None,
        *,
        awake_ttl_seconds: float = DEFAULT_AWAKE_TTL_SECONDS,
        depart_after_seconds: float = DEFAULT_DEPART_AFTER_SECONDS,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        quarantine_seconds: float = DEFAULT_QUARANTINE_SECONDS,
        event_sink: EventSink | None = _default_event_sink,
    ) -> None:
        if awake_ttl_seconds <= 0:
            raise ValueError("awake_ttl_seconds must be > 0")
        if depart_after_seconds <= awake_ttl_seconds:
            raise ValueError("depart_after_seconds must be > awake_ttl_seconds")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if quarantine_seconds <= 0:
            raise ValueError("quarantine_seconds must be > 0")

        self.state_path = state_path or (ROOT / "field.v0.json")
        self.awake_ttl_seconds = float(awake_ttl_seconds)
        self.depart_after_seconds = float(depart_after_seconds)
        self.failure_threshold = int(failure_threshold)
        self.quarantine_seconds = float(quarantine_seconds)
        self.event_sink = event_sink
        self.state = self._load()

    def _empty(self) -> dict[str, Any]:
        return {
            "kind": "ghot.field",
            "version": "0",
            "updated_at": now(),
            "policy": {
                "awake_ttl_seconds": self.awake_ttl_seconds,
                "depart_after_seconds": self.depart_after_seconds,
                "failure_threshold": self.failure_threshold,
                "quarantine_seconds": self.quarantine_seconds,
            },
            "bodies": {},
        }

    def _load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._empty()
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("kind") != "ghot.field":
                return self._empty()
            value.setdefault("bodies", {})
            return value
        except (OSError, json.JSONDecodeError):
            return self._empty()

    def _save(self, at: float | None = None) -> None:
        when = time.time() if at is None else at
        self.state["updated_at"] = _iso_from_epoch(when)
        self.state["policy"] = {
            "awake_ttl_seconds": self.awake_ttl_seconds,
            "depart_after_seconds": self.depart_after_seconds,
            "failure_threshold": self.failure_threshold,
            "quarantine_seconds": self.quarantine_seconds,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _event(
        self,
        event_type: str,
        node_id: str,
        *,
        at: float,
        previous_state: str | None = None,
        next_state: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "kind": "ghot.field.event",
            "version": "0",
            "event_id": f"event-{uuid.uuid4()}",
            "event_type": event_type,
            "node_id": node_id,
            "observed_at": _iso_from_epoch(at),
            "previous_state": previous_state,
            "next_state": next_state,
            "detail": detail or {},
        }
        if self.event_sink is not None:
            self.event_sink(event)
        return event

    def _classify(self, entry: dict[str, Any], at: float) -> str:
        quarantine_until = entry.get("quarantine_until_epoch")
        if isinstance(quarantine_until, (int, float)) and at < quarantine_until:
            return "quarantined"

        last_seen = entry.get("last_seen_epoch")
        if not isinstance(last_seen, (int, float)):
            return "departed"

        age = max(0.0, at - float(last_seen))
        if age <= self.awake_ttl_seconds:
            return "awake"
        if age <= self.depart_after_seconds:
            return "stale"
        return "departed"

    def observe(
        self,
        observation: dict[str, Any],
        *,
        at: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        node_id = observation.get("node_id")
        body_record = observation.get("body") or observation
        node_id = node_id or body_record.get("node_id")
        if not node_id:
            raise ValueError("observation requires node_id")

        bodies = self.state.setdefault("bodies", {})
        previous = bodies.get(node_id)
        previous_state = previous.get("state") if previous else None

        entry = dict(previous or {})
        entry.update({
            "node_id": node_id,
            "first_seen_epoch": (
                entry.get("first_seen_epoch")
                if entry.get("first_seen_epoch") is not None
                else when
            ),
            "first_seen": (
                entry.get("first_seen")
                if entry.get("first_seen")
                else _iso_from_epoch(when)
            ),
            "last_seen_epoch": when,
            "last_seen": _iso_from_epoch(when),
            "url": observation.get("url") or entry.get("url"),
            "address": observation.get("address") or entry.get("address"),
            "body": body_record,
            "consecutive_failures": int(entry.get("consecutive_failures", 0)),
            "quarantine_until_epoch": entry.get("quarantine_until_epoch"),
            "quarantine_until": entry.get("quarantine_until"),
            "last_failure": entry.get("last_failure"),
        })

        next_state = self._classify(entry, when)
        entry["state"] = next_state
        bodies[node_id] = entry

        if previous is None:
            self._event(
                "body.arrived",
                node_id,
                at=when,
                previous_state=None,
                next_state=next_state,
            )
        elif previous_state in {"stale", "departed"} and next_state == "awake":
            self._event(
                "body.returned",
                node_id,
                at=when,
                previous_state=previous_state,
                next_state=next_state,
            )
        elif previous_state == "quarantined" and next_state == "awake":
            self._event(
                "body.quarantine_expired",
                node_id,
                at=when,
                previous_state=previous_state,
                next_state=next_state,
            )

        self._save(when)
        return dict(entry)

    def sweep(self, *, at: float | None = None) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        bodies = self.state.setdefault("bodies", {})

        for node_id, entry in bodies.items():
            previous_state = entry.get("state")
            next_state = self._classify(entry, when)
            if next_state != previous_state:
                entry["state"] = next_state
                if next_state == "stale":
                    event_type = "body.stale"
                elif next_state == "departed":
                    event_type = "body.departed"
                elif previous_state == "quarantined" and next_state == "awake":
                    event_type = "body.quarantine_expired"
                else:
                    event_type = "body.state_changed"
                self._event(
                    event_type,
                    node_id,
                    at=when,
                    previous_state=previous_state,
                    next_state=next_state,
                )

        self._save(when)
        return self.snapshot(at=when, sweep_first=False)

    def refresh_observations(
        self,
        observations: list[dict[str, Any]],
        *,
        at: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        for observation in observations:
            self.observe(observation, at=when)
        return self.sweep(at=when)

    def record_failure(
        self,
        node_id: str,
        reason: str,
        *,
        at: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        bodies = self.state.setdefault("bodies", {})
        entry = bodies.setdefault(node_id, {
            "node_id": node_id,
            "first_seen_epoch": None,
            "first_seen": None,
            "last_seen_epoch": None,
            "last_seen": None,
            "url": None,
            "address": None,
            "body": {"node_id": node_id, "offers": []},
            "state": "departed",
            "consecutive_failures": 0,
            "quarantine_until_epoch": None,
            "quarantine_until": None,
            "last_failure": None,
        })

        previous_state = entry.get("state")
        entry["consecutive_failures"] = int(entry.get("consecutive_failures", 0)) + 1
        entry["last_failure"] = {
            "at": _iso_from_epoch(when),
            "reason": reason,
        }

        if entry["consecutive_failures"] >= self.failure_threshold:
            until = when + self.quarantine_seconds
            entry["quarantine_until_epoch"] = until
            entry["quarantine_until"] = _iso_from_epoch(until)
            entry["state"] = "quarantined"
            self._event(
                "body.quarantined",
                node_id,
                at=when,
                previous_state=previous_state,
                next_state="quarantined",
                detail={
                    "reason": reason,
                    "consecutive_failures": entry["consecutive_failures"],
                    "quarantine_until": entry["quarantine_until"],
                },
            )
        else:
            self._event(
                "body.failure",
                node_id,
                at=when,
                previous_state=previous_state,
                next_state=previous_state,
                detail={
                    "reason": reason,
                    "consecutive_failures": entry["consecutive_failures"],
                },
            )

        self._save(when)
        return dict(entry)

    def record_success(
        self,
        node_id: str,
        *,
        at: float | None = None,
    ) -> dict[str, Any] | None:
        when = time.time() if at is None else float(at)
        entry = self.state.setdefault("bodies", {}).get(node_id)
        if entry is None:
            return None

        previous_failures = int(entry.get("consecutive_failures", 0))
        entry["consecutive_failures"] = 0
        entry["last_success"] = _iso_from_epoch(when)
        if previous_failures:
            self._event(
                "body.recovered",
                node_id,
                at=when,
                previous_state=entry.get("state"),
                next_state=entry.get("state"),
                detail={"cleared_failures": previous_failures},
            )
        self._save(when)
        return dict(entry)

    def snapshot(
        self,
        *,
        at: float | None = None,
        sweep_first: bool = True,
    ) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        if sweep_first:
            return self.sweep(at=when)

        bodies = []
        for node_id in sorted(self.state.get("bodies", {})):
            entry = dict(self.state["bodies"][node_id])
            last_seen = entry.get("last_seen_epoch")
            entry["age_seconds"] = (
                round(max(0.0, when - float(last_seen)), 3)
                if isinstance(last_seen, (int, float))
                else None
            )
            bodies.append(entry)

        return {
            "kind": "ghot.field.snapshot",
            "version": "0",
            "observed_at": _iso_from_epoch(when),
            "policy": dict(self.state.get("policy") or {}),
            "bodies": bodies,
        }


def heartbeat_sweep(timeout: float = 2.0) -> dict[str, Any]:
    from lan_node import discover_peers
    field = LivenessField()
    return field.refresh_observations(discover_peers(timeout))


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or maintain the GHoT liveness field.")
    sub = parser.add_subparsers(dest="command", required=True)

    sweep_parser = sub.add_parser("sweep")
    sweep_parser.add_argument("--timeout", type=float, default=2.0)

    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--timeout", type=float, default=2.0)
    watch_parser.add_argument("--interval", type=float, default=5.0)

    sub.add_parser("show")

    fail_parser = sub.add_parser("failure")
    fail_parser.add_argument("node_id")
    fail_parser.add_argument("reason")

    success_parser = sub.add_parser("success")
    success_parser.add_argument("node_id")

    args = parser.parse_args()

    if args.command == "show":
        print(json.dumps(LivenessField().snapshot(), indent=2))
        return 0

    if args.command == "sweep":
        print(json.dumps(heartbeat_sweep(args.timeout), indent=2))
        return 0

    if args.command == "watch":
        if args.interval <= 0:
            raise SystemExit("--interval must be > 0")
        try:
            while True:
                print(json.dumps(heartbeat_sweep(args.timeout), indent=2))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    field = LivenessField()
    if args.command == "failure":
        print(json.dumps(field.record_failure(args.node_id, args.reason), indent=2))
        return 0
    if args.command == "success":
        print(json.dumps(field.record_success(args.node_id), indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
