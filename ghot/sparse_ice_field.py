#!/usr/bin/env python3
"""SPARSE ICE FIELD 001 primitives.

This module composes an Ice Field work spec with Lightwalker 067 exact sparse
region assignment. It intentionally treats a newly opened child as a genesis
missing set: zero regions are accepted, every root pixel region is missing.

The sparse workers produce exact region claims. The canonical PGM is rebuilt
from those claims rather than rendered again.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from ice_cube import content_address, work_address
from lightwalker_economy import content_address as lw_content_address
from lightwalker_work_region_salvage import make_pixel_region_plan


GENESIS_KIND = "ghot.sparse-ice.genesis-missing-set"
GENESIS_VERSION = "0"


def make_genesis_missing_set(
    work: dict[str, Any],
    *,
    assignment_owner_particular: str,
    continuation_lineage_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = make_pixel_region_plan(
        work,
        continuation_lineage_id=continuation_lineage_id,
    )
    missing_ids = [row["region_id"] for row in plan["regions"]]
    accepted: list[str] = []
    unit = plan["operational_accounting_policy"]["unit"]
    per_region = int(
        plan["operational_accounting_policy"]["quantity_per_region"]
    )
    body = {
        "kind": "ghot.lightwalker.exact-missing-region-set",
        "version": "0",
        "authority": "derived-exact-missing-work-observation",
        "pixel_region_plan_id": plan["pixel_region_plan_id"],
        "continuation_lineage_id": continuation_lineage_id,
        "work_address": work_address(work),
        "parent_checkpoint_id": "genesis:none",
        "recursive_branch_resolution_id": "genesis:none",
        "salvaged_region_admission_id": "genesis:none",
        "assignment_owner_particular": assignment_owner_particular,
        "accepted_region_count": 0,
        "accepted_region_ids": accepted,
        "accepted_coverage_digest": lw_content_address({
            "pixel_region_plan_id": plan["pixel_region_plan_id"],
            "accepted_region_ids": accepted,
        }),
        "missing_region_count": len(missing_ids),
        "missing_region_ids": missing_ids,
        "missing_region_set_digest": lw_content_address({
            "pixel_region_plan_id": plan["pixel_region_plan_id"],
            "missing_region_ids": missing_ids,
        }),
        "missing_work_measure": {
            "unit": unit,
            "quantity": per_region * len(missing_ids),
        },
        "assignment_authority": "none",
        "execution_authority": "none",
        "settlement_authority": "none",
        "laws": [
            "GENESIS MISSING SET != ASSIGNMENT",
            "QUANTITY != REGION AUTHORITY",
            "REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY",
        ],
    }
    missing = {
        **body,
        "exact_missing_region_set_id": lw_content_address(body),
        "genesis_profile": {
            "kind": GENESIS_KIND,
            "version": GENESIS_VERSION,
            "accepted_before_sparse_work": 0,
            "all_root_regions_missing": True,
        },
    }
    # The 067 intrinsic verifier hashes all fields except the id, so the
    # profile must be included before the final identity is frozen.
    body_with_profile = {
        key: value
        for key, value in missing.items()
        if key != "exact_missing_region_set_id"
    }
    missing["exact_missing_region_set_id"] = lw_content_address(
        body_with_profile
    )
    return plan, missing


def reconstruct_pgm_from_region_claims(
    work: dict[str, Any],
    plan: dict[str, Any],
    claims: list[dict[str, Any]],
) -> bytes:
    width = int(work["render"]["width"])
    height = int(work["render"]["height"])
    total = width * height
    if int(plan["region_count"]) != total:
        raise ValueError("region plan size does not match work render")
    if len(claims) != total:
        raise ValueError("claim set does not cover every root region")

    rows_by_id = {row["region_id"]: row for row in plan["regions"]}
    if len(rows_by_id) != total:
        raise ValueError("region plan identities are not unique")

    pixels = bytearray(total)
    seen: set[str] = set()
    for claim in claims:
        region_id = str(claim["region_id"])
        if region_id in seen:
            raise ValueError("region claimed more than once")
        seen.add(region_id)
        row = rows_by_id.get(region_id)
        if row is None:
            raise ValueError("claim names region outside plan")
        if int(claim["index"]) != int(row["index"]):
            raise ValueError("claim index mismatch")
        if int(claim["x"]) != int(row["x"]) or int(claim["y"]) != int(row["y"]):
            raise ValueError("claim coordinate mismatch")
        value = int(claim["value"])
        if not (0 <= value <= 255):
            raise ValueError("claim value outside byte range")
        pixels[int(row["index"])] = value

    if seen != set(rows_by_id):
        raise ValueError("claim set leaves missing root regions")
    return f"P5\n{width} {height}\n255\n".encode("ascii") + bytes(pixels)


def dogram_sparse_receipt_for(
    dogram_repo: Path,
    work: dict[str, Any],
    plan: dict[str, Any],
    claims: list[dict[str, Any]],
    *,
    root_probe_count: int = 4,
    prior: dict[str, str] | None = None,
) -> dict[str, Any]:
    dogram_repo = dogram_repo.resolve()
    module_path = dogram_repo / "dogram" / "sparse_ice_probe.py"
    if not module_path.exists():
        raise RuntimeError(
            "Sparse Dogram verifier missing; use branch impl/sparse-ice-probe-001"
        )

    old_path = list(sys.path)
    prior_module = sys.modules.pop("dogram.sparse_ice_probe", None)
    try:
        sys.path.insert(0, str(dogram_repo))
        importlib.invalidate_caches()
        module = importlib.import_module("dogram.sparse_ice_probe")
        origin = Path(module.__file__).resolve()
        if dogram_repo not in origin.parents:
            raise RuntimeError(f"wrong sparse Dogram module loaded: {origin}")
        receipt = module.verify_sparse_region_claims(
            work,
            plan,
            claims,
            root_probe_count=root_probe_count,
            prior=prior,
        )
    finally:
        sys.modules.pop("dogram.sparse_ice_probe", None)
        if prior_module is not None:
            sys.modules["dogram.sparse_ice_probe"] = prior_module
        sys.path[:] = old_path

    if not isinstance(receipt, dict):
        raise RuntimeError("sparse Dogram verifier returned non-object")
    return receipt


def sparse_receipt_address(receipt: dict[str, Any]) -> str:
    return content_address(receipt)


__all__ = [
    "dogram_sparse_receipt_for",
    "make_genesis_missing_set",
    "reconstruct_pgm_from_region_claims",
    "sparse_receipt_address",
]
