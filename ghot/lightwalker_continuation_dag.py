#!/usr/bin/env python3
"""Lightwalker Continuation DAG / Multi-Hop Resume Lineage 001.

A resumed checkpoint may become the state ancestor of another sovereign
continuation. State ancestry remains root-relative while every hop receives new
owner-local resource authority.

Core laws:
    CONTINUATION LINEAGE != RESOURCE LINEAGE
    MULTI-HOP RESUME != RESTART CHAIN
    ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED
    EACH HOP REQUIRES NEW LOCAL AUTHORITY
    ONLY ONE LIVE LEAF PER CONTINUATION BRANCH
    COMPLETION MUST PROVE THE FULL RESUME ANCESTRY
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_execution_resume import (
    verify_resume,
    verify_resumed_checkpoint,
    verify_resumed_stop,
)
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_finalization,
    verify_reservation,
)
from lightwalker_transition_execution_gate import derive_execution_gate
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


HANDOFF_KIND = "ghot.lightwalker.continuation-handoff"
HANDOFF_VERSION = "0"
NODE_KIND = "ghot.lightwalker.continuation-node"
NODE_VERSION = "0"
COMPLETION_KIND = "ghot.lightwalker.continuation-dag-completion"
COMPLETION_VERSION = "0"
DAG_KIND = "ghot.lightwalker.continuation-dag-view"
DAG_VERSION = "0"

HANDOFF_DOMAIN = "ghot.lightwalker-continuation-handoff-signature/v0"
NODE_DOMAIN = "ghot.lightwalker-continuation-node-signature/v0"
COMPLETION_DOMAIN = "ghot.lightwalker-continuation-dag-completion-signature/v0"

HANDOFF_BYTES = b"GHOT-LightwalkerContinuationHandoff-v0|"
NODE_BYTES = b"GHOT-LightwalkerContinuationNode-v0|"
COMPLETION_BYTES = b"GHOT-LightwalkerContinuationDagCompletion-v0|"


def _nni(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


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
            key: item
            for key, item in value.items()
            if key not in {id_field, "signing"}
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


def _root_measure(parent_resume: dict[str, Any]) -> dict[str, Any]:
    measure = parent_resume.get("source_work_measure")
    if not isinstance(measure, dict):
        raise LightwalkerEconomyError("parent resume has no source work measure")
    return {
        "unit": _nonempty(measure.get("unit"), "source unit"),
        "quantity": _nni(measure.get("quantity"), "source quantity"),
    }


def _measure_at_progress(
    source_measure: dict[str, Any],
    progress_percent: int,
) -> dict[str, Any]:
    progress = _nni(progress_percent, "progress_percent")
    if progress > 100:
        raise LightwalkerEconomyError("progress may not exceed 100")
    numerator = int(source_measure["quantity"]) * progress
    if numerator % 100 != 0:
        raise LightwalkerEconomyError(
            "source measure cannot represent progress exactly"
        )
    return {
        "unit": source_measure["unit"],
        "quantity": numerator // 100,
    }


def make_continuation_handoff(
    parent_resume: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_stop: dict[str, Any],
    parent_reservation: dict[str, Any],
    parent_finalization: dict[str, Any],
    next_reservation: dict[str, Any],
    *,
    steward: IdentityKey,
    observed_cut: int,
) -> dict[str, Any]:
    if not verify_resume(parent_resume):
        raise LightwalkerEconomyError("invalid parent resume")
    if not verify_resumed_checkpoint(parent_resume, parent_checkpoint):
        raise LightwalkerEconomyError("invalid parent resumed checkpoint")
    if not verify_resumed_stop(parent_resume, parent_stop):
        raise LightwalkerEconomyError("invalid parent resumed stop")
    if not verify_finalization(parent_reservation, parent_finalization):
        raise LightwalkerEconomyError("invalid parent reservation finalization")
    if parent_finalization.get("status") not in {
        "RELEASED",
        "PARTIALLY_CONSUMED",
    }:
        raise LightwalkerEconomyError(
            "parent reservation must be terminal before handoff"
        )
    if parent_stop.get("reservation_finalization_id") != (
        parent_finalization["finalization_id"]
    ):
        raise LightwalkerEconomyError("parent stop/finalization mismatch")
    if steward.particular() != parent_resume["new_steward_particular"]:
        raise LightwalkerEconomyError("handoff signer does not own parent resume")
    if next_reservation["reservation_id"] == parent_reservation["reservation_id"]:
        raise LightwalkerEconomyError("handoff requires distinct next authority")

    source = _root_measure(parent_resume)
    progress = int(parent_checkpoint["total_progress_percent"])
    cumulative = _measure_at_progress(source, progress)
    remaining = {
        "unit": source["unit"],
        "quantity": source["quantity"] - cumulative["quantity"],
    }
    if remaining["quantity"] <= 0:
        raise LightwalkerEconomyError("completed checkpoint needs no handoff")

    body = {
        "kind": HANDOFF_KIND,
        "version": HANDOFF_VERSION,
        "authority": "owner-local-continuation-handoff",
        "root_run_id": parent_resume["old_run_id"],
        "root_checkpoint_id": parent_resume["source_checkpoint_id"],
        "parent_resume_id": parent_resume["resume_id"],
        "parent_reservation_id": parent_reservation["reservation_id"],
        "parent_checkpoint_id": parent_checkpoint["resumed_checkpoint_id"],
        "parent_stop_id": parent_stop["resumed_stop_id"],
        "parent_finalization_id": parent_finalization["finalization_id"],
        "parent_steward_particular": steward.particular(),
        "cumulative_progress_percent": progress,
        "source_work_measure": source,
        "cumulative_work_measure": cumulative,
        "remaining_work_measure": remaining,
        "next_guild_id": next_reservation["guild_id"],
        "next_reservation_id": next_reservation["reservation_id"],
        "next_steward_particular": next_reservation["steward_particular"],
        "observed_cut": _nni(observed_cut, "observed_cut"),
        "parent_leaf_closed": True,
        "execution_authority": "none",
        "ownership_transfer": False,
        "history_rewritten": False,
        "laws": [
            "CONTINUATION LINEAGE != RESOURCE LINEAGE",
            "MULTI-HOP RESUME != RESTART CHAIN",
            "EACH HOP REQUIRES NEW LOCAL AUTHORITY",
            "ONLY ONE LIVE LEAF PER CONTINUATION BRANCH",
        ],
    }
    return _signed(
        body,
        id_field="continuation_handoff_id",
        signer=steward,
        domain=HANDOFF_DOMAIN,
        byte_domain=HANDOFF_BYTES,
    )


def verify_continuation_handoff(
    parent_resume: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_stop: dict[str, Any],
    parent_reservation: dict[str, Any],
    parent_finalization: dict[str, Any],
    next_reservation: dict[str, Any],
    handoff: dict[str, Any],
) -> bool:
    try:
        if handoff.get("kind") != HANDOFF_KIND:
            return False
        if handoff.get("version") != HANDOFF_VERSION:
            return False
        if not verify_resume(parent_resume):
            return False
        if not verify_resumed_checkpoint(parent_resume, parent_checkpoint):
            return False
        if not verify_resumed_stop(parent_resume, parent_stop):
            return False
        if not verify_finalization(parent_reservation, parent_finalization):
            return False
        source = _root_measure(parent_resume)
        progress = int(parent_checkpoint["total_progress_percent"])
        cumulative = _measure_at_progress(source, progress)
        remaining = {
            "unit": source["unit"],
            "quantity": source["quantity"] - cumulative["quantity"],
        }
        checks = {
            "authority": "owner-local-continuation-handoff",
            "root_run_id": parent_resume["old_run_id"],
            "root_checkpoint_id": parent_resume["source_checkpoint_id"],
            "parent_resume_id": parent_resume["resume_id"],
            "parent_reservation_id": parent_reservation["reservation_id"],
            "parent_checkpoint_id": parent_checkpoint["resumed_checkpoint_id"],
            "parent_stop_id": parent_stop["resumed_stop_id"],
            "parent_finalization_id": parent_finalization["finalization_id"],
            "parent_steward_particular": parent_resume["new_steward_particular"],
            "cumulative_progress_percent": progress,
            "source_work_measure": source,
            "cumulative_work_measure": cumulative,
            "remaining_work_measure": remaining,
            "next_guild_id": next_reservation["guild_id"],
            "next_reservation_id": next_reservation["reservation_id"],
            "next_steward_particular": next_reservation["steward_particular"],
            "parent_leaf_closed": True,
            "execution_authority": "none",
            "ownership_transfer": False,
            "history_rewritten": False,
        }
        if any(handoff.get(k) != v for k, v in checks.items()):
            return False
        return _verify_signed(
            handoff,
            id_field="continuation_handoff_id",
            particular_field="parent_steward_particular",
            domain=HANDOFF_DOMAIN,
            byte_domain=HANDOFF_BYTES,
        )
    except Exception:
        return False


class ContinuationDagStore:
    """Owner-local second-or-later continuation over a signed handoff."""

    def __init__(
        self,
        root: Path,
        *,
        steward: IdentityKey,
        reservation_store: GuildReservationStore,
    ) -> None:
        self.root = root
        self.steward = steward
        self.reservation_store = reservation_store
        self.events_dir = root / "continuation-dag" / "events"
        self.state_dir = root / "continuation-dag" / "state"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _event_path(self, node_id: str, event_id: str) -> Path:
        return self.events_dir / self._safe(node_id) / f"{self._safe(event_id)}.json"

    def _state_path(self, node_id: str) -> Path:
        return self.state_dir / f"{self._safe(node_id)}.json"

    def _write_exclusive(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(
                fd,
                (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            )
        finally:
            os.close(fd)

    def _write_state(self, node_id: str, value: dict[str, Any]) -> None:
        path = self._state_path(node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def state(self, node_id: str) -> dict[str, Any]:
        path = self._state_path(node_id)
        if not path.exists():
            raise LightwalkerEconomyError("continuation node state not found")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError("invalid continuation node state")
        return value

    def resume_from_handoff(
        self,
        *,
        parent_resume: dict[str, Any],
        parent_checkpoint: dict[str, Any],
        parent_stop: dict[str, Any],
        parent_reservation: dict[str, Any],
        parent_finalization: dict[str, Any],
        handoff: dict[str, Any],
        new_snapshot: dict[str, Any],
        new_proposal: dict[str, Any],
        new_authorization: dict[str, Any],
        new_reservation: dict[str, Any],
        promise: dict[str, Any],
        route_policy: dict[str, Any],
        bundles: list[dict[str, Any]],
        supplied_temporal_intersection: dict[str, Any],
        executor: IdentityKey,
        observed_cut: int,
    ) -> dict[str, Any]:
        if not verify_continuation_handoff(
            parent_resume,
            parent_checkpoint,
            parent_stop,
            parent_reservation,
            parent_finalization,
            new_reservation,
            handoff,
        ):
            raise LightwalkerEconomyError("invalid continuation handoff")
        if not verify_reservation(
            new_snapshot,
            new_proposal,
            new_authorization,
            new_reservation,
        ):
            raise LightwalkerEconomyError("invalid continuation reservation")
        if self.steward.particular() != new_reservation["steward_particular"]:
            raise LightwalkerEconomyError("store does not own continuation reservation")
        if executor.particular() != new_authorization["executor_particular"]:
            raise LightwalkerEconomyError("continuation executor mismatch")
        if new_reservation["reservation_id"] != handoff["next_reservation_id"]:
            raise LightwalkerEconomyError("handoff names another next reservation")
        if new_authorization["authorized_measure"] != handoff["remaining_work_measure"]:
            raise LightwalkerEconomyError(
                "new authority must equal exact root-relative remaining work"
            )

        cut = _nni(observed_cut, "observed_cut")
        gate = derive_execution_gate(
            promise,
            route_policy,
            bundles,
            new_reservation,
            new_reservation,
            supplied_temporal_intersection,
            observed_cut=cut,
            execution_started_at_cut=None,
        )

        source = handoff["source_work_measure"]
        prior = handoff["cumulative_work_measure"]
        remaining = handoff["remaining_work_measure"]
        body = {
            "kind": NODE_KIND,
            "version": NODE_VERSION,
            "authority": "owner-local-multihop-continuation",
            "continuation_lineage_id": content_address({
                "root_run_id": handoff["root_run_id"],
                "root_checkpoint_id": handoff["root_checkpoint_id"],
            }),
            "root_run_id": handoff["root_run_id"],
            "root_checkpoint_id": handoff["root_checkpoint_id"],
            "parent_resume_id": handoff["parent_resume_id"],
            "parent_checkpoint_id": handoff["parent_checkpoint_id"],
            "parent_handoff_id": handoff["continuation_handoff_id"],
            "checkpoint_ancestry": [
                handoff["root_checkpoint_id"],
                handoff["parent_checkpoint_id"],
            ],
            "hop_index": 2,
            "prior_progress_percent": handoff["cumulative_progress_percent"],
            "source_work_measure": source,
            "prior_work_measure": prior,
            "remaining_work_measure": remaining,
            "new_guild_id": new_reservation["guild_id"],
            "new_reservation_id": new_reservation["reservation_id"],
            "new_authorization_id": new_reservation["authorization_id"],
            "new_steward_particular": self.steward.particular(),
            "new_executor_particular": executor.particular(),
            "resumed_at_cut": cut,
            "resume_execution_gate_id": gate["execution_gate_id"],
            "resume_evidence_path": gate["evidence_path"],
            "status": "RUNNING",
            "service_complete": False,
            "ownership_transfer": False,
            "ancestor_work_reexecuted": False,
            "settlement_authority": "none",
            "laws": [
                "CONTINUATION LINEAGE != RESOURCE LINEAGE",
                "MULTI-HOP RESUME != RESTART CHAIN",
                "ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED",
                "EACH HOP REQUIRES NEW LOCAL AUTHORITY",
                "ONLY ONE LIVE LEAF PER CONTINUATION BRANCH",
                "COMPLETION MUST PROVE THE FULL RESUME ANCESTRY",
            ],
        }
        node = _signed(
            body,
            id_field="continuation_node_id",
            signer=self.steward,
            domain=NODE_DOMAIN,
            byte_domain=NODE_BYTES,
        )
        self._write_exclusive(
            self._event_path(node["continuation_node_id"], node["continuation_node_id"]),
            node,
        )
        self._write_state(
            node["continuation_node_id"],
            {
                "continuation_node_id": node["continuation_node_id"],
                "status": "RUNNING",
                "new_reservation_id": new_reservation["reservation_id"],
                "prior_progress_percent": node["prior_progress_percent"],
                "source_work_measure": source,
                "prior_work_measure": prior,
                "remaining_work_measure": remaining,
            },
        )
        return node

    def complete(
        self,
        node: dict[str, Any],
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        *,
        promise: dict[str, Any],
        route_policy: dict[str, Any],
        bundles: list[dict[str, Any]],
        supplied_temporal_intersection: dict[str, Any],
        executor: IdentityKey,
        observed_cut: int,
        result_ref: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        state = self.state(node["continuation_node_id"])
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError("continuation leaf is not live")
        if reservation["reservation_id"] != node["new_reservation_id"]:
            raise LightwalkerEconomyError("completion reservation mismatch")
        if executor.particular() != node["new_executor_particular"]:
            raise LightwalkerEconomyError("completion executor mismatch")
        cut = _nni(observed_cut, "observed_cut")
        gate = derive_execution_gate(
            promise,
            route_policy,
            bundles,
            reservation,
            reservation,
            supplied_temporal_intersection,
            observed_cut=cut,
            execution_started_at_cut=int(node["resumed_at_cut"]),
        )
        execution, finalization = self.reservation_store.execute_reserved(
            snapshot,
            proposal,
            authorization,
            reservation,
            executor=executor,
            observed_cut=cut,
            simulate_success=True,
            result_ref=_nonempty(result_ref, "result_ref"),
        )

        source = node["source_work_measure"]
        prior = node["prior_work_measure"]
        new = node["remaining_work_measure"]
        if int(prior["quantity"]) + int(new["quantity"]) != int(source["quantity"]):
            raise LightwalkerEconomyError("multi-hop work accounting does not conserve root")
        body = {
            "kind": COMPLETION_KIND,
            "version": COMPLETION_VERSION,
            "authority": "owner-local-continuation-dag-completion",
            "continuation_lineage_id": node["continuation_lineage_id"],
            "continuation_node_id": node["continuation_node_id"],
            "root_run_id": node["root_run_id"],
            "root_checkpoint_id": node["root_checkpoint_id"],
            "parent_resume_id": node["parent_resume_id"],
            "parent_checkpoint_id": node["parent_checkpoint_id"],
            "parent_handoff_id": node["parent_handoff_id"],
            "checkpoint_ancestry": node["checkpoint_ancestry"],
            "hop_count": 2,
            "new_steward_particular": self.steward.particular(),
            "new_reservation_id": reservation["reservation_id"],
            "completed_at_cut": cut,
            "completion_gate_id": gate["execution_gate_id"],
            "source_work_measure": source,
            "ancestor_work_measure": prior,
            "new_work_measure": new,
            "total_work_measure": source,
            "total_progress_percent": 100,
            "result_ref": result_ref,
            "execution_receipt_id": execution["execution_receipt_id"],
            "reservation_finalization_id": finalization["finalization_id"],
            "reservation_status": finalization["status"],
            "ancestor_work_reexecuted": False,
            "ancestor_work_double_counted": False,
            "full_ancestry_proven": True,
            "service_complete": True,
            "ownership_transfer": False,
            "settlement_authority": "none",
            "laws": [
                "CONTINUATION LINEAGE != RESOURCE LINEAGE",
                "MULTI-HOP RESUME != RESTART CHAIN",
                "ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED",
                "EACH HOP REQUIRES NEW LOCAL AUTHORITY",
                "ONLY ONE LIVE LEAF PER CONTINUATION BRANCH",
                "COMPLETION MUST PROVE THE FULL RESUME ANCESTRY",
            ],
        }
        completion = _signed(
            body,
            id_field="continuation_completion_id",
            signer=self.steward,
            domain=COMPLETION_DOMAIN,
            byte_domain=COMPLETION_BYTES,
        )
        self._write_exclusive(
            self._event_path(node["continuation_node_id"], completion["continuation_completion_id"]),
            completion,
        )
        self._write_state(
            node["continuation_node_id"],
            {
                **state,
                "status": "COMPLETED",
                "continuation_completion_id": completion["continuation_completion_id"],
                "total_progress_percent": 100,
            },
        )
        return completion, execution, finalization


def verify_continuation_node(node: dict[str, Any]) -> bool:
    try:
        if node.get("kind") != NODE_KIND or node.get("version") != NODE_VERSION:
            return False
        if node.get("authority") != "owner-local-multihop-continuation":
            return False
        if node.get("hop_index") != 2:
            return False
        if len(node.get("checkpoint_ancestry", [])) != 2:
            return False
        if node.get("service_complete") is not False:
            return False
        if node.get("ownership_transfer") is not False:
            return False
        if node.get("ancestor_work_reexecuted") is not False:
            return False
        return _verify_signed(
            node,
            id_field="continuation_node_id",
            particular_field="new_steward_particular",
            domain=NODE_DOMAIN,
            byte_domain=NODE_BYTES,
        )
    except Exception:
        return False


def verify_continuation_completion(
    node: dict[str, Any],
    completion: dict[str, Any],
) -> bool:
    try:
        if not verify_continuation_node(node):
            return False
        if completion.get("kind") != COMPLETION_KIND:
            return False
        if completion.get("version") != COMPLETION_VERSION:
            return False
        if completion.get("continuation_node_id") != node["continuation_node_id"]:
            return False
        if completion.get("checkpoint_ancestry") != node["checkpoint_ancestry"]:
            return False
        if completion.get("full_ancestry_proven") is not True:
            return False
        if completion.get("ancestor_work_reexecuted") is not False:
            return False
        if completion.get("ancestor_work_double_counted") is not False:
            return False
        if completion.get("total_progress_percent") != 100:
            return False
        if completion.get("settlement_authority") != "none":
            return False
        return _verify_signed(
            completion,
            id_field="continuation_completion_id",
            particular_field="new_steward_particular",
            domain=COMPLETION_DOMAIN,
            byte_domain=COMPLETION_BYTES,
        )
    except Exception:
        return False


def derive_continuation_dag(
    root_run: dict[str, Any],
    root_checkpoint: dict[str, Any],
    parent_resume: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_stop: dict[str, Any],
    handoff: dict[str, Any],
    child_nodes: list[dict[str, Any]],
    *,
    completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not verify_resume(parent_resume):
        raise LightwalkerEconomyError("invalid parent resume in DAG")
    if not verify_resumed_checkpoint(parent_resume, parent_checkpoint):
        raise LightwalkerEconomyError("invalid parent checkpoint in DAG")
    if not verify_resumed_stop(parent_resume, parent_stop):
        raise LightwalkerEconomyError("invalid parent stop in DAG")
    if parent_resume["old_run_id"] != root_run["run_id"]:
        raise LightwalkerEconomyError("parent resume root run mismatch")
    if parent_resume["source_checkpoint_id"] != root_checkpoint["checkpoint_id"]:
        raise LightwalkerEconomyError("parent resume root checkpoint mismatch")
    if handoff["parent_resume_id"] != parent_resume["resume_id"]:
        raise LightwalkerEconomyError("handoff parent resume mismatch")
    if handoff["parent_checkpoint_id"] != parent_checkpoint["resumed_checkpoint_id"]:
        raise LightwalkerEconomyError("handoff parent checkpoint mismatch")
    if len(child_nodes) != 1:
        raise LightwalkerEconomyError(
            "continuation branch must have exactly one live/terminal child node"
        )
    node = child_nodes[0]
    if not verify_continuation_node(node):
        raise LightwalkerEconomyError("invalid continuation child node")
    if node["parent_handoff_id"] != handoff["continuation_handoff_id"]:
        raise LightwalkerEconomyError("child node belongs to another handoff")

    if completion is None:
        status = "ACTIVE"
        live_leaf_ids = [node["continuation_node_id"]]
        terminal_leaf_id = None
    else:
        if not verify_continuation_completion(node, completion):
            raise LightwalkerEconomyError("invalid continuation completion")
        status = "COMPLETED"
        live_leaf_ids = []
        terminal_leaf_id = completion["continuation_completion_id"]

    body = {
        "kind": DAG_KIND,
        "version": DAG_VERSION,
        "authority": "derived-continuation-lineage-observation",
        "continuation_lineage_id": node["continuation_lineage_id"],
        "root_run_id": root_run["run_id"],
        "root_checkpoint_id": root_checkpoint["checkpoint_id"],
        "resume_ids": [parent_resume["resume_id"]],
        "checkpoint_ids": [
            root_checkpoint["checkpoint_id"],
            parent_checkpoint["resumed_checkpoint_id"],
        ],
        "handoff_ids": [handoff["continuation_handoff_id"]],
        "continuation_node_ids": [node["continuation_node_id"]],
        "resource_reservation_ids": [
            root_run["reservation_id"],
            parent_resume["new_reservation_id"],
            node["new_reservation_id"],
        ],
        "resource_reservations_distinct": len({
            root_run["reservation_id"],
            parent_resume["new_reservation_id"],
            node["new_reservation_id"],
        }) == 3,
        "status": status,
        "live_leaf_ids": live_leaf_ids,
        "live_leaf_count": len(live_leaf_ids),
        "terminal_leaf_id": terminal_leaf_id,
        "full_checkpoint_ancestry": node["checkpoint_ancestry"],
        "source_work_measure": node["source_work_measure"],
        "cumulative_work_before_leaf": node["prior_work_measure"],
        "remaining_work_at_leaf_start": node["remaining_work_measure"],
        "global_consensus": False,
        "execution_authority": "none",
        "laws": [
            "CONTINUATION LINEAGE != RESOURCE LINEAGE",
            "MULTI-HOP RESUME != RESTART CHAIN",
            "ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED",
            "EACH HOP REQUIRES NEW LOCAL AUTHORITY",
            "ONLY ONE LIVE LEAF PER CONTINUATION BRANCH",
            "COMPLETION MUST PROVE THE FULL RESUME ANCESTRY",
        ],
    }
    return {**body, "continuation_dag_id": content_address(body)}


__all__ = [
    "ContinuationDagStore",
    "derive_continuation_dag",
    "make_continuation_handoff",
    "verify_continuation_completion",
    "verify_continuation_handoff",
    "verify_continuation_node",
]
