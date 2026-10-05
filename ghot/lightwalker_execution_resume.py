#!/usr/bin/env python3
"""Lightwalker Resume / Migration of Paused Execution 001.

A stopped partial execution may seed a new owner-local resumed run on distinct
capacity. The checkpoint carries partial state and lineage, never execution
authority. The new resource owner must independently hold current reservation
authority and pass a fresh execution gate.

Core laws:
    RESUME != RESTART
    PARTIAL STATE != EXECUTION AUTHORITY
    MIGRATED CONTINUATION != OWNERSHIP TRANSFER
    OLD RUN != NEW RESOURCE AUTHORITY
    CHECKPOINT LINEAGE MUST SURVIVE MIGRATION
    RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK
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
from lightwalker_long_running_execution import (
    verify_execution_checkpoint,
)
from lightwalker_transition_execution_gate import derive_execution_gate
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


RESUME_KIND = "ghot.lightwalker.execution-resume"
RESUME_VERSION = "0"
RESUME_CHECKPOINT_KIND = "ghot.lightwalker.resumed-execution-checkpoint"
RESUME_CHECKPOINT_VERSION = "0"
RESUME_COMPLETION_KIND = "ghot.lightwalker.resumed-execution-completion"
RESUME_COMPLETION_VERSION = "0"

RESUME_DOMAIN = "ghot.lightwalker-execution-resume-signature/v0"
RESUME_CHECKPOINT_DOMAIN = (
    "ghot.lightwalker-resumed-execution-checkpoint-signature/v0"
)
RESUME_COMPLETION_DOMAIN = (
    "ghot.lightwalker-resumed-execution-completion-signature/v0"
)

RESUME_BYTES = b"GHOT-LightwalkerExecutionResume-v0|"
RESUME_CHECKPOINT_BYTES = b"GHOT-LightwalkerResumedExecutionCheckpoint-v0|"
RESUME_COMPLETION_BYTES = b"GHOT-LightwalkerResumedExecutionCompletion-v0|"


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


def _progress(value: Any, name: str = "progress_percent") -> int:
    number = _nni(value, name)
    if number > 100:
        raise LightwalkerEconomyError(
            f"{name} may not exceed 100"
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


def verify_resume(
    resume: dict[str, Any],
) -> bool:
    try:
        if resume.get("kind") != RESUME_KIND:
            return False
        if resume.get("version") != RESUME_VERSION:
            return False
        if resume.get("prior_progress_percent", -1) >= 100:
            return False
        if resume.get("remaining_work_percent") != (
            100 - int(resume["prior_progress_percent"])
        ):
            return False
        if resume.get("checkpoint_state_authority") != "none":
            return False
        if resume.get("ownership_transfer") is not False:
            return False
        if resume.get("old_run_rewritten") is not False:
            return False
        return _verify_signed(
            resume,
            id_field="resume_id",
            particular_field="new_steward_particular",
            domain=RESUME_DOMAIN,
            byte_domain=RESUME_BYTES,
        )
    except Exception:
        return False


class ResumedExecutionStore:
    """Owner-local durable resumed execution over a distinct reservation."""

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
        self.events_dir = root / "resumed-execution" / "events"
        self.state_dir = root / "resumed-execution" / "state"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _event_path(
        self,
        resume_id: str,
        event_id: str,
    ) -> Path:
        return (
            self.events_dir
            / self._safe(resume_id)
            / f"{self._safe(event_id)}.json"
        )

    def _state_path(self, resume_id: str) -> Path:
        return self.state_dir / f"{self._safe(resume_id)}.json"

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
                    json.dumps(value, indent=2, sort_keys=True)
                    + "\n"
                ).encode("utf-8"),
            )
        finally:
            os.close(fd)

    def _write_state(
        self,
        resume_id: str,
        state: dict[str, Any],
    ) -> None:
        path = self._state_path(resume_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)

    def state(self, resume_id: str) -> dict[str, Any]:
        path = self._state_path(resume_id)
        if not path.exists():
            raise LightwalkerEconomyError(
                "resumed execution state not found"
            )
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError(
                "invalid resumed execution state"
            )
        return value

    def resume(
        self,
        *,
        old_run: dict[str, Any],
        old_checkpoint: dict[str, Any],
        old_pause: dict[str, Any],
        old_stop: dict[str, Any],
        old_authorization: dict[str, Any],
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
        revalidation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not verify_execution_checkpoint(
            old_run, old_checkpoint
        ):
            raise LightwalkerEconomyError(
                "invalid source checkpoint"
            )
        if old_pause.get("run_id") != old_run["run_id"]:
            raise LightwalkerEconomyError(
                "pause belongs to another run"
            )
        if old_pause.get("last_checkpoint_id") != (
            old_checkpoint["checkpoint_id"]
        ):
            raise LightwalkerEconomyError(
                "pause does not preserve source checkpoint"
            )
        if old_stop.get("run_id") != old_run["run_id"]:
            raise LightwalkerEconomyError(
                "stop belongs to another run"
            )
        if old_stop.get("last_checkpoint_id") != (
            old_checkpoint["checkpoint_id"]
        ):
            raise LightwalkerEconomyError(
                "stop does not preserve source checkpoint"
            )
        if old_stop.get("reservation_status") != "RELEASED":
            raise LightwalkerEconomyError(
                "old reservation must be released before resume"
            )
        if old_stop.get("service_complete") is not False:
            raise LightwalkerEconomyError(
                "completed execution does not require resume"
            )
        if old_authorization.get("authorization_id") != (
            old_run["authorization_id"]
        ):
            raise LightwalkerEconomyError(
                "old authorization does not match source run"
            )
        if not verify_reservation(
            new_snapshot,
            new_proposal,
            new_authorization,
            new_reservation,
        ):
            raise LightwalkerEconomyError(
                "invalid new reservation"
            )
        if new_reservation["reservation_id"] == old_run["reservation_id"]:
            raise LightwalkerEconomyError(
                "resume requires distinct resource authority"
            )
        if self.steward.particular() != (
            new_reservation["steward_particular"]
        ):
            raise LightwalkerEconomyError(
                "resume store is not new reservation owner"
            )
        if executor.particular() != new_authorization[
            "executor_particular"
        ]:
            raise LightwalkerEconomyError(
                "resume executor does not match new authorization"
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
            revalidation_context=revalidation_context,
            migration_context=None,
        )
        prior = _progress(
            old_checkpoint["progress_percent"],
            "prior_progress_percent",
        )
        if prior >= 100:
            raise LightwalkerEconomyError(
                "completed checkpoint cannot be resumed"
            )
        source_measure = old_authorization.get("authorized_measure")
        new_measure = new_authorization.get("authorized_measure")
        if not isinstance(source_measure, dict) or not isinstance(
            new_measure, dict
        ):
            raise LightwalkerEconomyError(
                "resume requires native authorization measures"
            )
        if source_measure.get("unit") != new_measure.get("unit"):
            raise LightwalkerEconomyError(
                "resume authority unit mismatch"
            )
        source_quantity = _nni(
            source_measure.get("quantity"),
            "source_authorized_quantity",
        )
        completed_numerator = source_quantity * prior
        if completed_numerator % 100 != 0:
            raise LightwalkerEconomyError(
                "source measure cannot represent checkpoint progress exactly"
            )
        prior_quantity = completed_numerator // 100
        remaining_quantity = source_quantity - prior_quantity
        if int(new_measure.get("quantity", -1)) != remaining_quantity:
            raise LightwalkerEconomyError(
                "new reservation must equal exact remaining work measure"
            )

        body = {
            "kind": RESUME_KIND,
            "version": RESUME_VERSION,
            "authority": "owner-local-resumed-execution",
            "old_run_id": old_run["run_id"],
            "old_reservation_id": old_run["reservation_id"],
            "source_checkpoint_id": old_checkpoint["checkpoint_id"],
            "source_pause_id": old_pause["pause_id"],
            "source_stop_id": old_stop["stop_id"],
            "source_partial_result_ref": old_checkpoint[
                "partial_result_ref"
            ],
            "prior_progress_percent": prior,
            "remaining_work_percent": 100 - prior,
            "source_work_measure": {
                "unit": source_measure["unit"],
                "quantity": source_quantity,
            },
            "prior_work_measure": {
                "unit": source_measure["unit"],
                "quantity": prior_quantity,
            },
            "remaining_work_measure": {
                "unit": source_measure["unit"],
                "quantity": remaining_quantity,
            },
            "new_guild_id": new_reservation["guild_id"],
            "new_reservation_id": new_reservation["reservation_id"],
            "new_authorization_id": new_reservation[
                "authorization_id"
            ],
            "new_steward_particular": self.steward.particular(),
            "new_executor_particular": executor.particular(),
            "resumed_at_cut": cut,
            "resume_execution_gate_id": gate["execution_gate_id"],
            "resume_evidence_path": gate["evidence_path"],
            "status": "RUNNING",
            "total_progress_percent": prior,
            "new_work_progress_percent": 0,
            "last_resumed_checkpoint_id": None,
            "resumed_checkpoint_count": 0,
            "checkpoint_state_authority": "none",
            "ownership_transfer": False,
            "old_run_rewritten": False,
            "service_complete": False,
            "settlement_authority": "none",
            "laws": [
                "RESUME != RESTART",
                "PARTIAL STATE != EXECUTION AUTHORITY",
                "MIGRATED CONTINUATION != OWNERSHIP TRANSFER",
                "OLD RUN != NEW RESOURCE AUTHORITY",
                "CHECKPOINT LINEAGE MUST SURVIVE MIGRATION",
                "RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK",
            ],
        }
        resume = _signed(
            body,
            id_field="resume_id",
            signer=self.steward,
            domain=RESUME_DOMAIN,
            byte_domain=RESUME_BYTES,
        )
        self._write_exclusive(
            self._event_path(
                resume["resume_id"],
                resume["resume_id"],
            ),
            resume,
        )
        self._write_state(
            resume["resume_id"],
            {
                "resume_id": resume["resume_id"],
                "status": "RUNNING",
                "prior_progress_percent": prior,
                "remaining_work_percent": 100 - prior,
                "source_work_measure": body["source_work_measure"],
                "prior_work_measure": body["prior_work_measure"],
                "remaining_work_measure": body["remaining_work_measure"],
                "new_work_progress_percent": 0,
                "total_progress_percent": prior,
                "resumed_checkpoint_count": 0,
                "last_resumed_checkpoint_id": None,
                "source_checkpoint_id": old_checkpoint[
                    "checkpoint_id"
                ],
                "source_partial_result_ref": old_checkpoint[
                    "partial_result_ref"
                ],
                "new_reservation_id": new_reservation[
                    "reservation_id"
                ],
                "resumed_at_cut": cut,
            },
        )
        return resume

    def checkpoint(
        self,
        resume: dict[str, Any],
        *,
        executor: IdentityKey,
        observed_cut: int,
        total_progress_percent: int,
        partial_result_ref: str,
    ) -> dict[str, Any]:
        if not verify_resume(resume):
            raise LightwalkerEconomyError(
                "invalid resume record"
            )
        state = self.state(resume["resume_id"])
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError(
                "only running resumed execution may checkpoint"
            )
        if executor.particular() != resume[
            "new_executor_particular"
        ]:
            raise LightwalkerEconomyError(
                "resumed checkpoint executor mismatch"
            )
        total = _progress(
            total_progress_percent,
            "total_progress_percent",
        )
        prior = int(state["prior_progress_percent"])
        if total <= int(state["total_progress_percent"]):
            raise LightwalkerEconomyError(
                "resumed checkpoint must advance total progress"
            )
        if total >= 100:
            raise LightwalkerEconomyError(
                "use complete() for 100 percent"
            )
        new_work = total - prior
        if new_work <= 0:
            raise LightwalkerEconomyError(
                "resumed checkpoint double-counts prior work"
            )
        if new_work > int(state["remaining_work_percent"]):
            raise LightwalkerEconomyError(
                "resumed checkpoint exceeds remaining work"
            )

        body = {
            "kind": RESUME_CHECKPOINT_KIND,
            "version": RESUME_CHECKPOINT_VERSION,
            "authority": "owner-local-resumed-checkpoint",
            "resume_id": resume["resume_id"],
            "old_run_id": resume["old_run_id"],
            "source_checkpoint_id": resume["source_checkpoint_id"],
            "source_partial_result_ref": resume[
                "source_partial_result_ref"
            ],
            "new_reservation_id": resume["new_reservation_id"],
            "new_steward_particular": self.steward.particular(),
            "new_executor_particular": executor.particular(),
            "checkpoint_index": int(
                state["resumed_checkpoint_count"]
            ) + 1,
            "previous_resumed_checkpoint_id": state[
                "last_resumed_checkpoint_id"
            ],
            "checkpoint_at_cut": _nni(
                observed_cut, "observed_cut"
            ),
            "prior_progress_percent": prior,
            "new_work_progress_percent": new_work,
            "total_progress_percent": total,
            "partial_result_ref": _nonempty(
                partial_result_ref,
                "partial_result_ref",
            ),
            "service_complete": False,
            "settlement_authority": "none",
            "prior_work_reexecuted": False,
            "laws": [
                "RESUME != RESTART",
                "CHECKPOINT LINEAGE MUST SURVIVE MIGRATION",
                "RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK",
            ],
        }
        checkpoint = _signed(
            body,
            id_field="resumed_checkpoint_id",
            signer=self.steward,
            domain=RESUME_CHECKPOINT_DOMAIN,
            byte_domain=RESUME_CHECKPOINT_BYTES,
        )
        self._write_exclusive(
            self._event_path(
                resume["resume_id"],
                checkpoint["resumed_checkpoint_id"],
            ),
            checkpoint,
        )
        self._write_state(
            resume["resume_id"],
            {
                **state,
                "total_progress_percent": total,
                "new_work_progress_percent": new_work,
                "resumed_checkpoint_count": body[
                    "checkpoint_index"
                ],
                "last_resumed_checkpoint_id": checkpoint[
                    "resumed_checkpoint_id"
                ],
                "partial_result_ref": body["partial_result_ref"],
            },
        )
        return checkpoint

    def complete(
        self,
        resume: dict[str, Any],
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        *,
        executor: IdentityKey,
        observed_cut: int,
        result_ref: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        if not verify_resume(resume):
            raise LightwalkerEconomyError(
                "invalid resume record"
            )
        state = self.state(resume["resume_id"])
        if state["status"] != "RUNNING":
            raise LightwalkerEconomyError(
                "only running resumed execution may complete"
            )
        if reservation["reservation_id"] != resume[
            "new_reservation_id"
        ]:
            raise LightwalkerEconomyError(
                "completion reservation mismatch"
            )
        if executor.particular() != resume[
            "new_executor_particular"
        ]:
            raise LightwalkerEconomyError(
                "completion executor mismatch"
            )
        prior = int(state["prior_progress_percent"])
        remaining = int(state["remaining_work_percent"])
        if prior + remaining != 100:
            raise LightwalkerEconomyError(
                "resume accounting does not conserve total work"
            )
        if int(state["new_work_progress_percent"]) > remaining:
            raise LightwalkerEconomyError(
                "new work already exceeds remaining work"
            )

        execution, finalization = (
            self.reservation_store.execute_reserved(
                snapshot,
                proposal,
                authorization,
                reservation,
                executor=executor,
                observed_cut=_nni(
                    observed_cut, "observed_cut"
                ),
                simulate_success=True,
                result_ref=_nonempty(
                    result_ref, "result_ref"
                ),
            )
        )
        body = {
            "kind": RESUME_COMPLETION_KIND,
            "version": RESUME_COMPLETION_VERSION,
            "authority": "owner-local-resumed-completion",
            "resume_id": resume["resume_id"],
            "old_run_id": resume["old_run_id"],
            "source_checkpoint_id": resume["source_checkpoint_id"],
            "source_partial_result_ref": resume[
                "source_partial_result_ref"
            ],
            "new_reservation_id": reservation[
                "reservation_id"
            ],
            "new_steward_particular": self.steward.particular(),
            "new_executor_particular": executor.particular(),
            "completed_at_cut": _nni(
                observed_cut, "observed_cut"
            ),
            "prior_progress_percent": prior,
            "remaining_work_percent": remaining,
            "new_work_counted_percent": remaining,
            "source_work_measure": state["source_work_measure"],
            "prior_work_measure": state["prior_work_measure"],
            "new_work_counted_measure": state["remaining_work_measure"],
            "total_progress_percent": 100,
            "result_ref": result_ref,
            "execution_receipt_id": execution["execution_receipt_id"],
            "reservation_finalization_id": finalization[
                "finalization_id"
            ],
            "reservation_status": finalization["status"],
            "prior_work_reexecuted": False,
            "prior_work_double_counted": False,
            "service_complete": True,
            "settlement_authority": "none",
            "ownership_transfer": False,
            "old_run_rewritten": False,
            "laws": [
                "RESUME != RESTART",
                "MIGRATED CONTINUATION != OWNERSHIP TRANSFER",
                "OLD RUN != NEW RESOURCE AUTHORITY",
                "CHECKPOINT LINEAGE MUST SURVIVE MIGRATION",
                "RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK",
            ],
        }
        completion = _signed(
            body,
            id_field="resumed_completion_id",
            signer=self.steward,
            domain=RESUME_COMPLETION_DOMAIN,
            byte_domain=RESUME_COMPLETION_BYTES,
        )
        self._write_exclusive(
            self._event_path(
                resume["resume_id"],
                completion["resumed_completion_id"],
            ),
            completion,
        )
        self._write_state(
            resume["resume_id"],
            {
                **state,
                "status": "COMPLETED",
                "new_work_progress_percent": remaining,
                "total_progress_percent": 100,
                "resumed_completion_id": completion[
                    "resumed_completion_id"
                ],
                "result_ref": result_ref,
                "reservation_finalization_id": finalization[
                    "finalization_id"
                ],
            },
        )
        return completion, execution, finalization


__all__ = [
    "ResumedExecutionStore",
    "verify_resume",
]
