#!/usr/bin/env python3
"""Lightwalker Lease Repartition / Handoff 001.

A live capacity lease is never edited in place. A holder atomically surrenders
its remaining authority, freezing the parent locally. The Guild then signs one
or more successor child leases whose quantities are bounded by that exact
surrendered remainder.

Core laws:
    TRANSFER != DUPLICATION
    HANDOFF != SIMULTANEOUS AUTHORITY
    CHILD LEASE SUM <= PARENT REMAINDER
    RENEWAL != NEW OWNERSHIP
    EXPIRY != HISTORY ERASURE
    SURRENDER != CONSUMPTION
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lightwalker_capacity_lease import (
    LEASE_CAPABILITY,
    NodeLeaseBudget,
    verify_capacity_lease,
)
from lightwalker_economy import LightwalkerEconomyError, canonical_bytes, content_address
from lightwalker_guild_treasury import verify_treasury_snapshot
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

SURRENDER_KIND = "ghot.lightwalker.guild-capacity-lease-surrender"
SURRENDER_VERSION = "0"
CHILD_KIND = "ghot.lightwalker.guild-capacity-child-lease"
CHILD_VERSION = "0"

SURRENDER_DOMAIN = "ghot.lightwalker-guild-capacity-lease-surrender-signature/v0"
CHILD_DOMAIN = "ghot.lightwalker-guild-capacity-child-lease-signature/v0"
SURRENDER_BYTES = b"GHOT-LightwalkerGuildCapacityLeaseSurrender-v0|"
CHILD_BYTES = b"GHOT-LightwalkerGuildCapacityChildLease-v0|"


def _nonempty(v: Any, name: str) -> str:
    if not isinstance(v, str) or not v:
        raise LightwalkerEconomyError(f"{name} must be non-empty")
    return v


def _nni(v: Any, name: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return v


def _signed(
    body: dict[str, Any],
    *,
    id_field: str,
    signer: IdentityKey,
    domain: str,
    byte_domain: bytes,
) -> dict[str, Any]:
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


def _verify_signed(
    value: dict[str, Any],
    *,
    id_field: str,
    particular_field: str,
    domain: str,
    byte_domain: bytes,
) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != domain:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(particular_field):
            return False
        body = {
            k: v for k, v in value.items()
            if k not in {id_field, "signing"}
        }
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


def verify_child_lease(snapshot: dict[str, Any], lease: dict[str, Any]) -> bool:
    try:
        if lease.get("kind") != CHILD_KIND or lease.get("version") != CHILD_VERSION:
            return False
        if lease.get("authority") != "guild-repartitioned-capacity-budget":
            return False
        if lease.get("guild_id") != snapshot["guild_id"]:
            return False
        if lease.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        entry = _resource(snapshot, lease["resource_entry_id"])
        measure = entry.get("native_measure")
        child_measure = lease.get("leased_measure")
        if not isinstance(measure, dict) or not isinstance(child_measure, dict):
            return False
        if child_measure.get("unit") != measure.get("unit"):
            return False
        if int(child_measure.get("quantity", 0)) <= 0:
            return False
        if int(child_measure["quantity"]) > int(measure["quantity"]):
            return False
        if lease.get("steward_particular") != snapshot["steward_particular"]:
            return False
        if not isinstance(lease.get("parent_lease_id"), str):
            return False
        if not isinstance(lease.get("surrender_id"), str):
            return False
        if int(lease.get("generation", 0)) < 1:
            return False
        return _verify_signed(
            lease,
            id_field="lease_id",
            particular_field="steward_particular",
            domain=CHILD_DOMAIN,
            byte_domain=CHILD_BYTES,
        )
    except Exception:
        return False


def verify_mobile_lease(snapshot: dict[str, Any], lease: dict[str, Any]) -> bool:
    return verify_capacity_lease(snapshot, lease) or verify_child_lease(snapshot, lease)


class LeaseHandoffStore:
    """Holder-local atomic surrender of the remaining authority in one lease."""

    def __init__(self, root: Path, *, node: IdentityKey) -> None:
        self.root = root
        self.node = node
        self.budget = NodeLeaseBudget(root, node=node)

    def surrender(
        self,
        snapshot: dict[str, Any],
        lease: dict[str, Any],
        *,
        allocations: list[dict[str, Any]],
        observed_cut: int,
    ) -> dict[str, Any]:
        if not verify_mobile_lease(snapshot, lease):
            raise LightwalkerEconomyError("invalid mobile capacity lease")
        if self.node.particular() != lease["node_particular"]:
            raise LightwalkerEconomyError("node does not hold lease")
        cut = _nni(observed_cut, "observed_cut")
        if cut > int(lease["expires_after_cut"]):
            raise LightwalkerEconomyError("cannot handoff expired lease")
        if not allocations:
            raise LightwalkerEconomyError("handoff needs at least one allocation")

        with self.budget._locked():
            freeze_path = self.budget._freeze_path(lease["lease_id"])
            if freeze_path.exists():
                raise LightwalkerEconomyError("lease authority already surrendered")

            uses = self.budget._uses(lease["lease_id"])
            consumed = sum(
                int(x["consumed_measure"]["quantity"])
                for x in uses
                if x["status"] == "EXECUTED"
            )
            leased = int(lease["leased_measure"]["quantity"])
            remaining = leased - consumed

            normalized: list[dict[str, Any]] = []
            seen_targets: set[str] = set()
            total = 0
            for item in allocations:
                target = _nonempty(
                    item.get("target_node_particular"),
                    "target_node_particular",
                )
                if target in seen_targets:
                    raise LightwalkerEconomyError(
                        "v0 handoff allows one child per target node"
                    )
                seen_targets.add(target)
                q = _nni(item.get("quantity"), "allocation quantity")
                if q <= 0:
                    raise LightwalkerEconomyError(
                        "allocation quantity must be > 0"
                    )
                total += q
                normalized.append(
                    {
                        "target_node_id": _nonempty(
                            item.get("target_node_id"),
                            "target_node_id",
                        ),
                        "target_node_particular": target,
                        "quantity": q,
                    }
                )

            if total > remaining:
                raise LightwalkerEconomyError(
                    "child lease sum exceeds parent remainder"
                )

            body = {
                "kind": SURRENDER_KIND,
                "version": SURRENDER_VERSION,
                "authority": "holder-surrender-of-remaining-authority",
                "guild_id": lease["guild_id"],
                "snapshot_id": lease["snapshot_id"],
                "resource_entry_id": lease["resource_entry_id"],
                "parent_lease_id": lease["lease_id"],
                "source_node_particular": self.node.particular(),
                "unit": lease["leased_measure"]["unit"],
                "leased_quantity": leased,
                "consumed_before_surrender": consumed,
                "remaining_before_surrender": remaining,
                "allocations": sorted(
                    normalized,
                    key=lambda x: (
                        x["target_node_particular"],
                        x["target_node_id"],
                    ),
                ),
                "allocated_quantity": total,
                "returned_to_guild_quantity": remaining - total,
                "use_ids": sorted(x["use_id"] for x in uses),
                "observed_cut": cut,
                "status": "SURRENDERED",
                "laws": [
                    "TRANSFER != DUPLICATION",
                    "HANDOFF != SIMULTANEOUS AUTHORITY",
                    "CHILD LEASE SUM <= PARENT REMAINDER",
                    "SURRENDER != CONSUMPTION",
                ],
            }
            surrender = _signed(
                body,
                id_field="surrender_id",
                signer=self.node,
                domain=SURRENDER_DOMAIN,
                byte_domain=SURRENDER_BYTES,
            )

            freeze_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(
                freeze_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                os.write(
                    fd,
                    (
                        json.dumps(surrender, indent=2, sort_keys=True)
                        + "\n"
                    ).encode("utf-8"),
                )
            finally:
                os.close(fd)
            return surrender


def verify_surrender(
    snapshot: dict[str, Any],
    parent_lease: dict[str, Any],
    surrender: dict[str, Any],
) -> bool:
    try:
        if not verify_mobile_lease(snapshot, parent_lease):
            return False
        if surrender.get("kind") != SURRENDER_KIND:
            return False
        if surrender.get("version") != SURRENDER_VERSION:
            return False
        if surrender.get("authority") != "holder-surrender-of-remaining-authority":
            return False
        if surrender.get("parent_lease_id") != parent_lease["lease_id"]:
            return False
        if surrender.get("source_node_particular") != parent_lease["node_particular"]:
            return False
        if surrender.get("snapshot_id") != parent_lease["snapshot_id"]:
            return False
        if surrender.get("resource_entry_id") != parent_lease["resource_entry_id"]:
            return False
        if surrender.get("unit") != parent_lease["leased_measure"]["unit"]:
            return False
        leased = int(surrender["leased_quantity"])
        consumed = int(surrender["consumed_before_surrender"])
        remaining = int(surrender["remaining_before_surrender"])
        allocated = int(surrender["allocated_quantity"])
        returned = int(surrender["returned_to_guild_quantity"])
        if leased != int(parent_lease["leased_measure"]["quantity"]):
            return False
        if consumed + remaining != leased:
            return False
        if allocated + returned != remaining:
            return False
        quantities = sum(int(x["quantity"]) for x in surrender["allocations"])
        if quantities != allocated:
            return False
        if surrender.get("status") != "SURRENDERED":
            return False
        return _verify_signed(
            surrender,
            id_field="surrender_id",
            particular_field="source_node_particular",
            domain=SURRENDER_DOMAIN,
            byte_domain=SURRENDER_BYTES,
        )
    except Exception:
        return False


def materialize_children(
    snapshot: dict[str, Any],
    parent_lease: dict[str, Any],
    surrender: dict[str, Any],
    *,
    steward: IdentityKey,
    issued_at_cut: int,
    expires_after_cut: int,
    allow_renewal: bool = False,
) -> list[dict[str, Any]]:
    if not verify_surrender(snapshot, parent_lease, surrender):
        raise LightwalkerEconomyError("invalid lease surrender")
    if steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError("only Guild steward may materialize children")

    issued = _nni(issued_at_cut, "issued_at_cut")
    expiry = _nni(expires_after_cut, "expires_after_cut")
    if expiry < issued:
        raise LightwalkerEconomyError("child expiry precedes issue")
    parent_expiry = int(parent_lease["expires_after_cut"])
    if expiry > parent_expiry and not allow_renewal:
        raise LightwalkerEconomyError(
            "handoff may not extend parent expiry without renewal authority"
        )
    if allow_renewal:
        if len(surrender["allocations"]) != 1:
            raise LightwalkerEconomyError(
                "v0 renewal requires one successor allocation"
            )
        only = surrender["allocations"][0]
        if only["target_node_particular"] != parent_lease["node_particular"]:
            raise LightwalkerEconomyError(
                "v0 renewal may extend only the current holder"
            )

    generation = int(parent_lease.get("generation", 0)) + 1
    children: list[dict[str, Any]] = []
    for allocation in surrender["allocations"]:
        body = {
            "kind": CHILD_KIND,
            "version": CHILD_VERSION,
            "authority": "guild-repartitioned-capacity-budget",
            "guild_id": parent_lease["guild_id"],
            "snapshot_id": parent_lease["snapshot_id"],
            "resource_entry_id": parent_lease["resource_entry_id"],
            "resource_subject_ref": parent_lease["resource_subject_ref"],
            "steward_particular": steward.particular(),
            "parent_lease_id": parent_lease["lease_id"],
            "surrender_id": surrender["surrender_id"],
            "generation": generation,
            "node_id": allocation["target_node_id"],
            "node_particular": allocation["target_node_particular"],
            "leased_measure": {
                "unit": surrender["unit"],
                "quantity": allocation["quantity"],
            },
            "issued_at_cut": issued,
            "expires_after_cut": expiry,
            "renewal": bool(allow_renewal),
            "status": "ACTIVE",
            "laws": [
                "TRANSFER != DUPLICATION",
                "HANDOFF != SIMULTANEOUS AUTHORITY",
                "CHILD LEASE SUM <= PARENT REMAINDER",
                "RENEWAL != NEW OWNERSHIP",
                "EXPIRY != HISTORY ERASURE",
            ],
        }
        children.append(
            _signed(
                body,
                id_field="lease_id",
                signer=steward,
                domain=CHILD_DOMAIN,
                byte_domain=CHILD_BYTES,
            )
        )

    if sum(int(x["leased_measure"]["quantity"]) for x in children) != int(
        surrender["allocated_quantity"]
    ):
        raise LightwalkerEconomyError("child materialization quantity mismatch")
    return children


def make_child_lease_crossing(
    child: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    if signer.particular() != child.get("steward_particular"):
        raise LightwalkerEconomyError("child lease crossing signer mismatch")
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f'guild:{child["guild_id"]}',
        "source_history_head": child["surrender_id"],
        "parents": [child["parent_lease_id"], child["surrender_id"]],
        "declared_kind": "LIGHTWALKER_GUILD_CAPACITY_CHILD_LEASE",
        "payload_refs": [
            child["snapshot_id"],
            child["resource_entry_id"],
            child["parent_lease_id"],
            child["surrender_id"],
            child["lease_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-capacity-child-lease",
                "lease_id": child["lease_id"],
                "automatic_consumption_requested": False,
                "ownership_transfer_requested": False,
                "parent_reactivation_requested": False,
            }
        ),
        "capability_ref": LEASE_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "node_particular": child["node_particular"],
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-capacity-child-lease/v0",
            "handoff_is_not_simultaneous_authority": True,
            "parent_remains_history": True,
        },
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("child lease crossing failed")
    return signed


__all__ = [
    "LeaseHandoffStore",
    "make_child_lease_crossing",
    "materialize_children",
    "verify_child_lease",
    "verify_mobile_lease",
    "verify_surrender",
]
