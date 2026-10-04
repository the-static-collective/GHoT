#!/usr/bin/env python3
"""Lightwalker Lease Lineage / Authority DAG 001.

Derive the current authority surface from immutable lease ancestry.

Core laws:
    ANCESTOR HISTORY != LIVE AUTHORITY
    LEAF SET DEFINES CURRENT AUTHORITY
    DESCENDANT != DUPLICATE
    LINEAGE PROOF != OWNERSHIP
    COMPACTION != HISTORY DELETION
    CONSERVATION != GLOBAL CONSENSUS
"""

from __future__ import annotations

from typing import Any

from lightwalker_capacity_lease import verify_capacity_lease, verify_lease_use
from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_treasury import verify_treasury_snapshot
from lightwalker_lease_handoff import (
    verify_child_lease,
    verify_surrender,
)


DAG_KIND = "ghot.lightwalker.lease-authority-dag"
DAG_VERSION = "0"
VIEW_KIND = "ghot.lightwalker.lease-authority-view"
VIEW_VERSION = "0"


def _verify_lease(snapshot: dict[str, Any], lease: dict[str, Any]) -> bool:
    return verify_capacity_lease(snapshot, lease) or verify_child_lease(
        snapshot, lease
    )


def _successful_consumption(
    lease: dict[str, Any],
    uses: list[dict[str, Any]],
) -> int:
    total = 0
    seen: set[str] = set()
    for use in uses:
        use_id = use.get("use_id")
        if not isinstance(use_id, str) or use_id in seen:
            raise LightwalkerEconomyError("duplicate or missing lease-use id")
        seen.add(use_id)
        if not verify_lease_use(lease, use):
            raise LightwalkerEconomyError("invalid lease-use receipt")
        cut = int(use.get("observed_cut", -1))
        if cut < int(lease["issued_at_cut"]):
            raise LightwalkerEconomyError("lease use predates lease issuance")
        if cut > int(lease["expires_after_cut"]):
            raise LightwalkerEconomyError("lease use occurs after expiry")
        if use["status"] == "EXECUTED":
            total += int(use["consumed_measure"]["quantity"])
    return total


def derive_authority_dag(
    snapshot: dict[str, Any],
    *,
    root_lease: dict[str, Any],
    descendant_leases: list[dict[str, Any]],
    surrenders: list[dict[str, Any]],
    uses: list[dict[str, Any]],
    observed_cut: int,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    if not verify_capacity_lease(snapshot, root_lease):
        raise LightwalkerEconomyError("root must be a valid Guild capacity lease")

    cut = int(observed_cut)
    if cut < 0:
        raise LightwalkerEconomyError("observed_cut must be non-negative")

    leases = [root_lease, *descendant_leases]
    lease_by_id: dict[str, dict[str, Any]] = {}
    for lease in leases:
        lease_id = lease.get("lease_id")
        if not isinstance(lease_id, str):
            raise LightwalkerEconomyError("lease missing id")
        if lease_id in lease_by_id:
            raise LightwalkerEconomyError("duplicate lease object")
        if not _verify_lease(snapshot, lease):
            raise LightwalkerEconomyError("invalid lease in lineage")
        if lease["snapshot_id"] != root_lease["snapshot_id"]:
            raise LightwalkerEconomyError("lineage crosses Treasury snapshot")
        if lease["resource_entry_id"] != root_lease["resource_entry_id"]:
            raise LightwalkerEconomyError("lineage crosses resource entry")
        if lease["leased_measure"]["unit"] != root_lease["leased_measure"]["unit"]:
            raise LightwalkerEconomyError("lineage crosses native unit")
        lease_by_id[lease_id] = lease

    surrender_by_parent: dict[str, dict[str, Any]] = {}
    for surrender in surrenders:
        parent_id = surrender.get("parent_lease_id")
        if not isinstance(parent_id, str) or parent_id not in lease_by_id:
            raise LightwalkerEconomyError("surrender references unknown parent")
        if parent_id in surrender_by_parent:
            raise LightwalkerEconomyError("parent has multiple surrenders")
        parent = lease_by_id[parent_id]
        if not verify_surrender(snapshot, parent, surrender):
            raise LightwalkerEconomyError("invalid surrender")
        surrender_by_parent[parent_id] = surrender

    uses_by_lease: dict[str, list[dict[str, Any]]] = {
        lease_id: [] for lease_id in lease_by_id
    }
    global_use_ids: set[str] = set()
    for use in uses:
        lease_id = use.get("lease_id")
        if not isinstance(lease_id, str) or lease_id not in lease_by_id:
            raise LightwalkerEconomyError("use references unknown lease")
        use_id = use.get("use_id")
        if not isinstance(use_id, str) or use_id in global_use_ids:
            raise LightwalkerEconomyError("duplicate global lease-use id")
        global_use_ids.add(use_id)
        uses_by_lease[lease_id].append(use)

    children_by_parent: dict[str, list[dict[str, Any]]] = {
        lease_id: [] for lease_id in lease_by_id
    }
    for lease in descendant_leases:
        parent_id = lease.get("parent_lease_id")
        surrender_id = lease.get("surrender_id")
        if not isinstance(parent_id, str) or parent_id not in lease_by_id:
            raise LightwalkerEconomyError("child references unknown parent")
        surrender = surrender_by_parent.get(parent_id)
        if surrender is None:
            raise LightwalkerEconomyError("child descends from unsurrendered parent")
        if surrender_id != surrender["surrender_id"]:
            raise LightwalkerEconomyError("child references wrong surrender")
        if int(lease["issued_at_cut"]) < int(surrender["observed_cut"]):
            raise LightwalkerEconomyError("child predates parent surrender")
        children_by_parent[parent_id].append(lease)

    # Verify every surrender allocation has exactly one matching child and no
    # extra child occupies the same allocation slot.
    for parent_id, surrender in surrender_by_parent.items():
        expected = sorted(
            (
                item["target_node_id"],
                item["target_node_particular"],
                int(item["quantity"]),
            )
            for item in surrender["allocations"]
        )
        actual = sorted(
            (
                item["node_id"],
                item["node_particular"],
                int(item["leased_measure"]["quantity"]),
            )
            for item in children_by_parent[parent_id]
        )
        if actual != expected:
            raise LightwalkerEconomyError(
                "child set does not exactly materialize surrender allocations"
            )

        parent = lease_by_id[parent_id]
        parent_uses = uses_by_lease[parent_id]
        use_ids = sorted(item["use_id"] for item in parent_uses)
        if use_ids != sorted(surrender["use_ids"]):
            raise LightwalkerEconomyError(
                "surrender does not account for exact parent use history"
            )
        consumed = _successful_consumption(parent, parent_uses)
        if consumed != int(surrender["consumed_before_surrender"]):
            raise LightwalkerEconomyError(
                "surrender consumption disagrees with signed use history"
            )
        if consumed + int(surrender["remaining_before_surrender"]) != int(
            parent["leased_measure"]["quantity"]
        ):
            raise LightwalkerEconomyError("parent conservation failure")

        # Renewal may extend expiry only for one same-holder successor.
        for child in children_by_parent[parent_id]:
            if int(child["expires_after_cut"]) > int(parent["expires_after_cut"]):
                if child.get("renewal") is not True:
                    raise LightwalkerEconomyError(
                        "expiry extension lacks renewal flag"
                    )
                if len(children_by_parent[parent_id]) != 1:
                    raise LightwalkerEconomyError(
                        "renewal cannot coexist with sibling children"
                    )
                if child["node_particular"] != parent["node_particular"]:
                    raise LightwalkerEconomyError(
                        "renewal may not transfer holder in v0"
                    )

    # Rooted acyclic reachability.
    reachable: set[str] = set()
    visiting: set[str] = set()

    def walk(lease_id: str) -> None:
        if lease_id in visiting:
            raise LightwalkerEconomyError("cycle in lease lineage")
        if lease_id in reachable:
            return
        visiting.add(lease_id)
        for child in children_by_parent[lease_id]:
            walk(child["lease_id"])
        visiting.remove(lease_id)
        reachable.add(lease_id)

    walk(root_lease["lease_id"])
    if reachable != set(lease_by_id):
        raise LightwalkerEconomyError("orphan lease outside root lineage")

    nodes: list[dict[str, Any]] = []
    live_leaf_ids: list[str] = []
    expired_leaf_ids: list[str] = []
    ancestor_ids: list[str] = []
    total_consumed = 0
    total_returned = 0
    live_remaining = 0
    expired_remaining = 0

    for lease_id in sorted(lease_by_id):
        lease = lease_by_id[lease_id]
        lease_uses = uses_by_lease[lease_id]
        consumed = _successful_consumption(lease, lease_uses)
        leased = int(lease["leased_measure"]["quantity"])
        if consumed > leased:
            raise LightwalkerEconomyError("lease consumption exceeds budget")
        remaining = leased - consumed
        surrender = surrender_by_parent.get(lease_id)
        children = children_by_parent[lease_id]

        if surrender is not None:
            status = "ANCESTOR_SURRENDERED"
            ancestor_ids.append(lease_id)
            total_returned += int(surrender["returned_to_guild_quantity"])
        elif children:
            raise LightwalkerEconomyError("children exist without surrender")
        elif cut > int(lease["expires_after_cut"]):
            status = "LEAF_EXPIRED"
            expired_leaf_ids.append(lease_id)
            expired_remaining += remaining
        else:
            status = "LEAF_LIVE"
            live_leaf_ids.append(lease_id)
            live_remaining += remaining

        total_consumed += consumed
        nodes.append(
            {
                "lease_id": lease_id,
                "parent_lease_id": lease.get("parent_lease_id"),
                "generation": int(lease.get("generation", 0)),
                "node_particular": lease["node_particular"],
                "leased_quantity": leased,
                "consumed_quantity": consumed,
                "remaining_quantity": remaining,
                "expires_after_cut": int(lease["expires_after_cut"]),
                "status": status,
                "child_lease_ids": sorted(
                    child["lease_id"] for child in children
                ),
                "surrender_id": (
                    surrender["surrender_id"] if surrender is not None else None
                ),
            }
        )

    root_quantity = int(root_lease["leased_measure"]["quantity"])
    accounted = (
        total_consumed
        + total_returned
        + live_remaining
        + expired_remaining
    )
    if accounted != root_quantity:
        raise LightwalkerEconomyError(
            f"lineage conservation failed: {accounted} != {root_quantity}"
        )

    edges = sorted(
        [
            {
                "parent_lease_id": child["parent_lease_id"],
                "child_lease_id": child["lease_id"],
                "surrender_id": child["surrender_id"],
            }
            for child in descendant_leases
        ],
        key=lambda item: (item["parent_lease_id"], item["child_lease_id"]),
    )

    history_digest = content_address(
        {
            "root_lease_id": root_lease["lease_id"],
            "lease_ids": sorted(lease_by_id),
            "surrender_ids": sorted(
                item["surrender_id"] for item in surrenders
            ),
            "use_ids": sorted(global_use_ids),
        }
    )
    body = {
        "kind": DAG_KIND,
        "version": DAG_VERSION,
        "authority": "derived-lineage-observation",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": root_lease["resource_entry_id"],
        "root_lease_id": root_lease["lease_id"],
        "observed_cut": cut,
        "nodes": nodes,
        "edges": edges,
        "ancestor_lease_ids": sorted(ancestor_ids),
        "live_leaf_lease_ids": sorted(live_leaf_ids),
        "expired_leaf_lease_ids": sorted(expired_leaf_ids),
        "totals": {
            "root_quantity": root_quantity,
            "consumed_quantity": total_consumed,
            "returned_to_guild_quantity": total_returned,
            "live_leaf_remaining_quantity": live_remaining,
            "expired_leaf_remaining_quantity": expired_remaining,
            "accounted_quantity": accounted,
        },
        "history_digest": history_digest,
        "conservation_status": "BALANCED",
        "laws": [
            "ANCESTOR HISTORY != LIVE AUTHORITY",
            "LEAF SET DEFINES CURRENT AUTHORITY",
            "DESCENDANT != DUPLICATE",
            "LINEAGE PROOF != OWNERSHIP",
            "COMPACTION != HISTORY DELETION",
        ],
    }
    return {**body, "dag_id": content_address(body)}


def compact_authority_view(dag: dict[str, Any]) -> dict[str, Any]:
    if dag.get("kind") != DAG_KIND or dag.get("version") != DAG_VERSION:
        raise LightwalkerEconomyError("invalid authority DAG")
    if dag.get("conservation_status") != "BALANCED":
        raise LightwalkerEconomyError("cannot compact unbalanced lineage")
    by_id = {item["lease_id"]: item for item in dag["nodes"]}
    live = [by_id[lease_id] for lease_id in dag["live_leaf_lease_ids"]]
    expired = [
        by_id[lease_id] for lease_id in dag["expired_leaf_lease_ids"]
    ]
    body = {
        "kind": VIEW_KIND,
        "version": VIEW_VERSION,
        "authority": "derived-current-authority-view",
        "dag_id": dag["dag_id"],
        "history_digest": dag["history_digest"],
        "root_lease_id": dag["root_lease_id"],
        "observed_cut": dag["observed_cut"],
        "live_leaves": [
            {
                "lease_id": item["lease_id"],
                "node_particular": item["node_particular"],
                "remaining_quantity": item["remaining_quantity"],
                "expires_after_cut": item["expires_after_cut"],
            }
            for item in live
        ],
        "expired_leaves": [
            {
                "lease_id": item["lease_id"],
                "remaining_quantity": item["remaining_quantity"],
            }
            for item in expired
        ],
        "totals": dag["totals"],
        "history_retained_by_digest": True,
        "laws": [
            "LEAF SET DEFINES CURRENT AUTHORITY",
            "COMPACTION != HISTORY DELETION",
            "LINEAGE PROOF != OWNERSHIP",
        ],
    }
    return {**body, "view_id": content_address(body)}


__all__ = [
    "compact_authority_view",
    "derive_authority_dag",
]
