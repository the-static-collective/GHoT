#!/usr/bin/env python3
"""GHoT Epistemic Capability 001.

A bounded experimental worker model for proving that context posture can be an
explicit capability constraint and that the exact supplied context can be
audited without copying the context itself into the receipt.

This module deliberately uses deterministic fake workers. It proves the
contract shape before any LLM or remote runtime is involved.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


POSTURES = ("fresh", "bounded-window", "lineage-enabled", "owner-local")

FRESH_FORBIDDEN_KEYS = (
    "catalog_history",
    "prior_dj_transcripts",
    "motif_index",
    "hidden_retrieval",
)

POSTURE_REQUIREMENTS = {
    "fresh": {
        "required": ("current_track",),
        "forbidden": FRESH_FORBIDDEN_KEYS,
    },
    "bounded-window": {
        "required": ("current_track",),
        "forbidden": ("catalog_history", "hidden_retrieval"),
    },
    "lineage-enabled": {
        "required": ("current_track", "lineage_sources"),
        "forbidden": (),
    },
    "owner-local": {
        "required": (),
        "forbidden": (),
    },
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def context_sha256(context: Any) -> str:
    return hashlib.sha256(canonical_json(context).encode("utf-8")).hexdigest()


def fake_offer(worker_id: str, posture: str) -> dict[str, Any]:
    if posture not in POSTURES:
        raise ValueError(f"unknown context posture: {posture}")
    return {
        "kind": "ghot.offer",
        "version": "0",
        "node_id": worker_id,
        "capability": "listen.analyze",
        "context_posture": posture,
        "available": True,
        "executor": "ghot.epistemic.fake",
        "limits": {
            "deterministic_fake_worker": True,
            "network": "forbidden",
            "context_audit": "required",
        },
    }


def make_task(
    *,
    posture: str,
    context: dict[str, Any],
    requester_node_id: str = "epistemic-fixture",
) -> dict[str, Any]:
    if posture not in POSTURES:
        raise ValueError(f"unknown context posture: {posture}")
    if not isinstance(context, dict):
        raise TypeError("context must be an object")
    return {
        "kind": "ghot.task",
        "version": "0",
        "task_id": f"task-{uuid.uuid4()}",
        "capability": "listen.analyze",
        "created_at": now(),
        "requester_node_id": requester_node_id,
        "context_posture": posture,
        "context": context,
        "input": {
            "instruction": "Return a deterministic witness of the context posture.",
        },
        "constraints": {
            "network": "forbidden",
            "context_posture": posture,
        },
    }


def audit_context(posture: str, context: dict[str, Any]) -> dict[str, Any]:
    policy = POSTURE_REQUIREMENTS[posture]
    keys = sorted(context.keys())
    missing = [key for key in policy["required"] if key not in context]
    forbidden = [key for key in policy["forbidden"] if key in context]
    return {
        "supplied_context_sha256": context_sha256(context),
        "supplied_context_keys": keys,
        "required_context_keys_missing": missing,
        "forbidden_context_keys_present": forbidden,
        "audit_passed": not missing and not forbidden,
    }


def _deterministic_observation(posture: str, context: dict[str, Any]) -> dict[str, Any]:
    track = context.get("current_track")
    if isinstance(track, dict):
        track_label = track.get("title") or track.get("id") or "untitled"
    else:
        track_label = str(track) if track is not None else "none"

    result = {
        "posture_witness": posture,
        "current_track_witness": track_label,
        "visible_context_keys": sorted(context.keys()),
    }
    if posture == "lineage-enabled":
        sources = context.get("lineage_sources")
        result["lineage_source_count"] = len(sources) if isinstance(sources, list) else 0
    else:
        result["lineage_source_count"] = None
    return result


def execute_fake(worker_offer: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    started = now()
    posture = task.get("context_posture")
    context = task.get("context")
    status = "ok"
    error = None
    output: Any = None

    if worker_offer.get("capability") != task.get("capability"):
        status = "rejected"
        error = "capability mismatch"
    elif worker_offer.get("available") is not True:
        status = "rejected"
        error = "worker offer unavailable"
    elif worker_offer.get("context_posture") != posture:
        status = "rejected"
        error = (
            "context posture mismatch: "
            f"worker={worker_offer.get('context_posture')} task={posture}"
        )
    elif posture not in POSTURES:
        status = "rejected"
        error = f"unknown context posture: {posture}"
    elif not isinstance(context, dict):
        status = "rejected"
        error = "task context must be an object"

    audit = None
    if status == "ok":
        audit = audit_context(posture, context)
        if not audit["audit_passed"]:
            status = "rejected"
            if audit["forbidden_context_keys_present"]:
                error = (
                    "forbidden context present: "
                    + ", ".join(audit["forbidden_context_keys_present"])
                )
            else:
                error = (
                    "required context missing: "
                    + ", ".join(audit["required_context_keys_missing"])
                )
        else:
            output = _deterministic_observation(posture, context)

    if audit is None and isinstance(context, dict) and posture in POSTURES:
        audit = audit_context(posture, context)

    return {
        "kind": "ghot.receipt",
        "version": "0",
        "receipt_id": f"receipt-{uuid.uuid4()}",
        "task_id": task.get("task_id"),
        "requester_node_id": task.get("requester_node_id"),
        "executor_node_id": worker_offer.get("node_id") or "unknown-worker",
        "capability": task.get("capability"),
        "context_posture": posture,
        "context_audit": audit,
        "status": status,
        "started_at": started,
        "finished_at": now(),
        "output": output,
        "output_sha256": (
            hashlib.sha256(canonical_json(output).encode("utf-8")).hexdigest()
            if output is not None
            else None
        ),
        "error": error,
    }


def demo() -> dict[str, Any]:
    shared_track = {
        "id": "track-001",
        "title": "The Circle Was Never Closed",
        "lyrics_excerpt": "Every arrival bends the line.",
    }
    lineage = [
        {"source_id": "track-ancestor-001", "relation": "recurring-door-image"},
        {"source_id": "track-ancestor-002", "relation": "garden-image"},
    ]

    fresh_offer = fake_offer("worker-fresh", "fresh")
    archive_offer = fake_offer("worker-archive", "lineage-enabled")

    fresh_task = make_task(
        posture="fresh",
        context={"current_track": shared_track},
    )
    archive_task = make_task(
        posture="lineage-enabled",
        context={
            "current_track": shared_track,
            "lineage_sources": lineage,
        },
    )
    contaminated_fresh_task = make_task(
        posture="fresh",
        context={
            "current_track": shared_track,
            "catalog_history": lineage,
        },
    )

    return {
        "kind": "ghot.epistemic-capability-demo",
        "version": "0",
        "fresh": {
            "offer": fresh_offer,
            "task": fresh_task,
            "receipt": execute_fake(fresh_offer, fresh_task),
        },
        "archive": {
            "offer": archive_offer,
            "task": archive_task,
            "receipt": execute_fake(archive_offer, archive_task),
        },
        "contaminated_fresh": {
            "offer": fresh_offer,
            "task": contaminated_fresh_task,
            "receipt": execute_fake(fresh_offer, contaminated_fresh_task),
        },
        "laws": [
            "MEMORY POSTURE != IDENTITY",
            "CONTEXT GRANT != AUTHORITY",
            "CONTEXT DIGEST != CONTEXT CONTENT",
            "DISTRIBUTION != INDEPENDENCE",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, ensure_ascii=False))
