#!/usr/bin/env python3
"""Lightwalker Recursive Continuation Kernel 001.

Generalizes the explicit 062 second-hop specimen into an arbitrary-depth
continuation grammar. A 062 continuation node can seed the recursive kernel;
every later node is structurally identical regardless of depth.

Core laws:
    DEPTH != AUTHORITY
    RECURSION != HISTORY COLLAPSE
    EACH EDGE MUST PROVE ITS PARENT
    ROOT MEASURE MUST REMAIN INVARIANT
    ONLY ONE LIVE LEAF PER ACCEPTED BRANCH
    COMPACTION MAY SHORTEN PROOF TRANSPORT WITHOUT ERASING ANCESTRY
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lightwalker_continuation_dag import verify_continuation_node
from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
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


NODE_KIND = "ghot.lightwalker.recursive-continuation-node"
NODE_VERSION = "0"
CHECKPOINT_KIND = "ghot.lightwalker.recursive-continuation-checkpoint"
CHECKPOINT_VERSION = "0"
STOP_KIND = "ghot.lightwalker.recursive-continuation-stop"
STOP_VERSION = "0"
HANDOFF_KIND = "ghot.lightwalker.recursive-continuation-handoff"
HANDOFF_VERSION = "0"
COMPLETION_KIND = "ghot.lightwalker.recursive-continuation-completion"
COMPLETION_VERSION = "0"
VIEW_KIND = "ghot.lightwalker.recursive-continuation-view"
VIEW_VERSION = "0"
COMPACT_KIND = "ghot.lightwalker.recursive-continuation-compact-proof"
COMPACT_VERSION = "0"

NODE_DOMAIN = "ghot.lightwalker-recursive-continuation-node-signature/v0"
CHECKPOINT_DOMAIN = "ghot.lightwalker-recursive-continuation-checkpoint-signature/v0"
STOP_DOMAIN = "ghot.lightwalker-recursive-continuation-stop-signature/v0"
HANDOFF_DOMAIN = "ghot.lightwalker-recursive-continuation-handoff-signature/v0"
COMPLETION_DOMAIN = "ghot.lightwalker-recursive-continuation-completion-signature/v0"

NODE_BYTES = b"GHOT-LightwalkerRecursiveContinuationNode-v0|"
CHECKPOINT_BYTES = b"GHOT-LightwalkerRecursiveContinuationCheckpoint-v0|"
STOP_BYTES = b"GHOT-LightwalkerRecursiveContinuationStop-v0|"
HANDOFF_BYTES = b"GHOT-LightwalkerRecursiveContinuationHandoff-v0|"
COMPLETION_BYTES = b"GHOT-LightwalkerRecursiveContinuationCompletion-v0|"


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


def _measure_at_progress(
    source_measure: dict[str, Any],
    progress_percent: int,
) -> dict[str, Any]:
    progress = _nni(progress_percent, "progress_percent")
    if progress > 100:
        raise LightwalkerEconomyError("progress may not exceed 100")
    unit = _nonempty(source_measure.get("unit"), "source unit")
    quantity = _nni(source_measure.get("quantity"), "source quantity")
    numerator = quantity * progress
    if numerator % 100 != 0:
        raise LightwalkerEconomyError(
            "root measure cannot represent progress exactly"
        )
    return {"unit": unit, "quantity": numerator // 100}


def _node_id(node: dict[str, Any]) -> str:
    if node.get("kind") == "ghot.lightwalker.continuation-node":
        return str(node["continuation_node_id"])
    if node.get("kind") == NODE_KIND:
        return str(node["recursive_node_id"])
    raise LightwalkerEconomyError("unsupported continuation node kind")


def _normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    if node.get("kind") == "ghot.lightwalker.continuation-node":
        if not verify_continuation_node(node):
            raise LightwalkerEconomyError("invalid 062 seed continuation node")
        return {
            "node_id": node["continuation_node_id"],
            "node_kind": node["kind"],
            "continuation_lineage_id": node["continuation_lineage_id"],
            "root_run_id": node["root_run_id"],
            "root_checkpoint_id": node["root_checkpoint_id"],
            "checkpoint_ancestry": list(node["checkpoint_ancestry"]),
            "hop_index": int(node["hop_index"]),
            "prior_progress_percent": int(node["prior_progress_percent"]),
            "source_work_measure": dict(node["source_work_measure"]),
            "prior_work_measure": dict(node["prior_work_measure"]),
            "remaining_work_measure": dict(node["remaining_work_measure"]),
            "reservation_id": node["new_reservation_id"],
            "authorization_id": node["new_authorization_id"],
            "steward_particular": node["new_steward_particular"],
            "executor_particular": node["new_executor_particular"],
            "resumed_at_cut": int(node["resumed_at_cut"]),
        }
    if node.get("kind") == NODE_KIND:
        if not verify_recursive_node(node):
            raise LightwalkerEconomyError("invalid recursive continuation node")
        return {
            "node_id": node["recursive_node_id"],
            "node_kind": node["kind"],
            "continuation_lineage_id": node["continuation_lineage_id"],
            "root_run_id": node["root_run_id"],
            "root_checkpoint_id": node["root_checkpoint_id"],
            "checkpoint_ancestry": list(node["checkpoint_ancestry"]),
            "hop_index": int(node["hop_index"]),
            "prior_progress_percent": int(node["prior_progress_percent"]),
            "source_work_measure": dict(node["source_work_measure"]),
            "prior_work_measure": dict(node["prior_work_measure"]),
            "remaining_work_measure": dict(node["remaining_work_measure"]),
            "reservation_id": node["new_reservation_id"],
            "authorization_id": node["new_authorization_id"],
            "steward_particular": node["new_steward_particular"],
            "executor_particular": node["new_executor_particular"],
            "resumed_at_cut": int(node["resumed_at_cut"]),
        }
    raise LightwalkerEconomyError("unsupported recursive parent node")


def verify_recursive_node(node: dict[str, Any]) -> bool:
    try:
        if node.get("kind") != NODE_KIND or node.get("version") != NODE_VERSION:
            return False
        if node.get("authority") != "owner-local-recursive-continuation":
            return False
        hop = int(node.get("hop_index", -1))
        ancestry = node.get("checkpoint_ancestry")
        if hop < 3 or not isinstance(ancestry, list) or len(ancestry) != hop:
            return False
        if len(set(ancestry)) != len(ancestry):
            return False
        source = node.get("source_work_measure")
        prior = node.get("prior_work_measure")
        remaining = node.get("remaining_work_measure")
        if not all(isinstance(x, dict) for x in (source, prior, remaining)):
            return False
        if prior != _measure_at_progress(
            source,
            int(node.get("prior_progress_percent", -1)),
        ):
            return False
        if prior.get("unit") != remaining.get("unit"):
            return False
        if int(prior["quantity"]) + int(remaining["quantity"]) != int(
            source["quantity"]
        ):
            return False
        if node.get("service_complete") is not False:
            return False
        if node.get("ownership_transfer") is not False:
            return False
        if node.get("ancestor_work_reexecuted") is not False:
            return False
        if node.get("settlement_authority") != "none":
            return False
        return _verify_signed(
            node,
            id_field="recursive_node_id",
            particular_field="new_steward_particular",
            domain=NODE_DOMAIN,
            byte_domain=NODE_BYTES,
        )
    except Exception:
        return False


def verify_recursive_checkpoint(
    node: dict[str, Any],
    checkpoint: dict[str, Any],
) -> bool:
    try:
        parent = _normalize_node(node)
        if checkpoint.get("kind") != CHECKPOINT_KIND:
            return False
        if checkpoint.get("version") != CHECKPOINT_VERSION:
            return False
        if checkpoint.get("authority") != "owner-local-recursive-checkpoint":
            return False
        if checkpoint.get("parent_node_id") != parent["node_id"]:
            return False
        if checkpoint.get("continuation_lineage_id") != parent[
            "continuation_lineage_id"
        ]:
            return False
        if checkpoint.get("root_run_id") != parent["root_run_id"]:
            return False
        if checkpoint.get("root_checkpoint_id") != parent["root_checkpoint_id"]:
            return False
        if checkpoint.get("hop_index") != parent["hop_index"]:
            return False
        if checkpoint.get("reservation_id") != parent["reservation_id"]:
            return False
        if checkpoint.get("steward_particular") != parent["steward_particular"]:
            return False
        if checkpoint.get("executor_particular") != parent["executor_particular"]:
            return False
        if checkpoint.get("ancestor_checkpoint_ids") != parent[
            "checkpoint_ancestry"
        ]:
            return False
        total = int(checkpoint.get("total_progress_percent", -1))
        prior = parent["prior_progress_percent"]
        if not (prior < total < 100):
            return False
        cumulative = _measure_at_progress(parent["source_work_measure"], total)
        delta = {
            "unit": cumulative["unit"],
            "quantity": cumulative["quantity"] - parent["prior_work_measure"]["quantity"],
        }
        if checkpoint.get("cumulative_work_measure") != cumulative:
            return False
        if checkpoint.get("new_work_measure") != delta:
            return False
        if checkpoint.get("service_complete") is not False:
            return False
        if checkpoint.get("settlement_authority") != "none":
            return False
        return _verify_signed(
            checkpoint,
            id_field="recursive_checkpoint_id",
            particular_field="steward_particular",
            domain=CHECKPOINT_DOMAIN,
            byte_domain=CHECKPOINT_BYTES,
        )
    except Exception:
        return False


def verify_recursive_stop(
    node: dict[str, Any],
    checkpoint: dict[str, Any],
    reservation: dict[str, Any],
    finalization: dict[str, Any],
    stop: dict[str, Any],
) -> bool:
    try:
        parent = _normalize_node(node)
        if not verify_recursive_checkpoint(node, checkpoint):
            return False
        if not verify_finalization(reservation, finalization):
            return False
        if finalization.get("status") != "PARTIALLY_CONSUMED":
            return False
        if finalization.get("partial_evidence_ref") != checkpoint[
            "recursive_checkpoint_id"
        ]:
            return False
        if finalization.get("consumed_measure") != checkpoint["new_work_measure"]:
            return False
        if stop.get("kind") != STOP_KIND or stop.get("version") != STOP_VERSION:
            return False
        checks = {
            "authority": "owner-local-recursive-stop",
            "parent_node_id": parent["node_id"],
            "recursive_checkpoint_id": checkpoint["recursive_checkpoint_id"],
            "reservation_id": reservation["reservation_id"],
            "reservation_finalization_id": finalization["finalization_id"],
            "reservation_status": "PARTIALLY_CONSUMED",
            "steward_particular": parent["steward_particular"],
            "total_progress_percent": checkpoint["total_progress_percent"],
            "service_complete": False,
            "history_rewritten": False,
            "settlement_authority": "none",
        }
        if any(stop.get(k) != v for k, v in checks.items()):
            return False
        return _verify_signed(
            stop,
            id_field="recursive_stop_id",
            particular_field="steward_particular",
            domain=STOP_DOMAIN,
            byte_domain=STOP_BYTES,
        )
    except Exception:
        return False


def verify_recursive_handoff(
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_stop: dict[str, Any],
    parent_reservation: dict[str, Any],
    parent_finalization: dict[str, Any],
    next_reservation: dict[str, Any],
    handoff: dict[str, Any],
) -> bool:
    try:
        parent = _normalize_node(parent_node)
        if not verify_recursive_stop(
            parent_node,
            parent_checkpoint,
            parent_reservation,
            parent_finalization,
            parent_stop,
        ):
            return False
        if handoff.get("kind") != HANDOFF_KIND:
            return False
        if handoff.get("version") != HANDOFF_VERSION:
            return False
        if handoff.get("authority") != "owner-local-recursive-handoff":
            return False
        cumulative = parent_checkpoint["cumulative_work_measure"]
        remaining = {
            "unit": cumulative["unit"],
            "quantity": (
                int(parent["source_work_measure"]["quantity"])
                - int(cumulative["quantity"])
            ),
        }
        checks = {
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "root_run_id": parent["root_run_id"],
            "root_checkpoint_id": parent["root_checkpoint_id"],
            "parent_node_id": parent["node_id"],
            "parent_checkpoint_id": parent_checkpoint["recursive_checkpoint_id"],
            "parent_stop_id": parent_stop["recursive_stop_id"],
            "parent_finalization_id": parent_finalization["finalization_id"],
            "parent_hop_index": parent["hop_index"],
            "parent_steward_particular": parent["steward_particular"],
            "checkpoint_ancestry": (
                parent["checkpoint_ancestry"]
                + [parent_checkpoint["recursive_checkpoint_id"]]
            ),
            "cumulative_progress_percent": parent_checkpoint[
                "total_progress_percent"
            ],
            "source_work_measure": parent["source_work_measure"],
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
        if next_reservation["reserved_measure"] != remaining:
            return False
        return _verify_signed(
            handoff,
            id_field="recursive_handoff_id",
            particular_field="parent_steward_particular",
            domain=HANDOFF_DOMAIN,
            byte_domain=HANDOFF_BYTES,
        )
    except Exception:
        return False


class RecursiveContinuationStore:
    """Owner-local recursive continuation state and one-child handoff registry."""

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
        self.events_dir = root / "recursive-continuation" / "events"
        self.state_dir = root / "recursive-continuation" / "state"
        self.handoff_dir = root / "recursive-continuation" / "accepted-handoffs"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _event_path(self, node_id: str, event_id: str) -> Path:
        return self.events_dir / self._safe(node_id) / f"{self._safe(event_id)}.json"

    def _state_path(self, node_id: str) -> Path:
        return self.state_dir / f"{self._safe(node_id)}.json"

    def _handoff_path(self, checkpoint_id: str) -> Path:
        return self.handoff_dir / f"{self._safe(checkpoint_id)}.json"

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

    def state(self, node: dict[str, Any]) -> dict[str, Any]:
        node_id = _node_id(node)
        path = self._state_path(node_id)
        if not path.exists():
            raise LightwalkerEconomyError("recursive continuation state not found")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError("invalid recursive state")
        return value

    def register_seed(self, node: dict[str, Any]) -> dict[str, Any]:
        parent = _normalize_node(node)
        if node.get("kind") != "ghot.lightwalker.continuation-node":
            raise LightwalkerEconomyError("recursive seed must be a 062 node")
        if self.steward.particular() != parent["steward_particular"]:
            raise LightwalkerEconomyError("seed registrar is not node owner")
        if self.reservation_store.finalization(parent["reservation_id"]) is not None:
            raise LightwalkerEconomyError("seed reservation is already terminal")
        state = {
            "node_id": parent["node_id"],
            "node_kind": parent["node_kind"],
            "status": "RUNNING",
            "hop_index": parent["hop_index"],
            "prior_progress_percent": parent["prior_progress_percent"],
            "total_progress_percent": parent["prior_progress_percent"],
            "checkpoint_ancestry": parent["checkpoint_ancestry"],
            "source_work_measure": parent["source_work_measure"],
            "prior_work_measure": parent["prior_work_measure"],
            "remaining_work_measure": parent["remaining_work_measure"],
            "reservation_id": parent["reservation_id"],
            "last_checkpoint_id": None,
            "indexing_authority": "none",
        }
        self._write_exclusive(self._state_path(parent["node_id"]), state)
        return dict(state)

    def checkpoint(
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
        total_progress_percent: int,
        partial_result_ref: str,
    ) -> dict[str, Any]:
        parent = _normalize_node(node)
        state = self.state(node)
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError("only a live recursive leaf may checkpoint")
        if reservation["reservation_id"] != parent["reservation_id"]:
            raise LightwalkerEconomyError("recursive checkpoint reservation mismatch")
        if not verify_reservation(snapshot, proposal, authorization, reservation):
            raise LightwalkerEconomyError("invalid recursive checkpoint reservation")
        if self.steward.particular() != parent["steward_particular"]:
            raise LightwalkerEconomyError("recursive checkpoint store is not owner")
        if executor.particular() != parent["executor_particular"]:
            raise LightwalkerEconomyError("recursive checkpoint executor mismatch")
        if self.reservation_store.finalization(reservation["reservation_id"]) is not None:
            raise LightwalkerEconomyError("recursive checkpoint reservation is terminal")

        cut = _nni(observed_cut, "observed_cut")
        total = _nni(total_progress_percent, "total_progress_percent")
        if not (int(state["total_progress_percent"]) < total < 100):
            raise LightwalkerEconomyError("recursive checkpoint must advance below 100")
        cumulative = _measure_at_progress(parent["source_work_measure"], total)
        new_work = {
            "unit": cumulative["unit"],
            "quantity": cumulative["quantity"] - parent["prior_work_measure"]["quantity"],
        }
        if new_work["quantity"] <= 0:
            raise LightwalkerEconomyError("recursive checkpoint adds no work")
        if new_work["quantity"] > parent["remaining_work_measure"]["quantity"]:
            raise LightwalkerEconomyError("recursive checkpoint exceeds local authority")

        gate = derive_execution_gate(
            promise,
            route_policy,
            bundles,
            reservation,
            reservation,
            supplied_temporal_intersection,
            observed_cut=cut,
            execution_started_at_cut=parent["resumed_at_cut"],
        )
        body = {
            "kind": CHECKPOINT_KIND,
            "version": CHECKPOINT_VERSION,
            "authority": "owner-local-recursive-checkpoint",
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "root_run_id": parent["root_run_id"],
            "root_checkpoint_id": parent["root_checkpoint_id"],
            "parent_node_id": parent["node_id"],
            "hop_index": parent["hop_index"],
            "reservation_id": parent["reservation_id"],
            "steward_particular": self.steward.particular(),
            "executor_particular": executor.particular(),
            "ancestor_checkpoint_ids": parent["checkpoint_ancestry"],
            "checkpoint_at_cut": cut,
            "continuation_gate_id": gate["execution_gate_id"],
            "total_progress_percent": total,
            "cumulative_work_measure": cumulative,
            "new_work_measure": new_work,
            "partial_result_ref": _nonempty(partial_result_ref, "partial_result_ref"),
            "service_complete": False,
            "settlement_authority": "none",
            "laws": [
                "DEPTH != AUTHORITY",
                "EACH EDGE MUST PROVE ITS PARENT",
                "ROOT MEASURE MUST REMAIN INVARIANT",
            ],
        }
        checkpoint = _signed(
            body,
            id_field="recursive_checkpoint_id",
            signer=self.steward,
            domain=CHECKPOINT_DOMAIN,
            byte_domain=CHECKPOINT_BYTES,
        )
        self._write_exclusive(
            self._event_path(parent["node_id"], checkpoint["recursive_checkpoint_id"]),
            checkpoint,
        )
        self._write_state(
            parent["node_id"],
            {
                **state,
                "total_progress_percent": total,
                "last_checkpoint_id": checkpoint["recursive_checkpoint_id"],
                "partial_result_ref": body["partial_result_ref"],
            },
        )
        return checkpoint

    def stop(
        self,
        node: dict[str, Any],
        checkpoint: dict[str, Any],
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        *,
        observed_cut: int,
        reason: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        parent = _normalize_node(node)
        state = self.state(node)
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError("recursive node is not stoppable")
        if state["last_checkpoint_id"] != checkpoint.get("recursive_checkpoint_id"):
            raise LightwalkerEconomyError("stop must use latest recursive checkpoint")
        if not verify_recursive_checkpoint(node, checkpoint):
            raise LightwalkerEconomyError("invalid recursive checkpoint")
        finalization = self.reservation_store.partially_consume_and_release(
            snapshot,
            proposal,
            authorization,
            reservation,
            consumed_quantity=int(checkpoint["new_work_measure"]["quantity"]),
            partial_evidence_ref=checkpoint["recursive_checkpoint_id"],
            observed_cut=_nni(observed_cut, "observed_cut"),
            reason=_nonempty(reason, "reason"),
        )
        body = {
            "kind": STOP_KIND,
            "version": STOP_VERSION,
            "authority": "owner-local-recursive-stop",
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "parent_node_id": parent["node_id"],
            "recursive_checkpoint_id": checkpoint["recursive_checkpoint_id"],
            "reservation_id": reservation["reservation_id"],
            "reservation_finalization_id": finalization["finalization_id"],
            "reservation_status": finalization["status"],
            "steward_particular": self.steward.particular(),
            "stopped_at_cut": _nni(observed_cut, "observed_cut"),
            "reason": reason,
            "total_progress_percent": checkpoint["total_progress_percent"],
            "service_complete": False,
            "history_rewritten": False,
            "settlement_authority": "none",
            "laws": [
                "RECURSION != HISTORY COLLAPSE",
                "EACH EDGE MUST PROVE ITS PARENT",
                "ROOT MEASURE MUST REMAIN INVARIANT",
            ],
        }
        stop = _signed(
            body,
            id_field="recursive_stop_id",
            signer=self.steward,
            domain=STOP_DOMAIN,
            byte_domain=STOP_BYTES,
        )
        self._write_exclusive(
            self._event_path(parent["node_id"], stop["recursive_stop_id"]),
            stop,
        )
        self._write_state(
            parent["node_id"],
            {
                **state,
                "status": "STOPPED",
                "recursive_stop_id": stop["recursive_stop_id"],
                "reservation_finalization_id": finalization["finalization_id"],
            },
        )
        return stop, finalization

    def handoff(
        self,
        node: dict[str, Any],
        checkpoint: dict[str, Any],
        stop: dict[str, Any],
        reservation: dict[str, Any],
        finalization: dict[str, Any],
        next_reservation: dict[str, Any],
        *,
        observed_cut: int,
    ) -> dict[str, Any]:
        parent = _normalize_node(node)
        state = self.state(node)
        if state["status"] != "STOPPED":
            raise LightwalkerEconomyError("parent recursive leaf must be stopped")
        if not verify_recursive_stop(
            node,
            checkpoint,
            reservation,
            finalization,
            stop,
        ):
            raise LightwalkerEconomyError("invalid recursive stop lineage")
        cumulative = checkpoint["cumulative_work_measure"]
        remaining = {
            "unit": cumulative["unit"],
            "quantity": (
                int(parent["source_work_measure"]["quantity"])
                - int(cumulative["quantity"])
            ),
        }
        if next_reservation["reserved_measure"] != remaining:
            raise LightwalkerEconomyError(
                "next reservation must equal exact root-relative remainder"
            )
        if next_reservation["reservation_id"] == reservation["reservation_id"]:
            raise LightwalkerEconomyError("recursive handoff requires new authority")
        body = {
            "kind": HANDOFF_KIND,
            "version": HANDOFF_VERSION,
            "authority": "owner-local-recursive-handoff",
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "root_run_id": parent["root_run_id"],
            "root_checkpoint_id": parent["root_checkpoint_id"],
            "parent_node_id": parent["node_id"],
            "parent_checkpoint_id": checkpoint["recursive_checkpoint_id"],
            "parent_stop_id": stop["recursive_stop_id"],
            "parent_finalization_id": finalization["finalization_id"],
            "parent_hop_index": parent["hop_index"],
            "parent_steward_particular": parent["steward_particular"],
            "checkpoint_ancestry": (
                parent["checkpoint_ancestry"]
                + [checkpoint["recursive_checkpoint_id"]]
            ),
            "cumulative_progress_percent": checkpoint[
                "total_progress_percent"
            ],
            "source_work_measure": parent["source_work_measure"],
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
                "DEPTH != AUTHORITY",
                "EACH EDGE MUST PROVE ITS PARENT",
                "ONLY ONE LIVE LEAF PER ACCEPTED BRANCH",
            ],
        }
        handoff = _signed(
            body,
            id_field="recursive_handoff_id",
            signer=self.steward,
            domain=HANDOFF_DOMAIN,
            byte_domain=HANDOFF_BYTES,
        )
        self._write_exclusive(
            self._handoff_path(checkpoint["recursive_checkpoint_id"]),
            handoff,
        )
        self._write_exclusive(
            self._event_path(parent["node_id"], handoff["recursive_handoff_id"]),
            handoff,
        )
        return handoff

    def resume_child(
        self,
        *,
        parent_node: dict[str, Any],
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
        parent = _normalize_node(parent_node)
        if not verify_recursive_handoff(
            parent_node,
            parent_checkpoint,
            parent_stop,
            parent_reservation,
            parent_finalization,
            new_reservation,
            handoff,
        ):
            raise LightwalkerEconomyError("invalid recursive handoff")
        if not verify_reservation(
            new_snapshot,
            new_proposal,
            new_authorization,
            new_reservation,
        ):
            raise LightwalkerEconomyError("invalid child reservation")
        if self.steward.particular() != new_reservation["steward_particular"]:
            raise LightwalkerEconomyError("child store is not reservation owner")
        if executor.particular() != new_authorization["executor_particular"]:
            raise LightwalkerEconomyError("child executor mismatch")
        if new_authorization["authorized_measure"] != handoff[
            "remaining_work_measure"
        ]:
            raise LightwalkerEconomyError("child authority is not exact remainder")
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
        hop = parent["hop_index"] + 1
        ancestry = list(handoff["checkpoint_ancestry"])
        if len(ancestry) != hop:
            raise LightwalkerEconomyError("recursive ancestry depth mismatch")
        body = {
            "kind": NODE_KIND,
            "version": NODE_VERSION,
            "authority": "owner-local-recursive-continuation",
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "root_run_id": parent["root_run_id"],
            "root_checkpoint_id": parent["root_checkpoint_id"],
            "parent_node_id": parent["node_id"],
            "parent_node_kind": parent["node_kind"],
            "parent_checkpoint_id": parent_checkpoint["recursive_checkpoint_id"],
            "parent_handoff_id": handoff["recursive_handoff_id"],
            "checkpoint_ancestry": ancestry,
            "ancestry_digest": content_address({
                "continuation_lineage_id": parent["continuation_lineage_id"],
                "checkpoint_ancestry": ancestry,
            }),
            "hop_index": hop,
            "prior_progress_percent": handoff["cumulative_progress_percent"],
            "source_work_measure": handoff["source_work_measure"],
            "prior_work_measure": handoff["cumulative_work_measure"],
            "remaining_work_measure": handoff["remaining_work_measure"],
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
                "DEPTH != AUTHORITY",
                "RECURSION != HISTORY COLLAPSE",
                "EACH EDGE MUST PROVE ITS PARENT",
                "ROOT MEASURE MUST REMAIN INVARIANT",
                "ONLY ONE LIVE LEAF PER ACCEPTED BRANCH",
            ],
        }
        node = _signed(
            body,
            id_field="recursive_node_id",
            signer=self.steward,
            domain=NODE_DOMAIN,
            byte_domain=NODE_BYTES,
        )
        self._write_exclusive(
            self._event_path(node["recursive_node_id"], node["recursive_node_id"]),
            node,
        )
        self._write_exclusive(
            self._state_path(node["recursive_node_id"]),
            {
                "node_id": node["recursive_node_id"],
                "node_kind": node["kind"],
                "status": "RUNNING",
                "hop_index": hop,
                "prior_progress_percent": node["prior_progress_percent"],
                "total_progress_percent": node["prior_progress_percent"],
                "checkpoint_ancestry": ancestry,
                "source_work_measure": node["source_work_measure"],
                "prior_work_measure": node["prior_work_measure"],
                "remaining_work_measure": node["remaining_work_measure"],
                "reservation_id": node["new_reservation_id"],
                "last_checkpoint_id": None,
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
        parent = _normalize_node(node)
        state = self.state(node)
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError("only live recursive leaf may complete")
        if reservation["reservation_id"] != parent["reservation_id"]:
            raise LightwalkerEconomyError("recursive completion reservation mismatch")
        if executor.particular() != parent["executor_particular"]:
            raise LightwalkerEconomyError("recursive completion executor mismatch")
        cut = _nni(observed_cut, "observed_cut")
        gate = derive_execution_gate(
            promise,
            route_policy,
            bundles,
            reservation,
            reservation,
            supplied_temporal_intersection,
            observed_cut=cut,
            execution_started_at_cut=parent["resumed_at_cut"],
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
        if parent["prior_work_measure"]["quantity"] + parent[
            "remaining_work_measure"
        ]["quantity"] != parent["source_work_measure"]["quantity"]:
            raise LightwalkerEconomyError("recursive completion violates root conservation")
        body = {
            "kind": COMPLETION_KIND,
            "version": COMPLETION_VERSION,
            "authority": "owner-local-recursive-continuation-completion",
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "recursive_node_id": parent["node_id"],
            "root_run_id": parent["root_run_id"],
            "root_checkpoint_id": parent["root_checkpoint_id"],
            "checkpoint_ancestry": parent["checkpoint_ancestry"],
            "ancestry_digest": content_address({
                "continuation_lineage_id": parent["continuation_lineage_id"],
                "checkpoint_ancestry": parent["checkpoint_ancestry"],
            }),
            "hop_count": parent["hop_index"],
            "new_steward_particular": self.steward.particular(),
            "new_reservation_id": reservation["reservation_id"],
            "completed_at_cut": cut,
            "completion_gate_id": gate["execution_gate_id"],
            "source_work_measure": parent["source_work_measure"],
            "ancestor_work_measure": parent["prior_work_measure"],
            "new_work_measure": parent["remaining_work_measure"],
            "total_work_measure": parent["source_work_measure"],
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
                "DEPTH != AUTHORITY",
                "RECURSION != HISTORY COLLAPSE",
                "ROOT MEASURE MUST REMAIN INVARIANT",
                "COMPLETION MUST PROVE THE FULL RESUME ANCESTRY",
            ],
        }
        completion = _signed(
            body,
            id_field="recursive_completion_id",
            signer=self.steward,
            domain=COMPLETION_DOMAIN,
            byte_domain=COMPLETION_BYTES,
        )
        self._write_exclusive(
            self._event_path(parent["node_id"], completion["recursive_completion_id"]),
            completion,
        )
        self._write_state(
            parent["node_id"],
            {
                **state,
                "status": "COMPLETED",
                "recursive_completion_id": completion["recursive_completion_id"],
                "total_progress_percent": 100,
            },
        )
        return completion, execution, finalization


def verify_recursive_completion(
    node: dict[str, Any],
    completion: dict[str, Any],
) -> bool:
    try:
        parent = _normalize_node(node)
        if completion.get("kind") != COMPLETION_KIND:
            return False
        if completion.get("version") != COMPLETION_VERSION:
            return False
        if completion.get("authority") != (
            "owner-local-recursive-continuation-completion"
        ):
            return False
        checks = {
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "recursive_node_id": parent["node_id"],
            "root_run_id": parent["root_run_id"],
            "root_checkpoint_id": parent["root_checkpoint_id"],
            "checkpoint_ancestry": parent["checkpoint_ancestry"],
            "hop_count": parent["hop_index"],
            "new_steward_particular": parent["steward_particular"],
            "new_reservation_id": parent["reservation_id"],
            "source_work_measure": parent["source_work_measure"],
            "ancestor_work_measure": parent["prior_work_measure"],
            "new_work_measure": parent["remaining_work_measure"],
            "total_work_measure": parent["source_work_measure"],
            "total_progress_percent": 100,
            "ancestor_work_reexecuted": False,
            "ancestor_work_double_counted": False,
            "full_ancestry_proven": True,
            "service_complete": True,
            "ownership_transfer": False,
            "settlement_authority": "none",
        }
        if any(completion.get(k) != v for k, v in checks.items()):
            return False
        expected_digest = content_address({
            "continuation_lineage_id": parent["continuation_lineage_id"],
            "checkpoint_ancestry": parent["checkpoint_ancestry"],
        })
        if completion.get("ancestry_digest") != expected_digest:
            return False
        return _verify_signed(
            completion,
            id_field="recursive_completion_id",
            particular_field="new_steward_particular",
            domain=COMPLETION_DOMAIN,
            byte_domain=COMPLETION_BYTES,
        )
    except Exception:
        return False


def derive_recursive_lineage(
    seed_node: dict[str, Any],
    edges: list[dict[str, Any]],
    *,
    completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seed = _normalize_node(seed_node)
    if seed_node.get("kind") != "ghot.lightwalker.continuation-node":
        raise LightwalkerEconomyError("recursive lineage must start from 062 seed")
    current_node = seed_node
    node_ids = [seed["node_id"]]
    reservation_ids = [seed["reservation_id"]]
    handoff_ids: list[str] = []
    checkpoint_ids = list(seed["checkpoint_ancestry"])
    edge_ids: list[str] = []

    for index, edge in enumerate(edges):
        required = {
            "parent_node",
            "checkpoint",
            "stop",
            "reservation",
            "finalization",
            "handoff",
            "child_node",
        }
        if set(edge) != required:
            raise LightwalkerEconomyError("recursive edge bundle is incomplete")
        if _node_id(edge["parent_node"]) != _node_id(current_node):
            raise LightwalkerEconomyError("recursive edge parent is not current leaf")
        if not verify_recursive_handoff(
            edge["parent_node"],
            edge["checkpoint"],
            edge["stop"],
            edge["reservation"],
            edge["finalization"],
            {
                "reservation_id": _normalize_node(edge["child_node"])[
                    "reservation_id"
                ],
                "guild_id": _normalize_node(edge["child_node"])[
                    "new_guild_id"
                ] if "new_guild_id" in _normalize_node(edge["child_node"]) else edge["handoff"]["next_guild_id"],
                "steward_particular": _normalize_node(edge["child_node"])[
                    "steward_particular"
                ],
                "reserved_measure": _normalize_node(edge["child_node"])[
                    "remaining_work_measure"
                ],
            },
            edge["handoff"],
        ):
            raise LightwalkerEconomyError("recursive edge handoff does not verify")
        child = _normalize_node(edge["child_node"])
        parent = _normalize_node(edge["parent_node"])
        if child["hop_index"] != parent["hop_index"] + 1:
            raise LightwalkerEconomyError("recursive edge hop does not increment")
        expected_ancestry = parent["checkpoint_ancestry"] + [
            edge["checkpoint"]["recursive_checkpoint_id"]
        ]
        if child["checkpoint_ancestry"] != expected_ancestry:
            raise LightwalkerEconomyError("recursive ancestry prefix mismatch")
        if child["source_work_measure"] != seed["source_work_measure"]:
            raise LightwalkerEconomyError("root measure changed across recursion")
        if edge["handoff"]["recursive_handoff_id"] != edge["child_node"][
            "parent_handoff_id"
        ]:
            raise LightwalkerEconomyError("child does not name parent handoff")
        node_ids.append(child["node_id"])
        reservation_ids.append(child["reservation_id"])
        handoff_ids.append(edge["handoff"]["recursive_handoff_id"])
        checkpoint_ids.append(edge["checkpoint"]["recursive_checkpoint_id"])
        edge_ids.append(content_address({
            "parent_node_id": parent["node_id"],
            "checkpoint_id": edge["checkpoint"]["recursive_checkpoint_id"],
            "handoff_id": edge["handoff"]["recursive_handoff_id"],
            "child_node_id": child["node_id"],
        }))
        current_node = edge["child_node"]

    current = _normalize_node(current_node)
    if len(set(reservation_ids)) != len(reservation_ids):
        raise LightwalkerEconomyError("recursive resource authority was reused")
    if completion is None:
        status = "ACTIVE"
        live_leaf_ids = [current["node_id"]]
        terminal_leaf_id = None
    else:
        if not verify_recursive_completion(current_node, completion):
            raise LightwalkerEconomyError("recursive terminal completion invalid")
        status = "COMPLETED"
        live_leaf_ids = []
        terminal_leaf_id = completion["recursive_completion_id"]

    body = {
        "kind": VIEW_KIND,
        "version": VIEW_VERSION,
        "authority": "derived-recursive-continuation-observation",
        "continuation_lineage_id": seed["continuation_lineage_id"],
        "root_run_id": seed["root_run_id"],
        "root_checkpoint_id": seed["root_checkpoint_id"],
        "root_source_work_measure": seed["source_work_measure"],
        "seed_node_id": seed["node_id"],
        "recursive_depth": current["hop_index"],
        "node_ids": node_ids,
        "edge_ids": edge_ids,
        "handoff_ids": handoff_ids,
        "checkpoint_ancestry": current["checkpoint_ancestry"],
        "checkpoint_ids_observed": checkpoint_ids,
        "resource_reservation_ids": reservation_ids,
        "resource_reservations_distinct": True,
        "status": status,
        "live_leaf_ids": live_leaf_ids,
        "live_leaf_count": len(live_leaf_ids),
        "terminal_leaf_id": terminal_leaf_id,
        "tip_node_id": current["node_id"],
        "tip_prior_progress_percent": current["prior_progress_percent"],
        "tip_prior_work_measure": current["prior_work_measure"],
        "tip_remaining_work_measure": current["remaining_work_measure"],
        "ancestry_digest": content_address({
            "continuation_lineage_id": seed["continuation_lineage_id"],
            "checkpoint_ancestry": current["checkpoint_ancestry"],
        }),
        "global_consensus": False,
        "execution_authority": "none",
        "history_collapsed": False,
        "laws": [
            "DEPTH != AUTHORITY",
            "RECURSION != HISTORY COLLAPSE",
            "EACH EDGE MUST PROVE ITS PARENT",
            "ROOT MEASURE MUST REMAIN INVARIANT",
            "ONLY ONE LIVE LEAF PER ACCEPTED BRANCH",
        ],
    }
    return {**body, "recursive_view_id": content_address(body)}


def compact_recursive_lineage(view: dict[str, Any]) -> dict[str, Any]:
    if view.get("kind") != VIEW_KIND or view.get("version") != VIEW_VERSION:
        raise LightwalkerEconomyError("invalid recursive lineage view")
    body = {
        "kind": COMPACT_KIND,
        "version": COMPACT_VERSION,
        "authority": "derived-compact-lineage-proof-only",
        "recursive_view_id": view["recursive_view_id"],
        "continuation_lineage_id": view["continuation_lineage_id"],
        "root_run_id": view["root_run_id"],
        "root_checkpoint_id": view["root_checkpoint_id"],
        "root_source_work_measure": view["root_source_work_measure"],
        "recursive_depth": view["recursive_depth"],
        "tip_node_id": view["tip_node_id"],
        "status": view["status"],
        "ancestry_count": len(view["checkpoint_ancestry"]),
        "ancestry_digest": view["ancestry_digest"],
        "resource_reservation_count": len(view["resource_reservation_ids"]),
        "history_erased": False,
        "execution_authority": "none",
        "settlement_authority": "none",
        "sufficient_for_new_resume": False,
        "laws": [
            "COMPACTION MAY SHORTEN PROOF TRANSPORT WITHOUT ERASING ANCESTRY",
            "COMPACT PROOF != EXECUTION AUTHORITY",
            "RECURSION != HISTORY COLLAPSE",
        ],
    }
    return {**body, "compact_lineage_id": content_address(body)}


__all__ = [
    "RecursiveContinuationStore",
    "compact_recursive_lineage",
    "derive_recursive_lineage",
    "verify_recursive_checkpoint",
    "verify_recursive_completion",
    "verify_recursive_handoff",
    "verify_recursive_node",
    "verify_recursive_stop",
]
