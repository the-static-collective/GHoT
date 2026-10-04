#!/usr/bin/env python3
"""Lightwalker Authority Metabolism 001.

One end-to-end conservation witness across issue, partition, use, handoff,
expiry, reclaim, reissue, and use again.

This object is a derived audit. It grants no execution authority.

Core laws:
    AUTHORITY CHANGES FORM; ACCOUNTABILITY CONSERVES
    EXPIRED + RECLAIMED MAY NOT BE DOUBLE COUNTED
    RECLAIM != REVIVAL
    REISSUE != CONTINUATION
    METABOLISM WITNESS != SPENDING AUTHORITY
    CONSERVATION != GLOBAL CONSENSUS
"""

from __future__ import annotations

from typing import Any

from lightwalker_authority_compost import (
    verify_reclaim_receipt,
    verify_reclaimed_lease,
)
from lightwalker_capacity_lease import verify_lease_use
from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_treasury import verify_treasury_snapshot
from lightwalker_lease_lineage import derive_authority_dag
from relatte_identity import (
    IdentityKey,
    identity_safe,
    sign_crossing,
    timestamp_now,
    verify_crossing,
)


METABOLISM_KIND = "ghot.lightwalker.authority-metabolism"
METABOLISM_VERSION = "0"
METABOLISM_CAPABILITY = "ghot.lightwalker-authority-metabolism/v0"


def _successful_consumption(
    lease: dict[str, Any],
    uses: list[dict[str, Any]],
) -> int:
    consumed = 0
    seen: set[str] = set()
    for use in uses:
        use_id = use.get("use_id")
        if not isinstance(use_id, str) or use_id in seen:
            raise LightwalkerEconomyError(
                "duplicate or missing recycled-use id"
            )
        seen.add(use_id)
        if not verify_lease_use(lease, use):
            raise LightwalkerEconomyError(
                "invalid recycled lease-use receipt"
            )
        cut = int(use.get("observed_cut", -1))
        if cut < int(lease["issued_at_cut"]):
            raise LightwalkerEconomyError(
                "recycled use predates fresh lease"
            )
        if cut > int(lease["expires_after_cut"]):
            raise LightwalkerEconomyError(
                "recycled use occurs after fresh lease expiry"
            )
        if use["status"] == "EXECUTED":
            consumed += int(use["consumed_measure"]["quantity"])
    return consumed


def derive_authority_metabolism(
    snapshot: dict[str, Any],
    *,
    root_lease: dict[str, Any],
    descendant_leases: list[dict[str, Any]],
    surrenders: list[dict[str, Any]],
    source_uses: list[dict[str, Any]],
    reclaim_receipts: list[dict[str, Any]],
    reissued_leases: list[dict[str, Any]],
    recycled_uses: list[dict[str, Any]],
    source_observed_cut: int,
    observed_cut: int,
) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")

    dag = derive_authority_dag(
        snapshot,
        root_lease=root_lease,
        descendant_leases=descendant_leases,
        surrenders=surrenders,
        uses=source_uses,
        observed_cut=source_observed_cut,
    )

    reclaim_by_id: dict[str, dict[str, Any]] = {}
    reclaim_by_expired_lease: dict[str, dict[str, Any]] = {}
    for receipt in reclaim_receipts:
        reclaim_id = receipt.get("reclaim_id")
        expired_lease_id = receipt.get("expired_lease_id")
        if not isinstance(reclaim_id, str):
            raise LightwalkerEconomyError("reclaim missing id")
        if reclaim_id in reclaim_by_id:
            raise LightwalkerEconomyError("duplicate reclaim receipt")
        if not isinstance(expired_lease_id, str):
            raise LightwalkerEconomyError("reclaim missing expired lease")
        if expired_lease_id in reclaim_by_expired_lease:
            raise LightwalkerEconomyError(
                "expired leaf reclaimed more than once"
            )
        if not verify_reclaim_receipt(snapshot, dag, receipt):
            raise LightwalkerEconomyError("invalid reclaim receipt")
        reclaim_by_id[reclaim_id] = receipt
        reclaim_by_expired_lease[expired_lease_id] = receipt

    reissue_by_reclaim: dict[str, dict[str, Any]] = {}
    lease_by_id: dict[str, dict[str, Any]] = {}
    for lease in reissued_leases:
        lease_id = lease.get("lease_id")
        reclaim_id = lease.get("source_reclaim_id")
        if not isinstance(lease_id, str) or lease_id in lease_by_id:
            raise LightwalkerEconomyError(
                "duplicate or missing reissued lease id"
            )
        if not isinstance(reclaim_id, str):
            raise LightwalkerEconomyError(
                "reissued lease missing reclaim source"
            )
        if reclaim_id in reissue_by_reclaim:
            raise LightwalkerEconomyError(
                "one reclaim may materialize at most one fresh lease"
            )
        receipt = reclaim_by_id.get(reclaim_id)
        if receipt is None:
            raise LightwalkerEconomyError(
                "reissued lease lacks supplied reclaim evidence"
            )
        if not verify_reclaimed_lease(snapshot, dag, receipt, lease):
            raise LightwalkerEconomyError("invalid reissued lease")
        reissue_by_reclaim[reclaim_id] = lease
        lease_by_id[lease_id] = lease

    uses_by_lease: dict[str, list[dict[str, Any]]] = {
        lease_id: [] for lease_id in lease_by_id
    }
    global_use_ids: set[str] = set()
    for use in recycled_uses:
        use_id = use.get("use_id")
        lease_id = use.get("lease_id")
        if not isinstance(use_id, str) or use_id in global_use_ids:
            raise LightwalkerEconomyError(
                "duplicate or missing recycled-use id"
            )
        global_use_ids.add(use_id)
        if not isinstance(lease_id, str) or lease_id not in lease_by_id:
            raise LightwalkerEconomyError(
                "recycled use references unknown fresh lease"
            )
        uses_by_lease[lease_id].append(use)

    source_expired = int(
        dag["totals"]["expired_leaf_remaining_quantity"]
    )
    reclaimed_total = sum(
        int(receipt["reclaimed_quantity"])
        for receipt in reclaim_by_id.values()
    )
    if reclaimed_total > source_expired:
        raise LightwalkerEconomyError(
            "reclaimed quantity exceeds expired source bucket"
        )

    source_unreclaimed_expired = source_expired - reclaimed_total
    reclaimed_unissued = 0
    recycled_consumed = 0
    recycled_live = 0
    recycled_expired = 0
    recycled_rows: list[dict[str, Any]] = []

    for reclaim_id, receipt in sorted(reclaim_by_id.items()):
        lease = reissue_by_reclaim.get(reclaim_id)
        if lease is None:
            reclaimed_unissued += int(receipt["reclaimed_quantity"])
            recycled_rows.append(
                {
                    "reclaim_id": reclaim_id,
                    "expired_lease_id": receipt["expired_lease_id"],
                    "fresh_lease_id": None,
                    "status": "RECLAIMED_UNISSUED",
                    "quantity": int(receipt["reclaimed_quantity"]),
                    "consumed_quantity": 0,
                    "remaining_quantity": int(
                        receipt["reclaimed_quantity"]
                    ),
                }
            )
            continue

        lease_uses = uses_by_lease[lease["lease_id"]]
        consumed = _successful_consumption(lease, lease_uses)
        leased = int(lease["leased_measure"]["quantity"])
        if consumed > leased:
            raise LightwalkerEconomyError(
                "recycled consumption exceeds fresh authority"
            )
        remaining = leased - consumed
        recycled_consumed += consumed
        if int(observed_cut) > int(lease["expires_after_cut"]):
            status = "REISSUED_EXPIRED"
            recycled_expired += remaining
        else:
            status = "REISSUED_LIVE"
            recycled_live += remaining
        recycled_rows.append(
            {
                "reclaim_id": reclaim_id,
                "expired_lease_id": receipt["expired_lease_id"],
                "fresh_lease_id": lease["lease_id"],
                "status": status,
                "quantity": leased,
                "consumed_quantity": consumed,
                "remaining_quantity": remaining,
                "use_ids": sorted(
                    use["use_id"] for use in lease_uses
                ),
            }
        )

    source_consumed = int(dag["totals"]["consumed_quantity"])
    source_returned = int(
        dag["totals"]["returned_to_guild_quantity"]
    )
    source_live = int(
        dag["totals"]["live_leaf_remaining_quantity"]
    )
    root_quantity = int(dag["totals"]["root_quantity"])

    accounted = (
        source_consumed
        + source_returned
        + source_live
        + source_unreclaimed_expired
        + reclaimed_unissued
        + recycled_consumed
        + recycled_live
        + recycled_expired
    )
    if accounted != root_quantity:
        raise LightwalkerEconomyError(
            f"authority metabolism conservation failed: "
            f"{accounted} != {root_quantity}"
        )

    history_digest = content_address(
        {
            "source_dag_id": dag["dag_id"],
            "source_history_digest": dag["history_digest"],
            "reclaim_ids": sorted(reclaim_by_id),
            "reissued_lease_ids": sorted(lease_by_id),
            "recycled_use_ids": sorted(global_use_ids),
        }
    )

    body = {
        "kind": METABOLISM_KIND,
        "version": METABOLISM_VERSION,
        "authority": "derived-end-to-end-conservation-audit",
        "guild_id": snapshot["guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "resource_entry_id": dag["resource_entry_id"],
        "root_lease_id": dag["root_lease_id"],
        "source_dag_id": dag["dag_id"],
        "source_history_digest": dag["history_digest"],
        "source_observed_cut": int(source_observed_cut),
        "observed_cut": int(observed_cut),
        "recycled_paths": recycled_rows,
        "totals": {
            "root_quantity": root_quantity,
            "source_consumed_quantity": source_consumed,
            "source_returned_quantity": source_returned,
            "source_live_quantity": source_live,
            "source_unreclaimed_expired_quantity": (
                source_unreclaimed_expired
            ),
            "reclaimed_unissued_quantity": reclaimed_unissued,
            "recycled_consumed_quantity": recycled_consumed,
            "recycled_live_quantity": recycled_live,
            "recycled_expired_quantity": recycled_expired,
            "accounted_quantity": accounted,
        },
        "history_digest": history_digest,
        "conservation_status": "BALANCED",
        "spending_authority": "none",
        "laws": [
            "AUTHORITY CHANGES FORM; ACCOUNTABILITY CONSERVES",
            "EXPIRED + RECLAIMED MAY NOT BE DOUBLE COUNTED",
            "RECLAIM != REVIVAL",
            "REISSUE != CONTINUATION",
            "METABOLISM WITNESS != SPENDING AUTHORITY",
            "CONSERVATION != GLOBAL CONSENSUS",
        ],
    }
    return {**body, "metabolism_id": content_address(body)}


def make_metabolism_crossing(
    metabolism: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    if metabolism.get("kind") != METABOLISM_KIND:
        raise LightwalkerEconomyError("invalid metabolism witness")
    if metabolism.get("conservation_status") != "BALANCED":
        raise LightwalkerEconomyError(
            "cannot cross unbalanced metabolism witness"
        )
    if metabolism.get("spending_authority") != "none":
        raise LightwalkerEconomyError(
            "metabolism witness may not carry spending authority"
        )

    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f'guild:{metabolism["guild_id"]}',
        "source_history_head": metabolism["metabolism_id"],
        "parents": [
            metabolism["source_dag_id"],
            metabolism["history_digest"],
        ],
        "declared_kind": "LIGHTWALKER_AUTHORITY_METABOLISM",
        "payload_refs": [
            metabolism["snapshot_id"],
            metabolism["resource_entry_id"],
            metabolism["root_lease_id"],
            metabolism["source_dag_id"],
            metabolism["metabolism_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-authority-metabolism-audit",
                "metabolism_id": metabolism["metabolism_id"],
                "automatic_execution_requested": False,
                "mint_authority_requested": False,
                "history_rewrite_requested": False,
            }
        ),
        "capability_ref": METABOLISM_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "guild_id": metabolism["guild_id"],
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-authority-metabolism/v0",
            "witness_is_not_spending_authority": True,
            "conservation_is_not_consensus": True,
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
        raise LightwalkerEconomyError(
            "authority metabolism crossing failed verification"
        )
    return signed


__all__ = [
    "derive_authority_metabolism",
    "make_metabolism_crossing",
]
