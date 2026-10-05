#!/usr/bin/env python3
"""Lightwalker Work-Region Provenance / Non-Overlapping Salvage 001.

Turns aggregate continuation progress into exact pixel-region provenance for a
bounded Ice Cube render. Losing-branch regions may enter the authoritative
composition only after exact identity, correctness, and non-overlap are proven.

Core laws:
    PROGRESS PERCENT != WORK REGION
    NON-OVERLAP MUST BE PROVEN
    SALVAGED REGION != SALVAGED AUTHORITY
    REUSE != DOUBLE CREDIT
    ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE
    REGION COMPOSITION MAY COMPLETE WORK WITHOUT REEXECUTION
"""

from __future__ import annotations

from typing import Any

from ice_cube import pixel_for, render_pgm, work_address
from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_authorization import verify_execution_receipt
from lightwalker_guild_reservation import verify_finalization
from lightwalker_recursive_branch_fork import (
    verify_recursive_branch_resolution,
)
from lightwalker_recursive_continuation import (
    verify_recursive_checkpoint,
    verify_recursive_stop,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


PLAN_KIND = "ghot.lightwalker.pixel-region-plan"
PLAN_VERSION = "0"
COVERAGE_KIND = "ghot.lightwalker.region-coverage-attestation"
COVERAGE_VERSION = "0"
BRANCH_KIND = "ghot.lightwalker.branch-region-work-receipt"
BRANCH_VERSION = "0"
NONOVERLAP_KIND = "ghot.lightwalker.non-overlapping-region-salvage"
NONOVERLAP_VERSION = "0"
ADMISSION_KIND = "ghot.lightwalker.salvaged-region-admission"
ADMISSION_VERSION = "0"
TERMINAL_KIND = "ghot.lightwalker.region-execution-evidence"
TERMINAL_VERSION = "0"
COMPOSITION_KIND = "ghot.lightwalker.region-composed-completion"
COMPOSITION_VERSION = "0"

COVERAGE_DOMAIN = "ghot.lightwalker-region-coverage-signature/v0"
BRANCH_DOMAIN = "ghot.lightwalker-branch-region-work-signature/v0"
ADMISSION_DOMAIN = "ghot.lightwalker-salvaged-region-admission-signature/v0"

COVERAGE_BYTES = b"GHOT-LightwalkerRegionCoverage-v0|"
BRANCH_BYTES = b"GHOT-LightwalkerBranchRegionWork-v0|"
ADMISSION_BYTES = b"GHOT-LightwalkerSalvagedRegionAdmission-v0|"


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


def _operational_quantity(plan: dict[str, Any], region_count: int) -> int:
    mapping = plan["operational_accounting_policy"]
    return int(mapping["quantity_per_region"]) * int(region_count)


def make_pixel_region_plan(
    work: dict[str, Any],
    *,
    continuation_lineage_id: str,
) -> dict[str, Any]:
    width = int(work["render"]["width"])
    height = int(work["render"]["height"])
    if width <= 0 or height <= 0:
        raise LightwalkerEconomyError("render dimensions must be positive")
    address = work_address(work)
    regions: list[dict[str, Any]] = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            descriptor = {
                "work_address": address,
                "index": index,
                "x": x,
                "y": y,
            }
            regions.append({
                **descriptor,
                "region_id": content_address(descriptor),
            })
    body = {
        "kind": PLAN_KIND,
        "version": PLAN_VERSION,
        "authority": "derived-root-work-region-plan",
        "continuation_lineage_id": continuation_lineage_id,
        "work_address": address,
        "region_semantics": "one-canonical-render-pixel",
        "width": width,
        "height": height,
        "region_count": len(regions),
        "regions": regions,
        "operational_accounting_policy": {
            "scope": "066-specimen-only",
            "unit": "compute-minute",
            "quantity_per_region": 1,
        },
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "PROGRESS PERCENT != WORK REGION",
            "REGION IDENTITY != RESOURCE QUANTITY",
            "ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE",
        ],
    }
    return {**body, "pixel_region_plan_id": content_address(body)}


def verify_pixel_region_plan(
    work: dict[str, Any],
    plan: dict[str, Any],
) -> bool:
    try:
        expected = make_pixel_region_plan(
            work,
            continuation_lineage_id=plan["continuation_lineage_id"],
        )
        return plan == expected
    except Exception:
        return False


def _region_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = plan.get("regions")
    if not isinstance(rows, list):
        raise LightwalkerEconomyError("region plan has no region list")
    result = {row["region_id"]: row for row in rows}
    if len(result) != len(rows):
        raise LightwalkerEconomyError("region plan has duplicate region ids")
    return result


def region_ids_for_indices(
    plan: dict[str, Any],
    indices: list[int],
) -> list[str]:
    rows = plan["regions"]
    ids: list[str] = []
    seen: set[int] = set()
    for raw in indices:
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise LightwalkerEconomyError("region index must be integer")
        if raw < 0 or raw >= len(rows):
            raise LightwalkerEconomyError("region index outside plan")
        if raw in seen:
            raise LightwalkerEconomyError("duplicate region index")
        seen.add(raw)
        ids.append(rows[raw]["region_id"])
    return ids


def _claims_for_ids(
    work: dict[str, Any],
    plan: dict[str, Any],
    region_ids: list[str],
) -> list[dict[str, Any]]:
    region_map = _region_map(plan)
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for region_id in region_ids:
        if region_id in seen:
            raise LightwalkerEconomyError("duplicate region claim")
        seen.add(region_id)
        descriptor = region_map.get(region_id)
        if descriptor is None:
            raise LightwalkerEconomyError("region not present in root plan")
        claims.append({
            "region_id": region_id,
            "index": descriptor["index"],
            "x": descriptor["x"],
            "y": descriptor["y"],
            "value": pixel_for(
                work,
                int(descriptor["x"]),
                int(descriptor["y"]),
            ),
        })
    claims.sort(key=lambda row: int(row["index"]))
    return claims


def _verify_claims(
    work: dict[str, Any],
    plan: dict[str, Any],
    claims: list[dict[str, Any]],
) -> bool:
    try:
        ids = [row["region_id"] for row in claims]
        expected = _claims_for_ids(work, plan, ids)
        return claims == expected
    except Exception:
        return False


def make_region_coverage_attestation(
    work: dict[str, Any],
    plan: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    *,
    region_ids: list[str],
    signer: IdentityKey,
) -> dict[str, Any]:
    if not verify_pixel_region_plan(work, plan):
        raise LightwalkerEconomyError("invalid pixel region plan")
    if parent_checkpoint.get("kind") != (
        "ghot.lightwalker.recursive-continuation-checkpoint"
    ):
        raise LightwalkerEconomyError(
            "coverage attestation requires recursive checkpoint"
        )
    if signer.particular() != parent_checkpoint["steward_particular"]:
        raise LightwalkerEconomyError(
            "coverage attestor must own parent checkpoint"
        )
    claims = _claims_for_ids(work, plan, region_ids)
    cumulative = parent_checkpoint["cumulative_work_measure"]
    expected_quantity = _operational_quantity(plan, len(claims))
    if cumulative["unit"] != plan["operational_accounting_policy"]["unit"]:
        raise LightwalkerEconomyError("coverage unit mismatch")
    if int(cumulative["quantity"]) != expected_quantity:
        raise LightwalkerEconomyError(
            "aggregate progress does not match named coverage"
        )
    body = {
        "kind": COVERAGE_KIND,
        "version": COVERAGE_VERSION,
        "authority": "owner-local-accepted-region-coverage-attestation",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "continuation_lineage_id": plan["continuation_lineage_id"],
        "work_address": plan["work_address"],
        "parent_checkpoint_id": parent_checkpoint[
            "recursive_checkpoint_id"
        ],
        "attestor_particular": signer.particular(),
        "cumulative_work_measure": cumulative,
        "region_count": len(claims),
        "region_claims": claims,
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "PROGRESS PERCENT != WORK REGION",
            "COVERAGE ATTESTATION != EXECUTION RECEIPT",
            "ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE",
        ],
    }
    return _signed(
        body,
        id_field="region_coverage_attestation_id",
        signer=signer,
        domain=COVERAGE_DOMAIN,
        byte_domain=COVERAGE_BYTES,
    )


def verify_region_coverage_attestation(
    work: dict[str, Any],
    plan: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    attestation: dict[str, Any],
) -> bool:
    try:
        if not verify_pixel_region_plan(work, plan):
            return False
        if attestation.get("kind") != COVERAGE_KIND:
            return False
        if attestation.get("version") != COVERAGE_VERSION:
            return False
        if attestation.get("authority") != (
            "owner-local-accepted-region-coverage-attestation"
        ):
            return False
        if attestation.get("pixel_region_plan_id") != plan[
            "pixel_region_plan_id"
        ]:
            return False
        if attestation.get("parent_checkpoint_id") != parent_checkpoint[
            "recursive_checkpoint_id"
        ]:
            return False
        if attestation.get("attestor_particular") != parent_checkpoint[
            "steward_particular"
        ]:
            return False
        claims = attestation.get("region_claims")
        if not isinstance(claims, list) or not _verify_claims(
            work, plan, claims
        ):
            return False
        if attestation.get("region_count") != len(claims):
            return False
        expected_quantity = _operational_quantity(plan, len(claims))
        if attestation.get("cumulative_work_measure") != parent_checkpoint[
            "cumulative_work_measure"
        ]:
            return False
        if int(
            attestation["cumulative_work_measure"]["quantity"]
        ) != expected_quantity:
            return False
        return _verify_signed(
            attestation,
            id_field="region_coverage_attestation_id",
            particular_field="attestor_particular",
            domain=COVERAGE_DOMAIN,
            byte_domain=COVERAGE_BYTES,
        )
    except Exception:
        return False


def make_branch_region_work_receipt(
    work: dict[str, Any],
    plan: dict[str, Any],
    child_node: dict[str, Any],
    checkpoint: dict[str, Any],
    stop: dict[str, Any],
    reservation: dict[str, Any],
    finalization: dict[str, Any],
    *,
    region_ids: list[str],
    signer: IdentityKey,
) -> dict[str, Any]:
    if not verify_pixel_region_plan(work, plan):
        raise LightwalkerEconomyError("invalid pixel region plan")
    if not verify_recursive_checkpoint(child_node, checkpoint):
        raise LightwalkerEconomyError("invalid branch checkpoint")
    if not verify_recursive_stop(
        child_node,
        checkpoint,
        reservation,
        finalization,
        stop,
    ):
        raise LightwalkerEconomyError("invalid branch terminal evidence")
    if signer.particular() != child_node["new_steward_particular"]:
        raise LightwalkerEconomyError(
            "branch region signer is not child owner"
        )
    claims = _claims_for_ids(work, plan, region_ids)
    expected_quantity = _operational_quantity(plan, len(claims))
    new_work = checkpoint["new_work_measure"]
    consumed = finalization["consumed_measure"]
    if new_work["unit"] != plan["operational_accounting_policy"]["unit"]:
        raise LightwalkerEconomyError("branch work unit mismatch")
    if int(new_work["quantity"]) != expected_quantity:
        raise LightwalkerEconomyError(
            "branch progress does not match named regions"
        )
    if consumed != new_work:
        raise LightwalkerEconomyError(
            "branch finalization does not match checkpoint work"
        )
    body = {
        "kind": BRANCH_KIND,
        "version": BRANCH_VERSION,
        "authority": "owner-local-exact-region-work-receipt",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "continuation_lineage_id": plan["continuation_lineage_id"],
        "work_address": plan["work_address"],
        "child_node_id": child_node["recursive_node_id"],
        "checkpoint_id": checkpoint["recursive_checkpoint_id"],
        "stop_id": stop["recursive_stop_id"],
        "reservation_id": reservation["reservation_id"],
        "finalization_id": finalization["finalization_id"],
        "worker_particular": signer.particular(),
        "work_measure": new_work,
        "artifact_ref": checkpoint["partial_result_ref"],
        "region_count": len(claims),
        "region_claims": claims,
        "continuation_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "PROGRESS PERCENT != WORK REGION",
            "EXACT REGION RECEIPT != CONTINUATION AUTHORITY",
            "ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE",
        ],
    }
    return _signed(
        body,
        id_field="branch_region_work_receipt_id",
        signer=signer,
        domain=BRANCH_DOMAIN,
        byte_domain=BRANCH_BYTES,
    )


def verify_branch_region_work_receipt(
    work: dict[str, Any],
    plan: dict[str, Any],
    child_node: dict[str, Any],
    checkpoint: dict[str, Any],
    stop: dict[str, Any],
    reservation: dict[str, Any],
    finalization: dict[str, Any],
    receipt: dict[str, Any],
) -> bool:
    try:
        if not verify_recursive_checkpoint(child_node, checkpoint):
            return False
        if not verify_recursive_stop(
            child_node,
            checkpoint,
            reservation,
            finalization,
            stop,
        ):
            return False
        if receipt.get("kind") != BRANCH_KIND:
            return False
        if receipt.get("version") != BRANCH_VERSION:
            return False
        if receipt.get("authority") != (
            "owner-local-exact-region-work-receipt"
        ):
            return False
        checks = {
            "pixel_region_plan_id": plan["pixel_region_plan_id"],
            "continuation_lineage_id": plan["continuation_lineage_id"],
            "work_address": plan["work_address"],
            "child_node_id": child_node["recursive_node_id"],
            "checkpoint_id": checkpoint["recursive_checkpoint_id"],
            "stop_id": stop["recursive_stop_id"],
            "reservation_id": reservation["reservation_id"],
            "finalization_id": finalization["finalization_id"],
            "worker_particular": child_node["new_steward_particular"],
            "work_measure": checkpoint["new_work_measure"],
            "artifact_ref": checkpoint["partial_result_ref"],
        }
        if any(receipt.get(k) != v for k, v in checks.items()):
            return False
        claims = receipt.get("region_claims")
        if not isinstance(claims, list) or not _verify_claims(
            work, plan, claims
        ):
            return False
        if receipt.get("region_count") != len(claims):
            return False
        if _operational_quantity(plan, len(claims)) != int(
            checkpoint["new_work_measure"]["quantity"]
        ):
            return False
        return _verify_signed(
            receipt,
            id_field="branch_region_work_receipt_id",
            particular_field="worker_particular",
            domain=BRANCH_DOMAIN,
            byte_domain=BRANCH_BYTES,
        )
    except Exception:
        return False


def _verify_branch_bundle(
    work: dict[str, Any],
    plan: dict[str, Any],
    bundle: dict[str, Any],
) -> bool:
    try:
        required = {
            "child_node",
            "checkpoint",
            "stop",
            "reservation",
            "finalization",
            "receipt",
        }
        if set(bundle) != required:
            return False
        return verify_branch_region_work_receipt(
            work,
            plan,
            bundle["child_node"],
            bundle["checkpoint"],
            bundle["stop"],
            bundle["reservation"],
            bundle["finalization"],
            bundle["receipt"],
        )
    except Exception:
        return False


def derive_non_overlapping_region_salvage(
    work: dict[str, Any],
    plan: dict[str, Any],
    parent_node: dict[str, Any],
    parent_checkpoint: dict[str, Any],
    parent_coverage: dict[str, Any],
    fork: dict[str, Any],
    resolution: dict[str, Any],
    winning_bundle: dict[str, Any],
    losing_bundle: dict[str, Any],
) -> dict[str, Any]:
    if not verify_region_coverage_attestation(
        work,
        plan,
        parent_checkpoint,
        parent_coverage,
    ):
        raise LightwalkerEconomyError("invalid parent region coverage")
    if not verify_recursive_branch_resolution(
        parent_node,
        parent_checkpoint,
        fork,
        resolution,
    ):
        raise LightwalkerEconomyError("invalid recursive branch resolution")
    if not _verify_branch_bundle(work, plan, winning_bundle):
        raise LightwalkerEconomyError("invalid winning branch region bundle")
    if not _verify_branch_bundle(work, plan, losing_bundle):
        raise LightwalkerEconomyError("invalid losing branch region bundle")
    winning_receipt = winning_bundle["receipt"]
    losing_receipt = losing_bundle["receipt"]
    if winning_receipt.get("child_node_id") != resolution[
        "winning_child_node_id"
    ]:
        raise LightwalkerEconomyError("winning region receipt is not winner")
    if losing_receipt.get("child_node_id") not in resolution[
        "losing_child_node_ids"
    ]:
        raise LightwalkerEconomyError("losing region receipt is not loser")

    parent_ids = {
        row["region_id"] for row in parent_coverage["region_claims"]
    }
    winning_ids = {
        row["region_id"] for row in winning_receipt["region_claims"]
    }
    if parent_ids & winning_ids:
        raise LightwalkerEconomyError(
            "winning branch overlaps accepted parent coverage"
        )
    accepted_before = parent_ids | winning_ids
    losing_claim_map = {
        row["region_id"]: row for row in losing_receipt["region_claims"]
    }
    overlap_ids = sorted(set(losing_claim_map) & accepted_before)
    reusable_ids = sorted(set(losing_claim_map) - accepted_before)
    body = {
        "kind": NONOVERLAP_KIND,
        "version": NONOVERLAP_VERSION,
        "authority": "derived-region-non-overlap-evidence-only",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "recursive_branch_fork_id": fork["recursive_branch_fork_id"],
        "recursive_branch_resolution_id": resolution[
            "recursive_branch_resolution_id"
        ],
        "parent_region_coverage_id": parent_coverage[
            "region_coverage_attestation_id"
        ],
        "winning_region_receipt_id": winning_receipt[
            "branch_region_work_receipt_id"
        ],
        "losing_region_receipt_id": losing_receipt[
            "branch_region_work_receipt_id"
        ],
        "losing_region_count": len(losing_claim_map),
        "overlap_region_ids": overlap_ids,
        "overlap_region_count": len(overlap_ids),
        "reusable_region_ids": reusable_ids,
        "reusable_region_claims": [
            losing_claim_map[region_id] for region_id in reusable_ids
        ],
        "reusable_region_count": len(reusable_ids),
        "root_region_coverage_credit_count": 0,
        "continuation_progress_credit_measure": {
            "unit": plan["operational_accounting_policy"]["unit"],
            "quantity": 0,
        },
        "continuation_authority": "none",
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "NON-OVERLAP MUST BE PROVEN",
            "SALVAGED REGION != SALVAGED AUTHORITY",
            "REUSE != DOUBLE CREDIT",
        ],
    }
    return {
        **body,
        "non_overlapping_region_salvage_id": content_address(body),
    }


def make_salvaged_region_admission(
    plan: dict[str, Any],
    nonoverlap: dict[str, Any],
    resolution: dict[str, Any],
    *,
    parent_steward: IdentityKey,
) -> dict[str, Any]:
    if parent_steward.particular() != resolution[
        "parent_steward_particular"
    ]:
        raise LightwalkerEconomyError(
            "only fork parent owner may admit salvaged regions"
        )
    if nonoverlap.get("recursive_branch_resolution_id") != resolution[
        "recursive_branch_resolution_id"
    ]:
        raise LightwalkerEconomyError("salvage evidence resolution mismatch")
    if nonoverlap.get("pixel_region_plan_id") != plan[
        "pixel_region_plan_id"
    ]:
        raise LightwalkerEconomyError("salvage evidence plan mismatch")
    if int(nonoverlap.get("root_region_coverage_credit_count", -1)) != 0:
        raise LightwalkerEconomyError(
            "derived non-overlap may not self-authorize coverage credit"
        )
    claims = nonoverlap.get("reusable_region_claims")
    if not isinstance(claims, list):
        raise LightwalkerEconomyError("missing reusable region claims")
    body = {
        "kind": ADMISSION_KIND,
        "version": ADMISSION_VERSION,
        "authority": "parent-owner-local-region-composition-admission",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "recursive_branch_resolution_id": resolution[
            "recursive_branch_resolution_id"
        ],
        "non_overlapping_region_salvage_id": nonoverlap[
            "non_overlapping_region_salvage_id"
        ],
        "parent_steward_particular": parent_steward.particular(),
        "admitted_region_ids": list(nonoverlap["reusable_region_ids"]),
        "admitted_region_claims": list(claims),
        "root_region_coverage_credit_count": len(claims),
        "continuation_progress_credit_measure": {
            "unit": plan["operational_accounting_policy"]["unit"],
            "quantity": 0,
        },
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "SALVAGED REGION != SALVAGED AUTHORITY",
            "REGION COVERAGE CREDIT != CONTINUATION PROGRESS CREDIT",
            "REUSE != DOUBLE CREDIT",
        ],
    }
    return _signed(
        body,
        id_field="salvaged_region_admission_id",
        signer=parent_steward,
        domain=ADMISSION_DOMAIN,
        byte_domain=ADMISSION_BYTES,
    )


def verify_salvaged_region_admission(
    plan: dict[str, Any],
    nonoverlap: dict[str, Any],
    resolution: dict[str, Any],
    admission: dict[str, Any],
) -> bool:
    try:
        if admission.get("kind") != ADMISSION_KIND:
            return False
        if admission.get("version") != ADMISSION_VERSION:
            return False
        if admission.get("authority") != (
            "parent-owner-local-region-composition-admission"
        ):
            return False
        checks = {
            "pixel_region_plan_id": plan["pixel_region_plan_id"],
            "recursive_branch_resolution_id": resolution[
                "recursive_branch_resolution_id"
            ],
            "non_overlapping_region_salvage_id": nonoverlap[
                "non_overlapping_region_salvage_id"
            ],
            "parent_steward_particular": resolution[
                "parent_steward_particular"
            ],
            "admitted_region_ids": nonoverlap["reusable_region_ids"],
            "admitted_region_claims": nonoverlap[
                "reusable_region_claims"
            ],
            "root_region_coverage_credit_count": nonoverlap[
                "reusable_region_count"
            ],
            "continuation_progress_credit_measure": {
                "unit": plan["operational_accounting_policy"]["unit"],
                "quantity": 0,
            },
            "execution_authority": "none",
            "settlement_authority": "none",
        }
        if any(admission.get(k) != v for k, v in checks.items()):
            return False
        return _verify_signed(
            admission,
            id_field="salvaged_region_admission_id",
            particular_field="parent_steward_particular",
            domain=ADMISSION_DOMAIN,
            byte_domain=ADMISSION_BYTES,
        )
    except Exception:
        return False


def region_claim_set(
    work: dict[str, Any],
    plan: dict[str, Any],
    *,
    region_ids: list[str],
    executor_particular: str,
) -> dict[str, Any]:
    claims = _claims_for_ids(work, plan, region_ids)
    body = {
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "work_address": plan["work_address"],
        "executor_particular": executor_particular,
        "region_count": len(claims),
        "region_claims": claims,
    }
    return {**body, "region_claim_set_id": content_address(body)}


def make_region_execution_evidence(
    work: dict[str, Any],
    plan: dict[str, Any],
    claim_set: dict[str, Any],
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    execution: dict[str, Any],
    finalization: dict[str, Any],
) -> dict[str, Any]:
    if claim_set != region_claim_set(
        work,
        plan,
        region_ids=[
            row["region_id"] for row in claim_set["region_claims"]
        ],
        executor_particular=claim_set["executor_particular"],
    ):
        raise LightwalkerEconomyError("invalid region claim set")
    if not verify_execution_receipt(
        snapshot, proposal, authorization, execution
    ):
        raise LightwalkerEconomyError("invalid capacity execution receipt")
    if not verify_finalization(reservation, finalization):
        raise LightwalkerEconomyError("invalid capacity finalization")
    if execution.get("success") is not True:
        raise LightwalkerEconomyError("region execution did not succeed")
    if execution.get("result_ref") != claim_set["region_claim_set_id"]:
        raise LightwalkerEconomyError(
            "capacity execution does not name region claim set"
        )
    if finalization.get("status") != "CONSUMED":
        raise LightwalkerEconomyError("region capacity was not consumed")
    expected_q = _operational_quantity(
        plan, int(claim_set["region_count"])
    )
    if int(
        execution["consumed_measure"]["quantity"]
    ) != expected_q:
        raise LightwalkerEconomyError(
            "region claim count does not match consumed capacity"
        )
    body = {
        "kind": TERMINAL_KIND,
        "version": TERMINAL_VERSION,
        "authority": "derived-exact-region-execution-evidence",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "work_address": plan["work_address"],
        "region_claim_set_id": claim_set["region_claim_set_id"],
        "executor_particular": execution["executor_particular"],
        "execution_receipt_id": execution["execution_receipt_id"],
        "reservation_id": reservation["reservation_id"],
        "finalization_id": finalization["finalization_id"],
        "region_count": claim_set["region_count"],
        "region_claims": claim_set["region_claims"],
        "work_measure": execution["consumed_measure"],
        "continuation_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "REGION EXECUTION != CONTINUATION AUTHORITY",
            "ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE",
        ],
    }
    return {
        **body,
        "region_execution_evidence_id": content_address(body),
    }


def verify_region_execution_evidence(
    work: dict[str, Any],
    plan: dict[str, Any],
    claim_set: dict[str, Any],
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
    execution: dict[str, Any],
    finalization: dict[str, Any],
    evidence: dict[str, Any],
) -> bool:
    try:
        expected = make_region_execution_evidence(
            work,
            plan,
            claim_set,
            snapshot,
            proposal,
            authorization,
            reservation,
            execution,
            finalization,
        )
        return evidence == expected
    except Exception:
        return False


def missing_region_ids(
    plan: dict[str, Any],
    parent_coverage: dict[str, Any],
    winning_receipt: dict[str, Any],
    admission: dict[str, Any],
) -> list[str]:
    all_ids = {row["region_id"] for row in plan["regions"]}
    covered_sets = [
        {row["region_id"] for row in parent_coverage["region_claims"]},
        {row["region_id"] for row in winning_receipt["region_claims"]},
        set(admission["admitted_region_ids"]),
    ]
    if covered_sets[0] & covered_sets[1]:
        raise LightwalkerEconomyError("parent/winner region overlap")
    if (covered_sets[0] | covered_sets[1]) & covered_sets[2]:
        raise LightwalkerEconomyError("salvage admission overlaps coverage")
    covered = set().union(*covered_sets)
    if not covered <= all_ids:
        raise LightwalkerEconomyError("coverage includes unknown regions")
    region_order = {
        row["region_id"]: int(row["index"]) for row in plan["regions"]
    }
    return sorted(all_ids - covered, key=lambda rid: region_order[rid])


def derive_region_composed_completion(
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
    terminal_evidence: dict[str, Any],
) -> dict[str, Any]:
    if not verify_region_coverage_attestation(
        work, plan, parent_checkpoint, parent_coverage
    ):
        raise LightwalkerEconomyError("invalid parent coverage")
    if not verify_recursive_branch_resolution(
        parent_node,
        parent_checkpoint,
        fork,
        resolution,
    ):
        raise LightwalkerEconomyError("invalid recursive branch resolution")
    if not _verify_branch_bundle(work, plan, winning_bundle):
        raise LightwalkerEconomyError("invalid winning branch region bundle")
    if not _verify_branch_bundle(work, plan, losing_bundle):
        raise LightwalkerEconomyError("invalid losing branch region bundle")
    winning_receipt = winning_bundle["receipt"]
    losing_receipt = losing_bundle["receipt"]
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
        plan,
        nonoverlap,
        resolution,
        admission,
    ):
        raise LightwalkerEconomyError("invalid salvage admission")
    if terminal_evidence.get("kind") != TERMINAL_KIND:
        raise LightwalkerEconomyError("invalid terminal region evidence")
    if terminal_evidence.get("pixel_region_plan_id") != plan[
        "pixel_region_plan_id"
    ]:
        raise LightwalkerEconomyError("terminal evidence plan mismatch")
    if not _verify_claims(
        work, plan, terminal_evidence["region_claims"]
    ):
        raise LightwalkerEconomyError("terminal region claims invalid")

    credited_groups = [
        parent_coverage["region_claims"],
        winning_receipt["region_claims"],
        admission["admitted_region_claims"],
        terminal_evidence["region_claims"],
    ]
    seen: dict[str, dict[str, Any]] = {}
    for group in credited_groups:
        for claim in group:
            region_id = claim["region_id"]
            if region_id in seen:
                raise LightwalkerEconomyError(
                    "credited region appears more than once"
                )
            seen[region_id] = claim
    all_region_ids = [row["region_id"] for row in plan["regions"]]
    if set(seen) != set(all_region_ids):
        raise LightwalkerEconomyError(
            "region composition does not cover exact root plan"
        )

    pixels = bytearray(int(plan["region_count"]))
    for row in plan["regions"]:
        claim = seen[row["region_id"]]
        pixels[int(row["index"])] = int(claim["value"])
    assembled = (
        f"P5\n{plan['width']} {plan['height']}\n255\n".encode("ascii")
        + bytes(pixels)
    )
    canonical_render, _ = render_pgm(work)
    if assembled != canonical_render:
        raise LightwalkerEconomyError(
            "composed regions do not reconstruct canonical render"
        )
    render_address = content_address(assembled)

    parent_count = int(parent_coverage["region_count"])
    winner_count = int(winning_receipt["region_count"])
    loser_count = int(losing_receipt["region_count"])
    admitted_count = int(admission["root_region_coverage_credit_count"])
    terminal_count = int(terminal_evidence["region_count"])
    body = {
        "kind": COMPOSITION_KIND,
        "version": COMPOSITION_VERSION,
        "authority": "derived-exact-region-completion",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "continuation_lineage_id": plan["continuation_lineage_id"],
        "work_address": plan["work_address"],
        "canonical_render_address": render_address,
        "region_count": plan["region_count"],
        "pre_fork_credited_region_count": parent_count,
        "winning_branch_credited_region_count": winner_count,
        "salvaged_region_credited_count": admitted_count,
        "terminal_executed_region_count": terminal_count,
        "authoritative_region_coverage_count": len(seen),
        "losing_branch_observed_region_count": loser_count,
        "losing_branch_overlap_region_count": nonoverlap[
            "overlap_region_count"
        ],
        "useful_region_work_observed": (
            parent_count + winner_count + loser_count + terminal_count
        ),
        "salvaged_regions_reexecuted": 0,
        "root_region_double_counted": False,
        "work_complete": True,
        "execution_merged": False,
        "continuation_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "PROGRESS PERCENT != WORK REGION",
            "NON-OVERLAP MUST BE PROVEN",
            "SALVAGED REGION != SALVAGED AUTHORITY",
            "REUSE != DOUBLE CREDIT",
            "ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE",
            "REGION COMPOSITION MAY COMPLETE WORK WITHOUT REEXECUTION",
        ],
    }
    return {
        **body,
        "region_composed_completion_id": content_address(body),
    }


__all__ = [
    "derive_non_overlapping_region_salvage",
    "derive_region_composed_completion",
    "make_branch_region_work_receipt",
    "make_pixel_region_plan",
    "make_region_coverage_attestation",
    "make_region_execution_evidence",
    "make_salvaged_region_admission",
    "missing_region_ids",
    "region_claim_set",
    "region_ids_for_indices",
    "verify_branch_region_work_receipt",
    "verify_pixel_region_plan",
    "verify_region_coverage_attestation",
    "verify_region_execution_evidence",
    "verify_salvaged_region_admission",
]
