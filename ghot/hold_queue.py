#!/usr/bin/env python3
"""Durable active HOLD queue for GHoT Experiments 009/010."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reference_node import ROOT, persist


def iso_at(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


class HoldQueue:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.holds_dir = self.root / "holds"

    def _path(self, hold_id: str) -> Path:
        return self.holds_dir / f"{hold_id}.json"

    def _write(self, hold: dict[str, Any]) -> None:
        self.holds_dir.mkdir(parents=True, exist_ok=True)
        target = self._path(hold["hold_id"])
        temp = target.with_suffix(f".tmp-{uuid.uuid4()}")
        temp.write_text(
            json.dumps(hold, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(target)

    def _event(
        self,
        hold: dict[str, Any],
        event_type: str,
        *,
        detail: dict[str, Any] | None = None,
        at: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        event = {
            "kind": "ghot.hold.event",
            "version": "0",
            "event_id": f"hold-event-{uuid.uuid4()}",
            "event_type": event_type,
            "hold_id": hold["hold_id"],
            "energy_plan_id": hold.get("energy_plan_id"),
            "observed_at": iso_at(when),
            "status": hold.get("status"),
            "detail": detail or {},
        }
        persist("hold-event", event)
        return event

    def enqueue(self, hold: dict[str, Any], *, at: float | None = None) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        record = dict(hold)
        record.setdefault("status", "held")
        record.setdefault("evaluation_count", 0)
        record.setdefault("last_evaluated_at", record.get("created_at"))
        record.setdefault("updated_at", iso_at(when))
        record.setdefault("released_at", None)
        record.setdefault("released_energy_plan_id", None)
        record.setdefault("released_receipt_id", None)
        record.setdefault("cancelled_at", None)
        record.setdefault("cancellation_reason", None)
        record.setdefault("expired_at", None)
        self._write(record)
        persist("hold", record)
        self._event(record, "hold.enqueued", at=when)
        return record

    def get(self, hold_id: str) -> dict[str, Any] | None:
        path = self._path(hold_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if not self.holds_dir.is_dir():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(self.holds_dir.glob("hold-*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            if status is not None and value.get("status") != status:
                continue
            records.append(value)
        return records

    def is_expired(self, hold: dict[str, Any], *, at: float | None = None) -> bool:
        when = time.time() if at is None else float(at)
        expires = hold.get("expires_at_epoch")
        return isinstance(expires, (int, float)) and when >= float(expires)

    def note_recheck(
        self,
        hold_id: str,
        *,
        child_energy_plan_id: str,
        reason: str,
        at: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        hold = self.get(hold_id)
        if hold is None:
            raise KeyError(f"unknown hold: {hold_id}")
        if hold.get("status") != "held":
            return hold
        hold["evaluation_count"] = int(hold.get("evaluation_count", 0)) + 1
        hold["last_evaluated_at"] = iso_at(when)
        hold["last_child_energy_plan_id"] = child_energy_plan_id
        hold["last_recheck_reason"] = reason
        hold["updated_at"] = iso_at(when)
        self._write(hold)
        self._event(
            hold,
            "hold.rechecked",
            detail={
                "child_energy_plan_id": child_energy_plan_id,
                "reason": reason,
            },
            at=when,
        )
        return hold

    def release(
        self,
        hold_id: str,
        *,
        child_energy_plan_id: str,
        receipt_id: str | None,
        lease_id: str | None = None,
        at: float | None = None,
    ) -> dict[str, Any]:
        from work_lease import WorkLeaseStore

        when = time.time() if at is None else float(at)
        leases = WorkLeaseStore(self.root)
        with leases.transition(hold_id):
            hold = self.get(hold_id)
            if hold is None:
                raise KeyError(f"unknown hold: {hold_id}")
            if hold.get("status") != "held":
                return hold
            if self.is_expired(hold, at=when):
                return self._expire_locked(hold, when)

            current_claim = leases.get_claim(hold_id)
            if lease_id is not None:
                if current_claim is None or current_claim.get("lease_id") != lease_id:
                    return hold

            hold["status"] = "released"
            hold["released_at"] = iso_at(when)
            hold["released_energy_plan_id"] = child_energy_plan_id
            hold["released_receipt_id"] = receipt_id
            hold["released_lease_id"] = lease_id
            hold["updated_at"] = iso_at(when)
            self._write(hold)
            self._event(
                hold,
                "hold.released",
                detail={
                    "child_energy_plan_id": child_energy_plan_id,
                    "receipt_id": receipt_id,
                    "lease_id": lease_id,
                },
                at=when,
            )
            return hold

    def cancel(
        self,
        hold_id: str,
        reason: str = "cancelled by operator",
        *,
        at: float | None = None,
    ) -> dict[str, Any]:
        from work_lease import WorkLeaseStore

        when = time.time() if at is None else float(at)
        leases = WorkLeaseStore(self.root)
        with leases.transition(hold_id):
            hold = self.get(hold_id)
            if hold is None:
                raise KeyError(f"unknown hold: {hold_id}")
            if hold.get("status") != "held":
                return hold

            current_claim = leases.get_claim(hold_id)
            if current_claim is not None and not leases.is_claim_expired(current_claim, at=when):
                result = dict(hold)
                result["transition_blocked"] = "active-claim"
                result["active_lease_id"] = current_claim.get("lease_id")
                result["active_worker_id"] = current_claim.get("worker_id")
                return result

            if current_claim is not None:
                leases.remove_expired_claim_locked(
                    current_claim,
                    recovery_worker_id=None,
                    at=when,
                    reason="cancel-after-expired-lease",
                )

            hold["status"] = "cancelled"
            hold["cancelled_at"] = iso_at(when)
            hold["cancellation_reason"] = reason
            hold["updated_at"] = iso_at(when)
            self._write(hold)
            self._event(hold, "hold.cancelled", detail={"reason": reason}, at=when)
            return hold

    def _expire_locked(self, hold: dict[str, Any], when: float) -> dict[str, Any]:
        hold["status"] = "expired"
        hold["expired_at"] = iso_at(when)
        hold["updated_at"] = iso_at(when)
        self._write(hold)
        self._event(hold, "hold.expired", at=when)
        return hold

    def expire(self, hold_id: str, *, at: float | None = None) -> dict[str, Any]:
        from work_lease import WorkLeaseStore

        when = time.time() if at is None else float(at)
        leases = WorkLeaseStore(self.root)
        with leases.transition(hold_id):
            hold = self.get(hold_id)
            if hold is None:
                raise KeyError(f"unknown hold: {hold_id}")
            if hold.get("status") != "held":
                return hold

            current_claim = leases.get_claim(hold_id)
            if current_claim is not None and not leases.is_claim_expired(current_claim, at=when):
                result = dict(hold)
                result["transition_blocked"] = "active-claim"
                result["active_lease_id"] = current_claim.get("lease_id")
                result["active_worker_id"] = current_claim.get("worker_id")
                return result

            if current_claim is not None:
                leases.remove_expired_claim_locked(
                    current_claim,
                    recovery_worker_id=None,
                    at=when,
                    reason="expire-after-expired-lease",
                )

            return self._expire_locked(hold, when)

    def expire_due(self, *, at: float | None = None) -> list[dict[str, Any]]:
        when = time.time() if at is None else float(at)
        expired: list[dict[str, Any]] = []
        for hold in self.list(status="held"):
            if self.is_expired(hold, at=when):
                result = self.expire(hold["hold_id"], at=when)
                if result.get("status") == "expired":
                    expired.append(result)
        return expired
