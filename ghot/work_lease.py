#!/usr/bin/env python3
"""Atomic HOLD claims and expiring work leases — Experiment 010.

Filesystem contract:
- one transition lock per HOLD serializes claim/cancel/expire decisions;
- one claim file per HOLD represents the current execution lease;
- claim creation uses O_CREAT|O_EXCL;
- expired claims can be recovered by another worker;
- durable claim events preserve the transition trail.

This is a local/shared-filesystem primitive, not a distributed consensus system.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Iterator
from contextlib import contextmanager

from hold_queue import iso_at
from reference_node import ROOT, persist


class HoldBusy(RuntimeError):
    pass


class TransitionLock:
    def __init__(
        self,
        path: Path,
        *,
        timeout_seconds: float = 2.0,
        retry_seconds: float = 0.01,
    ) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.retry_seconds = retry_seconds
        self.fd: int | None = None

    def __enter__(self) -> "TransitionLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(
                    self.path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                os.write(
                    self.fd,
                    json.dumps({
                        "pid": os.getpid(),
                        "created_at_epoch": time.time(),
                    }).encode("utf-8"),
                )
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise HoldBusy(f"transition lock busy: {self.path.name}")
                time.sleep(self.retry_seconds)

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.fd is not None:
                os.close(self.fd)
        finally:
            self.fd = None
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


class WorkLeaseStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.claims_dir = self.root / "claims"
        self.locks_dir = self.root / "locks"

    def claim_path(self, hold_id: str) -> Path:
        return self.claims_dir / f"{hold_id}.json"

    def lock_path(self, hold_id: str) -> Path:
        return self.locks_dir / f"{hold_id}.lock"

    @contextmanager
    def transition(self, hold_id: str) -> Iterator[None]:
        with TransitionLock(self.lock_path(hold_id)):
            yield

    def get_claim(self, hold_id: str) -> dict[str, Any] | None:
        path = self.claim_path(hold_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def is_claim_expired(
        self,
        claim: dict[str, Any],
        *,
        at: float | None = None,
    ) -> bool:
        when = time.time() if at is None else float(at)
        until = claim.get("lease_until_epoch")
        return not isinstance(until, (int, float)) or when >= float(until)

    def _event(
        self,
        event_type: str,
        *,
        hold_id: str,
        worker_id: str | None,
        lease_id: str | None,
        at: float,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "kind": "ghot.claim.event",
            "version": "0",
            "event_id": f"claim-event-{uuid.uuid4()}",
            "event_type": event_type,
            "hold_id": hold_id,
            "worker_id": worker_id,
            "lease_id": lease_id,
            "observed_at": iso_at(at),
            "detail": detail or {},
        }
        persist("claim-event", event)
        return event

    def _exclusive_write(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(
                fd,
                (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            )
        finally:
            os.close(fd)

    def _remove_claim(self, hold_id: str) -> None:
        try:
            self.claim_path(hold_id).unlink()
        except FileNotFoundError:
            pass

    def claim_locked(
        self,
        hold: dict[str, Any],
        *,
        worker_id: str,
        lease_seconds: float,
        at: float,
    ) -> dict[str, Any]:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")

        hold_id = hold["hold_id"]
        existing = self.get_claim(hold_id)
        recovered_from: dict[str, Any] | None = None

        if existing is not None:
            if not self.is_claim_expired(existing, at=at):
                return {
                    "status": "busy",
                    "claim": existing,
                    "recovered": False,
                }
            recovered_from = existing
            self._remove_claim(hold_id)
            self._event(
                "claim.recovered",
                hold_id=hold_id,
                worker_id=worker_id,
                lease_id=existing.get("lease_id"),
                at=at,
                detail={
                    "previous_worker_id": existing.get("worker_id"),
                    "previous_lease_until": existing.get("lease_until"),
                },
            )

        lease_id = f"lease-{uuid.uuid4()}"
        lease_until = at + lease_seconds
        claim = {
            "kind": "ghot.claim",
            "version": "0",
            "hold_id": hold_id,
            "lease_id": lease_id,
            "worker_id": worker_id,
            "claimed_at_epoch": at,
            "claimed_at": iso_at(at),
            "lease_seconds": lease_seconds,
            "lease_until_epoch": lease_until,
            "lease_until": iso_at(lease_until),
            "parent_energy_plan_id": hold.get("energy_plan_id"),
            "recovered_from_lease_id": (
                recovered_from.get("lease_id") if recovered_from else None
            ),
        }
        self._exclusive_write(self.claim_path(hold_id), claim)
        persist("claim", claim)
        self._event(
            "claim.acquired",
            hold_id=hold_id,
            worker_id=worker_id,
            lease_id=lease_id,
            at=at,
            detail={"lease_until": claim["lease_until"]},
        )
        return {
            "status": "claimed",
            "claim": claim,
            "recovered": recovered_from is not None,
        }

    def finish(
        self,
        claim: dict[str, Any],
        *,
        outcome: str,
        receipt_id: str | None = None,
        at: float | None = None,
    ) -> None:
        when = time.time() if at is None else float(at)
        hold_id = claim["hold_id"]
        with self.transition(hold_id):
            current = self.get_claim(hold_id)
            if current is None:
                return
            if current.get("lease_id") != claim.get("lease_id"):
                return
            self._remove_claim(hold_id)
            self._event(
                "claim.completed",
                hold_id=hold_id,
                worker_id=claim.get("worker_id"),
                lease_id=claim.get("lease_id"),
                at=when,
                detail={
                    "outcome": outcome,
                    "receipt_id": receipt_id,
                },
            )

    def abandon(
        self,
        claim: dict[str, Any],
        *,
        reason: str,
        at: float | None = None,
    ) -> None:
        when = time.time() if at is None else float(at)
        hold_id = claim["hold_id"]
        with self.transition(hold_id):
            current = self.get_claim(hold_id)
            if current is None:
                return
            if current.get("lease_id") != claim.get("lease_id"):
                return
            self._remove_claim(hold_id)
            self._event(
                "claim.abandoned",
                hold_id=hold_id,
                worker_id=claim.get("worker_id"),
                lease_id=claim.get("lease_id"),
                at=when,
                detail={"reason": reason},
            )
