#!/usr/bin/env python3
"""Lightwalker Long-Running Execution / Checkpoint Revalidation 001.

A valid start gate does not create perpetual continuation authority. Long-running
work emits owner-local checkpoints. Selected continuation boundaries must
recompute current temporal policy evidence before more work may be recorded.

Core laws:
    START AUTHORITY != CONTINUATION AUTHORITY
    CHECKPOINT REVALIDATION != REEXECUTION
    PAUSE != FAILURE
    STOP != HISTORY REWRITE
    PARTIAL RESULT != SETTLEMENT
    CONTINUATION MUST REMAIN OWNER-LOCAL
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
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_reservation,
)
from lightwalker_transition_execution_gate import derive_execution_gate
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


RUN_KIND = "ghot.lightwalker.long-running-execution"
RUN_VERSION = "0"
CHECKPOINT_KIND = "ghot.lightwalker.execution-checkpoint"
CHECKPOINT_VERSION = "0"
PAUSE_KIND = "ghot.lightwalker.execution-pause"
PAUSE_VERSION = "0"
STOP_KIND = "ghot.lightwalker.execution-stop"
STOP_VERSION = "0"

RUN_DOMAIN = "ghot.lightwalker-long-running-execution-signature/v0"
CHECKPOINT_DOMAIN = "ghot.lightwalker-execution-checkpoint-signature/v0"
PAUSE_DOMAIN = "ghot.lightwalker-execution-pause-signature/v0"
STOP_DOMAIN = "ghot.lightwalker-execution-stop-signature/v0"

RUN_BYTES = b"GHOT-LightwalkerLongRunningExecution-v0|"
CHECKPOINT_BYTES = b"GHOT-LightwalkerExecutionCheckpoint-v0|"
PAUSE_BYTES = b"GHOT-LightwalkerExecutionPause-v0|"
STOP_BYTES = b"GHOT-LightwalkerExecutionStop-v0|"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(
            f"{name} must be a non-empty string"
        )
    return value


def _nni(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(
            f"{name} must be a non-negative integer"
        )
    return value


def _progress(value: Any) -> int:
    number = _nni(value, "progress_percent")
    if number > 100:
        raise LightwalkerEconomyError(
            "progress_percent may not exceed 100"
        )
    return number


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
        byte_domain
        + canonical_bytes({id_field: item_id, **body})
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
        if particular_for_public_key(public_key) != value.get(
            particular_field
        ):
            return False
        body = {
            key: item
            for key, item in value.items()
            if key not in {id_field, "signing"}
        }
        item_id = value.get(id_field)
        if not isinstance(item_id, str):
            return False
        if content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            byte_domain
            + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def verify_execution_checkpoint(
    run: dict[str, Any],
    checkpoint: dict[str, Any],
) -> bool:
    try:
        if checkpoint.get("kind") != CHECKPOINT_KIND:
            return False
        if checkpoint.get("version") != CHECKPOINT_VERSION:
            return False
        if checkpoint.get("run_id") != run["run_id"]:
            return False
        if checkpoint.get("reservation_id") != run["reservation_id"]:
            return False
        if checkpoint.get("steward_particular") != (
            run["steward_particular"]
        ):
            return False
        if checkpoint.get("executor_particular") != (
            run["executor_particular"]
        ):
            return False
        if checkpoint.get("service_complete") is not False:
            return False
        if checkpoint.get("settlement_authority") != "none":
            return False
        return _verify_signed(
            checkpoint,
            id_field="checkpoint_id",
            particular_field="steward_particular",
            domain=CHECKPOINT_DOMAIN,
            byte_domain=CHECKPOINT_BYTES,
        )
    except Exception:
        return False


class LongRunningExecutionStore:
    """Owner-local durable event log for a reserved long-running execution."""

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
        self.events_dir = root / "long-running" / "events"
        self.state_dir = root / "long-running" / "state"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _event_path(
        self,
        run_id: str,
        event_id: str,
    ) -> Path:
        return (
            self.events_dir
            / self._safe(run_id)
            / f"{self._safe(event_id)}.json"
        )

    def _state_path(self, run_id: str) -> Path:
        return self.state_dir / f"{self._safe(run_id)}.json"

    def _write_exclusive(
        self,
        path: Path,
        value: dict[str, Any],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.write(
                fd,
                (
                    json.dumps(
                        value,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8"),
            )
        finally:
            os.close(fd)

    def _write_state(
        self,
        run_id: str,
        state: dict[str, Any],
    ) -> None:
        path = self._state_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def state(self, run_id: str) -> dict[str, Any]:
        path = self._state_path(run_id)
        if not path.exists():
            raise LightwalkerEconomyError(
                "long-running execution state not found"
            )
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError(
                "invalid long-running execution state"
            )
        return value

    def start(
        self,
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
        revalidation_context: dict[str, Any] | None = None,
        migration_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not verify_reservation(
            snapshot,
            proposal,
            authorization,
            reservation,
        ):
            raise LightwalkerEconomyError(
                "invalid reservation for long-running start"
            )
        if self.steward.particular() != (
            reservation["steward_particular"]
        ):
            raise LightwalkerEconomyError(
                "continuation store is not reservation owner"
            )
        if executor.particular() != authorization[
            "executor_particular"
        ]:
            raise LightwalkerEconomyError(
                "start executor does not match authorization"
            )
        cut = _nni(observed_cut, "observed_cut")
        gate = derive_execution_gate(
            promise,
            route_policy,
            bundles,
            reservation,
            reservation,
            supplied_temporal_intersection,
            observed_cut=cut,
            execution_started_at_cut=None,
            revalidation_context=revalidation_context,
            migration_context=migration_context,
        )
        body = {
            "kind": RUN_KIND,
            "version": RUN_VERSION,
            "authority": "owner-local-long-running-execution",
            "guild_id": reservation["guild_id"],
            "reservation_id": reservation["reservation_id"],
            "authorization_id": reservation["authorization_id"],
            "steward_particular": self.steward.particular(),
            "executor_particular": executor.particular(),
            "started_at_cut": cut,
            "start_execution_gate_id": gate["execution_gate_id"],
            "start_evidence_path": gate["evidence_path"],
            "status": "RUNNING",
            "progress_percent": 0,
            "last_checkpoint_id": None,
            "checkpoint_count": 0,
            "partial_result_ref": None,
            "service_complete": False,
            "settlement_authority": "none",
            "laws": [
                "START AUTHORITY != CONTINUATION AUTHORITY",
                "CHECKPOINT REVALIDATION != REEXECUTION",
                "PARTIAL RESULT != SETTLEMENT",
                "CONTINUATION MUST REMAIN OWNER-LOCAL",
            ],
        }
        run = _signed(
            body,
            id_field="run_id",
            signer=self.steward,
            domain=RUN_DOMAIN,
            byte_domain=RUN_BYTES,
        )
        self._write_exclusive(
            self._event_path(run["run_id"], run["run_id"]),
            run,
        )
        self._write_state(
            run["run_id"],
            {
                "run_id": run["run_id"],
                "status": "RUNNING",
                "progress_percent": 0,
                "checkpoint_count": 0,
                "last_checkpoint_id": None,
                "partial_result_ref": None,
                "reservation_id": reservation["reservation_id"],
                "started_at_cut": cut,
            },
        )
        return run

    def checkpoint(
        self,
        run: dict[str, Any],
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
        progress_percent: int,
        partial_result_ref: str,
        revalidation_context: dict[str, Any] | None = None,
        migration_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.state(run["run_id"])
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError(
                "only a running execution may checkpoint"
            )
        if reservation["reservation_id"] != state["reservation_id"]:
            raise LightwalkerEconomyError(
                "checkpoint reservation mismatch"
            )
        if executor.particular() != run["executor_particular"]:
            raise LightwalkerEconomyError(
                "checkpoint executor mismatch"
            )
        progress = _progress(progress_percent)
        if progress <= int(state["progress_percent"]):
            raise LightwalkerEconomyError(
                "checkpoint progress must advance"
            )
        cut = _nni(observed_cut, "observed_cut")
        if cut < int(run["started_at_cut"]):
            raise LightwalkerEconomyError(
                "checkpoint precedes execution start"
            )

        gate = derive_execution_gate(
            promise,
            route_policy,
            bundles,
            reservation,
            reservation,
            supplied_temporal_intersection,
            observed_cut=cut,
            execution_started_at_cut=int(run["started_at_cut"]),
            revalidation_context=revalidation_context,
            migration_context=migration_context,
        )

        body = {
            "kind": CHECKPOINT_KIND,
            "version": CHECKPOINT_VERSION,
            "authority": "owner-local-continuation-checkpoint",
            "run_id": run["run_id"],
            "guild_id": run["guild_id"],
            "reservation_id": reservation["reservation_id"],
            "steward_particular": self.steward.particular(),
            "executor_particular": executor.particular(),
            "checkpoint_index": int(state["checkpoint_count"]) + 1,
            "previous_checkpoint_id": state["last_checkpoint_id"],
            "checkpoint_at_cut": cut,
            "progress_percent": progress,
            "partial_result_ref": _nonempty(
                partial_result_ref,
                "partial_result_ref",
            ),
            "continuation_gate_id": gate["execution_gate_id"],
            "continuation_evidence_path": gate["evidence_path"],
            "service_complete": False,
            "settlement_authority": "none",
            "underlying_execution_attempted": False,
            "laws": [
                "START AUTHORITY != CONTINUATION AUTHORITY",
                "CHECKPOINT REVALIDATION != REEXECUTION",
                "PARTIAL RESULT != SETTLEMENT",
                "CONTINUATION MUST REMAIN OWNER-LOCAL",
            ],
        }
        checkpoint = _signed(
            body,
            id_field="checkpoint_id",
            signer=self.steward,
            domain=CHECKPOINT_DOMAIN,
            byte_domain=CHECKPOINT_BYTES,
        )
        self._write_exclusive(
            self._event_path(
                run["run_id"],
                checkpoint["checkpoint_id"],
            ),
            checkpoint,
        )
        self._write_state(
            run["run_id"],
            {
                **state,
                "status": "RUNNING",
                "progress_percent": progress,
                "checkpoint_count": body["checkpoint_index"],
                "last_checkpoint_id": checkpoint["checkpoint_id"],
                "partial_result_ref": body["partial_result_ref"],
                "last_checkpoint_cut": cut,
            },
        )
        return checkpoint

    def pause(
        self,
        run: dict[str, Any],
        *,
        observed_cut: int,
        reason: str,
    ) -> dict[str, Any]:
        state = self.state(run["run_id"])
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError(
                "only a running execution may pause"
            )
        cut = _nni(observed_cut, "observed_cut")
        body = {
            "kind": PAUSE_KIND,
            "version": PAUSE_VERSION,
            "authority": "owner-local-execution-pause",
            "run_id": run["run_id"],
            "reservation_id": state["reservation_id"],
            "steward_particular": self.steward.particular(),
            "paused_at_cut": cut,
            "reason": _nonempty(reason, "reason"),
            "progress_percent": state["progress_percent"],
            "last_checkpoint_id": state["last_checkpoint_id"],
            "partial_result_ref": state["partial_result_ref"],
            "failure": False,
            "service_complete": False,
            "reservation_released": False,
            "history_rewritten": False,
            "settlement_authority": "none",
            "laws": [
                "PAUSE != FAILURE",
                "PARTIAL RESULT != SETTLEMENT",
                "STOP != HISTORY REWRITE",
            ],
        }
        pause = _signed(
            body,
            id_field="pause_id",
            signer=self.steward,
            domain=PAUSE_DOMAIN,
            byte_domain=PAUSE_BYTES,
        )
        self._write_exclusive(
            self._event_path(
                run["run_id"],
                pause["pause_id"],
            ),
            pause,
        )
        self._write_state(
            run["run_id"],
            {
                **state,
                "status": "PAUSED",
                "paused_at_cut": cut,
                "pause_id": pause["pause_id"],
            },
        )
        return pause

    def stop(
        self,
        run: dict[str, Any],
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        *,
        observed_cut: int,
        reason: str,
    ) -> dict[str, Any]:
        state = self.state(run["run_id"])
        if state["status"] not in {"RUNNING", "PAUSED"}:
            raise LightwalkerEconomyError(
                "execution is not stoppable"
            )
        cut = _nni(observed_cut, "observed_cut")
        progress = int(state["progress_percent"])
        reserved_measure = authorization["authorized_measure"]
        reserved_q = int(reserved_measure["quantity"])
        if progress > 0:
            numerator = reserved_q * progress
            if numerator % 100 != 0:
                raise LightwalkerEconomyError(
                    "checkpoint progress cannot be represented in reserved measure"
                )
            consumed_q = numerator // 100
            if consumed_q >= reserved_q:
                raise LightwalkerEconomyError(
                    "partial stop cannot represent full completion"
                )
            finalization = self.reservation_store.partially_consume_and_release(
                snapshot,
                proposal,
                authorization,
                reservation,
                consumed_quantity=consumed_q,
                partial_evidence_ref=_nonempty(
                    state["last_checkpoint_id"],
                    "last_checkpoint_id",
                ),
                observed_cut=cut,
                reason=_nonempty(reason, "reason"),
            )
        else:
            finalization = self.reservation_store.release(
                snapshot,
                proposal,
                authorization,
                reservation,
                observed_cut=cut,
                reason=_nonempty(reason, "reason"),
            )
        body = {
            "kind": STOP_KIND,
            "version": STOP_VERSION,
            "authority": "owner-local-execution-stop",
            "run_id": run["run_id"],
            "reservation_id": reservation["reservation_id"],
            "steward_particular": self.steward.particular(),
            "stopped_at_cut": cut,
            "reason": reason,
            "progress_percent": state["progress_percent"],
            "last_checkpoint_id": state["last_checkpoint_id"],
            "partial_result_ref": state["partial_result_ref"],
            "reservation_finalization_id": finalization[
                "finalization_id"
            ],
            "reservation_status": finalization["status"],
            "failure": False,
            "service_complete": False,
            "history_rewritten": False,
            "settlement_authority": "none",
            "laws": [
                "STOP != HISTORY REWRITE",
                "PAUSE != FAILURE",
                "PARTIAL RESULT != SETTLEMENT",
            ],
        }
        stop = _signed(
            body,
            id_field="stop_id",
            signer=self.steward,
            domain=STOP_DOMAIN,
            byte_domain=STOP_BYTES,
        )
        self._write_exclusive(
            self._event_path(
                run["run_id"],
                stop["stop_id"],
            ),
            stop,
        )
        self._write_state(
            run["run_id"],
            {
                **state,
                "status": "STOPPED",
                "stopped_at_cut": cut,
                "stop_id": stop["stop_id"],
                "reservation_finalization_id": finalization[
                    "finalization_id"
                ],
            },
        )
        return stop


__all__ = [
    "LongRunningExecutionStore",
    "verify_execution_checkpoint",
]
