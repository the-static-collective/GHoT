#!/usr/bin/env python3
"""RSC Composer 001 — deterministic reseeding instrument.

Consumes an explicit RSC seed packet. It does not invent crossings or silently
promote recommendations into selections. It validates declared evidence,
boundary checks, and experiment metadata, then emits a content-addressed
reseed packet that can be carried into another composition cycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COST_ORDER = {"small": 0, "medium": 1, "large": 2}


class SeedError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require(obj: dict[str, Any], key: str, expected: type | tuple[type, ...]) -> Any:
    if key not in obj:
        raise SeedError(f"missing required field: {key}")
    value = obj[key]
    if not isinstance(value, expected):
        names = expected.__name__ if isinstance(expected, type) else "/".join(t.__name__ for t in expected)
        raise SeedError(f"{key} must be {names}")
    return value


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def validate_seed(seed: dict[str, Any]) -> None:
    if seed.get("kind") != "rsc.seed":
        raise SeedError("kind must be rsc.seed")
    if str(seed.get("version")) != "0":
        raise SeedError("version must be 0")

    artifacts = _require(seed, "artifacts", list)
    crossings = _require(seed, "crossings", list)
    if not artifacts:
        raise SeedError("artifacts must contain at least one artifact")

    artifact_ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise SeedError(f"artifacts[{index}] must be an object")
        artifact_id = _require(artifact, "id", str).strip()
        if not artifact_id:
            raise SeedError(f"artifacts[{index}].id must not be blank")
        if artifact_id in artifact_ids:
            raise SeedError(f"duplicate artifact id: {artifact_id}")
        artifact_ids.add(artifact_id)
        _require(artifact, "kind", str)
        _require(artifact, "current_role", str)
        _require(artifact, "primitives", list)
        _require(artifact, "migratable_parts", list)
        _require(artifact, "boundaries", list)

    crossing_ids: set[str] = set()
    for index, crossing in enumerate(crossings):
        if not isinstance(crossing, dict):
            raise SeedError(f"crossings[{index}] must be an object")
        crossing_id = _require(crossing, "id", str).strip()
        if not crossing_id:
            raise SeedError(f"crossings[{index}].id must not be blank")
        if crossing_id in crossing_ids:
            raise SeedError(f"duplicate crossing id: {crossing_id}")
        crossing_ids.add(crossing_id)

        sources = _require(crossing, "from", list)
        targets = _require(crossing, "to", list)
        for ref in [*sources, *targets]:
            if ref not in artifact_ids:
                raise SeedError(f"crossing {crossing_id} references unknown artifact: {ref}")

        _require(crossing, "proposal", str)
        _require(crossing, "exaptation", str)
        evidence = _require(crossing, "evidence", list)
        checks = _require(crossing, "boundary_checks", list)
        if not evidence:
            raise SeedError(f"crossing {crossing_id} must cite at least one evidence item")
        if not checks:
            raise SeedError(f"crossing {crossing_id} must declare at least one boundary check")

        experiment = _require(crossing, "experiment", dict)
        _require(experiment, "title", str)
        cost = _require(experiment, "cost", str)
        if cost not in COST_ORDER:
            raise SeedError(f"crossing {crossing_id} experiment cost must be one of {sorted(COST_ORDER)}")
        _require(experiment, "reversible", bool)
        _require(experiment, "requires", list)
        _require(experiment, "produces", list)

        readiness = crossing.get("readiness", "hold")
        if readiness not in {"ready", "hold"}:
            raise SeedError(f"crossing {crossing_id} readiness must be ready or hold")


def _check_statuses(crossing: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for item in crossing.get("boundary_checks", []):
        if not isinstance(item, dict):
            failures.append("malformed boundary check")
            continue
        law = str(item.get("law") or "unnamed law")
        status = item.get("status")
        if status != "pass":
            failures.append(f"{law}: {status or 'missing status'}")
    return (not failures, failures)


def _artifact_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": artifact["id"],
        "kind": artifact["kind"],
        "source": artifact.get("source"),
        "current_role": artifact["current_role"],
    }


def _primitive_rows(seed: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for artifact in seed["artifacts"]:
        for primitive in artifact.get("primitives", []):
            if isinstance(primitive, str):
                name, evidence = primitive, None
            elif isinstance(primitive, dict):
                name = str(primitive.get("name") or "").strip()
                evidence = primitive.get("evidence")
            else:
                continue
            if not name:
                continue
            key = (artifact["id"], name)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "artifact_id": artifact["id"],
                "name": name,
                "evidence": evidence,
            })
    return rows


def _migratable_rows(seed: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in seed["artifacts"]:
        for part in artifact.get("migratable_parts", []):
            if isinstance(part, str):
                rows.append({"artifact_id": artifact["id"], "name": part})
            elif isinstance(part, dict):
                rows.append({"artifact_id": artifact["id"], **part})
    return rows


def _boundary_inventory(seed: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for artifact in seed["artifacts"]:
        values.extend(str(x) for x in artifact.get("boundaries", []) if str(x).strip())
    return _dedupe_text(values)


def _candidate_view(crossing: dict[str, Any]) -> dict[str, Any]:
    passed, failures = _check_statuses(crossing)
    ready = crossing.get("readiness", "hold") == "ready" and passed
    return {
        "id": crossing["id"],
        "from": crossing["from"],
        "to": crossing["to"],
        "proposal": crossing["proposal"],
        "exaptation": crossing["exaptation"],
        "evidence": crossing["evidence"],
        "preserves": crossing.get("preserves", []),
        "boundary_status": "pass" if passed else "hold",
        "boundary_failures": failures,
        "declared_readiness": crossing.get("readiness", "hold"),
        "eligible_for_recommendation": ready,
        "experiment": crossing["experiment"],
    }


def _experiment_sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
    exp = candidate["experiment"]
    return (
        0 if exp["reversible"] else 1,
        COST_ORDER[exp["cost"]],
        -len(candidate.get("evidence", [])),
        candidate["id"],
    )


def compose(seed: dict[str, Any]) -> dict[str, Any]:
    validate_seed(seed)
    candidates = [_candidate_view(c) for c in seed["crossings"]]
    eligible = sorted(
        [c for c in candidates if c["eligible_for_recommendation"]],
        key=_experiment_sort_key,
    )

    experiments = []
    for candidate in eligible[:3]:
        exp = candidate["experiment"]
        experiments.append({
            "crossing_id": candidate["id"],
            "title": exp["title"],
            "cost": exp["cost"],
            "reversible": exp["reversible"],
            "requires": exp["requires"],
            "produces": exp["produces"],
            "why_recommended": [
                "all declared boundary checks pass",
                f"declared cost is {exp['cost']}",
                "reversible" if exp["reversible"] else "not declared reversible",
                f"{len(candidate.get('evidence', []))} evidence reference(s)",
            ],
            "selection_status": "recommendation-only",
        })

    holds = [
        {
            "crossing_id": c["id"],
            "reason": c["boundary_failures"] or [f"declared readiness is {c['declared_readiness']}"],
        }
        for c in candidates
        if not c["eligible_for_recommendation"]
    ]

    body = {
        "kind": "rsc.reseed-packet",
        "version": "0",
        "title": seed.get("title") or "Untitled RSC composition",
        "source_seed_sha256": sha256_json(seed),
        "current_artifacts": [_artifact_summary(a) for a in seed["artifacts"]],
        "discovered_primitives": _primitive_rows(seed),
        "migratable_parts": _migratable_rows(seed),
        "boundary_inventory": _boundary_inventory(seed),
        "crossing_candidates": candidates,
        "recommended_next_experiments": experiments,
        "held_crossings": holds,
        "human_selection_required": True,
        "laws": [
            "RECOMMENDATION != SELECTION",
            "CROSSING != COLLAPSE",
            "EXAPTATION != AUTHORITY",
            "RESEED != CANON",
        ],
    }
    body["reseed_id"] = f"rsc-{sha256_json(body)[:24]}"
    body["generated_at"] = now()
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", type=Path, help="Path to an rsc.seed JSON file")
    parser.add_argument("--output", type=Path, default=None, help="Optional output path")
    args = parser.parse_args()

    try:
        seed = json.loads(args.seed.read_text(encoding="utf-8"))
        packet = compose(seed)
    except (OSError, json.JSONDecodeError, SeedError) as exc:
        parser.error(str(exc))

    rendered = json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
