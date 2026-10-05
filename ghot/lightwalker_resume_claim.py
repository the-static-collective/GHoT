#!/usr/bin/env python3
"""Lightwalker Resume Claim / Fork Prevention 001.

A resumable checkpoint may be known by many sovereign providers, but the
checkpoint lineage permits at most one active continuation claim in one
owner-local registry. Competing claims remain history. If disconnected
owner-local replicas later reveal contradictory ACTIVE receipts, execution is
blocked until the checkpoint owner explicitly resolves that exact fork set.

Core laws:
    RESUMABLE STATE != MULTIPLE CONTINUATION AUTHORITY
    ONE CHECKPOINT -> AT MOST ONE ACTIVE RESUME CLAIM
    CLAIM != EXECUTION
    LOSING CLAIM != HISTORY DELETION
    FORK DETECTION != GLOBAL CONSENSUS
    COMPLETION MUST NAME THE WINNING CONTINUATION LINEAGE
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_execution_resume import (
    ResumedExecutionStore,
    verify_resume,
)
from lightwalker_guild_reservation import verify_reservation
from lightwalker_long_running_execution import verify_execution_checkpoint
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


CLAIM_KIND = "ghot.lightwalker.resume-claim"
CLAIM_VERSION = "0"
DECISION_KIND = "ghot.lightwalker.resume-claim-decision"
DECISION_VERSION = "0"
FORK_KIND = "ghot.lightwalker.resume-claim-fork"
FORK_VERSION = "0"
RESOLUTION_KIND = "ghot.lightwalker.resume-claim-resolution"
RESOLUTION_VERSION = "0"
BINDING_KIND = "ghot.lightwalker.claim-bound-resume"
BINDING_VERSION = "0"
COMPLETION_BINDING_KIND = "ghot.lightwalker.claim-bound-resume-completion"
COMPLETION_BINDING_VERSION = "0"

CLAIM_DOMAIN = "ghot.lightwalker-resume-claim-signature/v0"
DECISION_DOMAIN = "ghot.lightwalker-resume-claim-decision-signature/v0"
RESOLUTION_DOMAIN = "ghot.lightwalker-resume-claim-resolution-signature/v0"

CLAIM_BYTES = b"GHOT-LightwalkerResumeClaim-v0|"
DECISION_BYTES = b"GHOT-LightwalkerResumeClaimDecision-v0|"
RESOLUTION_BYTES = b"GHOT-LightwalkerResumeClaimResolution-v0|"


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


def make_resume_claim(
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    old_stop: dict[str, Any],
    new_snapshot: dict[str, Any],
    new_proposal: dict[str, Any],
    new_authorization: dict[str, Any],
    new_reservation: dict[str, Any],
    *,
    claimant: IdentityKey,
    claimed_at_cut: int,
) -> dict[str, Any]:
    if not verify_execution_checkpoint(
        old_run, old_checkpoint
    ):
        raise LightwalkerEconomyError(
            "resume claim requires valid source checkpoint"
        )
    if old_stop.get("run_id") != old_run["run_id"]:
        raise LightwalkerEconomyError(
            "resume claim stop belongs to another run"
        )
    if old_stop.get("last_checkpoint_id") != (
        old_checkpoint["checkpoint_id"]
    ):
        raise LightwalkerEconomyError(
            "resume claim stop does not preserve checkpoint"
        )
    if old_stop.get("reservation_status") not in {"RELEASED", "PARTIALLY_CONSUMED"}:
        raise LightwalkerEconomyError(
            "resume claim requires released source reservation"
        )
    if not verify_reservation(
        new_snapshot,
        new_proposal,
        new_authorization,
        new_reservation,
    ):
        raise LightwalkerEconomyError(
            "resume claim requires valid new reservation"
        )
    if claimant.particular() != new_reservation[
        "steward_particular"
    ]:
        raise LightwalkerEconomyError(
            "resume claimant must own new reservation"
        )
    if new_reservation["reservation_id"] == old_run[
        "reservation_id"
    ]:
        raise LightwalkerEconomyError(
            "resume claim requires distinct new authority"
        )
    cut = _nni(claimed_at_cut, "claimed_at_cut")
    body = {
        "kind": CLAIM_KIND,
        "version": CLAIM_VERSION,
        "authority": "candidate-resume-claim-only",
        "source_run_id": old_run["run_id"],
        "source_reservation_id": old_run["reservation_id"],
        "source_checkpoint_id": old_checkpoint["checkpoint_id"],
        "source_stop_id": old_stop["stop_id"],
        "source_progress_percent": old_checkpoint[
            "progress_percent"
        ],
        "source_partial_result_ref": old_checkpoint[
            "partial_result_ref"
        ],
        "source_steward_particular": old_run[
            "steward_particular"
        ],
        "claimant_particular": claimant.particular(),
        "candidate_guild_id": new_reservation["guild_id"],
        "candidate_reservation_id": new_reservation[
            "reservation_id"
        ],
        "candidate_authorization_id": new_reservation[
            "authorization_id"
        ],
        "candidate_measure": new_authorization[
            "authorized_measure"
        ],
        "claimed_at_cut": cut,
        "execution_authority": "none",
        "ownership_transfer": False,
        "source_history_rewritten": False,
        "laws": [
            "RESUMABLE STATE != MULTIPLE CONTINUATION AUTHORITY",
            "CLAIM != EXECUTION",
            "MIGRATED CONTINUATION != OWNERSHIP TRANSFER",
        ],
    }
    return _signed(
        body,
        id_field="resume_claim_id",
        signer=claimant,
        domain=CLAIM_DOMAIN,
        byte_domain=CLAIM_BYTES,
    )


def verify_resume_claim(
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    old_stop: dict[str, Any],
    new_snapshot: dict[str, Any],
    new_proposal: dict[str, Any],
    new_authorization: dict[str, Any],
    new_reservation: dict[str, Any],
    claim: dict[str, Any],
) -> bool:
    try:
        if claim.get("kind") != CLAIM_KIND:
            return False
        if claim.get("version") != CLAIM_VERSION:
            return False
        if claim.get("authority") != "candidate-resume-claim-only":
            return False
        if not verify_execution_checkpoint(
            old_run, old_checkpoint
        ):
            return False
        if old_stop.get("reservation_status") not in {"RELEASED", "PARTIALLY_CONSUMED"}:
            return False
        if not verify_reservation(
            new_snapshot,
            new_proposal,
            new_authorization,
            new_reservation,
        ):
            return False
        checks = {
            "source_run_id": old_run["run_id"],
            "source_reservation_id": old_run["reservation_id"],
            "source_checkpoint_id": old_checkpoint["checkpoint_id"],
            "source_stop_id": old_stop["stop_id"],
            "source_progress_percent": old_checkpoint[
                "progress_percent"
            ],
            "source_partial_result_ref": old_checkpoint[
                "partial_result_ref"
            ],
            "source_steward_particular": old_run[
                "steward_particular"
            ],
            "claimant_particular": new_reservation[
                "steward_particular"
            ],
            "candidate_guild_id": new_reservation["guild_id"],
            "candidate_reservation_id": new_reservation[
                "reservation_id"
            ],
            "candidate_authorization_id": new_reservation[
                "authorization_id"
            ],
            "candidate_measure": new_authorization[
                "authorized_measure"
            ],
            "execution_authority": "none",
            "ownership_transfer": False,
            "source_history_rewritten": False,
        }
        if any(claim.get(k) != v for k, v in checks.items()):
            return False
        return _verify_signed(
            claim,
            id_field="resume_claim_id",
            particular_field="claimant_particular",
            domain=CLAIM_DOMAIN,
            byte_domain=CLAIM_BYTES,
        )
    except Exception:
        return False


class ResumeClaimRegistry:
    """Checkpoint-owner-local atomic selection of one active resume claim."""

    def __init__(
        self,
        root: Path,
        *,
        source_steward: IdentityKey,
    ) -> None:
        self.root = root
        self.source_steward = source_steward
        self.claims_dir = root / "resume-claims" / "claims"
        self.decisions_dir = root / "resume-claims" / "decisions"
        self.active_dir = root / "resume-claims" / "active"
        self.lock_path = root / "resume-claims" / "registry.lock"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _claim_path(self, claim_id: str) -> Path:
        return self.claims_dir / f"{self._safe(claim_id)}.json"

    def _decision_path(self, decision_id: str) -> Path:
        return self.decisions_dir / f"{self._safe(decision_id)}.json"

    def _active_path(self, checkpoint_id: str) -> Path:
        return self.active_dir / f"{self._safe(checkpoint_id)}.json"

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

    def _read(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError(
                "invalid resume claim registry record"
            )
        return value

    def consider(
        self,
        old_run: dict[str, Any],
        old_checkpoint: dict[str, Any],
        old_stop: dict[str, Any],
        new_snapshot: dict[str, Any],
        new_proposal: dict[str, Any],
        new_authorization: dict[str, Any],
        new_reservation: dict[str, Any],
        claim: dict[str, Any],
        *,
        observed_cut: int,
    ) -> dict[str, Any]:
        if self.source_steward.particular() != old_run[
            "steward_particular"
        ]:
            raise LightwalkerEconomyError(
                "claim registry is not source lineage owner"
            )
        if not verify_resume_claim(
            old_run,
            old_checkpoint,
            old_stop,
            new_snapshot,
            new_proposal,
            new_authorization,
            new_reservation,
            claim,
        ):
            raise LightwalkerEconomyError(
                "invalid resume claim"
            )
        cut = _nni(observed_cut, "observed_cut")
        checkpoint_id = old_checkpoint["checkpoint_id"]

        with self._locked():
            claim_path = self._claim_path(
                claim["resume_claim_id"]
            )
            if not claim_path.exists():
                self._write_exclusive(claim_path, claim)

            active_path = self._active_path(checkpoint_id)
            active = self._read(active_path)
            if active is None:
                status = "ACTIVE"
                active_claim_id = claim["resume_claim_id"]
            elif active.get("resume_claim_id") == claim[
                "resume_claim_id"
            ]:
                return active
            else:
                status = "LOSING"
                active_claim_id = active["resume_claim_id"]

            body = {
                "kind": DECISION_KIND,
                "version": DECISION_VERSION,
                "authority": (
                    "checkpoint-owner-local-resume-claim-decision"
                ),
                "source_run_id": old_run["run_id"],
                "source_checkpoint_id": checkpoint_id,
                "source_stop_id": old_stop["stop_id"],
                "source_steward_particular": (
                    self.source_steward.particular()
                ),
                "resume_claim_id": claim["resume_claim_id"],
                "claimant_particular": claim[
                    "claimant_particular"
                ],
                "candidate_reservation_id": claim[
                    "candidate_reservation_id"
                ],
                "active_resume_claim_id": active_claim_id,
                "observed_cut": cut,
                "status": status,
                "execution_authority": "none",
                "claim_deleted": False,
                "global_consensus": False,
                "laws": [
                    "ONE CHECKPOINT -> AT MOST ONE ACTIVE RESUME CLAIM",
                    "CLAIM != EXECUTION",
                    "LOSING CLAIM != HISTORY DELETION",
                    "FORK DETECTION != GLOBAL CONSENSUS",
                ],
            }
            decision = _signed(
                body,
                id_field="claim_decision_id",
                signer=self.source_steward,
                domain=DECISION_DOMAIN,
                byte_domain=DECISION_BYTES,
            )
            self._write_exclusive(
                self._decision_path(
                    decision["claim_decision_id"]
                ),
                decision,
            )
            if status == "ACTIVE":
                self._write_exclusive(active_path, decision)
            return decision


def verify_claim_decision(
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    old_stop: dict[str, Any],
    claim: dict[str, Any],
    decision: dict[str, Any],
) -> bool:
    try:
        if decision.get("kind") != DECISION_KIND:
            return False
        if decision.get("version") != DECISION_VERSION:
            return False
        if decision.get("authority") != (
            "checkpoint-owner-local-resume-claim-decision"
        ):
            return False
        if decision.get("source_run_id") != old_run["run_id"]:
            return False
        if decision.get("source_checkpoint_id") != (
            old_checkpoint["checkpoint_id"]
        ):
            return False
        if decision.get("source_stop_id") != old_stop["stop_id"]:
            return False
        if decision.get("source_steward_particular") != (
            old_run["steward_particular"]
        ):
            return False
        if decision.get("resume_claim_id") != claim[
            "resume_claim_id"
        ]:
            return False
        if decision.get("claimant_particular") != claim[
            "claimant_particular"
        ]:
            return False
        if decision.get("candidate_reservation_id") != claim[
            "candidate_reservation_id"
        ]:
            return False
        if decision.get("status") not in {"ACTIVE", "LOSING"}:
            return False
        if decision.get("execution_authority") != "none":
            return False
        if decision.get("claim_deleted") is not False:
            return False
        if decision.get("global_consensus") is not False:
            return False
        if decision["status"] == "ACTIVE":
            if decision.get("active_resume_claim_id") != claim[
                "resume_claim_id"
            ]:
                return False
        return _verify_signed(
            decision,
            id_field="claim_decision_id",
            particular_field="source_steward_particular",
            domain=DECISION_DOMAIN,
            byte_domain=DECISION_BYTES,
        )
    except Exception:
        return False


def reconcile_active_resume_claims(
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    claims: list[dict[str, Any]],
    active_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    if not active_decisions:
        raise LightwalkerEconomyError(
            "resume claim reconciliation requires active decisions"
        )
    claim_by_id = {
        claim["resume_claim_id"]: claim for claim in claims
    }
    if len(claim_by_id) != len(claims):
        raise LightwalkerEconomyError(
            "duplicate resume claim"
        )
    active_claim_ids: list[str] = []
    decision_ids: list[str] = []
    for decision in active_decisions:
        if decision.get("status") != "ACTIVE":
            raise LightwalkerEconomyError(
                "fork reconciliation only accepts ACTIVE receipts"
            )
        claim = claim_by_id.get(
            decision.get("resume_claim_id")
        )
        if claim is None:
            raise LightwalkerEconomyError(
                "active decision references unavailable claim"
            )
        if decision.get("source_run_id") != old_run["run_id"]:
            raise LightwalkerEconomyError(
                "active decision source run mismatch"
            )
        if decision.get("source_checkpoint_id") != (
            old_checkpoint["checkpoint_id"]
        ):
            raise LightwalkerEconomyError(
                "active decision checkpoint mismatch"
            )
        if decision.get("source_steward_particular") != (
            old_run["steward_particular"]
        ):
            raise LightwalkerEconomyError(
                "active decision source steward mismatch"
            )
        if not _verify_signed(
            decision,
            id_field="claim_decision_id",
            particular_field="source_steward_particular",
            domain=DECISION_DOMAIN,
            byte_domain=DECISION_BYTES,
        ):
            raise LightwalkerEconomyError(
                "invalid ACTIVE resume decision"
            )
        active_claim_ids.append(claim["resume_claim_id"])
        decision_ids.append(decision["claim_decision_id"])

    unique = sorted(set(active_claim_ids))
    fork = len(unique) > 1
    body = {
        "kind": FORK_KIND,
        "version": FORK_VERSION,
        "authority": "derived-resume-claim-fork-observation",
        "source_run_id": old_run["run_id"],
        "source_checkpoint_id": old_checkpoint["checkpoint_id"],
        "source_steward_particular": old_run[
            "steward_particular"
        ],
        "active_resume_claim_ids": unique,
        "active_decision_ids": sorted(decision_ids),
        "status": "FORK" if fork else "NO_FORK",
        "global_consensus": False,
        "claim_deleted": False,
        "execution_authority": "none",
        "laws": [
            "RESUMABLE STATE != MULTIPLE CONTINUATION AUTHORITY",
            "FORK DETECTION != GLOBAL CONSENSUS",
            "LOSING CLAIM != HISTORY DELETION",
        ],
    }
    return {**body, "fork_id": content_address(body)}


def make_resume_claim_resolution(
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    fork: dict[str, Any],
    claims: list[dict[str, Any]],
    *,
    source_steward: IdentityKey,
    rule: str = "lowest-claim-id",
) -> dict[str, Any]:
    if source_steward.particular() != old_run[
        "steward_particular"
    ]:
        raise LightwalkerEconomyError(
            "only source lineage owner may resolve resume fork"
        )
    if fork.get("status") != "FORK":
        raise LightwalkerEconomyError(
            "resume resolution requires a fork"
        )
    if fork.get("source_checkpoint_id") != (
        old_checkpoint["checkpoint_id"]
    ):
        raise LightwalkerEconomyError(
            "resume fork checkpoint mismatch"
        )
    ids = sorted(
        claim["resume_claim_id"] for claim in claims
        if claim["resume_claim_id"] in fork[
            "active_resume_claim_ids"
        ]
    )
    if ids != fork["active_resume_claim_ids"]:
        raise LightwalkerEconomyError(
            "resume resolution claim set mismatch"
        )
    if rule != "lowest-claim-id":
        raise LightwalkerEconomyError(
            "unsupported resume fork resolution rule"
        )
    winner = min(ids)
    body = {
        "kind": RESOLUTION_KIND,
        "version": RESOLUTION_VERSION,
        "authority": "checkpoint-owner-local-resume-fork-resolution",
        "source_run_id": old_run["run_id"],
        "source_checkpoint_id": old_checkpoint["checkpoint_id"],
        "source_steward_particular": source_steward.particular(),
        "fork_id": fork["fork_id"],
        "resume_claim_ids": ids,
        "rule": rule,
        "winning_resume_claim_id": winner,
        "losing_resume_claim_ids": [
            claim_id for claim_id in ids
            if claim_id != winner
        ],
        "claim_deleted": False,
        "global_consensus": False,
        "execution_authority": "none",
        "laws": [
            "ONE CHECKPOINT -> AT MOST ONE ACTIVE RESUME CLAIM",
            "LOSING CLAIM != HISTORY DELETION",
            "FORK DETECTION != GLOBAL CONSENSUS",
        ],
    }
    return _signed(
        body,
        id_field="resume_resolution_id",
        signer=source_steward,
        domain=RESOLUTION_DOMAIN,
        byte_domain=RESOLUTION_BYTES,
    )


def verify_resume_claim_resolution(
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
) -> bool:
    try:
        if resolution.get("kind") != RESOLUTION_KIND:
            return False
        if resolution.get("version") != RESOLUTION_VERSION:
            return False
        if resolution.get("authority") != (
            "checkpoint-owner-local-resume-fork-resolution"
        ):
            return False
        if resolution.get("source_run_id") != old_run["run_id"]:
            return False
        if resolution.get("source_checkpoint_id") != (
            old_checkpoint["checkpoint_id"]
        ):
            return False
        if resolution.get("fork_id") != fork["fork_id"]:
            return False
        ids = fork["active_resume_claim_ids"]
        if resolution.get("resume_claim_ids") != ids:
            return False
        if resolution.get("rule") != "lowest-claim-id":
            return False
        if resolution.get("winning_resume_claim_id") != min(ids):
            return False
        if resolution.get("losing_resume_claim_ids") != [
            item for item in ids if item != min(ids)
        ]:
            return False
        if resolution.get("claim_deleted") is not False:
            return False
        if resolution.get("global_consensus") is not False:
            return False
        if resolution.get("execution_authority") != "none":
            return False
        return _verify_signed(
            resolution,
            id_field="resume_resolution_id",
            particular_field="source_steward_particular",
            domain=RESOLUTION_DOMAIN,
            byte_domain=RESOLUTION_BYTES,
        )
    except Exception:
        return False


def resume_claim_gate(
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    claim: dict[str, Any],
    active_decisions: list[dict[str, Any]],
    *,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claim_id = claim["resume_claim_id"]
    relevant = [
        decision for decision in active_decisions
        if decision.get("resume_claim_id") == claim_id
        and decision.get("status") == "ACTIVE"
    ]
    if not relevant:
        raise LightwalkerEconomyError(
            "resume claim is not ACTIVE"
        )
    fork = reconcile_active_resume_claims(
        old_run,
        old_checkpoint,
        [claim] + [
            {
                "resume_claim_id": decision["resume_claim_id"]
            }
            for decision in active_decisions
            if decision["resume_claim_id"] != claim_id
        ],
        active_decisions,
    )
    if fork["status"] == "FORK":
        if resolution is None:
            return {
                "status": "BLOCKED_FORK",
                "fork_id": fork["fork_id"],
                "resume_claim_id": claim_id,
                "execution_authority": "none",
            }
        if not verify_resume_claim_resolution(
            old_run,
            old_checkpoint,
            fork,
            resolution,
        ):
            raise LightwalkerEconomyError(
                "invalid resume claim resolution"
            )
        if claim_id == resolution["winning_resume_claim_id"]:
            status = "ELIGIBLE_RESOLVED"
        else:
            status = "SUPERSEDED"
        return {
            "status": status,
            "fork_id": fork["fork_id"],
            "resume_resolution_id": resolution[
                "resume_resolution_id"
            ],
            "resume_claim_id": claim_id,
            "execution_authority": "none",
        }
    return {
        "status": "ELIGIBLE_ACTIVE",
        "fork_id": fork["fork_id"],
        "resume_claim_id": claim_id,
        "execution_authority": "none",
    }


def claim_bound_resume(
    store: ResumedExecutionStore,
    *,
    claim: dict[str, Any],
    claim_decision: dict[str, Any],
    all_active_decisions: list[dict[str, Any]],
    old_run: dict[str, Any],
    old_checkpoint: dict[str, Any],
    resolution: dict[str, Any] | None = None,
    resume_kwargs: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = resume_claim_gate(
        old_run,
        old_checkpoint,
        claim,
        all_active_decisions,
        resolution=resolution,
    )
    if gate["status"] not in {
        "ELIGIBLE_ACTIVE",
        "ELIGIBLE_RESOLVED",
    }:
        raise LightwalkerEconomyError(
            "resume claim gate does not permit continuation"
        )
    if not verify_claim_decision(
        old_run,
        old_checkpoint,
        resume_kwargs["old_stop"],
        claim,
        claim_decision,
    ):
        raise LightwalkerEconomyError(
            "claim decision does not verify"
        )
    if claim_decision.get("status") != "ACTIVE":
        raise LightwalkerEconomyError(
            "claim decision is not ACTIVE"
        )
    if claim.get("candidate_reservation_id") != resume_kwargs[
        "new_reservation"
    ]["reservation_id"]:
        raise LightwalkerEconomyError(
            "claim does not name resume reservation"
        )
    resume = store.resume(**resume_kwargs)
    body = {
        "kind": BINDING_KIND,
        "version": BINDING_VERSION,
        "authority": "derived-claim-resume-lineage-only",
        "source_run_id": old_run["run_id"],
        "source_checkpoint_id": old_checkpoint["checkpoint_id"],
        "resume_claim_id": claim["resume_claim_id"],
        "claim_decision_id": claim_decision[
            "claim_decision_id"
        ],
        "claim_gate_status": gate["status"],
        "resume_resolution_id": gate.get(
            "resume_resolution_id"
        ),
        "resume_id": resume["resume_id"],
        "new_reservation_id": resume[
            "new_reservation_id"
        ],
        "claim_is_execution": False,
        "ownership_transfer": False,
        "source_history_rewritten": False,
        "laws": [
            "CLAIM != EXECUTION",
            "OLD RUN != NEW RESOURCE AUTHORITY",
            "COMPLETION MUST NAME THE WINNING CONTINUATION LINEAGE",
        ],
    }
    return resume, {
        **body,
        "claim_bound_resume_id": content_address(body),
    }


def bind_completion_to_winning_claim(
    claim_bound_resume_artifact: dict[str, Any],
    resumed_completion: dict[str, Any],
) -> dict[str, Any]:
    if claim_bound_resume_artifact.get("resume_id") != (
        resumed_completion.get("resume_id")
    ):
        raise LightwalkerEconomyError(
            "completion belongs to another resumed execution"
        )
    if resumed_completion.get("service_complete") is not True:
        raise LightwalkerEconomyError(
            "claim completion binding requires completed resumed execution"
        )
    body = {
        "kind": COMPLETION_BINDING_KIND,
        "version": COMPLETION_BINDING_VERSION,
        "authority": "derived-winning-continuation-completion-linkage",
        "claim_bound_resume_id": claim_bound_resume_artifact[
            "claim_bound_resume_id"
        ],
        "resume_claim_id": claim_bound_resume_artifact[
            "resume_claim_id"
        ],
        "claim_decision_id": claim_bound_resume_artifact[
            "claim_decision_id"
        ],
        "resume_resolution_id": claim_bound_resume_artifact[
            "resume_resolution_id"
        ],
        "resume_id": resumed_completion["resume_id"],
        "resumed_completion_id": resumed_completion[
            "resumed_completion_id"
        ],
        "source_checkpoint_id": claim_bound_resume_artifact[
            "source_checkpoint_id"
        ],
        "winning_continuation_named": True,
        "losing_claims_deleted": False,
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "LOSING CLAIM != HISTORY DELETION",
            "COMPLETION MUST NAME THE WINNING CONTINUATION LINEAGE",
            "CLAIM != EXECUTION",
        ],
    }
    return {
        **body,
        "claim_bound_completion_id": content_address(body),
    }


__all__ = [
    "ResumeClaimRegistry",
    "bind_completion_to_winning_claim",
    "claim_bound_resume",
    "make_resume_claim",
    "make_resume_claim_resolution",
    "reconcile_active_resume_claims",
    "resume_claim_gate",
    "verify_claim_decision",
    "verify_resume_claim",
    "verify_resume_claim_resolution",
]
