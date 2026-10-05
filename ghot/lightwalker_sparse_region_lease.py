#!/usr/bin/env python3
"""Lightwalker Exact Region Assignment / Sparse Work Lease 001.

Makes exact missing work regions first-class delegated authority. A sparse
region lease says which root regions a node may work on; it does not grant the
node compute capacity, ownership, settlement authority, or authority over any
other region.

Core laws:
    QUANTITY != REGION AUTHORITY
    REGION ASSIGNMENT != OWNERSHIP
    REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY
    ASSIGNMENT MUST NAME EXACT MISSING WORK
    REGION LEASE != REGION RESULT
    PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS
    REASSIGNMENT MAY NOT DUPLICATE LIVE REGION AUTHORITY
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ice_cube import render_pgm
from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_authorization import verify_execution_receipt
from lightwalker_guild_reservation import verify_finalization
from lightwalker_work_region_salvage import (
    derive_non_overlapping_region_salvage,
    missing_region_ids,
    region_claim_set,
    verify_salvaged_region_admission,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


MISSING_KIND = "ghot.lightwalker.exact-missing-region-set"
MISSING_VERSION = "0"
LEASE_KIND = "ghot.lightwalker.sparse-region-work-lease"
LEASE_VERSION = "0"
USE_KIND = "ghot.lightwalker.sparse-region-work-use"
USE_VERSION = "0"
RELEASE_KIND = "ghot.lightwalker.sparse-region-work-release"
RELEASE_VERSION = "0"
CLOSE_KIND = "ghot.lightwalker.sparse-region-work-close"
CLOSE_VERSION = "0"
EXECUTION_KIND = "ghot.lightwalker.sparse-region-execution-evidence"
EXECUTION_VERSION = "0"
COMPOSITION_KIND = "ghot.lightwalker.sparse-region-composed-completion"
COMPOSITION_VERSION = "0"

LEASE_DOMAIN = "ghot.lightwalker-sparse-region-work-lease-signature/v0"
USE_DOMAIN = "ghot.lightwalker-sparse-region-work-use-signature/v0"
RELEASE_DOMAIN = "ghot.lightwalker-sparse-region-work-release-signature/v0"
CLOSE_DOMAIN = "ghot.lightwalker-sparse-region-work-close-signature/v0"

LEASE_BYTES = b"GHOT-LightwalkerSparseRegionWorkLease-v0|"
USE_BYTES = b"GHOT-LightwalkerSparseRegionWorkUse-v0|"
RELEASE_BYTES = b"GHOT-LightwalkerSparseRegionWorkRelease-v0|"
CLOSE_BYTES = b"GHOT-LightwalkerSparseRegionWorkClose-v0|"


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


def _region_order(plan: dict[str, Any]) -> dict[str, int]:
    rows = plan.get("regions")
    if not isinstance(rows, list):
        raise LightwalkerEconomyError("region plan missing regions")
    order = {row["region_id"]: int(row["index"]) for row in rows}
    if len(order) != len(rows):
        raise LightwalkerEconomyError("region plan has duplicate region ids")
    return order


def _ordered_subset(
    plan: dict[str, Any],
    region_ids: list[str],
) -> list[str]:
    order = _region_order(plan)
    if len(region_ids) != len(set(region_ids)):
        raise LightwalkerEconomyError("duplicate region id")
    if any(region_id not in order for region_id in region_ids):
        raise LightwalkerEconomyError("region outside root plan")
    return sorted(region_ids, key=lambda region_id: order[region_id])


def derive_exact_missing_region_set(
    work: dict[str, Any],
    plan: dict[str, Any],
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_coverage: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
    winning_bundle: dict[str, Any],
    losing_bundle: dict[str, Any],
    nonoverlap: dict[str, Any],
    admission: dict[str, Any],
) -> dict[str, Any]:
    expected_nonoverlap = derive_non_overlapping_region_salvage(
        work,
        plan,
        parent_node,
        parent_checkpoint,
        parent_coverage,
        fork,
        resolution,
        winning_bundle,
        losing_bundle,
    )
    if nonoverlap != expected_nonoverlap:
        raise LightwalkerEconomyError("non-overlap evidence mismatch")
    if not verify_salvaged_region_admission(
        work,
        plan,
        parent_node,
        parent_checkpoint,
        parent_coverage,
        fork,
        resolution,
        winning_bundle,
        losing_bundle,
        nonoverlap,
        admission,
    ):
        raise LightwalkerEconomyError("invalid salvaged-region admission")

    winning_receipt = winning_bundle["receipt"]
    missing = missing_region_ids(
        plan,
        parent_coverage,
        winning_receipt,
        admission,
    )
    accepted = _ordered_subset(
        plan,
        [
            *[row["region_id"] for row in parent_coverage["region_claims"]],
            *[row["region_id"] for row in winning_receipt["region_claims"]],
            *list(admission["admitted_region_ids"]),
        ],
    )
    unit = plan["operational_accounting_policy"]["unit"]
    per_region = int(
        plan["operational_accounting_policy"]["quantity_per_region"]
    )
    body = {
        "kind": MISSING_KIND,
        "version": MISSING_VERSION,
        "authority": "derived-exact-missing-work-observation",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "continuation_lineage_id": plan["continuation_lineage_id"],
        "work_address": plan["work_address"],
        "parent_checkpoint_id": parent_checkpoint["recursive_checkpoint_id"],
        "recursive_branch_resolution_id": resolution[
            "recursive_branch_resolution_id"
        ],
        "salvaged_region_admission_id": admission[
            "salvaged_region_admission_id"
        ],
        "accepted_region_count": len(accepted),
        "accepted_region_ids": accepted,
        "accepted_coverage_digest": content_address({
            "pixel_region_plan_id": plan["pixel_region_plan_id"],
            "accepted_region_ids": accepted,
        }),
        "missing_region_count": len(missing),
        "missing_region_ids": missing,
        "missing_region_set_digest": content_address({
            "pixel_region_plan_id": plan["pixel_region_plan_id"],
            "missing_region_ids": missing,
        }),
        "missing_work_measure": {
            "unit": unit,
            "quantity": per_region * len(missing),
        },
        "assignment_authority": "none",
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "QUANTITY != REGION AUTHORITY",
            "ASSIGNMENT MUST NAME EXACT MISSING WORK",
            "MISSING SET != ASSIGNMENT",
        ],
    }
    return {
        **body,
        "exact_missing_region_set_id": content_address(body),
    }


def verify_exact_missing_region_set(
    work: dict[str, Any],
    plan: dict[str, Any],
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_coverage: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
    winning_bundle: dict[str, Any],
    losing_bundle: dict[str, Any],
    nonoverlap: dict[str, Any],
    admission: dict[str, Any],
    missing_set: dict[str, Any],
) -> bool:
    try:
        expected = derive_exact_missing_region_set(
            work,
            plan,
            parent_node,
            parent_checkpoint,
            parent_coverage,
            fork,
            resolution,
            winning_bundle,
            losing_bundle,
            nonoverlap,
            admission,
        )
        return missing_set == expected
    except Exception:
        return False


def verify_sparse_region_lease(
    missing_set: dict[str, Any],
    lease: dict[str, Any],
) -> bool:
    try:
        if lease.get("kind") != LEASE_KIND:
            return False
        if lease.get("version") != LEASE_VERSION:
            return False
        if lease.get("authority") != "owner-local-sparse-region-assignment":
            return False
        if lease.get("exact_missing_region_set_id") != missing_set[
            "exact_missing_region_set_id"
        ]:
            return False
        if lease.get("pixel_region_plan_id") != missing_set[
            "pixel_region_plan_id"
        ]:
            return False
        if lease.get("work_address") != missing_set["work_address"]:
            return False
        if lease.get("accepted_coverage_digest") != missing_set[
            "accepted_coverage_digest"
        ]:
            return False
        if lease.get("missing_region_set_digest") != missing_set[
            "missing_region_set_digest"
        ]:
            return False
        region_ids = lease.get("assigned_region_ids")
        if not isinstance(region_ids, list) or not region_ids:
            return False
        if len(region_ids) != len(set(region_ids)):
            return False
        if not set(region_ids) <= set(missing_set["missing_region_ids"]):
            return False
        if lease.get("assigned_region_count") != len(region_ids):
            return False
        if lease.get("region_set_digest") != content_address({
            "pixel_region_plan_id": missing_set["pixel_region_plan_id"],
            "assigned_region_ids": region_ids,
        }):
            return False
        measure = lease.get("assigned_work_measure")
        if not isinstance(measure, dict):
            return False
        if measure.get("unit") != missing_set["missing_work_measure"]["unit"]:
            return False
        missing_count = int(missing_set["missing_region_count"])
        missing_quantity = int(missing_set["missing_work_measure"]["quantity"])
        if missing_count <= 0:
            return False
        per_region = missing_quantity // missing_count
        if per_region * missing_count != missing_quantity:
            return False
        if int(measure.get("quantity", -1)) != per_region * len(region_ids):
            return False
        if lease.get("compute_capacity_authority") != "none":
            return False
        if lease.get("ownership_transfer") is not False:
            return False
        if lease.get("status") != "ACTIVE":
            return False
        if int(lease["expires_after_cut"]) < int(lease["issued_at_cut"]):
            return False
        return _verify_signed(
            lease,
            id_field="sparse_region_lease_id",
            particular_field="assigner_particular",
            domain=LEASE_DOMAIN,
            byte_domain=LEASE_BYTES,
        )
    except Exception:
        return False


class SparseRegionLeaseIssuer:
    """Owner-local exact region assignment ledger.

    Active leases may not overlap. Regions consumed by closed leases may never
    be reissued from the same missing-set observation. Returned regions may be
    assigned again.
    """

    def __init__(self, root: Path, *, assigner: IdentityKey) -> None:
        self.root = root
        self.assigner = assigner
        self.leases_dir = root / "sparse-region-leases" / "leases"
        self.closes_dir = root / "sparse-region-leases" / "closes"
        self.lock_path = root / "sparse-region-leases" / "ledger.lock"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _lease_path(self, lease_id: str) -> Path:
        return self.leases_dir / f"{self._safe(lease_id)}.json"

    def _close_path(self, lease_id: str) -> Path:
        return self.closes_dir / f"{self._safe(lease_id)}.json"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _write_exclusive(
        self,
        path: Path,
        value: dict[str, Any],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(
                fd,
                (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
        finally:
            os.close(fd)

    def _all_leases(
        self,
        missing_set_id: str,
    ) -> list[dict[str, Any]]:
        if not self.leases_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in self.leases_dir.glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("exact_missing_region_set_id") == missing_set_id:
                rows.append(value)
        return rows

    def _close_record(
        self,
        lease_id: str,
    ) -> dict[str, Any] | None:
        path = self._close_path(lease_id)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError("invalid sparse lease close")
        return value

    def issue(
        self,
        missing_set: dict[str, Any],
        *,
        pixel_region_plan_id: str,
        node_id: str,
        node_particular: str,
        region_ids: list[str],
        issued_at_cut: int,
        expires_after_cut: int,
    ) -> dict[str, Any]:
        if pixel_region_plan_id != missing_set["pixel_region_plan_id"]:
            raise LightwalkerEconomyError("region plan mismatch")
        ordered_missing = list(missing_set["missing_region_ids"])
        order = {
            region_id: index
            for index, region_id in enumerate(ordered_missing)
        }
        if len(region_ids) != len(set(region_ids)) or not region_ids:
            raise LightwalkerEconomyError(
                "sparse lease needs unique nonempty regions"
            )
        if any(region_id not in order for region_id in region_ids):
            raise LightwalkerEconomyError(
                "assignment includes non-missing region"
            )
        assigned = sorted(region_ids, key=lambda region_id: order[region_id])
        issued = int(issued_at_cut)
        expiry = int(expires_after_cut)
        if issued < 0 or expiry < issued:
            raise LightwalkerEconomyError("invalid lease cut range")

        missing_count = int(missing_set["missing_region_count"])
        missing_quantity = int(missing_set["missing_work_measure"]["quantity"])
        if missing_count <= 0 or missing_quantity % missing_count:
            raise LightwalkerEconomyError("non-integral region accounting")
        per_region = missing_quantity // missing_count

        with self._locked():
            leases = self._all_leases(
                missing_set["exact_missing_region_set_id"]
            )
            active_region_ids: set[str] = set()
            consumed_region_ids: set[str] = set()
            for prior in leases:
                close = self._close_record(prior["sparse_region_lease_id"])
                if close is None:
                    active_region_ids.update(prior["assigned_region_ids"])
                else:
                    consumed_region_ids.update(
                        close["consumed_region_ids"]
                    )
            requested = set(assigned)
            if requested & active_region_ids:
                raise LightwalkerEconomyError(
                    "assignment overlaps live region authority"
                )
            if requested & consumed_region_ids:
                raise LightwalkerEconomyError(
                    "assignment reuses already consumed region"
                )

            body = {
                "kind": LEASE_KIND,
                "version": LEASE_VERSION,
                "authority": "owner-local-sparse-region-assignment",
                "exact_missing_region_set_id": missing_set[
                    "exact_missing_region_set_id"
                ],
                "pixel_region_plan_id": pixel_region_plan_id,
                "continuation_lineage_id": missing_set[
                    "continuation_lineage_id"
                ],
                "work_address": missing_set["work_address"],
                "accepted_coverage_digest": missing_set[
                    "accepted_coverage_digest"
                ],
                "missing_region_set_digest": missing_set[
                    "missing_region_set_digest"
                ],
                "assigner_particular": self.assigner.particular(),
                "node_id": str(node_id),
                "node_particular": str(node_particular),
                "assigned_region_count": len(assigned),
                "assigned_region_ids": assigned,
                "region_set_digest": content_address({
                    "pixel_region_plan_id": pixel_region_plan_id,
                    "assigned_region_ids": assigned,
                }),
                "assigned_work_measure": {
                    "unit": missing_set["missing_work_measure"]["unit"],
                    "quantity": per_region * len(assigned),
                },
                "issued_at_cut": issued,
                "expires_after_cut": expiry,
                "status": "ACTIVE",
                "compute_capacity_authority": "none",
                "ownership_transfer": False,
                "settlement_authority": "none",
                "laws": [
                    "QUANTITY != REGION AUTHORITY",
                    "REGION ASSIGNMENT != OWNERSHIP",
                    "REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY",
                    "ASSIGNMENT MUST NAME EXACT MISSING WORK",
                    "REASSIGNMENT MAY NOT DUPLICATE LIVE REGION AUTHORITY",
                ],
            }
            lease = _signed(
                body,
                id_field="sparse_region_lease_id",
                signer=self.assigner,
                domain=LEASE_DOMAIN,
                byte_domain=LEASE_BYTES,
            )
            self._write_exclusive(
                self._lease_path(lease["sparse_region_lease_id"]),
                lease,
            )
            return lease

    def close(
        self,
        missing_set: dict[str, Any],
        lease: dict[str, Any],
        release: dict[str, Any],
        *,
        observed_cut: int,
    ) -> dict[str, Any]:
        if not verify_sparse_region_lease(missing_set, lease):
            raise LightwalkerEconomyError("invalid sparse region lease")
        if lease["assigner_particular"] != self.assigner.particular():
            raise LightwalkerEconomyError("assigner does not own lease")
        if not verify_sparse_region_release(lease, release):
            raise LightwalkerEconomyError("invalid sparse region release")
        with self._locked():
            if self._close_record(lease["sparse_region_lease_id"]) is not None:
                raise LightwalkerEconomyError("sparse lease already closed")
            body = {
                "kind": CLOSE_KIND,
                "version": CLOSE_VERSION,
                "authority": "owner-local-sparse-region-close",
                "sparse_region_lease_id": lease["sparse_region_lease_id"],
                "exact_missing_region_set_id": lease[
                    "exact_missing_region_set_id"
                ],
                "assigner_particular": self.assigner.particular(),
                "node_particular": lease["node_particular"],
                "consumed_region_ids": list(release["consumed_region_ids"]),
                "returned_region_ids": list(release["returned_region_ids"]),
                "consumed_work_measure": release["consumed_work_measure"],
                "returned_work_measure": release["returned_work_measure"],
                "node_release_id": release["sparse_region_release_id"],
                "observed_cut": int(observed_cut),
                "status": "CLOSED",
                "history_deleted": False,
                "laws": [
                    "REGION LEASE != REGION RESULT",
                    "PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS",
                    "RETURN != HISTORY DELETION",
                ],
            }
            close = _signed(
                body,
                id_field="sparse_region_close_id",
                signer=self.assigner,
                domain=CLOSE_DOMAIN,
                byte_domain=CLOSE_BYTES,
            )
            self._write_exclusive(
                self._close_path(lease["sparse_region_lease_id"]),
                close,
            )
            return close


def verify_sparse_region_use(
    work: dict[str, Any],
    plan: dict[str, Any],
    missing_set: dict[str, Any],
    lease: dict[str, Any],
    use: dict[str, Any],
) -> bool:
    try:
        if not verify_sparse_region_lease(missing_set, lease):
            return False
        if use.get("kind") != USE_KIND or use.get("version") != USE_VERSION:
            return False
        if use.get("authority") != "node-local-sparse-region-result":
            return False
        if use.get("sparse_region_lease_id") != lease[
            "sparse_region_lease_id"
        ]:
            return False
        if use.get("node_particular") != lease["node_particular"]:
            return False
        region_ids = use.get("consumed_region_ids")
        if not isinstance(region_ids, list) or not region_ids:
            return False
        if len(region_ids) != len(set(region_ids)):
            return False
        if not set(region_ids) <= set(lease["assigned_region_ids"]):
            return False
        claims = use.get("region_claims")
        if not isinstance(claims, list):
            return False
        expected_claim_set = region_claim_set(
            work,
            plan,
            region_ids=region_ids,
            executor_particular=lease["node_particular"],
        )
        if claims != expected_claim_set["region_claims"]:
            return False
        if use.get("region_claim_set_id") != expected_claim_set[
            "region_claim_set_id"
        ]:
            return False
        if use.get("region_count") != len(region_ids):
            return False
        if use.get("result_ref") != expected_claim_set[
            "region_claim_set_id"
        ]:
            return False
        if use.get("compute_capacity_authority") != "external-local-evidence":
            return False
        if use.get("continuation_authority") != "none":
            return False
        return _verify_signed(
            use,
            id_field="sparse_region_use_id",
            particular_field="node_particular",
            domain=USE_DOMAIN,
            byte_domain=USE_BYTES,
        )
    except Exception:
        return False


class SparseRegionLeaseBudget:
    """Node-local exact region spend ledger."""

    def __init__(self, root: Path, *, node: IdentityKey) -> None:
        self.root = root
        self.node = node
        self.uses_dir = root / "sparse-region-budget" / "uses"
        self.lock_path = root / "sparse-region-budget" / "budget.lock"

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

    def _uses(
        self,
        lease_id: str,
    ) -> list[dict[str, Any]]:
        if not self.uses_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in self.uses_dir.glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("sparse_region_lease_id") == lease_id:
                rows.append(value)
        return rows

    def _write_exclusive(
        self,
        path: Path,
        value: dict[str, Any],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(
                fd,
                (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
        finally:
            os.close(fd)

    def state(
        self,
        missing_set: dict[str, Any],
        lease: dict[str, Any],
    ) -> dict[str, Any]:
        if self.node.particular() != lease["node_particular"]:
            raise LightwalkerEconomyError("node does not hold sparse lease")
        if not verify_sparse_region_lease(missing_set, lease):
            raise LightwalkerEconomyError("invalid sparse region lease")
        with self._locked():
            uses = self._uses(lease["sparse_region_lease_id"])
            consumed: set[str] = set()
            for use in uses:
                consumed.update(use["consumed_region_ids"])
            assigned = list(lease["assigned_region_ids"])
            returned = [
                region_id for region_id in assigned if region_id not in consumed
            ]
            return {
                "sparse_region_lease_id": lease["sparse_region_lease_id"],
                "assigned_region_ids": assigned,
                "consumed_region_ids": [
                    region_id for region_id in assigned if region_id in consumed
                ],
                "remaining_region_ids": returned,
                "use_ids": sorted(
                    use["sparse_region_use_id"] for use in uses
                ),
            }

    def record_execution(
        self,
        work: dict[str, Any],
        plan: dict[str, Any],
        missing_set: dict[str, Any],
        lease: dict[str, Any],
        *,
        region_ids: list[str],
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        execution: dict[str, Any],
        finalization: dict[str, Any],
        observed_cut: int,
    ) -> dict[str, Any]:
        if self.node.particular() != lease["node_particular"]:
            raise LightwalkerEconomyError("node does not hold sparse lease")
        if not verify_sparse_region_lease(missing_set, lease):
            raise LightwalkerEconomyError("invalid sparse region lease")
        cut = int(observed_cut)
        if cut < int(lease["issued_at_cut"]):
            raise LightwalkerEconomyError("region use predates lease")
        if cut > int(lease["expires_after_cut"]):
            raise LightwalkerEconomyError("sparse region lease expired")
        assigned = list(lease["assigned_region_ids"])
        order = {
            region_id: index for index, region_id in enumerate(assigned)
        }
        if len(region_ids) != len(set(region_ids)) or not region_ids:
            raise LightwalkerEconomyError(
                "region execution needs unique nonempty ids"
            )
        if any(region_id not in order for region_id in region_ids):
            raise LightwalkerEconomyError(
                "execution includes region outside sparse lease"
            )
        selected = sorted(region_ids, key=lambda region_id: order[region_id])

        if not verify_execution_receipt(
            snapshot, proposal, authorization, execution
        ):
            raise LightwalkerEconomyError("invalid local capacity execution")
        if not verify_finalization(reservation, finalization):
            raise LightwalkerEconomyError("invalid local capacity finalization")
        if execution.get("success") is not True:
            raise LightwalkerEconomyError("local capacity execution failed")
        if finalization.get("status") != "CONSUMED":
            raise LightwalkerEconomyError("local capacity not consumed")
        if execution["executor_particular"] != self.node.particular():
            raise LightwalkerEconomyError("capacity executor is not sparse holder")
        if proposal.get("purpose_ref") != lease["sparse_region_lease_id"]:
            raise LightwalkerEconomyError(
                "capacity proposal is not bound to sparse lease"
            )
        claim_set = region_claim_set(
            work,
            plan,
            region_ids=selected,
            executor_particular=self.node.particular(),
        )
        if execution.get("result_ref") != claim_set["region_claim_set_id"]:
            raise LightwalkerEconomyError(
                "capacity execution result does not bind exact region set"
            )
        consumed_measure = execution["consumed_measure"]
        per_region = (
            int(lease["assigned_work_measure"]["quantity"])
            // int(lease["assigned_region_count"])
        )
        if int(consumed_measure["quantity"]) != per_region * len(selected):
            raise LightwalkerEconomyError(
                "capacity quantity does not match exact region count"
            )

        with self._locked():
            prior = self._uses(lease["sparse_region_lease_id"])
            already = {
                region_id
                for use in prior
                for region_id in use["consumed_region_ids"]
            }
            if set(selected) & already:
                raise LightwalkerEconomyError(
                    "region already consumed under sparse lease"
                )
            body = {
                "kind": USE_KIND,
                "version": USE_VERSION,
                "authority": "node-local-sparse-region-result",
                "sparse_region_lease_id": lease["sparse_region_lease_id"],
                "exact_missing_region_set_id": missing_set[
                    "exact_missing_region_set_id"
                ],
                "pixel_region_plan_id": plan["pixel_region_plan_id"],
                "work_address": plan["work_address"],
                "node_particular": self.node.particular(),
                "region_count": len(selected),
                "consumed_region_ids": selected,
                "region_claim_set_id": claim_set["region_claim_set_id"],
                "region_claims": claim_set["region_claims"],
                "capacity_proposal_id": proposal["proposal_id"],
                "capacity_authorization_id": authorization["authorization_id"],
                "capacity_reservation_id": reservation["reservation_id"],
                "capacity_execution_receipt_id": execution[
                    "execution_receipt_id"
                ],
                "capacity_finalization_id": finalization["finalization_id"],
                "consumed_work_measure": consumed_measure,
                "result_ref": claim_set["region_claim_set_id"],
                "observed_cut": cut,
                "compute_capacity_authority": "external-local-evidence",
                "continuation_authority": "none",
                "settlement_authority": "none",
                "laws": [
                    "REGION LEASE != REGION RESULT",
                    "REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY",
                    "PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS",
                ],
            }
            use = _signed(
                body,
                id_field="sparse_region_use_id",
                signer=self.node,
                domain=USE_DOMAIN,
                byte_domain=USE_BYTES,
            )
            self._write_exclusive(
                self.uses_dir
                / f"{self._safe(use['sparse_region_use_id'])}.json",
                use,
            )
            return use

    def release(
        self,
        missing_set: dict[str, Any],
        lease: dict[str, Any],
        *,
        observed_cut: int,
    ) -> dict[str, Any]:
        state = self.state(missing_set, lease)
        missing_count = int(missing_set["missing_region_count"])
        missing_quantity = int(missing_set["missing_work_measure"]["quantity"])
        per_region = missing_quantity // missing_count
        consumed = state["consumed_region_ids"]
        returned = state["remaining_region_ids"]
        body = {
            "kind": RELEASE_KIND,
            "version": RELEASE_VERSION,
            "authority": "node-local-sparse-region-release",
            "sparse_region_lease_id": lease["sparse_region_lease_id"],
            "node_particular": self.node.particular(),
            "consumed_region_ids": consumed,
            "returned_region_ids": returned,
            "consumed_work_measure": {
                "unit": missing_set["missing_work_measure"]["unit"],
                "quantity": per_region * len(consumed),
            },
            "returned_work_measure": {
                "unit": missing_set["missing_work_measure"]["unit"],
                "quantity": per_region * len(returned),
            },
            "use_ids": state["use_ids"],
            "observed_cut": int(observed_cut),
            "status": "RELEASED",
            "history_deleted": False,
            "laws": [
                "PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS",
                "RETURN != HISTORY DELETION",
            ],
        }
        return _signed(
            body,
            id_field="sparse_region_release_id",
            signer=self.node,
            domain=RELEASE_DOMAIN,
            byte_domain=RELEASE_BYTES,
        )


def verify_sparse_region_release(
    lease: dict[str, Any],
    release: dict[str, Any],
) -> bool:
    try:
        if release.get("kind") != RELEASE_KIND:
            return False
        if release.get("version") != RELEASE_VERSION:
            return False
        if release.get("authority") != "node-local-sparse-region-release":
            return False
        if release.get("sparse_region_lease_id") != lease[
            "sparse_region_lease_id"
        ]:
            return False
        if release.get("node_particular") != lease["node_particular"]:
            return False
        consumed = release.get("consumed_region_ids")
        returned = release.get("returned_region_ids")
        if not isinstance(consumed, list) or not isinstance(returned, list):
            return False
        if set(consumed) & set(returned):
            return False
        if consumed + returned != lease["assigned_region_ids"]:
            # Both lists preserve lease order, so concatenation is only valid
            # when consumption is a prefix. Accept general partitions below.
            if set(consumed) | set(returned) != set(lease["assigned_region_ids"]):
                return False
        if len(consumed) + len(returned) != len(
            lease["assigned_region_ids"]
        ):
            return False
        unit = lease["assigned_work_measure"]["unit"]
        cq = release.get("consumed_work_measure")
        rq = release.get("returned_work_measure")
        if not isinstance(cq, dict) or not isinstance(rq, dict):
            return False
        if cq.get("unit") != unit or rq.get("unit") != unit:
            return False
        if int(cq["quantity"]) + int(rq["quantity"]) != int(
            lease["assigned_work_measure"]["quantity"]
        ):
            return False
        return _verify_signed(
            release,
            id_field="sparse_region_release_id",
            particular_field="node_particular",
            domain=RELEASE_DOMAIN,
            byte_domain=RELEASE_BYTES,
        )
    except Exception:
        return False


def verify_sparse_region_close(
    missing_set: dict[str, Any],
    lease: dict[str, Any],
    close: dict[str, Any],
) -> bool:
    try:
        if not verify_sparse_region_lease(missing_set, lease):
            return False
        if close.get("kind") != CLOSE_KIND:
            return False
        if close.get("version") != CLOSE_VERSION:
            return False
        if close.get("authority") != "owner-local-sparse-region-close":
            return False
        if close.get("sparse_region_lease_id") != lease[
            "sparse_region_lease_id"
        ]:
            return False
        if close.get("exact_missing_region_set_id") != missing_set[
            "exact_missing_region_set_id"
        ]:
            return False
        if close.get("assigner_particular") != lease["assigner_particular"]:
            return False
        if close.get("node_particular") != lease["node_particular"]:
            return False
        consumed = close.get("consumed_region_ids")
        returned = close.get("returned_region_ids")
        if not isinstance(consumed, list) or not isinstance(returned, list):
            return False
        if set(consumed) & set(returned):
            return False
        if set(consumed) | set(returned) != set(
            lease["assigned_region_ids"]
        ):
            return False
        if close.get("status") != "CLOSED":
            return False
        if close.get("history_deleted") is not False:
            return False
        return _verify_signed(
            close,
            id_field="sparse_region_close_id",
            particular_field="assigner_particular",
            domain=CLOSE_DOMAIN,
            byte_domain=CLOSE_BYTES,
        )
    except Exception:
        return False


def derive_sparse_region_execution_evidence(
    work: dict[str, Any],
    plan: dict[str, Any],
    missing_set: dict[str, Any],
    bundles: list[dict[str, Any]],
) -> dict[str, Any]:
    if not bundles:
        raise LightwalkerEconomyError("sparse execution needs lease bundles")
    all_claims: dict[str, dict[str, Any]] = {}
    lease_ids: list[str] = []
    use_ids: list[str] = []
    close_ids: list[str] = []
    total_capacity = 0
    for bundle in bundles:
        required = {
            "lease",
            "use",
            "release",
            "close",
            "snapshot",
            "proposal",
            "authorization",
            "reservation",
            "execution",
            "finalization",
        }
        if set(bundle) != required:
            raise LightwalkerEconomyError("invalid sparse execution bundle")
        lease = bundle["lease"]
        use = bundle["use"]
        release = bundle["release"]
        close = bundle["close"]
        if not verify_sparse_region_lease(missing_set, lease):
            raise LightwalkerEconomyError("invalid sparse lease in evidence")
        if not verify_sparse_region_use(
            work, plan, missing_set, lease, use
        ):
            raise LightwalkerEconomyError("invalid sparse use in evidence")
        if not verify_sparse_region_release(lease, release):
            raise LightwalkerEconomyError("invalid sparse release in evidence")
        if not verify_sparse_region_close(missing_set, lease, close):
            raise LightwalkerEconomyError("invalid sparse close in evidence")
        if use["sparse_region_use_id"] not in release["use_ids"]:
            raise LightwalkerEconomyError(
                "release does not retain sparse use history"
            )
        if set(use["consumed_region_ids"]) - set(
            close["consumed_region_ids"]
        ):
            raise LightwalkerEconomyError(
                "close omits consumed sparse regions"
            )
        if not verify_execution_receipt(
            bundle["snapshot"],
            bundle["proposal"],
            bundle["authorization"],
            bundle["execution"],
        ):
            raise LightwalkerEconomyError(
                "invalid local capacity execution in sparse evidence"
            )
        if not verify_finalization(
            bundle["reservation"],
            bundle["finalization"],
        ):
            raise LightwalkerEconomyError(
                "invalid local capacity finalization in sparse evidence"
            )
        if bundle["execution"]["execution_receipt_id"] != use[
            "capacity_execution_receipt_id"
        ]:
            raise LightwalkerEconomyError(
                "sparse use/capacity execution mismatch"
            )
        for claim in use["region_claims"]:
            region_id = claim["region_id"]
            if region_id in all_claims:
                raise LightwalkerEconomyError(
                    "region consumed by more than one sparse lease"
                )
            all_claims[region_id] = claim
        lease_ids.append(lease["sparse_region_lease_id"])
        use_ids.append(use["sparse_region_use_id"])
        close_ids.append(close["sparse_region_close_id"])
        total_capacity += int(
            use["consumed_work_measure"]["quantity"]
        )

    missing_ids = list(missing_set["missing_region_ids"])
    if set(all_claims) != set(missing_ids):
        raise LightwalkerEconomyError(
            "sparse execution does not cover exact missing set"
        )
    order = {
        region_id: index
        for index, region_id in enumerate(missing_ids)
    }
    claims = sorted(
        all_claims.values(),
        key=lambda claim: order[claim["region_id"]],
    )
    if total_capacity != int(missing_set["missing_work_measure"]["quantity"]):
        raise LightwalkerEconomyError(
            "sparse capacity consumption does not match missing work"
        )
    body = {
        "kind": EXECUTION_KIND,
        "version": EXECUTION_VERSION,
        "authority": "derived-sparse-region-execution-evidence",
        "exact_missing_region_set_id": missing_set[
            "exact_missing_region_set_id"
        ],
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "work_address": plan["work_address"],
        "lease_ids": lease_ids,
        "use_ids": use_ids,
        "close_ids": close_ids,
        "region_count": len(claims),
        "region_claims": claims,
        "consumed_work_measure": {
            "unit": missing_set["missing_work_measure"]["unit"],
            "quantity": total_capacity,
        },
        "all_missing_regions_satisfied": True,
        "region_authority_duplicated": False,
        "compute_capacity_authority": "none",
        "continuation_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "QUANTITY != REGION AUTHORITY",
            "REGION LEASE != REGION RESULT",
            "REASSIGNMENT MAY NOT DUPLICATE LIVE REGION AUTHORITY",
        ],
    }
    return {
        **body,
        "sparse_region_execution_evidence_id": content_address(body),
    }


def derive_sparse_region_composed_completion(
    work: dict[str, Any],
    plan: dict[str, Any],
    parent_coverage: dict[str, Any],
    winning_receipt: dict[str, Any],
    admission: dict[str, Any],
    missing_set: dict[str, Any],
    sparse_execution: dict[str, Any],
) -> dict[str, Any]:
    if sparse_execution.get("kind") != EXECUTION_KIND:
        raise LightwalkerEconomyError("invalid sparse execution evidence")
    if sparse_execution.get("exact_missing_region_set_id") != missing_set[
        "exact_missing_region_set_id"
    ]:
        raise LightwalkerEconomyError("sparse execution missing-set mismatch")
    groups = [
        parent_coverage["region_claims"],
        winning_receipt["region_claims"],
        admission["admitted_region_claims"],
        sparse_execution["region_claims"],
    ]
    seen: dict[str, dict[str, Any]] = {}
    for group in groups:
        for claim in group:
            region_id = claim["region_id"]
            if region_id in seen:
                raise LightwalkerEconomyError(
                    "region credited more than once in sparse composition"
                )
            seen[region_id] = claim
    all_ids = [row["region_id"] for row in plan["regions"]]
    if set(seen) != set(all_ids):
        raise LightwalkerEconomyError(
            "sparse composition does not cover exact root plan"
        )
    pixels = bytearray(int(plan["region_count"]))
    for row in plan["regions"]:
        pixels[int(row["index"])] = int(seen[row["region_id"]]["value"])
    assembled = (
        f"P5\n{plan['width']} {plan['height']}\n255\n".encode("ascii")
        + bytes(pixels)
    )
    canonical, _ = render_pgm(work)
    if assembled != canonical:
        raise LightwalkerEconomyError(
            "sparse composition differs from canonical render"
        )
    body = {
        "kind": COMPOSITION_KIND,
        "version": COMPOSITION_VERSION,
        "authority": "derived-sparse-region-completion",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "continuation_lineage_id": plan["continuation_lineage_id"],
        "work_address": plan["work_address"],
        "canonical_render_address": content_address(canonical),
        "accepted_coverage_digest": missing_set["accepted_coverage_digest"],
        "missing_region_set_digest": missing_set["missing_region_set_digest"],
        "pre_fork_region_count": parent_coverage["region_count"],
        "winning_region_count": winning_receipt["region_count"],
        "salvaged_region_count": admission[
            "root_region_coverage_credit_count"
        ],
        "sparse_executed_region_count": sparse_execution["region_count"],
        "authoritative_region_coverage_count": len(seen),
        "root_region_double_counted": False,
        "work_complete": True,
        "sparse_assignment_authority_consumed": True,
        "continuation_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "QUANTITY != REGION AUTHORITY",
            "ASSIGNMENT MUST NAME EXACT MISSING WORK",
            "REGION LEASE != REGION RESULT",
            "REGION COMPOSITION MAY COMPLETE WORK WITHOUT REEXECUTION",
        ],
    }
    return {
        **body,
        "sparse_region_composed_completion_id": content_address(body),
    }


__all__ = [
    "SparseRegionLeaseBudget",
    "SparseRegionLeaseIssuer",
    "derive_exact_missing_region_set",
    "derive_sparse_region_composed_completion",
    "derive_sparse_region_execution_evidence",
    "verify_exact_missing_region_set",
    "verify_sparse_region_close",
    "verify_sparse_region_lease",
    "verify_sparse_region_release",
    "verify_sparse_region_use",
]
