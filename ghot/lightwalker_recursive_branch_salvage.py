#!/usr/bin/env python3
"""Lightwalker Recursive Branch Salvage / Losing Work Preservation 001.

Preserves verified useful work from a superseded recursive branch without
crediting it toward the authoritative root execution. The resolved branch may
continue through ordinary recursive handoff; salvage remains artifact/evidence
only.

Core laws:
    LOSING BRANCH WORK != ZERO WORK
    SALVAGE != CONTINUATION AUTHORITY
    MERGEABLE ARTIFACT != MERGED EXECUTION
    USEFUL OUTPUT MAY SURVIVE A LOSING BRANCH
    ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE
    FORK RESOLUTION != ARTIFACT DESTRUCTION
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_recursive_branch_fork import (
    recursive_branch_gate,
    verify_recursive_branch_resolution,
)
from lightwalker_recursive_continuation import (
    RecursiveContinuationStore,
    verify_recursive_checkpoint,
    verify_recursive_completion,
    verify_recursive_handoff,
    verify_recursive_node,
    verify_recursive_stop,
)


SALVAGE_KIND = "ghot.lightwalker.recursive-branch-salvage"
SALVAGE_VERSION = "0"
PROGRESS_KIND = "ghot.lightwalker.resolved-branch-progress"
PROGRESS_VERSION = "0"
ATTACHMENT_KIND = "ghot.lightwalker.salvaged-artifact-attachment"
ATTACHMENT_VERSION = "0"
ACCOUNTING_KIND = "ghot.lightwalker.branch-salvage-accounting"
ACCOUNTING_VERSION = "0"


def _branch_row_for_child(
    fork: dict[str, Any],
    child_node_id: str,
) -> dict[str, Any]:
    rows = [
        row for row in fork.get("branches", [])
        if row.get("child_node_id") == child_node_id
    ]
    if len(rows) != 1:
        raise LightwalkerEconomyError(
            "fork must contain exactly one row for child"
        )
    return rows[0]


def _verify_child_terminal_work(
    child_node: dict[str, Any],
    checkpoint: dict[str, Any],
    stop: dict[str, Any],
    reservation: dict[str, Any],
    finalization: dict[str, Any],
) -> bool:
    try:
        if not verify_recursive_node(child_node):
            return False
        if not verify_recursive_checkpoint(child_node, checkpoint):
            return False
        if not verify_recursive_stop(
            child_node,
            checkpoint,
            reservation,
            finalization,
            stop,
        ):
            return False
        if finalization.get("status") != "PARTIALLY_CONSUMED":
            return False
        if finalization.get("partial_evidence_ref") != checkpoint[
            "recursive_checkpoint_id"
        ]:
            return False
        if finalization.get("consumed_measure") != checkpoint[
            "new_work_measure"
        ]:
            return False
        if int(checkpoint["new_work_measure"]["quantity"]) <= 0:
            return False
        return True
    except Exception:
        return False


def make_losing_branch_salvage(
    *,
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
    losing_child: dict[str, Any],
    losing_checkpoint: dict[str, Any],
    losing_stop: dict[str, Any],
    losing_reservation: dict[str, Any],
    losing_finalization: dict[str, Any],
) -> dict[str, Any]:
    if not verify_recursive_branch_resolution(
        parent_node,
        parent_checkpoint,
        fork,
        resolution,
    ):
        raise LightwalkerEconomyError(
            "invalid recursive branch resolution"
        )
    child_id = losing_child["recursive_node_id"]
    if child_id not in resolution["losing_child_node_ids"]:
        raise LightwalkerEconomyError(
            "salvage source is not a losing descendant"
        )
    row = _branch_row_for_child(fork, child_id)
    if row["child_reservation_id"] != losing_reservation["reservation_id"]:
        raise LightwalkerEconomyError(
            "losing reservation does not match fork branch"
        )
    if not _verify_child_terminal_work(
        losing_child,
        losing_checkpoint,
        losing_stop,
        losing_reservation,
        losing_finalization,
    ):
        raise LightwalkerEconomyError(
            "invalid losing branch work evidence"
        )

    work = losing_checkpoint["new_work_measure"]
    zero_credit = {
        "unit": work["unit"],
        "quantity": 0,
    }
    body = {
        "kind": SALVAGE_KIND,
        "version": SALVAGE_VERSION,
        "authority": "derived-losing-branch-artifact-evidence-only",
        "recursive_branch_fork_id": fork["recursive_branch_fork_id"],
        "recursive_branch_resolution_id": resolution[
            "recursive_branch_resolution_id"
        ],
        "continuation_lineage_id": parent_node[
            "continuation_lineage_id"
        ],
        "parent_checkpoint_id": parent_checkpoint[
            "recursive_checkpoint_id"
        ],
        "losing_handoff_id": row["recursive_handoff_id"],
        "losing_child_node_id": child_id,
        "losing_checkpoint_id": losing_checkpoint[
            "recursive_checkpoint_id"
        ],
        "losing_stop_id": losing_stop["recursive_stop_id"],
        "losing_reservation_id": losing_reservation[
            "reservation_id"
        ],
        "losing_finalization_id": losing_finalization[
            "finalization_id"
        ],
        "artifact_ref": losing_checkpoint["partial_result_ref"],
        "salvaged_work_measure": work,
        "root_progress_credit_measure": zero_credit,
        "artifact_survives": True,
        "continuation_authority": "none",
        "execution_authority": "none",
        "settlement_authority": "none",
        "history_deleted": False,
        "laws": [
            "LOSING BRANCH WORK != ZERO WORK",
            "SALVAGE != CONTINUATION AUTHORITY",
            "USEFUL OUTPUT MAY SURVIVE A LOSING BRANCH",
            "ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE",
            "FORK RESOLUTION != ARTIFACT DESTRUCTION",
        ],
    }
    return {
        **body,
        "recursive_branch_salvage_id": content_address(body),
    }


def verify_losing_branch_salvage(
    *,
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
    losing_child: dict[str, Any],
    losing_checkpoint: dict[str, Any],
    losing_stop: dict[str, Any],
    losing_reservation: dict[str, Any],
    losing_finalization: dict[str, Any],
    salvage: dict[str, Any],
) -> bool:
    try:
        expected = make_losing_branch_salvage(
            parent_node=parent_node,
            parent_checkpoint=parent_checkpoint,
            fork=fork,
            resolution=resolution,
            losing_child=losing_child,
            losing_checkpoint=losing_checkpoint,
            losing_stop=losing_stop,
            losing_reservation=losing_reservation,
            losing_finalization=losing_finalization,
        )
        return salvage == expected
    except Exception:
        return False


def make_resolved_branch_progress(
    *,
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
    winning_child: dict[str, Any],
    winning_checkpoint: dict[str, Any],
    winning_stop: dict[str, Any],
    winning_reservation: dict[str, Any],
    winning_finalization: dict[str, Any],
) -> dict[str, Any]:
    if not verify_recursive_branch_resolution(
        parent_node,
        parent_checkpoint,
        fork,
        resolution,
    ):
        raise LightwalkerEconomyError(
            "invalid recursive branch resolution"
        )
    child_id = winning_child["recursive_node_id"]
    if child_id != resolution["winning_child_node_id"]:
        raise LightwalkerEconomyError(
            "progress source is not resolved winning descendant"
        )
    row = _branch_row_for_child(fork, child_id)
    if row["child_reservation_id"] != winning_reservation[
        "reservation_id"
    ]:
        raise LightwalkerEconomyError(
            "winning reservation does not match fork branch"
        )
    if not _verify_child_terminal_work(
        winning_child,
        winning_checkpoint,
        winning_stop,
        winning_reservation,
        winning_finalization,
    ):
        raise LightwalkerEconomyError(
            "invalid winning branch work evidence"
        )
    body = {
        "kind": PROGRESS_KIND,
        "version": PROGRESS_VERSION,
        "authority": "derived-resolved-root-progress-evidence",
        "recursive_branch_fork_id": fork["recursive_branch_fork_id"],
        "recursive_branch_resolution_id": resolution[
            "recursive_branch_resolution_id"
        ],
        "continuation_lineage_id": parent_node[
            "continuation_lineage_id"
        ],
        "parent_checkpoint_id": parent_checkpoint[
            "recursive_checkpoint_id"
        ],
        "winning_handoff_id": row["recursive_handoff_id"],
        "winning_child_node_id": child_id,
        "winning_checkpoint_id": winning_checkpoint[
            "recursive_checkpoint_id"
        ],
        "winning_stop_id": winning_stop["recursive_stop_id"],
        "winning_finalization_id": winning_finalization[
            "finalization_id"
        ],
        "credited_work_measure": winning_checkpoint[
            "new_work_measure"
        ],
        "authoritative_cumulative_work_measure": (
            winning_checkpoint["cumulative_work_measure"]
        ),
        "authoritative_progress_percent": winning_checkpoint[
            "total_progress_percent"
        ],
        "continuation_authority": "none",
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE",
            "RESOLUTION SELECTS LINEAGE; IT DOES NOT CREATE WORK",
            "PROGRESS EVIDENCE != EXECUTION AUTHORITY",
        ],
    }
    return {
        **body,
        "resolved_branch_progress_id": content_address(body),
    }


def branch_guarded_handoff(
    store: RecursiveContinuationStore,
    *,
    parent_fork_node: dict[str, Any],
    parent_fork_checkpoint: dict[str, Any],
    parent_fork_stop: dict[str, Any],
    parent_fork_reservation: dict[str, Any],
    parent_fork_finalization: dict[str, Any],
    branches: list[dict[str, Any]],
    branch_child_node: dict[str, Any],
    resolution: dict[str, Any] | None,
    handoff_args: dict[str, Any],
) -> dict[str, Any]:
    gate = recursive_branch_gate(
        parent_fork_node,
        parent_fork_checkpoint,
        parent_fork_stop,
        parent_fork_reservation,
        parent_fork_finalization,
        branches,
        branch_child_node,
        resolution=resolution,
    )
    if gate["status"] not in {
        "ELIGIBLE_LOCAL",
        "ELIGIBLE_RESOLVED",
    }:
        raise LightwalkerEconomyError(
            "recursive branch gate does not permit handoff"
        )
    if handoff_args.get("node") is not branch_child_node:
        raise LightwalkerEconomyError(
            "guarded handoff must use exact reconciled child"
        )
    return store.handoff(**handoff_args)


def attach_salvaged_artifact(
    salvage: dict[str, Any],
    authoritative_node: dict[str, Any],
    authoritative_completion: dict[str, Any],
) -> dict[str, Any]:
    if salvage.get("kind") != SALVAGE_KIND:
        raise LightwalkerEconomyError("invalid salvage artifact")
    if salvage.get("artifact_survives") is not True:
        raise LightwalkerEconomyError("salvage artifact does not survive")
    if salvage.get("continuation_authority") != "none":
        raise LightwalkerEconomyError("salvage carries continuation authority")
    if salvage.get("root_progress_credit_measure", {}).get(
        "quantity"
    ) != 0:
        raise LightwalkerEconomyError(
            "salvage with root progress credit cannot attach"
        )
    if not verify_recursive_completion(
        authoritative_node,
        authoritative_completion,
    ):
        raise LightwalkerEconomyError(
            "invalid authoritative recursive completion"
        )
    body = {
        "kind": ATTACHMENT_KIND,
        "version": ATTACHMENT_VERSION,
        "authority": "derived-auxiliary-artifact-linkage-only",
        "recursive_branch_salvage_id": salvage[
            "recursive_branch_salvage_id"
        ],
        "authoritative_completion_id": authoritative_completion[
            "recursive_completion_id"
        ],
        "authoritative_result_ref": authoritative_completion[
            "result_ref"
        ],
        "salvaged_artifact_ref": salvage["artifact_ref"],
        "attachment_role": "auxiliary-artifact",
        "artifact_retained": True,
        "merged_execution": False,
        "root_progress_credit_measure": salvage[
            "root_progress_credit_measure"
        ],
        "continuation_authority": "none",
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "MERGEABLE ARTIFACT != MERGED EXECUTION",
            "SALVAGE != CONTINUATION AUTHORITY",
            "FORK RESOLUTION != ARTIFACT DESTRUCTION",
        ],
    }
    return {
        **body,
        "salvaged_artifact_attachment_id": content_address(body),
    }


def derive_salvage_accounting(
    *,
    parent_checkpoint: dict[str, Any],
    resolved_progress: dict[str, Any],
    salvage: dict[str, Any],
    terminal_node: dict[str, Any],
    terminal_completion: dict[str, Any],
) -> dict[str, Any]:
    if resolved_progress.get("kind") != PROGRESS_KIND:
        raise LightwalkerEconomyError("invalid resolved branch progress")
    if salvage.get("kind") != SALVAGE_KIND:
        raise LightwalkerEconomyError("invalid salvage artifact")
    if not verify_recursive_completion(
        terminal_node,
        terminal_completion,
    ):
        raise LightwalkerEconomyError("invalid terminal completion")
    source = terminal_completion["source_work_measure"]
    parent_cumulative = parent_checkpoint["cumulative_work_measure"]
    winner_work = resolved_progress["credited_work_measure"]
    terminal_new = terminal_completion["new_work_measure"]
    loser_work = salvage["salvaged_work_measure"]
    unit = source["unit"]
    for measure in (
        parent_cumulative,
        winner_work,
        terminal_new,
        loser_work,
        salvage["root_progress_credit_measure"],
    ):
        if measure["unit"] != unit:
            raise LightwalkerEconomyError(
                "salvage accounting unit mismatch"
            )
    credited_total = (
        int(parent_cumulative["quantity"])
        + int(winner_work["quantity"])
        + int(terminal_new["quantity"])
    )
    if credited_total != int(source["quantity"]):
        raise LightwalkerEconomyError(
            "authoritative root accounting does not conserve source"
        )
    if int(salvage["root_progress_credit_measure"]["quantity"]) != 0:
        raise LightwalkerEconomyError(
            "losing salvage may not receive root progress credit"
        )
    useful_observed = credited_total + int(loser_work["quantity"])
    body = {
        "kind": ACCOUNTING_KIND,
        "version": ACCOUNTING_VERSION,
        "authority": "derived-branch-salvage-accounting-only",
        "continuation_lineage_id": salvage[
            "continuation_lineage_id"
        ],
        "parent_checkpoint_id": parent_checkpoint[
            "recursive_checkpoint_id"
        ],
        "resolved_branch_progress_id": resolved_progress[
            "resolved_branch_progress_id"
        ],
        "recursive_branch_salvage_id": salvage[
            "recursive_branch_salvage_id"
        ],
        "terminal_completion_id": terminal_completion[
            "recursive_completion_id"
        ],
        "root_source_work_measure": source,
        "pre_fork_cumulative_work_measure": parent_cumulative,
        "winning_branch_credited_work_measure": winner_work,
        "terminal_credited_work_measure": terminal_new,
        "losing_branch_salvaged_work_measure": loser_work,
        "losing_branch_root_credit_measure": salvage[
            "root_progress_credit_measure"
        ],
        "authoritative_root_total": {
            "unit": unit,
            "quantity": credited_total,
        },
        "useful_work_observed_including_salvage": {
            "unit": unit,
            "quantity": useful_observed,
        },
        "root_progress_double_counted": False,
        "artifact_destroyed": False,
        "execution_merged": False,
        "settlement_authority": "none",
        "laws": [
            "LOSING BRANCH WORK != ZERO WORK",
            "ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE",
            "USEFUL OUTPUT MAY SURVIVE A LOSING BRANCH",
            "MERGEABLE ARTIFACT != MERGED EXECUTION",
        ],
    }
    return {
        **body,
        "branch_salvage_accounting_id": content_address(body),
    }


__all__ = [
    "attach_salvaged_artifact",
    "branch_guarded_handoff",
    "derive_salvage_accounting",
    "make_losing_branch_salvage",
    "make_resolved_branch_progress",
    "verify_losing_branch_salvage",
]
