#!/usr/bin/env python3
"""Lightwalker Expiry Reclamation / Authority Compost 001.

Expiry removes live authority. Reclamation is a separate Guild-signed act that
proves one expired leaf, claims exactly its stranded remainder once, and may
reissue that reclaimed capacity as a fresh bounded lease.

Core laws:
    EXPIRY != RETURN
    RECLAIM != REVIVAL
    STRANDED AUTHORITY != LIVE AUTHORITY
    RECLAIMED CAPACITY REQUIRES EVIDENCE
    COMPOST != HISTORY ERASURE
    REISSUE != CONTINUATION
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
from lightwalker_guild_treasury import verify_treasury_snapshot
from lightwalker_lease_lineage import derive_authority_dag
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


RECLAIM_KIND = "ghot.lightwalker.expired-authority-reclaim"
RECLAIM_VERSION = "0"
LEASE_KIND = "ghot.lightwalker.reclaimed-capacity-lease"
LEASE_VERSION = "0"
VIEW_KIND = "ghot.lightwalker.post-reclaim-authority-view"
VIEW_VERSION = "0"

RECLAIM_DOMAIN = "ghot.lightwalker-expired-authority-reclaim-signature/v0"
LEASE_DOMAIN = "ghot.lightwalker-reclaimed-capacity-lease-signature/v0"
RECLAIM_BYTES = b"GHOT-LightwalkerExpiredAuthorityReclaim-v0|"
LEASE_BYTES = b"GHOT-LightwalkerReclaimedCapacityLease-v0|"
RECLAIM_LEASE_CAPABILITY = "ghot.lightwalker-reclaimed-capacity-lease/v0"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nni(value: Any, name: str) -> int:
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


def _dag_node(dag: dict[str, Any], lease_id: str) -> dict[str, Any]:
    for node in dag.get("nodes", []):
        if node.get("lease_id") == lease_id:
            return node
    raise LightwalkerEconomyError("lease is not present in authority DAG")


def verify_reclaim_receipt(
    snapshot: dict[str, Any],
    dag: dict[str, Any],
    receipt: dict[str, Any],
) -> bool:
    try:
        if not verify_treasury_snapshot(snapshot):
            return False
        if receipt.get("kind") != RECLAIM_KIND:
            return False
        if receipt.get("version") != RECLAIM_VERSION:
            return False
        if receipt.get("authority") != "guild-local-expiry-reclaim":
            return False
        if receipt.get("guild_id") != snapshot["guild_id"]:
            return False
        if receipt.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if receipt.get("steward_particular") != snapshot["steward_particular"]:
            return False
        if receipt.get("dag_id") != dag.get("dag_id"):
            return False
        if receipt.get("history_digest") != dag.get("history_digest"):
            return False
        lease_id = receipt.get("expired_lease_id")
        if lease_id not in dag.get("expired_leaf_lease_ids", []):
            return False
        node = _dag_node(dag, str(lease_id))
        if node.get("status") != "LEAF_EXPIRED":
            return False
        if receipt.get("reclaimed_quantity") != node.get("remaining_quantity"):
            return False
        if receipt.get("expired_after_cut") != node.get("expires_after_cut"):
            return False
        if int(receipt.get("observed_cut", -1)) <= int(node["expires_after_cut"]):
            return False
        if receipt.get("status") != "RECLAIMED":
            return False
        if receipt.get("revival_requested") is not False:
            return False
        return _verify_signed(
            receipt,
            id_field="reclaim_id",
            particular_field="steward_particular",
            domain=RECLAIM_DOMAIN,
            byte_domain=RECLAIM_BYTES,
        )
    except Exception:
        return False


class ExpiredAuthorityReclaimStore:
    """Guild-local one-shot reclaim ledger keyed by expired lease ID."""

    def __init__(self, root: Path, *, steward: IdentityKey) -> None:
        self.root = root
        self.steward = steward
        self.reclaims_dir = root / "authority-compost" / "reclaims"
        self.reissues_dir = root / "authority-compost" / "reissues"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _reclaim_path(self, lease_id: str) -> Path:
        return self.reclaims_dir / f"{self._safe(lease_id)}.json"

    def _reissue_path(self, reclaim_id: str) -> Path:
        return self.reissues_dir / f"{self._safe(reclaim_id)}.json"

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

    def reclaim(
        self,
        snapshot: dict[str, Any],
        *,
        root_lease: dict[str, Any],
        descendant_leases: list[dict[str, Any]],
        surrenders: list[dict[str, Any]],
        uses: list[dict[str, Any]],
        expired_lease_id: str,
        observed_cut: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not verify_treasury_snapshot(snapshot):
            raise LightwalkerEconomyError("invalid treasury snapshot")
        if self.steward.particular() != snapshot["steward_particular"]:
            raise LightwalkerEconomyError("local steward does not own treasury")

        dag = derive_authority_dag(
            snapshot,
            root_lease=root_lease,
            descendant_leases=descendant_leases,
            surrenders=surrenders,
            uses=uses,
            observed_cut=observed_cut,
        )
        if expired_lease_id not in dag["expired_leaf_lease_ids"]:
            raise LightwalkerEconomyError(
                "reclaim target is not an expired authority leaf"
            )
        node = _dag_node(dag, expired_lease_id)
        remaining = int(node["remaining_quantity"])
        if remaining <= 0:
            raise LightwalkerEconomyError(
                "expired lease has no stranded authority to reclaim"
            )

        body = {
            "kind": RECLAIM_KIND,
            "version": RECLAIM_VERSION,
            "authority": "guild-local-expiry-reclaim",
            "guild_id": snapshot["guild_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "resource_entry_id": dag["resource_entry_id"],
            "root_lease_id": dag["root_lease_id"],
            "dag_id": dag["dag_id"],
            "history_digest": dag["history_digest"],
            "steward_particular": self.steward.particular(),
            "expired_lease_id": expired_lease_id,
            "expired_after_cut": int(node["expires_after_cut"]),
            "observed_cut": _nni(observed_cut, "observed_cut"),
            "unit": root_lease["leased_measure"]["unit"],
            "reclaimed_quantity": remaining,
            "status": "RECLAIMED",
            "revival_requested": False,
            "laws": [
                "EXPIRY != RETURN",
                "RECLAIM != REVIVAL",
                "STRANDED AUTHORITY != LIVE AUTHORITY",
                "RECLAIMED CAPACITY REQUIRES EVIDENCE",
                "COMPOST != HISTORY ERASURE",
            ],
        }
        receipt = _signed(
            body,
            id_field="reclaim_id",
            signer=self.steward,
            domain=RECLAIM_DOMAIN,
            byte_domain=RECLAIM_BYTES,
        )
        try:
            self._exclusive_write(
                self._reclaim_path(expired_lease_id),
                receipt,
            )
        except FileExistsError as exc:
            raise LightwalkerEconomyError(
                "expired authority leaf already reclaimed"
            ) from exc
        return dag, receipt

    def reissue(
        self,
        snapshot: dict[str, Any],
        dag: dict[str, Any],
        receipt: dict[str, Any],
        *,
        node_id: str,
        node_particular: str,
        issued_at_cut: int,
        expires_after_cut: int,
    ) -> dict[str, Any]:
        if not verify_treasury_snapshot(snapshot):
            raise LightwalkerEconomyError("invalid treasury snapshot")
        if self.steward.particular() != snapshot["steward_particular"]:
            raise LightwalkerEconomyError("local steward does not own treasury")
        if not verify_reclaim_receipt(snapshot, dag, receipt):
            raise LightwalkerEconomyError("invalid reclaim receipt")
        if receipt["guild_id"] != snapshot["guild_id"]:
            raise LightwalkerEconomyError("reclaim belongs to another Guild")
        if receipt["snapshot_id"] != snapshot["snapshot_id"]:
            raise LightwalkerEconomyError("reclaim belongs to another snapshot")

        issued = _nni(issued_at_cut, "issued_at_cut")
        expiry = _nni(expires_after_cut, "expires_after_cut")
        if issued < int(receipt["observed_cut"]):
            raise LightwalkerEconomyError("reissue predates reclaim")
        if expiry < issued:
            raise LightwalkerEconomyError("reissued lease expiry precedes issue")

        body = {
            "kind": LEASE_KIND,
            "version": LEASE_VERSION,
            "authority": "guild-reclaimed-capacity-budget",
            "guild_id": snapshot["guild_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "resource_entry_id": receipt["resource_entry_id"],
            "resource_subject_ref": "reclaimed:" + receipt["resource_entry_id"],
            "steward_particular": self.steward.particular(),
            "source_reclaim_id": receipt["reclaim_id"],
            "reclaimed_from_lease_id": receipt["expired_lease_id"],
            "node_id": _nonempty(node_id, "node_id"),
            "node_particular": _nonempty(node_particular, "node_particular"),
            "leased_measure": {
                "unit": receipt["unit"],
                "quantity": int(receipt["reclaimed_quantity"]),
            },
            "issued_at_cut": issued,
            "expires_after_cut": expiry,
            "status": "ACTIVE",
            "laws": [
                "RECLAIM != REVIVAL",
                "REISSUE != CONTINUATION",
                "RECLAIMED CAPACITY REQUIRES EVIDENCE",
                "COMPOST != HISTORY ERASURE",
            ],
        }
        lease = _signed(
            body,
            id_field="lease_id",
            signer=self.steward,
            domain=LEASE_DOMAIN,
            byte_domain=LEASE_BYTES,
        )
        try:
            self._exclusive_write(
                self._reissue_path(receipt["reclaim_id"]),
                lease,
            )
        except FileExistsError as exc:
            raise LightwalkerEconomyError(
                "reclaim already reissued as fresh authority"
            ) from exc
        return lease


def verify_reclaimed_lease(
    snapshot: dict[str, Any],
    dag: dict[str, Any],
    receipt: dict[str, Any],
    lease: dict[str, Any],
) -> bool:
    try:
        if not verify_treasury_snapshot(snapshot):
            return False
        if not verify_reclaim_receipt(snapshot, dag, receipt):
            return False
        if lease.get("kind") != LEASE_KIND:
            return False
        if lease.get("version") != LEASE_VERSION:
            return False
        if lease.get("authority") != "guild-reclaimed-capacity-budget":
            return False
        if lease.get("guild_id") != snapshot["guild_id"]:
            return False
        if lease.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if lease.get("resource_entry_id") != receipt["resource_entry_id"]:
            return False
        if lease.get("source_reclaim_id") != receipt["reclaim_id"]:
            return False
        if lease.get("reclaimed_from_lease_id") != receipt["expired_lease_id"]:
            return False
        if lease.get("steward_particular") != snapshot["steward_particular"]:
            return False
        if lease.get("leased_measure") != {
            "unit": receipt["unit"],
            "quantity": receipt["reclaimed_quantity"],
        }:
            return False
        if int(lease.get("issued_at_cut", -1)) < int(receipt["observed_cut"]):
            return False
        if int(lease.get("expires_after_cut", -1)) < int(lease["issued_at_cut"]):
            return False
        return _verify_signed(
            lease,
            id_field="lease_id",
            particular_field="steward_particular",
            domain=LEASE_DOMAIN,
            byte_domain=LEASE_BYTES,
        )
    except Exception:
        return False


def make_reclaim_overlay(
    snapshot: dict[str, Any],
    dag: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    reclaimed_by_lease: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if not verify_reclaim_receipt(snapshot, dag, receipt):
            raise LightwalkerEconomyError("invalid reclaim receipt")
        lease_id = receipt["expired_lease_id"]
        if lease_id in reclaimed_by_lease:
            raise LightwalkerEconomyError("duplicate reclaim for expired leaf")
        reclaimed_by_lease[lease_id] = receipt

    expired_total = int(dag["totals"]["expired_leaf_remaining_quantity"])
    reclaimed_total = sum(
        int(item["reclaimed_quantity"])
        for item in reclaimed_by_lease.values()
    )
    if reclaimed_total > expired_total:
        raise LightwalkerEconomyError("reclaim exceeds expired authority")

    body = {
        "kind": VIEW_KIND,
        "version": VIEW_VERSION,
        "authority": "derived-post-reclaim-view",
        "dag_id": dag["dag_id"],
        "history_digest": dag["history_digest"],
        "root_lease_id": dag["root_lease_id"],
        "observed_cut": dag["observed_cut"],
        "consumed_quantity": int(dag["totals"]["consumed_quantity"]),
        "returned_to_guild_quantity": int(
            dag["totals"]["returned_to_guild_quantity"]
        ),
        "live_leaf_remaining_quantity": int(
            dag["totals"]["live_leaf_remaining_quantity"]
        ),
        "expired_leaf_remaining_quantity": expired_total,
        "reclaimed_expired_quantity": reclaimed_total,
        "unreclaimed_expired_quantity": expired_total - reclaimed_total,
        "reclaimed_lease_ids": sorted(reclaimed_by_lease),
        "accounted_quantity": int(dag["totals"]["accounted_quantity"]),
        "laws": [
            "EXPIRY != RETURN",
            "RECLAIM != REVIVAL",
            "COMPOST != HISTORY ERASURE",
        ],
    }
    return {**body, "view_id": content_address(body)}


def make_reclaimed_lease_crossing(
    lease: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    if signer.particular() != lease.get("steward_particular"):
        raise LightwalkerEconomyError("reclaimed lease crossing signer mismatch")
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f'guild:{lease["guild_id"]}',
        "source_history_head": lease["source_reclaim_id"],
        "parents": [
            lease["source_reclaim_id"],
            lease["reclaimed_from_lease_id"],
        ],
        "declared_kind": "LIGHTWALKER_RECLAIMED_CAPACITY_LEASE",
        "payload_refs": [
            lease["snapshot_id"],
            lease["resource_entry_id"],
            lease["source_reclaim_id"],
            lease["reclaimed_from_lease_id"],
            lease["lease_id"],
        ],
        "requested_effect": identity_safe(
            {
                "operation": "consider-reclaimed-capacity-lease",
                "lease_id": lease["lease_id"],
                "expired_lease_revival_requested": False,
                "automatic_consumption_requested": False,
                "ownership_transfer_requested": False,
            }
        ),
        "capability_ref": RECLAIM_LEASE_CAPABILITY,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "node_particular": lease["node_particular"],
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-reclaimed-capacity-lease/v0",
            "reclaim_is_not_revival": True,
            "compost_preserves_history": True,
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
        raise LightwalkerEconomyError("reclaimed lease crossing failed")
    return signed


__all__ = [
    "ExpiredAuthorityReclaimStore",
    "make_reclaim_overlay",
    "make_reclaimed_lease_crossing",
    "verify_reclaim_receipt",
    "verify_reclaimed_lease",
]
