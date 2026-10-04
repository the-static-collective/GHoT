#!/usr/bin/env python3
"""Lightwalker Guild Proposal / Treasury Authorization 001.

A Treasury snapshot describes capacity. It does not grant spending authority.

Flow:
    signed treasury snapshot
      -> attributable resource proposal
      -> steward-signed bounded authorization
      -> one execution attempt
      -> signed success/failure receipt
      -> new treasury snapshot

Core laws:
    CAPACITY != SPENDING AUTHORITY
    PROPOSAL != AUTHORIZATION
    AUTHORIZATION != EXECUTION
    EXECUTION != SUCCESS
    FAILED EXECUTION != RESOURCE CONSUMPTION
    ONE AUTHORIZATION -> AT MOST ONE EXECUTION ATTEMPT
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_treasury import (
    make_treasury_entry,
    next_treasury_snapshot,
    verify_treasury_snapshot,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


PROPOSAL_KIND = "ghot.lightwalker.guild-resource-proposal"
PROPOSAL_VERSION = "0"
AUTH_KIND = "ghot.lightwalker.guild-resource-authorization"
AUTH_VERSION = "0"
EXECUTION_KIND = "ghot.lightwalker.guild-resource-execution-receipt"
EXECUTION_VERSION = "0"

PROPOSAL_DOMAIN = "ghot.lightwalker-guild-resource-proposal-signature/v0"
AUTH_DOMAIN = "ghot.lightwalker-guild-resource-authorization-signature/v0"
EXECUTION_DOMAIN = "ghot.lightwalker-guild-resource-execution-signature/v0"

PROPOSAL_BYTES = b"GHOT-LightwalkerGuildResourceProposal-v0|"
AUTH_BYTES = b"GHOT-LightwalkerGuildResourceAuthorization-v0|"
EXECUTION_BYTES = b"GHOT-LightwalkerGuildResourceExecution-v0|"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
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


def _find_entry(snapshot: dict[str, Any], entry_id: str) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    for entry in snapshot["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise LightwalkerEconomyError("resource entry not present in treasury snapshot")


def make_resource_proposal(
    snapshot: dict[str, Any],
    *,
    proposer: IdentityKey,
    resource_entry_id: str,
    requested_quantity: int,
    requested_unit: str,
    purpose_ref: str,
    proposed_at_cut: int,
) -> dict[str, Any]:
    entry = _find_entry(snapshot, resource_entry_id)
    if entry["category"] != "capability" or entry["position"] != "available":
        raise LightwalkerEconomyError("proposal requires available capability entry")
    measure = entry.get("native_measure")
    if not isinstance(measure, dict):
        raise LightwalkerEconomyError("resource entry has no native capacity measure")

    quantity = _nonnegative_int(requested_quantity, "requested_quantity")
    if quantity <= 0:
        raise LightwalkerEconomyError("requested_quantity must be > 0")
    unit = _nonempty(requested_unit, "requested_unit")
    if unit != measure["unit"]:
        raise LightwalkerEconomyError("proposal unit must match resource native unit")
    if quantity > int(measure["quantity"]):
        raise LightwalkerEconomyError("proposal exceeds visible treasury capacity")

    body = {
        "kind": PROPOSAL_KIND,
        "version": PROPOSAL_VERSION,
        "authority": "proposal-only",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": entry["entry_id"],
        "resource_subject_ref": entry["subject_ref"],
        "proposer_particular": proposer.particular(),
        "requested_measure": {
            "unit": unit,
            "quantity": quantity,
        },
        "purpose_ref": _nonempty(purpose_ref, "purpose_ref"),
        "proposed_at_cut": _nonnegative_int(proposed_at_cut, "proposed_at_cut"),
        "laws": [
            "CAPACITY != SPENDING AUTHORITY",
            "PROPOSAL != AUTHORIZATION",
            "PROPOSAL DOES NOT ENCUMBER RESOURCE",
        ],
    }
    return _signed(
        body,
        id_field="proposal_id",
        signer=proposer,
        domain=PROPOSAL_DOMAIN,
        byte_domain=PROPOSAL_BYTES,
    )


def verify_resource_proposal(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
) -> bool:
    try:
        if not verify_treasury_snapshot(snapshot):
            return False
        if proposal.get("kind") != PROPOSAL_KIND:
            return False
        if proposal.get("version") != PROPOSAL_VERSION:
            return False
        if proposal.get("authority") != "proposal-only":
            return False
        if proposal.get("guild_id") != snapshot["guild_id"]:
            return False
        if proposal.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        entry = _find_entry(snapshot, str(proposal.get("resource_entry_id")))
        if entry["category"] != "capability" or entry["position"] != "available":
            return False
        measure = entry.get("native_measure")
        requested = proposal.get("requested_measure")
        if not isinstance(measure, dict) or not isinstance(requested, dict):
            return False
        if requested.get("unit") != measure.get("unit"):
            return False
        quantity = _nonnegative_int(requested.get("quantity"), "requested quantity")
        if quantity <= 0 or quantity > int(measure["quantity"]):
            return False
        return _verify_signed(
            proposal,
            id_field="proposal_id",
            particular_field="proposer_particular",
            domain=PROPOSAL_DOMAIN,
            byte_domain=PROPOSAL_BYTES,
        )
    except Exception:
        return False


def authorize_resource_proposal(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    *,
    steward: IdentityKey,
    executor_particular: str,
    authorized_at_cut: int,
    expires_after_cut: int,
) -> dict[str, Any]:
    if not verify_resource_proposal(snapshot, proposal):
        raise LightwalkerEconomyError("invalid resource proposal")
    if steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError("only treasury steward may authorize")

    authorized_cut = _nonnegative_int(authorized_at_cut, "authorized_at_cut")
    expiry = _nonnegative_int(expires_after_cut, "expires_after_cut")
    if expiry < authorized_cut:
        raise LightwalkerEconomyError("authorization expiry precedes authorization")

    body = {
        "kind": AUTH_KIND,
        "version": AUTH_VERSION,
        "authority": "guild-local-bounded-authorization",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "proposal_id": proposal["proposal_id"],
        "resource_entry_id": proposal["resource_entry_id"],
        "steward_particular": steward.particular(),
        "executor_particular": _nonempty(
            executor_particular, "executor_particular"
        ),
        "authorized_measure": proposal["requested_measure"],
        "purpose_ref": proposal["purpose_ref"],
        "authorized_at_cut": authorized_cut,
        "expires_after_cut": expiry,
        "one_execution_attempt": True,
        "laws": [
            "PROPOSAL != AUTHORIZATION",
            "AUTHORIZATION != EXECUTION",
            "AUTHORIZATION BINDS EXACT PROPOSAL",
            "AUTHORIZATION IS ONE-SHOT",
        ],
    }
    return _signed(
        body,
        id_field="authorization_id",
        signer=steward,
        domain=AUTH_DOMAIN,
        byte_domain=AUTH_BYTES,
    )


def verify_resource_authorization(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
) -> bool:
    try:
        if not verify_resource_proposal(snapshot, proposal):
            return False
        if authorization.get("kind") != AUTH_KIND:
            return False
        if authorization.get("version") != AUTH_VERSION:
            return False
        if authorization.get("authority") != "guild-local-bounded-authorization":
            return False
        if authorization.get("guild_id") != snapshot["guild_id"]:
            return False
        if authorization.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if authorization.get("proposal_id") != proposal["proposal_id"]:
            return False
        if authorization.get("resource_entry_id") != proposal["resource_entry_id"]:
            return False
        if authorization.get("authorized_measure") != proposal["requested_measure"]:
            return False
        if authorization.get("purpose_ref") != proposal["purpose_ref"]:
            return False
        if authorization.get("steward_particular") != snapshot["steward_particular"]:
            return False
        if authorization.get("one_execution_attempt") is not True:
            return False
        if int(authorization.get("expires_after_cut", -1)) < int(
            authorization.get("authorized_at_cut", 0)
        ):
            return False
        return _verify_signed(
            authorization,
            id_field="authorization_id",
            particular_field="steward_particular",
            domain=AUTH_DOMAIN,
            byte_domain=AUTH_BYTES,
        )
    except Exception:
        return False


def verify_execution_receipt(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    receipt: dict[str, Any],
) -> bool:
    try:
        if not verify_resource_authorization(snapshot, proposal, authorization):
            return False
        if receipt.get("kind") != EXECUTION_KIND:
            return False
        if receipt.get("version") != EXECUTION_VERSION:
            return False
        if receipt.get("authorization_id") != authorization["authorization_id"]:
            return False
        if receipt.get("proposal_id") != proposal["proposal_id"]:
            return False
        if receipt.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if receipt.get("resource_entry_id") != proposal["resource_entry_id"]:
            return False
        if receipt.get("executor_particular") != authorization["executor_particular"]:
            return False
        if receipt.get("authorization_spent") is not True:
            return False
        if receipt.get("status") not in {"EXECUTED", "FAILED"}:
            return False
        if receipt.get("status") == "EXECUTED":
            if receipt.get("success") is not True:
                return False
            if receipt.get("consumed_measure") != authorization["authorized_measure"]:
                return False
        if receipt.get("status") == "FAILED":
            if receipt.get("success") is not False:
                return False
            if receipt.get("consumed_measure") is not None:
                return False
        return _verify_signed(
            receipt,
            id_field="execution_receipt_id",
            particular_field="executor_particular",
            domain=EXECUTION_DOMAIN,
            byte_domain=EXECUTION_BYTES,
        )
    except Exception:
        return False


class GuildAuthorizationStore:
    """One-shot execution claim store keyed by authorization ID."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.claims_dir = root / "guild-authorizations" / "claims"
        self.receipts_dir = root / "guild-authorizations" / "receipts"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _claim_path(self, authorization_id: str) -> Path:
        return self.claims_dir / f"{self._safe(authorization_id)}.json"

    def _receipt_path(self, authorization_id: str) -> Path:
        return self.receipts_dir / f"{self._safe(authorization_id)}.json"

    def _exclusive_write(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(
                fd,
                (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            )
        finally:
            os.close(fd)

    def execute(
        self,
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any] | None,
        *,
        executor: IdentityKey,
        observed_cut: int,
        simulate_success: bool,
        result_ref: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        if authorization is None:
            raise LightwalkerEconomyError(
                "treasury capacity does not authorize execution"
            )
        if not verify_resource_authorization(snapshot, proposal, authorization):
            raise LightwalkerEconomyError("invalid resource authorization")
        if executor.particular() != authorization["executor_particular"]:
            raise LightwalkerEconomyError("executor is not authorized")
        cut = _nonnegative_int(observed_cut, "observed_cut")
        if cut < int(authorization["authorized_at_cut"]):
            raise LightwalkerEconomyError("execution predates authorization")
        if cut > int(authorization["expires_after_cut"]):
            raise LightwalkerEconomyError("authorization expired")

        claim = {
            "kind": "ghot.lightwalker.guild-authorization-claim",
            "version": "0",
            "authorization_id": authorization["authorization_id"],
            "proposal_id": proposal["proposal_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "executor_particular": executor.particular(),
            "observed_cut": cut,
        }
        try:
            self._exclusive_write(
                self._claim_path(authorization["authorization_id"]),
                claim,
            )
        except FileExistsError as exc:
            raise LightwalkerEconomyError(
                "authorization already spent by an execution attempt"
            ) from exc

        status = "EXECUTED" if simulate_success else "FAILED"
        body = {
            "kind": EXECUTION_KIND,
            "version": EXECUTION_VERSION,
            "guild_id": snapshot["guild_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "proposal_id": proposal["proposal_id"],
            "authorization_id": authorization["authorization_id"],
            "resource_entry_id": proposal["resource_entry_id"],
            "executor_particular": executor.particular(),
            "observed_cut": cut,
            "status": status,
            "success": bool(simulate_success),
            "authorization_spent": True,
            "consumed_measure": (
                authorization["authorized_measure"]
                if simulate_success
                else None
            ),
            "result_ref": (
                _nonempty(result_ref, "result_ref")
                if simulate_success
                else None
            ),
            "error": (
                None
                if simulate_success
                else _nonempty(error, "error")
            ),
            "laws": [
                "AUTHORIZATION != EXECUTION",
                "EXECUTION != SUCCESS",
                "AUTHORIZATION IS SPENT BY ATTEMPT",
                "FAILED EXECUTION != RESOURCE CONSUMPTION",
            ],
        }
        receipt = _signed(
            body,
            id_field="execution_receipt_id",
            signer=executor,
            domain=EXECUTION_DOMAIN,
            byte_domain=EXECUTION_BYTES,
        )
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        self._receipt_path(authorization["authorization_id"]).write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return receipt


def apply_execution_to_treasury(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    receipt: dict[str, Any],
    *,
    steward: IdentityKey,
) -> dict[str, Any]:
    if not verify_execution_receipt(
        snapshot, proposal, authorization, receipt
    ):
        raise LightwalkerEconomyError("invalid execution receipt")
    if steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError("only steward may transition treasury")

    resource = _find_entry(snapshot, proposal["resource_entry_id"])
    add_entries: list[dict[str, Any]] = []
    retire_ids: list[str] = []

    if receipt["success"]:
        measure = resource["native_measure"]
        consumed = receipt["consumed_measure"]
        if measure["unit"] != consumed["unit"]:
            raise LightwalkerEconomyError("consumed unit does not match treasury resource")
        remaining = int(measure["quantity"]) - int(consumed["quantity"])
        if remaining < 0:
            raise LightwalkerEconomyError("execution would overdraw treasury capacity")
        retire_ids.append(resource["entry_id"])
        if remaining > 0:
            add_entries.append(
                make_treasury_entry(
                    category=resource["category"],
                    position=resource["position"],
                    subject_ref=resource["subject_ref"],
                    source_ref=receipt["execution_receipt_id"],
                    evidence_refs=[
                        *resource["evidence_refs"],
                        receipt["execution_receipt_id"],
                    ],
                    native_measure={
                        "unit": measure["unit"],
                        "quantity": remaining,
                    },
                    metadata={
                        **resource["metadata"],
                        "prior_entry_id": resource["entry_id"],
                        "last_execution_receipt_id": receipt[
                            "execution_receipt_id"
                        ],
                    },
                )
            )

    add_entries.append(
        make_treasury_entry(
            category="receipt",
            position="evidence",
            subject_ref="guild-resource-execution:" + receipt["execution_receipt_id"],
            source_ref=receipt["execution_receipt_id"],
            evidence_refs=[
                proposal["proposal_id"],
                authorization["authorization_id"],
                receipt["execution_receipt_id"],
            ],
            metadata={
                "status": receipt["status"],
                "success": receipt["success"],
                "authorization_spent": True,
                "resource_entry_id": resource["entry_id"],
            },
        )
    )

    return next_treasury_snapshot(
        snapshot,
        steward=steward,
        add_entries=add_entries,
        retire_entry_ids=retire_ids,
    )


__all__ = [
    "GuildAuthorizationStore",
    "apply_execution_to_treasury",
    "authorize_resource_proposal",
    "make_resource_proposal",
    "verify_execution_receipt",
    "verify_resource_authorization",
    "verify_resource_proposal",
]
