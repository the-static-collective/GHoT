#!/usr/bin/env python3
"""GHoT reference node — body, pantry and power-aware execution.

Zero external Python dependencies. Probes the current body, discovers bounded
local executors, applies current power willingness to offers, accepts
allowlisted capabilities, and produces task/receipt records.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from executor_pantry import derive_offers, execute_adapter, pantry_report, probe_executors
from power_field import apply_power_policy, probe_power

ROOT = Path(os.environ.get("GHOT_HOME", ".ghot"))
RECORDS = ROOT / "records"
NODE_ID_FILE = ROOT / "node-id"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def node_id() -> str:
    ROOT.mkdir(parents=True, exist_ok=True)
    if NODE_ID_FILE.exists():
        value = NODE_ID_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = f"node-{uuid.uuid4()}"
    NODE_ID_FILE.write_text(value + "\n", encoding="utf-8")
    return value


def memory_bytes() -> int | None:
    try:
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int(pages) * int(page_size)
    except (ValueError, OSError, AttributeError):
        pass
    return None


def _base_offers(executors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    builtins = [
        {
            "kind": "ghot.offer",
            "version": "0",
            "capability": capability,
            "available": True,
            "executor": "ghot.reference",
            "limits": {
                "remote_shell": False,
                "bounded_adapter_only": True,
            },
        }
        for capability in [
            "system.echo",
            "system.hash",
            "system.info",
            "system.pantry",
            "system.power",
        ]
    ]
    return builtins + derive_offers(executors)


def body() -> dict[str, Any]:
    usage = shutil.disk_usage(Path.cwd())
    executors = probe_executors()
    power = probe_power()
    offers = apply_power_policy(_base_offers(executors), power)

    return {
        "kind": "ghot.body",
        "version": "0",
        "node_id": node_id(),
        "observed_at": now(),
        "system": {
            "os": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count() or 1,
            "hostname": socket.gethostname(),
            "memory_bytes": memory_bytes(),
            "free_disk_bytes": usage.free,
            "python": platform.python_version(),
        },
        "power": power,
        "executors": executors,
        "offers": offers,
    }


def persist(kind: str, record: dict[str, Any]) -> Path:
    RECORDS.mkdir(parents=True, exist_ok=True)
    ident = (
        record.get("event_id")
        or record.get("hold_id")
        or record.get("energy_plan_id")
        or record.get("attempt_id")
        or record.get("plan_id")
        or record.get("receipt_id")
        or record.get("task_id")
        or record.get("composition_id")
        or record.get("node_id")
        or str(uuid.uuid4())
    )
    path = RECORDS / f"{int(time.time() * 1000)}-{kind}-{ident}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _current_offer(capability: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    current_body = body()
    for offer in current_body.get("offers", []):
        if offer.get("capability") == capability:
            return offer, current_body
    return None, current_body


def execute(
    capability: str,
    payload: Any,
    requester_node_id: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    task = {
        "kind": "ghot.task",
        "version": "0",
        "task_id": f"task-{uuid.uuid4()}",
        "capability": capability,
        "created_at": now(),
        "requester_node_id": requester_node_id or node_id(),
        "input": payload,
        "constraints": constraints or {"network": "not-required"},
    }
    persist("task", task)

    started = now()
    status = "ok"
    error = None
    output: Any = None

    try:
        offer, current_body = _current_offer(capability)
        if offer is None:
            raise ValueError(f"capability not offered by this body: {capability}")
        if offer.get("available") is not True:
            power = offer.get("power") or {}
            reasons = power.get("policy_reasons") or []
            reason = "; ".join(reasons) if reasons else "current policy withdrew offer"
            raise RuntimeError(
                f"capability currently unavailable: {capability}: {reason}"
            )

        if capability == "system.echo":
            output = payload
        elif capability == "system.hash":
            raw = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
            output = {"sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}
        elif capability == "system.info":
            output = current_body
        elif capability == "system.pantry":
            output = pantry_report()
        elif capability == "system.power":
            output = current_body["power"]
        else:
            output = execute_adapter(capability, payload)
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc}"

    receipt = {
        "kind": "ghot.receipt",
        "version": "0",
        "receipt_id": f"receipt-{uuid.uuid4()}",
        "task_id": task["task_id"],
        "requester_node_id": task["requester_node_id"],
        "executor_node_id": node_id(),
        "capability": capability,
        "status": status,
        "started_at": started,
        "finished_at": now(),
        "output": output,
        "output_sha256": sha256_json(output) if output is not None else None,
        "error": error,
    }
    persist("receipt", receipt)
    return task, receipt


def parse_payload(args: list[str]) -> Any:
    if not args:
        return None
    raw = " ".join(args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip())
        return 2

    command = argv[1]

    if command == "probe":
        record = body()
        persist("body", record)
        print(json.dumps(record, indent=2))
        return 0

    if command == "pantry":
        _, receipt = execute("system.pantry", None)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["status"] == "ok" else 1

    if command == "power":
        _, receipt = execute("system.power", None)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["status"] == "ok" else 1

    if command == "echo":
        payload = " ".join(argv[2:])
        _, receipt = execute("system.echo", payload)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["status"] == "ok" else 1

    if command == "hash":
        payload = " ".join(argv[2:])
        _, receipt = execute("system.hash", payload)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["status"] == "ok" else 1

    if command == "info":
        _, receipt = execute("system.info", None)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["status"] == "ok" else 1

    if command == "run":
        if len(argv) < 3:
            print("run requires a capability", file=sys.stderr)
            return 2
        capability = argv[2]
        payload = parse_payload(argv[3:])
        _, receipt = execute(capability, payload)
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["status"] == "ok" else 1

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
