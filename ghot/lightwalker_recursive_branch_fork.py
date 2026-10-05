#!/usr/bin/env python3
"""Lightwalker Recursive Branch Fork / Reconciliation 001.

Compares actual signed recursive descendants produced by disconnected replicas.
A fork observation carries no authority. The exact parent owner may resolve the
exact contradictory branch set; only the resolved child may continue.

Core laws:
    LOCAL SINGLE-CHILD != GLOBAL SINGLE-CHILD
    RECURSIVE FORK != HISTORY DELETION
    FORK DETECTION != CONSENSUS
    RESOLUTION MUST NAME THE EXACT PARENT CHECKPOINT
    LOSING DESCENDANT != NONEXISTENT DESCENDANT
    ONLY THE RESOLVED LEAF MAY CONTINUE
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_recursive_continuation import (
    RecursiveContinuationStore,
    verify_recursive_checkpoint,
    verify_recursive_handoff,
    verify_recursive_node,
    verify_recursive_stop,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


FORK_KIND = "ghot.lightwalker.recursive-branch-fork"
FORK_VERSION = "0"
RESOLUTION_KIND = "ghot.lightwalker.recursive-branch-resolution"
RESOLUTION_VERSION = "0"
SUPERSESSION_KIND = "ghot.lightwalker.recursive-branch-supersession"
SUPERSESSION_VERSION = "0"

RESOLUTION_DOMAIN = "ghot.lightwalker-recursive-branch-resolution-signature/v0"
RESOLUTION_BYTES = b"GHOT-LightwalkerRecursiveBranchResolution-v0|"


def _signed(
    body: dict[str, Any],
    *,
    id_field: str,
    signer: IdentityKey,
) -> dict[str, Any]:
    item_id = content_address(body)
    value = {
        **body,
        id_field: item_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": RESOLUTION_DOMAIN,
        },
    }
    value["signing"]["signature"] = signer.sign(
        RESOLUTION_BYTES + canonical_bytes({id_field: item_id, **body})
    )
    return value


def _verify_resolution_signature(
    value: dict[str, Any],
    *,
    id_field: str,
    particular_field: str,
) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != RESOLUTION_DOMAIN:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(particular_field):
            return False
        body = {
            key: item
            for key, item in value.items()
            if key not in {id_field, "signing"}
        }
        item_id = value.get(id_field)
        if not isinstance(item_id, str) or content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            RESOLUTION_BYTES + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _verify_branch(
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_stop: dict[str, Any],
    parent_reservation: dict[str, Any],
    parent_finalization: dict[str, Any],
    branch: dict[str, Any],
) -> bool:
    try:
        required = {"handoff", "next_reservation", "child_node"}
        if set(branch) != required:
            return False
        if not verify_recursive_node(parent_node):
            return False
        if not verify_recursive_checkpoint(parent_node, parent_checkpoint):
            return False
        if not verify_recursive_stop(
            parent_node,
            parent_checkpoint,
            parent_reservation,
            parent_finalization,
            parent_stop,
        ):
            return False
        handoff = branch["handoff"]
        next_reservation = branch["next_reservation"]
        child = branch["child_node"]
        if not verify_recursive_handoff(
            parent_node,
            parent_checkpoint,
            parent_stop,
            parent_reservation,
            parent_finalization,
            next_reservation,
            handoff,
        ):
            return False
        if not verify_recursive_node(child):
            return False
        if child.get("parent_node_id") != parent_node["recursive_node_id"]:
            return False
        if child.get("parent_checkpoint_id") != parent_checkpoint[
            "recursive_checkpoint_id"
        ]:
            return False
        if child.get("parent_handoff_id") != handoff["recursive_handoff_id"]:
            return False
        if child.get("new_reservation_id") != next_reservation["reservation_id"]:
            return False
        if child.get("hop_index") != parent_node["hop_index"] + 1:
            return False
        if child.get("checkpoint_ancestry") != handoff["checkpoint_ancestry"]:
            return False
        return True
    except Exception:
        return False


def reconcile_recursive_branches(
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_stop: dict[str, Any],
    parent_reservation: dict[str, Any],
    parent_finalization: dict[str, Any],
    branches: list[dict[str, Any]],
) -> dict[str, Any]:
    if not branches:
        raise LightwalkerEconomyError("recursive branch reconciliation needs descendants")
    rows: list[dict[str, Any]] = []
    for branch in branches:
        if not _verify_branch(
            parent_node,
            parent_checkpoint,
            parent_stop,
            parent_reservation,
            parent_finalization,
            branch,
        ):
            raise LightwalkerEconomyError("invalid recursive branch descendant")
        rows.append({
            "recursive_handoff_id": branch["handoff"]["recursive_handoff_id"],
            "child_node_id": branch["child_node"]["recursive_node_id"],
            "child_guild_id": branch["child_node"]["new_guild_id"],
            "child_reservation_id": branch["next_reservation"]["reservation_id"],
        })
    rows.sort(key=lambda row: row["recursive_handoff_id"])
    handoff_ids = [row["recursive_handoff_id"] for row in rows]
    child_ids = [row["child_node_id"] for row in rows]
    if len(set(handoff_ids)) != len(handoff_ids):
        raise LightwalkerEconomyError("duplicate recursive handoff in branch set")
    if len(set(child_ids)) != len(child_ids):
        raise LightwalkerEconomyError("duplicate recursive child in branch set")

    fork = len(rows) > 1
    body = {
        "kind": FORK_KIND,
        "version": FORK_VERSION,
        "authority": "derived-recursive-branch-fork-observation",
        "continuation_lineage_id": parent_node["continuation_lineage_id"],
        "root_run_id": parent_node["root_run_id"],
        "root_checkpoint_id": parent_node["root_checkpoint_id"],
        "parent_node_id": parent_node["recursive_node_id"],
        "parent_hop_index": parent_node["hop_index"],
        "parent_checkpoint_id": parent_checkpoint["recursive_checkpoint_id"],
        "parent_steward_particular": parent_node["new_steward_particular"],
        "branches": rows,
        "status": "FORK" if fork else "NO_FORK",
        "global_consensus": False,
        "history_deleted": False,
        "execution_authority": "none",
        "laws": [
            "LOCAL SINGLE-CHILD != GLOBAL SINGLE-CHILD",
            "RECURSIVE FORK != HISTORY DELETION",
            "FORK DETECTION != CONSENSUS",
        ],
    }
    return {**body, "recursive_branch_fork_id": content_address(body)}


def make_recursive_branch_resolution(
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    fork: dict[str, Any],
    *,
    parent_steward: IdentityKey,
    rule: str = "lowest-handoff-id",
) -> dict[str, Any]:
    if fork.get("status") != "FORK":
        raise LightwalkerEconomyError("recursive branch resolution requires a fork")
    if fork.get("parent_node_id") != parent_node["recursive_node_id"]:
        raise LightwalkerEconomyError("fork belongs to another parent node")
    if fork.get("parent_checkpoint_id") != parent_checkpoint[
        "recursive_checkpoint_id"
    ]:
        raise LightwalkerEconomyError("fork belongs to another parent checkpoint")
    if parent_steward.particular() != parent_node["new_steward_particular"]:
        raise LightwalkerEconomyError("only exact parent owner may resolve branch fork")
    if rule != "lowest-handoff-id":
        raise LightwalkerEconomyError("unsupported recursive branch resolution rule")

    branches = fork.get("branches")
    if not isinstance(branches, list) or len(branches) < 2:
        raise LightwalkerEconomyError("fork branch set is incomplete")
    winner = min(branches, key=lambda row: row["recursive_handoff_id"])
    losers = [
        row for row in branches
        if row["recursive_handoff_id"] != winner["recursive_handoff_id"]
    ]
    body = {
        "kind": RESOLUTION_KIND,
        "version": RESOLUTION_VERSION,
        "authority": "parent-owner-local-recursive-fork-resolution",
        "recursive_branch_fork_id": fork["recursive_branch_fork_id"],
        "continuation_lineage_id": parent_node["continuation_lineage_id"],
        "parent_node_id": parent_node["recursive_node_id"],
        "parent_checkpoint_id": parent_checkpoint["recursive_checkpoint_id"],
        "parent_steward_particular": parent_steward.particular(),
        "rule": rule,
        "branch_handoff_ids": [
            row["recursive_handoff_id"] for row in branches
        ],
        "branch_child_node_ids": [
            row["child_node_id"] for row in branches
        ],
        "winning_handoff_id": winner["recursive_handoff_id"],
        "winning_child_node_id": winner["child_node_id"],
        "losing_handoff_ids": [
            row["recursive_handoff_id"] for row in losers
        ],
        "losing_child_node_ids": [
            row["child_node_id"] for row in losers
        ],
        "history_deleted": False,
        "global_consensus": False,
        "execution_authority": "none",
        "laws": [
            "RESOLUTION MUST NAME THE EXACT PARENT CHECKPOINT",
            "LOSING DESCENDANT != NONEXISTENT DESCENDANT",
            "ONLY THE RESOLVED LEAF MAY CONTINUE",
        ],
    }
    return _signed(
        body,
        id_field="recursive_branch_resolution_id",
        signer=parent_steward,
    )


def verify_recursive_branch_resolution(
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
) -> bool:
    try:
        if resolution.get("kind") != RESOLUTION_KIND:
            return False
        if resolution.get("version") != RESOLUTION_VERSION:
            return False
        if resolution.get("authority") != (
            "parent-owner-local-recursive-fork-resolution"
        ):
            return False
        if resolution.get("recursive_branch_fork_id") != fork[
            "recursive_branch_fork_id"
        ]:
            return False
        if resolution.get("parent_node_id") != parent_node["recursive_node_id"]:
            return False
        if resolution.get("parent_checkpoint_id") != parent_checkpoint[
            "recursive_checkpoint_id"
        ]:
            return False
        if resolution.get("parent_steward_particular") != parent_node[
            "new_steward_particular"
        ]:
            return False
        if resolution.get("rule") != "lowest-handoff-id":
            return False
        branches = fork.get("branches")
        if not isinstance(branches, list) or len(branches) < 2:
            return False
        winner = min(branches, key=lambda row: row["recursive_handoff_id"])
        losers = [
            row for row in branches
            if row["recursive_handoff_id"] != winner["recursive_handoff_id"]
        ]
        checks = {
            "branch_handoff_ids": [
                row["recursive_handoff_id"] for row in branches
            ],
            "branch_child_node_ids": [
                row["child_node_id"] for row in branches
            ],
            "winning_handoff_id": winner["recursive_handoff_id"],
            "winning_child_node_id": winner["child_node_id"],
            "losing_handoff_ids": [
                row["recursive_handoff_id"] for row in losers
            ],
            "losing_child_node_ids": [
                row["child_node_id"] for row in losers
            ],
            "history_deleted": False,
            "global_consensus": False,
            "execution_authority": "none",
        }
        if any(resolution.get(k) != v for k, v in checks.items()):
            return False
        return _verify_resolution_signature(
            resolution,
            id_field="recursive_branch_resolution_id",
            particular_field="parent_steward_particular",
        )
    except Exception:
        return False


def recursive_branch_gate(
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_stop: dict[str, Any],
    parent_reservation: dict[str, Any],
    parent_finalization: dict[str, Any],
    branches: list[dict[str, Any]],
    child_node: dict[str, Any],
    *,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fork = reconcile_recursive_branches(
        parent_node,
        parent_checkpoint,
        parent_stop,
        parent_reservation,
        parent_finalization,
        branches,
    )
    child_id = child_node["recursive_node_id"]
    known = {
        row["child_node_id"] for row in fork["branches"]
    }
    if child_id not in known:
        raise LightwalkerEconomyError("child is not part of reconciled branch set")
    if fork["status"] == "NO_FORK":
        return {
            "status": "ELIGIBLE_LOCAL",
            "recursive_branch_fork_id": fork["recursive_branch_fork_id"],
            "child_node_id": child_id,
            "execution_authority": "none",
        }
    if resolution is None:
        return {
            "status": "BLOCKED_FORK",
            "recursive_branch_fork_id": fork["recursive_branch_fork_id"],
            "child_node_id": child_id,
            "execution_authority": "none",
        }
    if not verify_recursive_branch_resolution(
        parent_node,
        parent_checkpoint,
        fork,
        resolution,
    ):
        raise LightwalkerEconomyError("invalid recursive branch resolution")
    status = (
        "ELIGIBLE_RESOLVED"
        if child_id == resolution["winning_child_node_id"]
        else "SUPERSEDED"
    )
    return {
        "status": status,
        "recursive_branch_fork_id": fork["recursive_branch_fork_id"],
        "recursive_branch_resolution_id": resolution[
            "recursive_branch_resolution_id"
        ],
        "child_node_id": child_id,
        "execution_authority": "none",
    }


def close_superseded_child(
    store: RecursiveContinuationStore,
    child_node: dict[str, Any],
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    *,
    resolution: dict[str, Any],
    observed_cut: int,
) -> dict[str, Any]:
    child_id = child_node["recursive_node_id"]
    if child_id not in resolution.get("losing_child_node_ids", []):
        raise LightwalkerEconomyError("child is not superseded by resolution")
    finalization = store.close_unstarted(
        child_node,
        snapshot,
        proposal,
        authorization,
        reservation,
        observed_cut=observed_cut,
        reason="RECURSIVE_BRANCH_SUPERSEDED",
    )
    body = {
        "kind": SUPERSESSION_KIND,
        "version": SUPERSESSION_VERSION,
        "authority": "derived-recursive-branch-supersession-linkage",
        "recursive_branch_resolution_id": resolution[
            "recursive_branch_resolution_id"
        ],
        "child_node_id": child_id,
        "reservation_id": reservation["reservation_id"],
        "reservation_finalization_id": finalization["finalization_id"],
        "reservation_status": finalization["status"],
        "history_deleted": False,
        "execution_authority": "none",
        "laws": [
            "LOSING DESCENDANT != NONEXISTENT DESCENDANT",
            "ONLY THE RESOLVED LEAF MAY CONTINUE",
        ],
    }
    return {**body, "recursive_branch_supersession_id": content_address(body)}


__all__ = [
    "close_superseded_child",
    "make_recursive_branch_resolution",
    "reconcile_recursive_branches",
    "recursive_branch_gate",
    "verify_recursive_branch_resolution",
]
