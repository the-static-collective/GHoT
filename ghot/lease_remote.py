#!/usr/bin/env python3
"""Remote GHoT worker for portable owner-issued work leases — Experiment 011."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from portable_lease import (
    env_secret,
    make_crossing,
    verify_receipt,
)
from reference_node import execute, node_id


def get_authority(base_url: str) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/authority"
    with urllib.request.urlopen(url, timeout=5) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("authority advert is not an object")
    return value


def post_crossing(
    base_url: str,
    crossing: dict[str, Any],
    *,
    secret: str,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/crossing"
    data = json.dumps(crossing).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        receipt = json.loads(response.read().decode("utf-8"))
    if not isinstance(receipt, dict):
        raise RuntimeError("authority receipt is not an object")
    if receipt.get("crossing_id") != crossing.get("crossing_id"):
        raise RuntimeError("authority receipt crossing_id mismatch")
    if not verify_receipt(secret, receipt):
        raise RuntimeError("authority receipt signature verification failed")
    return receipt


def extension(receipt: dict[str, Any]) -> dict[str, Any]:
    return ((receipt.get("extensions") or {}).get("ghot_lease") or {})


def crossing_for(
    action: str,
    *,
    base_url: str,
    authority: dict[str, Any],
    secret: str,
    worker_id: str,
    hold_id: str | None = None,
    dispatch_id: str | None = None,
    lease_id: str | None = None,
    lease_seconds: float | None = None,
    child_energy_plan_id: str | None = None,
    receipt_id: str | None = None,
    outcome: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return make_crossing(
        action,
        secret=secret,
        authority_id=authority["authority_id"],
        worker_id=worker_id,
        worker_node_id=node_id(),
        hold_id=hold_id,
        dispatch_id=dispatch_id,
        lease_id=lease_id,
        lease_seconds=lease_seconds,
        child_energy_plan_id=child_energy_plan_id,
        receipt_id=receipt_id,
        outcome=outcome,
        error=error,
        return_address=None,
    )


def poll(
    base_url: str,
    *,
    authority: dict[str, Any],
    secret: str,
    worker_id: str,
) -> dict[str, Any]:
    crossing = crossing_for(
        "POLL",
        base_url=base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
    )
    return post_crossing(base_url, crossing, secret=secret)


def claim(
    base_url: str,
    *,
    authority: dict[str, Any],
    secret: str,
    worker_id: str,
    dispatch: dict[str, Any],
    lease_seconds: float,
) -> dict[str, Any]:
    crossing = crossing_for(
        "CLAIM",
        base_url=base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
        hold_id=dispatch["hold_id"],
        dispatch_id=dispatch["dispatch_id"],
        lease_seconds=lease_seconds,
    )
    return post_crossing(base_url, crossing, secret=secret)


def renew(
    base_url: str,
    *,
    authority: dict[str, Any],
    secret: str,
    worker_id: str,
    hold_id: str,
    lease_id: str,
    lease_seconds: float,
) -> dict[str, Any]:
    crossing = crossing_for(
        "RENEW",
        base_url=base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
        hold_id=hold_id,
        lease_id=lease_id,
        lease_seconds=lease_seconds,
    )
    return post_crossing(base_url, crossing, secret=secret)


def complete(
    base_url: str,
    *,
    authority: dict[str, Any],
    secret: str,
    worker_id: str,
    hold_id: str,
    lease_id: str,
    child_energy_plan_id: str,
    receipt_id: str | None,
    outcome: str,
    error: str | None,
) -> dict[str, Any]:
    crossing = crossing_for(
        "COMPLETE",
        base_url=base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
        hold_id=hold_id,
        lease_id=lease_id,
        child_energy_plan_id=child_energy_plan_id,
        receipt_id=receipt_id,
        outcome=outcome,
        error=error,
    )
    return post_crossing(base_url, crossing, secret=secret)


def abandon(
    base_url: str,
    *,
    authority: dict[str, Any],
    secret: str,
    worker_id: str,
    hold_id: str,
    lease_id: str,
    reason: str,
) -> dict[str, Any]:
    crossing = crossing_for(
        "ABANDON",
        base_url=base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
        hold_id=hold_id,
        lease_id=lease_id,
        error=reason,
    )
    return post_crossing(base_url, crossing, secret=secret)


class RemoteRenewal:
    def __init__(
        self,
        base_url: str,
        *,
        authority: dict[str, Any],
        secret: str,
        worker_id: str,
        hold_id: str,
        lease_id: str,
        lease_seconds: float,
    ) -> None:
        self.base_url = base_url
        self.authority = authority
        self.secret = secret
        self.worker_id = worker_id
        self.hold_id = hold_id
        self.lease_id = lease_id
        self.lease_seconds = lease_seconds
        self.interval = max(0.5, min(10.0, lease_seconds / 3.0))
        self.stop = threading.Event()
        self.lost = threading.Event()
        self.error: str | None = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.wait(self.interval):
            try:
                receipt = renew(
                    self.base_url,
                    authority=self.authority,
                    secret=self.secret,
                    worker_id=self.worker_id,
                    hold_id=self.hold_id,
                    lease_id=self.lease_id,
                    lease_seconds=self.lease_seconds,
                )
                if receipt.get("kind") == "REFUSED":
                    self.error = receipt.get("note") or "renewal refused"
                    self.lost.set()
                    return
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                self.lost.set()
                return

    def __enter__(self) -> "RemoteRenewal":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop.set()
        self.thread.join(timeout=max(1.0, self.interval + 0.5))


def work_one(
    base_url: str,
    *,
    worker_id: str,
    lease_seconds: float,
) -> dict[str, Any]:
    secret = env_secret(required=True)
    assert secret is not None
    authority = get_authority(base_url)

    poll_receipt = poll(
        base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
    )
    dispatches = extension(poll_receipt).get("dispatches") or []
    if not dispatches:
        return {
            "status": "no-dispatch",
            "worker_id": worker_id,
            "authority_id": authority.get("authority_id"),
        }

    dispatch = dispatches[0]
    claim_receipt = claim(
        base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
        dispatch=dispatch,
        lease_seconds=lease_seconds,
    )
    if claim_receipt.get("kind") == "REFUSED":
        return {
            "status": "claim-refused",
            "receipt": claim_receipt,
        }

    claim_ext = extension(claim_receipt)
    claim_record = claim_ext["claim"]
    granted_dispatch = claim_ext["dispatch"]
    hold = claim_ext["hold"]

    lease_id = claim_record["lease_id"]
    with RemoteRenewal(
        base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
        hold_id=hold["hold_id"],
        lease_id=lease_id,
        lease_seconds=lease_seconds,
    ) as renewal:
        task, local_receipt = execute(
            hold["capability"],
            hold.get("payload"),
            requester_node_id=f"ghot-authority:{authority['authority_id']}",
            constraints={
                "portable_lease": True,
                "authority_id": authority["authority_id"],
                "dispatch_id": granted_dispatch["dispatch_id"],
                "lease_id": lease_id,
                "child_energy_plan_id": granted_dispatch["child_energy_plan_id"],
            },
        )

    if renewal.lost.is_set():
        return {
            "status": "lease-lost",
            "error": renewal.error,
            "task": task,
            "local_receipt": local_receipt,
        }

    completion = complete(
        base_url,
        authority=authority,
        secret=secret,
        worker_id=worker_id,
        hold_id=hold["hold_id"],
        lease_id=lease_id,
        child_energy_plan_id=granted_dispatch["child_energy_plan_id"],
        receipt_id=local_receipt.get("receipt_id"),
        outcome=local_receipt.get("status", "error"),
        error=local_receipt.get("error"),
    )
    return {
        "status": (
            "completed"
            if completion.get("kind") == "EXECUTED"
            else "completion-not-accepted"
        ),
        "task": task,
        "local_receipt": local_receipt,
        "authority_receipt": completion,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Use GHoT portable work leases remotely.")
    parser.add_argument("authority_url")
    parser.add_argument(
        "--worker-id",
        default=None,
        help="stable worker identity; defaults to <node-id>:pid-<pid>",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("poll")

    work = sub.add_parser("work")
    work.add_argument("--lease-seconds", type=float, default=60.0)

    args = parser.parse_args()
    worker_id = args.worker_id or f"{node_id()}:pid-{os.getpid()}"
    secret = env_secret(required=True)
    assert secret is not None

    if args.command == "poll":
        authority = get_authority(args.authority_url)
        receipt = poll(
            args.authority_url,
            authority=authority,
            secret=secret,
            worker_id=worker_id,
        )
        print(json.dumps(receipt, indent=2))
        return 0 if receipt.get("kind") != "REFUSED" else 1

    if args.command == "work":
        result = work_one(
            args.authority_url,
            worker_id=worker_id,
            lease_seconds=args.lease_seconds,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") in {"completed", "no-dispatch"} else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
