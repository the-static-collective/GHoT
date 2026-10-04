#!/usr/bin/env python3
"""Lightwalker Distributed Reservation 001.

Two sovereign nodes may each form a locally valid reservation claim from the
same stale Treasury snapshot. The protocol does not pretend one claim never
happened. Exchange makes the conflict visible; execution is blocked until an
explicit Guild resolution addresses the exact conflict set.

Core laws:
    LOCAL KNOWLEDGE != GLOBAL KNOWLEDGE
    RESERVATION CLAIM != CONSENSUS
    CONFLICT != SILENT OVERCOMMIT
    RECONCILIATION != HISTORY REWRITE
    RESOLUTION != CLAIM DELETION
    LOCAL CLAIM != EXECUTION AUTHORITY
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_authorization import verify_resource_proposal
from lightwalker_guild_reservation import GuildReservationStore
from lightwalker_guild_treasury import verify_treasury_snapshot
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    particular_for_public_key,
    sign_crossing,
    timestamp_now,
    verify_crossing,
    verify_p256,
)


CLAIM_KIND = "ghot.lightwalker.distributed-reservation-claim"
CLAIM_VERSION = "0"
RECONCILIATION_KIND = "ghot.lightwalker.distributed-reservation-reconciliation"
RECONCILIATION_VERSION = "0"
RESOLUTION_KIND = "ghot.lightwalker.distributed-reservation-resolution"
RESOLUTION_VERSION = "0"

CLAIM_DOMAIN = "ghot.lightwalker-distributed-reservation-claim-signature/v0"
RESOLUTION_DOMAIN = "ghot.lightwalker-distributed-reservation-resolution-signature/v0"
CLAIM_BYTES = b"GHOT-LightwalkerDistributedReservationClaim-v0|"
RESOLUTION_BYTES = b"GHOT-LightwalkerDistributedReservationResolution-v0|"

CLAIM_CAPABILITY = "ghot.lightwalker-distributed-reservation-claim/v0"


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


def _resource_entry(snapshot: dict[str, Any], entry_id: str) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    for entry in snapshot["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise LightwalkerEconomyError("resource entry not found")


def make_local_reservation_claim(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    *,
    node: IdentityKey,
    node_id: str,
    executor_particular: str,
    claimed_at_cut: int,
    expires_after_cut: int,
    known_claim_ids: list[str],
) -> dict[str, Any]:
    if not verify_resource_proposal(snapshot, proposal):
        raise LightwalkerEconomyError("invalid resource proposal")
    entry = _resource_entry(snapshot, proposal["resource_entry_id"])
    if entry["category"] != "capability" or entry["position"] != "available":
        raise LightwalkerEconomyError("claim requires available capability")

    claimed = _nonnegative_int(claimed_at_cut, "claimed_at_cut")
    expiry = _nonnegative_int(expires_after_cut, "expires_after_cut")
    if expiry < claimed:
        raise LightwalkerEconomyError("claim expiry precedes claim")
    if not isinstance(known_claim_ids, list) or any(
        not isinstance(item, str) or not item for item in known_claim_ids
    ):
        raise LightwalkerEconomyError("known_claim_ids must contain non-empty strings")

    body = {
        "kind": CLAIM_KIND,
        "version": CLAIM_VERSION,
        "authority": "node-local-tentative-claim",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": proposal["resource_entry_id"],
        "resource_subject_ref": proposal["resource_subject_ref"],
        "proposal_id": proposal["proposal_id"],
        "node_id": _nonempty(node_id, "node_id"),
        "node_particular": node.particular(),
        "executor_particular": _nonempty(
            executor_particular, "executor_particular"
        ),
        "claimed_measure": proposal["requested_measure"],
        "claimed_at_cut": claimed,
        "expires_after_cut": expiry,
        "known_claim_ids": sorted(set(known_claim_ids)),
        "status": "LOCAL_TENTATIVE",
        "laws": [
            "LOCAL KNOWLEDGE != GLOBAL KNOWLEDGE",
            "RESERVATION CLAIM != CONSENSUS",
            "LOCAL CLAIM != EXECUTION AUTHORITY",
        ],
    }
    return _signed(
        body,
        id_field="claim_id",
        signer=node,
        domain=CLAIM_DOMAIN,
        byte_domain=CLAIM_BYTES,
    )


def verify_local_reservation_claim(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    claim: dict[str, Any],
) -> bool:
    try:
        if not verify_resource_proposal(snapshot, proposal):
            return False
        if claim.get("kind") != CLAIM_KIND:
            return False
        if claim.get("version") != CLAIM_VERSION:
            return False
        if claim.get("authority") != "node-local-tentative-claim":
            return False
        if claim.get("guild_id") != snapshot["guild_id"]:
            return False
        if claim.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if claim.get("resource_entry_id") != proposal["resource_entry_id"]:
            return False
        if claim.get("proposal_id") != proposal["proposal_id"]:
            return False
        if claim.get("claimed_measure") != proposal["requested_measure"]:
            return False
        if claim.get("status") != "LOCAL_TENTATIVE":
            return False
        if int(claim.get("expires_after_cut", -1)) < int(
            claim.get("claimed_at_cut", 0)
        ):
            return False
        return _verify_signed(
            claim,
            id_field="claim_id",
            particular_field="node_particular",
            domain=CLAIM_DOMAIN,
            byte_domain=CLAIM_BYTES,
        )
    except Exception:
        return False


def make_claim_crossing(
    claim: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    if signer.particular() != claim.get("node_particular"):
        raise LightwalkerEconomyError("claim crossing signer mismatch")
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f'guild-node:{claim["node_id"]}',
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_DISTRIBUTED_RESERVATION_CLAIM",
        "payload_refs": [
            claim["snapshot_id"],
            claim["resource_entry_id"],
            claim["proposal_id"],
            claim["claim_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-distributed-reservation-claim",
                "claim_id": claim["claim_id"],
                "automatic_consensus_requested": False,
                "automatic_execution_requested": False,
                "remote_history_rewrite_requested": False,
            }
        ),
        "capability_ref": CLAIM_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "guild_id": claim["guild_id"],
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-distributed-reservation-claim/v0",
            "claim_is_not_consensus": True,
            "claim_is_not_execution_authority": True,
        },
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("claim crossing failed verification")
    return signed


def reconcile_claims(
    snapshot: dict[str, Any],
    claims: list[dict[str, Any]],
    proposals_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    if not claims:
        raise LightwalkerEconomyError("reconciliation requires at least one claim")

    verified: list[dict[str, Any]] = []
    for claim in claims:
        proposal = proposals_by_id.get(str(claim.get("proposal_id")))
        if proposal is None or not verify_local_reservation_claim(
            snapshot, proposal, claim
        ):
            raise LightwalkerEconomyError("invalid distributed reservation claim")
        verified.append(claim)

    snapshot_ids = {item["snapshot_id"] for item in verified}
    resource_ids = {item["resource_entry_id"] for item in verified}
    units = {item["claimed_measure"]["unit"] for item in verified}
    if snapshot_ids != {snapshot["snapshot_id"]}:
        raise LightwalkerEconomyError("claims address different snapshot")
    if len(resource_ids) != 1 or len(units) != 1:
        raise LightwalkerEconomyError(
            "v0 reconciliation handles one resource/unit conflict set"
        )

    resource_id = next(iter(resource_ids))
    entry = _resource_entry(snapshot, resource_id)
    measure = entry.get("native_measure")
    if not isinstance(measure, dict):
        raise LightwalkerEconomyError("resource has no native measure")
    unit = next(iter(units))
    if unit != measure["unit"]:
        raise LightwalkerEconomyError("claim unit differs from resource unit")

    ordered = sorted(verified, key=lambda item: item["claim_id"])
    total = sum(int(item["claimed_measure"]["quantity"]) for item in ordered)
    visible = int(measure["quantity"])
    conflict = total > visible
    body = {
        "kind": RECONCILIATION_KIND,
        "version": RECONCILIATION_VERSION,
        "authority": "derived-conflict-observation",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": resource_id,
        "unit": unit,
        "visible_quantity": visible,
        "claim_ids": [item["claim_id"] for item in ordered],
        "total_claimed_quantity": total,
        "status": "CONFLICT" if conflict else "NO_CONFLICT",
        "overcommit_quantity": max(0, total - visible),
        "laws": [
            "CONFLICT != SILENT OVERCOMMIT",
            "RECONCILIATION != HISTORY REWRITE",
            "DERIVED CONFLICT != CLAIM DELETION",
        ],
    }
    return {**body, "reconciliation_id": content_address(body)}


def make_conflict_resolution(
    snapshot: dict[str, Any],
    reconciliation: dict[str, Any],
    claims: list[dict[str, Any]],
    *,
    steward: IdentityKey,
    rule: str = "lowest-claim-id",
) -> dict[str, Any]:
    if steward.particular() != snapshot["steward_particular"]:
        raise LightwalkerEconomyError("only Guild steward may resolve conflict")
    if reconciliation.get("status") != "CONFLICT":
        raise LightwalkerEconomyError("resolution requires a conflict")
    claim_ids = sorted(item["claim_id"] for item in claims)
    if claim_ids != reconciliation.get("claim_ids"):
        raise LightwalkerEconomyError("resolution claim set mismatch")
    if rule != "lowest-claim-id":
        raise LightwalkerEconomyError("unsupported v0 resolution rule")

    selected = min(claim_ids)
    body = {
        "kind": RESOLUTION_KIND,
        "version": RESOLUTION_VERSION,
        "authority": "guild-local-conflict-resolution",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": reconciliation["resource_entry_id"],
        "reconciliation_id": reconciliation["reconciliation_id"],
        "claim_ids": claim_ids,
        "steward_particular": steward.particular(),
        "rule": rule,
        "selected_claim_ids": [selected],
        "superseded_claim_ids": [
            item for item in claim_ids if item != selected
        ],
        "laws": [
            "RESOLUTION != CLAIM DELETION",
            "LOSING CLAIM REMAINS HISTORY",
            "RESOLUTION ADDRESSES EXACT CONFLICT SET",
        ],
    }
    return _signed(
        body,
        id_field="resolution_id",
        signer=steward,
        domain=RESOLUTION_DOMAIN,
        byte_domain=RESOLUTION_BYTES,
    )


def verify_conflict_resolution(
    snapshot: dict[str, Any],
    reconciliation: dict[str, Any],
    claims: list[dict[str, Any]],
    resolution: dict[str, Any],
) -> bool:
    try:
        if not verify_treasury_snapshot(snapshot):
            return False
        if reconciliation.get("status") != "CONFLICT":
            return False
        if resolution.get("kind") != RESOLUTION_KIND:
            return False
        if resolution.get("version") != RESOLUTION_VERSION:
            return False
        if resolution.get("authority") != "guild-local-conflict-resolution":
            return False
        if resolution.get("guild_id") != snapshot["guild_id"]:
            return False
        if resolution.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if resolution.get("reconciliation_id") != reconciliation["reconciliation_id"]:
            return False
        claim_ids = sorted(item["claim_id"] for item in claims)
        if claim_ids != reconciliation["claim_ids"]:
            return False
        if resolution.get("claim_ids") != claim_ids:
            return False
        if resolution.get("rule") != "lowest-claim-id":
            return False
        expected = [min(claim_ids)]
        if resolution.get("selected_claim_ids") != expected:
            return False
        if resolution.get("superseded_claim_ids") != [
            item for item in claim_ids if item != expected[0]
        ]:
            return False
        if resolution.get("steward_particular") != snapshot["steward_particular"]:
            return False
        return _verify_signed(
            resolution,
            id_field="resolution_id",
            particular_field="steward_particular",
            domain=RESOLUTION_DOMAIN,
            byte_domain=RESOLUTION_BYTES,
        )
    except Exception:
        return False


def execution_gate(
    snapshot: dict[str, Any],
    claim: dict[str, Any],
    claims: list[dict[str, Any]],
    proposals_by_id: dict[str, dict[str, Any]],
    *,
    resolution: dict[str, Any] | None = None,
) -> str:
    reconciliation = reconcile_claims(snapshot, claims, proposals_by_id)
    if claim["claim_id"] not in reconciliation["claim_ids"]:
        raise LightwalkerEconomyError("claim is outside reconciliation set")

    if reconciliation["status"] == "NO_CONFLICT":
        return "ELIGIBLE_UNCONTESTED"

    if resolution is None:
        return "BLOCKED_CONFLICT"
    if not verify_conflict_resolution(
        snapshot, reconciliation, claims, resolution
    ):
        raise LightwalkerEconomyError("invalid conflict resolution")
    if claim["claim_id"] in resolution["selected_claim_ids"]:
        return "ELIGIBLE_RESOLVED"
    return "SUPERSEDED"


def materialize_resolved_claim(
    snapshot: dict[str, Any],
    claim: dict[str, Any],
    claims: list[dict[str, Any]],
    proposals_by_id: dict[str, dict[str, Any]],
    resolution: dict[str, Any],
    *,
    reservation_store: GuildReservationStore,
) -> tuple[dict[str, Any], dict[str, Any]]:
    gate = execution_gate(
        snapshot,
        claim,
        claims,
        proposals_by_id,
        resolution=resolution,
    )
    if gate != "ELIGIBLE_RESOLVED":
        raise LightwalkerEconomyError(
            f"distributed claim cannot materialize: {gate}"
        )
    proposal = proposals_by_id[claim["proposal_id"]]
    return reservation_store.reserve_and_authorize(
        snapshot,
        proposal,
        executor_particular=claim["executor_particular"],
        authorized_at_cut=claim["claimed_at_cut"],
        expires_after_cut=claim["expires_after_cut"],
    )


__all__ = [
    "execution_gate",
    "make_claim_crossing",
    "make_conflict_resolution",
    "make_local_reservation_claim",
    "materialize_resolved_claim",
    "reconcile_claims",
    "verify_conflict_resolution",
    "verify_local_reservation_claim",
]
