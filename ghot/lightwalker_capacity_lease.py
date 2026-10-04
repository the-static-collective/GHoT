#!/usr/bin/env python3
"""Lightwalker Capacity Lease / Partitioned Authority 001.

A Guild steward may partition one Treasury capability into bounded, node-local
leases. Nodes act independently inside their leased budget; no cross-node
reservation lock is required because authority itself is partitioned.

Core laws:
    SHARED CAPACITY != SHARED AUTHORITY
    DELEGATED BUDGET != OWNERSHIP
    LEASE != CONSUMPTION
    PARTITION != GLOBAL CONSENSUS
    FAILED USE != CONSUMPTION
    UNUSED LEASE CAPACITY MAY RETURN WITHOUT HISTORY REWRITE
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from lightwalker_economy import LightwalkerEconomyError, canonical_bytes, content_address
from lightwalker_guild_treasury import (
    make_treasury_entry,
    next_treasury_snapshot,
    verify_treasury_snapshot,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    particular_for_public_key,
    sign_crossing,
    timestamp_now,
    verify_crossing,
    verify_p256,
)

LEASE_KIND = "ghot.lightwalker.guild-capacity-lease"
LEASE_VERSION = "0"
USE_KIND = "ghot.lightwalker.guild-capacity-lease-use"
USE_VERSION = "0"
CLOSE_KIND = "ghot.lightwalker.guild-capacity-lease-close"
CLOSE_VERSION = "0"

LEASE_DOMAIN = "ghot.lightwalker-guild-capacity-lease-signature/v0"
USE_DOMAIN = "ghot.lightwalker-guild-capacity-lease-use-signature/v0"
CLOSE_DOMAIN = "ghot.lightwalker-guild-capacity-lease-close-signature/v0"
LEASE_BYTES = b"GHOT-LightwalkerGuildCapacityLease-v0|"
USE_BYTES = b"GHOT-LightwalkerGuildCapacityLeaseUse-v0|"
CLOSE_BYTES = b"GHOT-LightwalkerGuildCapacityLeaseClose-v0|"
LEASE_CAPABILITY = "ghot.lightwalker-guild-capacity-lease/v0"


def _nonempty(v: Any, name: str) -> str:
    if not isinstance(v, str) or not v:
        raise LightwalkerEconomyError(f"{name} must be non-empty")
    return v


def _nni(v: Any, name: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return v


def _signed(body: dict[str, Any], *, id_field: str, signer: IdentityKey, domain: str, byte_domain: bytes) -> dict[str, Any]:
    item_id = content_address(body)
    value = {
        **body,
        id_field: item_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": domain,
        },
    }
    value["signing"]["signature"] = signer.sign(
        byte_domain + canonical_bytes({id_field: item_id, **body})
    )
    return value


def _verify_signed(value: dict[str, Any], *, id_field: str, particular_field: str, domain: str, byte_domain: bytes) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM or signing.get("domain") != domain:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(particular_field):
            return False
        body = {k: v for k, v in value.items() if k not in {id_field, "signing"}}
        item_id = value.get(id_field)
        if not isinstance(item_id, str) or content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            byte_domain + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _resource(snapshot: dict[str, Any], entry_id: str) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    for entry in snapshot["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise LightwalkerEconomyError("resource entry not found")


def verify_capacity_lease(snapshot: dict[str, Any], lease: dict[str, Any]) -> bool:
    try:
        if lease.get("kind") != LEASE_KIND or lease.get("version") != LEASE_VERSION:
            return False
        if lease.get("authority") != "guild-delegated-capacity-budget":
            return False
        if lease.get("guild_id") != snapshot["guild_id"] or lease.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        entry = _resource(snapshot, lease["resource_entry_id"])
        measure = entry.get("native_measure")
        if not isinstance(measure, dict) or lease.get("leased_measure", {}).get("unit") != measure.get("unit"):
            return False
        if int(lease["leased_measure"]["quantity"]) <= 0 or int(lease["leased_measure"]["quantity"]) > int(measure["quantity"]):
            return False
        if lease.get("steward_particular") != snapshot["steward_particular"]:
            return False
        return _verify_signed(
            lease,
            id_field="lease_id",
            particular_field="steward_particular",
            domain=LEASE_DOMAIN,
            byte_domain=LEASE_BYTES,
        )
    except Exception:
        return False


class GuildCapacityLeaseIssuer:
    """Steward-local atomic partitioning ledger."""

    def __init__(self, root: Path, *, steward: IdentityKey) -> None:
        self.root = root
        self.steward = steward
        self.leases_dir = root / "capacity-leases" / "leases"
        self.closes_dir = root / "capacity-leases" / "closes"
        self.lock_path = root / "capacity-leases" / "ledger.lock"

    def _safe(self, s: str) -> str:
        return s.replace(":", "_").replace("/", "_")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as h:
            fcntl.flock(h.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(h.fileno(), fcntl.LOCK_UN)

    def _write_exclusive(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())
        finally:
            os.close(fd)

    def _lease_path(self, lease_id: str) -> Path:
        return self.leases_dir / f"{self._safe(lease_id)}.json"

    def _close_path(self, lease_id: str) -> Path:
        return self.closes_dir / f"{self._safe(lease_id)}.json"

    def _all_leases(self, snapshot_id: str, resource_entry_id: str) -> list[dict[str, Any]]:
        if not self.leases_dir.exists():
            return []
        out = []
        for p in self.leases_dir.glob("*.json"):
            v = json.loads(p.read_text(encoding="utf-8"))
            if v.get("snapshot_id") == snapshot_id and v.get("resource_entry_id") == resource_entry_id:
                out.append(v)
        return out

    def _closed(self, lease_id: str) -> bool:
        return self._close_path(lease_id).exists()

    def _close_record(self, lease_id: str) -> dict[str, Any] | None:
        path = self._close_path(lease_id)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError("invalid lease close record")
        return value

    def issue(
        self,
        snapshot: dict[str, Any],
        *,
        resource_entry_id: str,
        node_id: str,
        node_particular: str,
        unit: str,
        quantity: int,
        issued_at_cut: int,
        expires_after_cut: int,
    ) -> dict[str, Any]:
        if self.steward.particular() != snapshot["steward_particular"]:
            raise LightwalkerEconomyError("local steward does not own treasury")
        entry = _resource(snapshot, resource_entry_id)
        measure = entry.get("native_measure")
        if not isinstance(measure, dict) or unit != measure["unit"]:
            raise LightwalkerEconomyError("lease unit mismatch")
        q = _nni(quantity, "quantity")
        if q <= 0:
            raise LightwalkerEconomyError("lease quantity must be > 0")
        issued = _nni(issued_at_cut, "issued_at_cut")
        expiry = _nni(expires_after_cut, "expires_after_cut")
        if expiry < issued:
            raise LightwalkerEconomyError("lease expiry precedes issuance")

        with self._locked():
            all_leases = self._all_leases(
                snapshot["snapshot_id"], resource_entry_id
            )
            active = [x for x in all_leases if not self._closed(x["lease_id"])]
            active_leased = sum(
                int(x["leased_measure"]["quantity"]) for x in active
            )
            closed_consumed = 0
            for prior in all_leases:
                close = self._close_record(prior["lease_id"])
                if close is not None:
                    closed_consumed += int(
                        close["consumed_measure"]["quantity"]
                    )
            visible = int(measure["quantity"])
            unpartitioned = visible - active_leased - closed_consumed
            if q > unpartitioned:
                raise LightwalkerEconomyError(
                    "lease exceeds unpartitioned capacity"
                )

            body = {
                "kind": LEASE_KIND,
                "version": LEASE_VERSION,
                "authority": "guild-delegated-capacity-budget",
                "guild_id": snapshot["guild_id"],
                "snapshot_id": snapshot["snapshot_id"],
                "resource_entry_id": resource_entry_id,
                "resource_subject_ref": entry["subject_ref"],
                "steward_particular": self.steward.particular(),
                "node_id": _nonempty(node_id, "node_id"),
                "node_particular": _nonempty(node_particular, "node_particular"),
                "leased_measure": {"unit": unit, "quantity": q},
                "issued_at_cut": issued,
                "expires_after_cut": expiry,
                "status": "ACTIVE",
                "laws": [
                    "SHARED CAPACITY != SHARED AUTHORITY",
                    "DELEGATED BUDGET != OWNERSHIP",
                    "LEASE != CONSUMPTION",
                    "PARTITION != GLOBAL CONSENSUS",
                ],
            }
            lease = _signed(
                body,
                id_field="lease_id",
                signer=self.steward,
                domain=LEASE_DOMAIN,
                byte_domain=LEASE_BYTES,
            )
            self._write_exclusive(self._lease_path(lease["lease_id"]), lease)
            return lease

    def close(
        self,
        snapshot: dict[str, Any],
        lease: dict[str, Any],
        *,
        node_release_receipt: dict[str, Any],
        observed_cut: int,
    ) -> dict[str, Any]:
        if not verify_capacity_lease(snapshot, lease):
            raise LightwalkerEconomyError("invalid capacity lease")
        if self.steward.particular() != lease["steward_particular"]:
            raise LightwalkerEconomyError("local steward does not own lease")
        if not verify_release_receipt(lease, node_release_receipt):
            raise LightwalkerEconomyError("invalid node release receipt")
        consumed = int(
            node_release_receipt["consumed_measure"]["quantity"]
        )
        leased = int(lease["leased_measure"]["quantity"])
        with self._locked():
            if self._closed(lease["lease_id"]):
                raise LightwalkerEconomyError("lease already closed")
            body = {
                "kind": CLOSE_KIND,
                "version": CLOSE_VERSION,
                "lease_id": lease["lease_id"],
                "guild_id": lease["guild_id"],
                "snapshot_id": lease["snapshot_id"],
                "resource_entry_id": lease["resource_entry_id"],
                "steward_particular": self.steward.particular(),
                "leased_measure": lease["leased_measure"],
                "consumed_measure": {
                    "unit": lease["leased_measure"]["unit"],
                    "quantity": consumed,
                },
                "returned_measure": {
                    "unit": lease["leased_measure"]["unit"],
                    "quantity": leased - consumed,
                },
                "node_release_receipt_id": node_release_receipt[
                    "release_receipt_id"
                ],
                "observed_cut": _nni(observed_cut, "observed_cut"),
                "status": "CLOSED",
                "laws": [
                    "LEASE != CONSUMPTION",
                    "RETURN != HISTORY REWRITE",
                    "UNUSED CAPACITY MAY RETURN",
                ],
            }
            close = _signed(
                body,
                id_field="close_id",
                signer=self.steward,
                domain=CLOSE_DOMAIN,
                byte_domain=CLOSE_BYTES,
            )
            self._write_exclusive(self._close_path(lease["lease_id"]), close)
            return close


def make_lease_crossing(lease: dict[str, Any], *, signer: IdentityKey) -> dict[str, Any]:
    if signer.particular() != lease.get("steward_particular"):
        raise LightwalkerEconomyError("lease crossing signer mismatch")
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f'guild:{lease["guild_id"]}',
        "source_history_head": lease["snapshot_id"],
        "parents": [lease["snapshot_id"]],
        "declared_kind": "LIGHTWALKER_GUILD_CAPACITY_LEASE",
        "payload_refs": [lease["snapshot_id"], lease["resource_entry_id"], lease["lease_id"]],
        "requested_effect": identity_safe({
            "operation": "consider-capacity-lease",
            "lease_id": lease["lease_id"],
            "automatic_consumption_requested": False,
            "ownership_transfer_requested": False,
            "global_consensus_requested": False,
        }),
        "capability_ref": LEASE_CAPABILITY,
        "privacy_policy": {"transport": "replaceable", "payload_encryption": False},
        "audience_policy": {"node_particular": lease["node_particular"]},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-guild-capacity-lease/v0",
            "lease_is_not_consumption": True,
            "delegated_budget_is_not_ownership": True,
        },
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("capacity lease crossing failed")
    return signed


class NodeLeaseBudget:
    """Node-local one-lease budget ledger. No cross-node lock is required."""

    def __init__(self, root: Path, *, node: IdentityKey) -> None:
        self.root = root
        self.node = node
        self.uses_dir = root / "lease-budget" / "uses"
        self.lock_path = root / "lease-budget" / "budget.lock"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as h:
            fcntl.flock(h.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(h.fileno(), fcntl.LOCK_UN)

    def _freeze_path(self, lease_id: str) -> Path:
        return self.root / "lease-budget" / "frozen" / (
            lease_id.replace(":", "_").replace("/", "_") + ".json"
        )

    def _uses(self, lease_id: str) -> list[dict[str, Any]]:
        if not self.uses_dir.exists():
            return []
        out = []
        for p in self.uses_dir.glob("*.json"):
            v = json.loads(p.read_text(encoding="utf-8"))
            if v.get("lease_id") == lease_id:
                out.append(v)
        return out

    def state(self, lease: dict[str, Any]) -> dict[str, Any]:
        if self.node.particular() != lease["node_particular"]:
            raise LightwalkerEconomyError("node does not hold lease")
        with self._locked():
            if self._freeze_path(lease["lease_id"]).exists():
                raise LightwalkerEconomyError(
                    "lease authority surrendered/frozen"
                )
            uses = self._uses(lease["lease_id"])
            consumed = sum(
                int(x["consumed_measure"]["quantity"])
                for x in uses if x["status"] == "EXECUTED"
            )
            leased = int(lease["leased_measure"]["quantity"])
            return {
                "lease_id": lease["lease_id"],
                "unit": lease["leased_measure"]["unit"],
                "leased_quantity": leased,
                "consumed_quantity": consumed,
                "remaining_quantity": leased - consumed,
                "use_ids": sorted(x["use_id"] for x in uses),
            }

    def execute(
        self,
        lease: dict[str, Any],
        *,
        quantity: int,
        observed_cut: int,
        purpose_ref: str,
        success: bool,
    ) -> dict[str, Any]:
        if self.node.particular() != lease["node_particular"]:
            raise LightwalkerEconomyError("node does not hold lease")
        cut = _nni(observed_cut, "observed_cut")
        if cut > int(lease["expires_after_cut"]):
            raise LightwalkerEconomyError("capacity lease expired")
        q = _nni(quantity, "quantity")
        if q <= 0:
            raise LightwalkerEconomyError("use quantity must be > 0")

        with self._locked():
            uses = self._uses(lease["lease_id"])
            consumed = sum(
                int(x["consumed_measure"]["quantity"])
                for x in uses if x["status"] == "EXECUTED"
            )
            leased = int(lease["leased_measure"]["quantity"])
            if q > leased - consumed:
                raise LightwalkerEconomyError("use exceeds remaining leased budget")
            body = {
                "kind": USE_KIND,
                "version": USE_VERSION,
                "lease_id": lease["lease_id"],
                "node_particular": self.node.particular(),
                "purpose_ref": _nonempty(purpose_ref, "purpose_ref"),
                "observed_cut": cut,
                "status": "EXECUTED" if success else "FAILED",
                "success": bool(success),
                "consumed_measure": (
                    {"unit": lease["leased_measure"]["unit"], "quantity": q}
                    if success else None
                ),
                "attempted_measure": {
                    "unit": lease["leased_measure"]["unit"],
                    "quantity": q,
                },
                "laws": [
                    "LEASE != CONSUMPTION",
                    "FAILED USE != CONSUMPTION",
                    "NODE MAY ACT ONLY INSIDE LEASED BUDGET",
                ],
            }
            use = _signed(
                body,
                id_field="use_id",
                signer=self.node,
                domain=USE_DOMAIN,
                byte_domain=USE_BYTES,
            )
            self.uses_dir.mkdir(parents=True, exist_ok=True)
            p = self.uses_dir / f'{use["use_id"].replace(":", "_")}.json'
            self._write(p, use)
            return use

    def _write(self, path: Path, value: dict[str, Any]) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())
        finally:
            os.close(fd)

    def release_receipt(self, lease: dict[str, Any], *, observed_cut: int) -> dict[str, Any]:
        if self._freeze_path(lease["lease_id"]).exists():
            raise LightwalkerEconomyError(
                "lease authority surrendered/frozen"
            )
        state = self.state(lease)
        body = {
            "kind": "ghot.lightwalker.guild-capacity-lease-release",
            "version": "0",
            "lease_id": lease["lease_id"],
            "node_particular": self.node.particular(),
            "consumed_measure": {
                "unit": state["unit"],
                "quantity": state["consumed_quantity"],
            },
            "returned_measure": {
                "unit": state["unit"],
                "quantity": state["remaining_quantity"],
            },
            "observed_cut": _nni(observed_cut, "observed_cut"),
            "status": "RELEASED",
            "use_ids": state["use_ids"],
            "laws": [
                "UNUSED CAPACITY MAY RETURN",
                "RELEASE != HISTORY REWRITE",
            ],
        }
        return _signed(
            body,
            id_field="release_receipt_id",
            signer=self.node,
            domain=USE_DOMAIN,
            byte_domain=USE_BYTES,
        )


def verify_lease_use(lease: dict[str, Any], use: dict[str, Any]) -> bool:
    try:
        if use.get("kind") != USE_KIND or use.get("version") != USE_VERSION:
            return False
        if use.get("lease_id") != lease["lease_id"]:
            return False
        if use.get("node_particular") != lease["node_particular"]:
            return False
        if use.get("status") not in {"EXECUTED", "FAILED"}:
            return False
        if use.get("status") == "EXECUTED":
            measure = use.get("consumed_measure")
            if not isinstance(measure, dict):
                return False
            if measure.get("unit") != lease["leased_measure"]["unit"]:
                return False
        if use.get("status") == "FAILED" and use.get("consumed_measure") is not None:
            return False
        return _verify_signed(
            use,
            id_field="use_id",
            particular_field="node_particular",
            domain=USE_DOMAIN,
            byte_domain=USE_BYTES,
        )
    except Exception:
        return False


def verify_release_receipt(
    lease: dict[str, Any],
    receipt: dict[str, Any],
) -> bool:
    try:
        if receipt.get("kind") != "ghot.lightwalker.guild-capacity-lease-release":
            return False
        if receipt.get("version") != "0":
            return False
        if receipt.get("lease_id") != lease["lease_id"]:
            return False
        if receipt.get("node_particular") != lease["node_particular"]:
            return False
        if receipt.get("status") != "RELEASED":
            return False
        consumed = receipt.get("consumed_measure")
        returned = receipt.get("returned_measure")
        if not isinstance(consumed, dict) or not isinstance(returned, dict):
            return False
        unit = lease["leased_measure"]["unit"]
        if consumed.get("unit") != unit or returned.get("unit") != unit:
            return False
        if int(consumed["quantity"]) + int(returned["quantity"]) != int(
            lease["leased_measure"]["quantity"]
        ):
            return False
        return _verify_signed(
            receipt,
            id_field="release_receipt_id",
            particular_field="node_particular",
            domain=USE_DOMAIN,
            byte_domain=USE_BYTES,
        )
    except Exception:
        return False



def verify_lease_close(close: dict[str, Any]) -> bool:
    try:
        if close.get("kind") != CLOSE_KIND or close.get("version") != CLOSE_VERSION:
            return False
        if close.get("status") != "CLOSED":
            return False
        leased = close.get("leased_measure")
        consumed = close.get("consumed_measure")
        returned = close.get("returned_measure")
        if not all(isinstance(x, dict) for x in [leased, consumed, returned]):
            return False
        unit = leased.get("unit")
        if consumed.get("unit") != unit or returned.get("unit") != unit:
            return False
        if int(consumed["quantity"]) + int(returned["quantity"]) != int(
            leased["quantity"]
        ):
            return False
        return _verify_signed(
            close,
            id_field="close_id",
            particular_field="steward_particular",
            domain=CLOSE_DOMAIN,
            byte_domain=CLOSE_BYTES,
        )
    except Exception:
        return False



def settle_closed_leases_to_treasury(
    snapshot: dict[str, Any],
    *,
    resource_entry_id: str,
    closes: list[dict[str, Any]],
    steward: IdentityKey,
) -> dict[str, Any]:
    entry = _resource(snapshot, resource_entry_id)
    measure = entry["native_measure"]
    if not closes:
        raise LightwalkerEconomyError("at least one lease close is required")
    close_ids = [x.get("close_id") for x in closes]
    if len(close_ids) != len(set(close_ids)):
        raise LightwalkerEconomyError("duplicate lease close")
    lease_ids = [x.get("lease_id") for x in closes]
    if len(lease_ids) != len(set(lease_ids)):
        raise LightwalkerEconomyError("duplicate closed lease")
    if any(not verify_lease_close(x) for x in closes):
        raise LightwalkerEconomyError("invalid lease close")
    consumed = sum(int(x["consumed_measure"]["quantity"]) for x in closes)
    if any(x["snapshot_id"] != snapshot["snapshot_id"] for x in closes):
        raise LightwalkerEconomyError("close references different snapshot")
    if any(x["resource_entry_id"] != resource_entry_id for x in closes):
        raise LightwalkerEconomyError("close references different resource")
    if any(x["steward_particular"] != steward.particular() for x in closes):
        raise LightwalkerEconomyError("close steward mismatch")
    remaining = int(measure["quantity"]) - consumed
    if remaining < 0:
        raise LightwalkerEconomyError("lease closes over-consume treasury")

    replacement = make_treasury_entry(
        category=entry["category"],
        position=entry["position"],
        subject_ref=entry["subject_ref"],
        source_ref=content_address({"kind": "lease-batch-close", "close_ids": sorted(x["close_id"] for x in closes)}),
        evidence_refs=[*entry["evidence_refs"], *sorted(x["close_id"] for x in closes)],
        native_measure={"unit": measure["unit"], "quantity": remaining},
        metadata={
            **entry["metadata"],
            "prior_entry_id": entry["entry_id"],
            "closed_lease_ids": sorted(x["lease_id"] for x in closes),
        },
    )
    return next_treasury_snapshot(
        snapshot,
        steward=steward,
        add_entries=[replacement],
        retire_entry_ids=[entry["entry_id"]],
    )


__all__ = [
    "GuildCapacityLeaseIssuer",
    "NodeLeaseBudget",
    "make_lease_crossing",
    "settle_closed_leases_to_treasury",
    "verify_capacity_lease",
    "verify_lease_close",
    "verify_lease_use",
    "verify_release_receipt",
]
