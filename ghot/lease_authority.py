#!/usr/bin/env python3
"""Owner-local portable work-lease authority — Experiment 011.

The queue owner remains the sole writer of HOLD / claim authority. Remote
workers cross requests as reLATTE-shaped envelopes and receive reLATTE-shaped
receipts.

Remote workers cannot claim arbitrary held work. The owner must first prepare a
short-lived DISPATCH naming the target worker and child energy plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hold_queue import HoldQueue, iso_at
from portable_lease import (
    env_secret,
    key_id,
    make_receipt,
    validate_crossing_shape,
    verify_signature,
)
from reference_node import ROOT, node_id, persist
from work_lease import WorkLeaseStore


def parse_iso_epoch(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class LeaseAuthority:
    def __init__(
        self,
        root: Path | None = None,
        *,
        authority_id: str | None = None,
        secret: str | bytes | None = None,
    ) -> None:
        self.root = root or ROOT
        self.queue = HoldQueue(self.root)
        self.leases = WorkLeaseStore(self.root)
        self.authority_root = self.root / "lease-authority"
        self.receipts_dir = self.authority_root / "receipts"
        self.dispatches_dir = self.authority_root / "dispatches"
        self.authority_id = authority_id or self._load_authority_id()
        self.secret = secret if secret is not None else self._load_secret(create=True)

    def _load_authority_id(self) -> str:
        self.authority_root.mkdir(parents=True, exist_ok=True)
        path = self.authority_root / "authority-id"
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = f"lease-authority-{uuid.uuid4()}"
        path.write_text(value + "\n", encoding="utf-8")
        return value

    def _load_secret(self, *, create: bool) -> str:
        explicit = env_secret(required=False)
        if explicit:
            return explicit

        self.authority_root.mkdir(parents=True, exist_ok=True)
        path = self.authority_root / "shared-secret"
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value

        if not create:
            raise RuntimeError("portable lease authority secret is unavailable")

        value = secrets.token_hex(32)
        path.write_text(value + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return value

    def secret_value(self) -> str:
        if isinstance(self.secret, bytes):
            return self.secret.decode("utf-8")
        return self.secret

    def advert(self) -> dict[str, Any]:
        return {
            "kind": "ghot.lease.authority",
            "version": "0",
            "authority_id": self.authority_id,
            "owner_node_id": node_id(),
            "world_id": f"ghot-authority-world:{self.authority_id}",
            "capability_ref": "ghot.work-lease/v0",
            "crossing_schema": "relatte.crossing-envelope/v0",
            "receipt_schema": "relatte.receipt/v0",
            "signing_profile": "shared-secret-hmac-v0",
            "key_id": key_id(self.secret),
            "public_key_identity_claimed": False,
        }

    def _dispatch_path(self, hold_id: str) -> Path:
        safe = hashlib.sha256(hold_id.encode("utf-8")).hexdigest()
        return self.dispatches_dir / f"{safe}.json"

    def _write_dispatch(self, dispatch: dict[str, Any]) -> None:
        self.dispatches_dir.mkdir(parents=True, exist_ok=True)
        target = self._dispatch_path(dispatch["hold_id"])
        temp = target.with_suffix(f".tmp-{uuid.uuid4()}")
        temp.write_text(
            json.dumps(dispatch, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(target)

    def _read_dispatch(self, hold_id: str) -> dict[str, Any] | None:
        path = self._dispatch_path(hold_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _dispatch_event(
        self,
        event_type: str,
        dispatch: dict[str, Any],
        *,
        at: float,
        detail: dict[str, Any] | None = None,
    ) -> None:
        persist("dispatch-event", {
            "kind": "ghot.dispatch.event",
            "version": "0",
            "event_id": f"dispatch-event-{uuid.uuid4()}",
            "event_type": event_type,
            "dispatch_id": dispatch["dispatch_id"],
            "hold_id": dispatch["hold_id"],
            "target_worker_id": dispatch["target_worker_id"],
            "observed_at": iso_at(at),
            "detail": detail or {},
        })

    def _dispatch_expired(self, dispatch: dict[str, Any], at: float) -> bool:
        expires = dispatch.get("expires_at_epoch")
        return isinstance(expires, (int, float)) and at >= float(expires)

    def _expire_dispatch_if_due(
        self,
        dispatch: dict[str, Any] | None,
        *,
        at: float,
    ) -> dict[str, Any] | None:
        if dispatch is None:
            return None
        if (
            dispatch.get("status") in {"offered", "claimed"}
            and self._dispatch_expired(dispatch, at)
        ):
            dispatch["status"] = "expired"
            dispatch["expired_at"] = iso_at(at)
            dispatch["updated_at"] = iso_at(at)
            self._write_dispatch(dispatch)
            self._dispatch_event("dispatch.expired", dispatch, at=at)
        return dispatch

    def prepare_dispatch(
        self,
        hold_id: str,
        *,
        target_worker_id: str,
        child_energy_plan_id: str,
        ttl_seconds: float = 120.0,
        at: float | None = None,
    ) -> dict[str, Any]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        when = time.time() if at is None else float(at)

        with self.leases.transition(hold_id):
            hold = self.queue.get(hold_id)
            if hold is None:
                raise KeyError(f"unknown hold: {hold_id}")
            if hold.get("status") != "held":
                raise ValueError(f"hold is not active: {hold.get('status')}")
            if self.queue.is_expired(hold, at=when):
                raise ValueError("hold is expired")

            claim = self.leases.get_claim(hold_id)
            if claim is not None and not self.leases.is_claim_expired(claim, at=when):
                raise ValueError("hold already has a live execution claim")

            existing = self._expire_dispatch_if_due(
                self._read_dispatch(hold_id),
                at=when,
            )
            if existing is not None and existing.get("status") in {"offered", "claimed"}:
                raise ValueError("hold already has an active dispatch")

            dispatch = {
                "kind": "ghot.dispatch",
                "version": "0",
                "dispatch_id": f"dispatch-{uuid.uuid4()}",
                "authority_id": self.authority_id,
                "hold_id": hold_id,
                "target_worker_id": target_worker_id,
                "child_energy_plan_id": child_energy_plan_id,
                "capability": hold.get("capability"),
                "payload": hold.get("payload"),
                "payload_address": "sha256:" + hashlib.sha256(
                    json.dumps(
                        hold.get("payload"),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "created_at_epoch": when,
                "created_at": iso_at(when),
                "expires_at_epoch": when + ttl_seconds,
                "expires_at": iso_at(when + ttl_seconds),
                "status": "offered",
                "lease_id": None,
                "claimed_at": None,
                "completed_at": None,
                "updated_at": iso_at(when),
            }
            self._write_dispatch(dispatch)
            persist("dispatch", dispatch)
            self._dispatch_event("dispatch.offered", dispatch, at=when)
            return dispatch

    def poll_dispatches(
        self,
        worker_id: str,
        *,
        at: float,
    ) -> list[dict[str, Any]]:
        if not self.dispatches_dir.is_dir():
            return []
        results: list[dict[str, Any]] = []
        for path in sorted(self.dispatches_dir.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            value = self._expire_dispatch_if_due(value, at=at)
            if (
                value
                and value.get("status") == "offered"
                and value.get("target_worker_id") == worker_id
            ):
                results.append(value)
        return results

    def _receipt_path(self, crossing_id: str) -> Path:
        digest = hashlib.sha256(crossing_id.encode("utf-8")).hexdigest()
        return self.receipts_dir / f"{digest}.json"

    def _cached_receipt(self, crossing_id: str) -> dict[str, Any] | None:
        path = self._receipt_path(crossing_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _cache_receipt(self, receipt: dict[str, Any]) -> None:
        crossing_id = str(receipt["crossing_id"])
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        path = self._receipt_path(crossing_id)
        if path.exists():
            return
        temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
        temp.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
        persist("portable-receipt", receipt)

    def _respond(
        self,
        crossing: dict[str, Any],
        *,
        kind: str,
        semantic_effect: str,
        note: str,
        extension: dict[str, Any] | None,
        at: float,
    ) -> dict[str, Any]:
        receipt = make_receipt(
            crossing,
            secret=self.secret,
            authority_id=self.authority_id,
            kind=kind,
            semantic_effect=semantic_effect,
            note=note,
            lease_extension=extension,
            created_at=iso_at(at),
        )
        self._cache_receipt(receipt)
        return receipt

    def _refuse(
        self,
        crossing: dict[str, Any],
        note: str,
        *,
        at: float,
        extension: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._respond(
            crossing,
            kind="REFUSED",
            semantic_effect="none",
            note=note,
            extension=extension,
            at=at,
        )

    def handle_crossing(
        self,
        crossing: dict[str, Any],
        *,
        at: float | None = None,
    ) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        crossing_id = str(crossing.get("crossing_id") or "")

        if crossing_id:
            cached = self._cached_receipt(crossing_id)
            if cached is not None:
                return cached

        shape_errors = validate_crossing_shape(crossing)
        if shape_errors:
            return self._refuse(
                crossing,
                "structural verification failed: " + "; ".join(shape_errors),
                at=when,
            )

        if not verify_signature(self.secret, crossing):
            return self._refuse(
                crossing,
                "source verification failed for V0 shared-secret profile",
                at=when,
            )

        effect = crossing["requested_effect"]
        if effect.get("authority_id") != self.authority_id:
            return self._refuse(
                crossing,
                "crossing addressed to a different lease authority",
                at=when,
            )

        action = effect["action"]
        worker_id = str(effect.get("worker_id") or "")
        hold_id = effect.get("hold_id")

        if action == "POLL":
            dispatches = self.poll_dispatches(worker_id, at=when)
            return self._respond(
                crossing,
                kind="VERIFIED",
                semantic_effect="none",
                note=f"{len(dispatches)} dispatch(es) available",
                extension={
                    "action": action,
                    "authority_id": self.authority_id,
                    "dispatches": dispatches,
                },
                at=when,
            )

        if not hold_id:
            return self._refuse(crossing, "hold_id is required", at=when)

        hold = self.queue.get(hold_id)
        if hold is None:
            return self._refuse(crossing, "unknown hold", at=when)
        if hold.get("status") != "held":
            return self._refuse(
                crossing,
                f"hold is not active: {hold.get('status')}",
                at=when,
            )
        if self.queue.is_expired(hold, at=when):
            self.queue.expire(hold_id, at=when)
            return self._refuse(crossing, "hold expired before crossing", at=when)

        if action == "CLAIM":
            dispatch_id = effect.get("dispatch_id")
            if not dispatch_id:
                return self._refuse(crossing, "dispatch_id is required", at=when)

            with self.leases.transition(hold_id):
                current_hold = self.queue.get(hold_id)
                if current_hold is None or current_hold.get("status") != "held":
                    return self._refuse(
                        crossing,
                        "hold became inactive before claim",
                        at=when,
                    )
                if self.queue.is_expired(current_hold, at=when):
                    return self._refuse(
                        crossing,
                        "hold expired before claim",
                        at=when,
                    )

                dispatch = self._expire_dispatch_if_due(
                    self._read_dispatch(hold_id),
                    at=when,
                )
                if dispatch is None:
                    return self._refuse(crossing, "no owner dispatch exists", at=when)
                if dispatch.get("status") != "offered":
                    return self._refuse(
                        crossing,
                        f"dispatch is not claimable: {dispatch.get('status')}",
                        at=when,
                    )
                if dispatch.get("dispatch_id") != dispatch_id:
                    return self._refuse(
                        crossing,
                        "dispatch_id does not match owner dispatch",
                        at=when,
                    )
                if dispatch.get("target_worker_id") != worker_id:
                    return self._refuse(
                        crossing,
                        "dispatch belongs to a different worker",
                        at=when,
                    )

                lease_seconds = float(effect.get("lease_seconds") or 60.0)
                claim_result = self.leases.claim_locked(
                    current_hold,
                    worker_id=worker_id,
                    lease_seconds=lease_seconds,
                    at=when,
                )
                if claim_result.get("status") != "claimed":
                    return self._refuse(
                        crossing,
                        "execution claim is busy",
                        at=when,
                        extension={"claim": claim_result.get("claim")},
                    )

                claim = claim_result["claim"]
                dispatch["status"] = "claimed"
                dispatch["lease_id"] = claim["lease_id"]
                dispatch["claimed_at"] = iso_at(when)
                dispatch["updated_at"] = iso_at(when)
                self._write_dispatch(dispatch)
                self._dispatch_event(
                    "dispatch.claimed",
                    dispatch,
                    at=when,
                    detail={"lease_id": claim["lease_id"]},
                )

            return self._respond(
                crossing,
                kind="ADMITTED",
                semantic_effect="capability-issued",
                note="portable execution lease granted",
                extension={
                    "action": action,
                    "authority_id": self.authority_id,
                    "dispatch": dispatch,
                    "claim": claim,
                    "hold": current_hold,
                },
                at=when,
            )

        current_claim = self.leases.get_claim(hold_id)
        lease_id = effect.get("lease_id")
        if (
            current_claim is None
            or current_claim.get("lease_id") != lease_id
            or current_claim.get("worker_id") != worker_id
        ):
            return self._refuse(
                crossing,
                "worker does not own the current lease",
                at=when,
            )
        if self.leases.is_claim_expired(current_claim, at=when):
            return self._refuse(
                crossing,
                "lease expired before crossing",
                at=when,
            )

        if action == "RENEW":
            lease_seconds = float(
                effect.get("lease_seconds")
                or current_claim.get("lease_seconds")
                or 60.0
            )
            renewed = self.leases.renew(
                current_claim,
                lease_seconds=lease_seconds,
                at=when,
            )
            if renewed is None:
                return self._refuse(
                    crossing,
                    "lease could not be renewed",
                    at=when,
                )
            return self._respond(
                crossing,
                kind="VERIFIED",
                semantic_effect="local-state-change",
                note="portable execution lease renewed",
                extension={
                    "action": action,
                    "authority_id": self.authority_id,
                    "claim": renewed,
                },
                at=when,
            )

        dispatch = self._expire_dispatch_if_due(
            self._read_dispatch(hold_id),
            at=when,
        )
        if (
            dispatch is None
            or dispatch.get("lease_id") != current_claim.get("lease_id")
            or dispatch.get("target_worker_id") != worker_id
        ):
            return self._refuse(
                crossing,
                "current lease is not backed by the owner dispatch",
                at=when,
            )

        if action == "ABANDON":
            reason = str(effect.get("error") or "remote worker abandoned lease")
            self.leases.abandon(current_claim, reason=reason, at=when)
            dispatch["status"] = "abandoned"
            dispatch["updated_at"] = iso_at(when)
            self._write_dispatch(dispatch)
            self._dispatch_event(
                "dispatch.abandoned",
                dispatch,
                at=when,
                detail={"reason": reason},
            )
            return self._respond(
                crossing,
                kind="RETURNED",
                semantic_effect="local-state-change",
                note="portable lease returned without completing HOLD",
                extension={
                    "action": action,
                    "authority_id": self.authority_id,
                    "dispatch": dispatch,
                },
                at=when,
            )

        if action == "COMPLETE":
            outcome = str(effect.get("outcome") or "")
            child_plan = str(
                effect.get("child_energy_plan_id")
                or dispatch.get("child_energy_plan_id")
                or ""
            )
            remote_receipt_id = effect.get("receipt_id")

            if outcome != "ok":
                reason = str(effect.get("error") or f"remote outcome: {outcome}")
                self.queue.note_recheck(
                    hold_id,
                    child_energy_plan_id=child_plan,
                    reason=reason,
                    at=when,
                )
                self.leases.abandon(current_claim, reason=reason, at=when)
                dispatch["status"] = "failed"
                dispatch["updated_at"] = iso_at(when)
                self._write_dispatch(dispatch)
                self._dispatch_event(
                    "dispatch.failed",
                    dispatch,
                    at=when,
                    detail={"reason": reason},
                )
                return self._respond(
                    crossing,
                    kind="FAILED",
                    semantic_effect="local-state-change",
                    note=reason,
                    extension={
                        "action": action,
                        "authority_id": self.authority_id,
                        "dispatch": dispatch,
                        "remote_receipt_id": remote_receipt_id,
                    },
                    at=when,
                )

            released = self.queue.release(
                hold_id,
                child_energy_plan_id=child_plan,
                receipt_id=remote_receipt_id,
                lease_id=current_claim["lease_id"],
                at=when,
            )
            if released.get("status") != "released":
                return self._refuse(
                    crossing,
                    "authority could not commit HOLD release",
                    at=when,
                )

            self.leases.finish(
                current_claim,
                outcome="ok",
                receipt_id=remote_receipt_id,
                at=when,
            )
            dispatch["status"] = "completed"
            dispatch["completed_at"] = iso_at(when)
            dispatch["updated_at"] = iso_at(when)
            self._write_dispatch(dispatch)
            self._dispatch_event(
                "dispatch.completed",
                dispatch,
                at=when,
                detail={"remote_receipt_id": remote_receipt_id},
            )
            return self._respond(
                crossing,
                kind="EXECUTED",
                semantic_effect="local-state-change",
                note="remote execution accepted; owner committed HOLD release",
                extension={
                    "action": action,
                    "authority_id": self.authority_id,
                    "dispatch": dispatch,
                    "hold": released,
                    "remote_receipt_id": remote_receipt_id,
                },
                at=when,
            )

        return self._refuse(
            crossing,
            f"unsupported action: {action}",
            at=when,
        )


def handler_for(authority: LeaseAuthority) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GHoTLeaseAuthority/0"

        def _json(self, status: int, value: Any) -> None:
            payload = json.dumps(value, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if urlparse(self.path).path == "/authority":
                self._json(200, authority.advert())
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/crossing":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                crossing = json.loads(body.decode("utf-8"))
                if not isinstance(crossing, dict):
                    raise ValueError("JSON body must be an object")
            except Exception as exc:
                self._json(400, {"error": f"{type(exc).__name__}: {exc}"})
                return

            receipt = authority.handle_crossing(crossing)
            self._json(200, receipt)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the GHoT portable lease authority.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=7790)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("hold_id")
    prepare.add_argument("worker_id")
    prepare.add_argument("child_energy_plan_id")
    prepare.add_argument("--ttl", type=float, default=120.0)

    sub.add_parser("show")
    sub.add_parser("show-secret")

    args = parser.parse_args()
    authority = LeaseAuthority()

    if args.command == "show":
        print(json.dumps(authority.advert(), indent=2))
        return 0

    if args.command == "show-secret":
        print(authority.secret_value())
        return 0

    if args.command == "prepare":
        dispatch = authority.prepare_dispatch(
            args.hold_id,
            target_worker_id=args.worker_id,
            child_energy_plan_id=args.child_energy_plan_id,
            ttl_seconds=args.ttl,
        )
        print(json.dumps(dispatch, indent=2))
        return 0

    if args.command == "serve":
        server = ThreadingHTTPServer(
            (args.host, args.port),
            handler_for(authority),
        )
        print(json.dumps({
            **authority.advert(),
            "listen": f"http://{args.host}:{args.port}",
            "crossing_endpoint": "/crossing",
        }, indent=2))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 0
        finally:
            server.server_close()

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
