#!/usr/bin/env python3
"""GHoT Mineral Registry 001.

A mineral is a typed useful-work family. An Ice Cube is one possible frozen,
content-addressed result shape.

Declarations may exist before execution support. Only executable minerals are
advertised as capabilities.

    DECLARED != EXECUTABLE
    EXECUTABLE != VERIFIED
    PROVENANCE != DOMAIN TRUTH
    SAME FREEZER != SAME VERIFIER
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


REGISTRY_CAPABILITY = "mineral.registry/v0"

FRACTAL_CAPABILITY = "mineral.fractal.tile/v0"
OPTIMIZATION_CAPABILITY = "mineral.optimization.landscape/v0"
PARAMETER_SWEEP_CAPABILITY = "mineral.parameter-sweep/v0"
PROCEDURAL_WORLD_CAPABILITY = "mineral.procedural-world.chunk/v0"

EXECUTABLE_CAPABILITIES = {
    FRACTAL_CAPABILITY,
    OPTIMIZATION_CAPABILITY,
    PARAMETER_SWEEP_CAPABILITY,
    PROCEDURAL_WORLD_CAPABILITY,
}

MINERAL_REGISTRY = [
    {
        "mineral_id": "math.fractal.tile/v0",
        "capability": FRACTAL_CAPABILITY,
        "status": "EXECUTABLE_NATIVE",
        "decomposition": "pixel-grid",
        "verification_contract": "deterministic-exact-recompute/v0",
        "artifact_shape": "P5-PGM",
        "notes": "Mandelbrot escape-time tile.",
    },
    {
        "mineral_id": "math.topology.mapping-torus/v0",
        "capability": "ghot.ice-cube/v0",
        "status": "EXECUTABLE_COMPOSED",
        "decomposition": "exact-pixel-regions+monodromy",
        "verification_contract": "Dogram Ice Cube + sparse-region receipts",
        "artifact_shape": "Ice Cube result bundle",
        "notes": "Current Lucas/Halley/Mandelbrot/mapping-torus specimen.",
    },
    {
        "mineral_id": "math.projection.nd/v0",
        "capability": "mineral.projection.nd/v0",
        "status": "HOLD_VERIFIER_REQUIRED",
        "decomposition": "projection/slice regions",
        "verification_contract": "proof-of-projection required",
        "artifact_shape": "mesh/point-cloud/raster",
        "notes": "Higher-dimensional projections require a declared formal object and projection verifier.",
    },
    {
        "mineral_id": "science.numeric.simulation/v0",
        "capability": "mineral.simulation.numeric/v0",
        "status": "HOLD_VERIFIER_REQUIRED",
        "decomposition": "time-window/state-region",
        "verification_contract": "checkpoint + invariant contract required",
        "artifact_shape": "state/checkpoint bundle",
        "notes": "Generic numerical simulation is not advertised until integration/invariant semantics are explicit.",
    },
    {
        "mineral_id": "render.raytrace.tile/v0",
        "capability": "render.raytrace.tile/v0",
        "status": "HOLD_EXTERNAL_ADAPTER",
        "decomposition": "frame/tile/sample-range",
        "verification_contract": "scene hash + renderer manifest + sample contract",
        "artifact_shape": "image tile",
        "notes": "Requires a bounded external ray-tracing adapter.",
    },
    {
        "mineral_id": "render.blender.tile/v0",
        "capability": "render.blender.tile/v0",
        "status": "HOLD_EXTERNAL_ADAPTER",
        "decomposition": "frame/tile/sample-range",
        "verification_contract": "blend hash + Blender/version + render manifest",
        "artifact_shape": "image/frame tile",
        "notes": "Requires a bounded Blender adapter; network execution must not imply scene authority.",
    },
    {
        "mineral_id": "science.protein.search/v0",
        "capability": "science.protein.search/v0",
        "status": "HOLD_DOMAIN_VERIFIER",
        "decomposition": "candidate/search shard",
        "verification_contract": "domain-specific scientific witness required",
        "artifact_shape": "candidate + scientific evidence",
        "notes": "No biological correctness claim is made by GHoT alone.",
    },
    {
        "mineral_id": "math.optimization.landscape/v0",
        "capability": OPTIMIZATION_CAPABILITY,
        "status": "EXECUTABLE_NATIVE",
        "decomposition": "exact-grid-region",
        "verification_contract": "deterministic-exact-recompute/v0",
        "artifact_shape": "JSON integer grid",
        "notes": "Exact integer Rosenbrock landscape samples.",
    },
    {
        "mineral_id": "world.procedural.chunk/v0",
        "capability": PROCEDURAL_WORLD_CAPABILITY,
        "status": "EXECUTABLE_NATIVE",
        "decomposition": "chunk/cell",
        "verification_contract": "seed+coordinate exact recompute/v0",
        "artifact_shape": "JSON byte heightfield",
        "notes": "Hash-derived deterministic world chunk.",
    },
    {
        "mineral_id": "ai.asset.batch/v0",
        "capability": "ai.asset.batch/v0",
        "status": "HOLD_PROVENANCE_CONTRACT",
        "decomposition": "asset/ticket",
        "verification_contract": "recipe/model/input provenance; semantic truth not implied",
        "artifact_shape": "asset bundle",
        "notes": "Generative outputs need frozen recipes and honest reproducibility envelopes.",
    },
    {
        "mineral_id": "science.parameter-sweep/v0",
        "capability": PARAMETER_SWEEP_CAPABILITY,
        "status": "EXECUTABLE_NATIVE",
        "decomposition": "parameter point/range",
        "verification_contract": "exact-rational-recompute/v0",
        "artifact_shape": "JSON rational sweep",
        "notes": "Exact logistic-map rational parameter sweep.",
    },
]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_address(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def registry() -> dict[str, Any]:
    rows = [dict(item) for item in MINERAL_REGISTRY]
    return {
        "kind": "ghot.mineral-registry",
        "version": "0",
        "mineral_count": len(rows),
        "executable_count": sum(
            str(item["status"]).startswith("EXECUTABLE")
            for item in rows
        ),
        "minerals": rows,
        "laws": [
            "DECLARED != EXECUTABLE",
            "EXECUTABLE != VERIFIED",
            "PROVENANCE != DOMAIN TRUTH",
            "SAME FREEZER != SAME VERIFIER",
        ],
    }


def capability_offers() -> list[dict[str, Any]]:
    offers = [{
        "kind": "ghot.offer",
        "version": "0",
        "capability": REGISTRY_CAPABILITY,
        "available": True,
        "executor": "ghot.mineral-registry",
        "limits": {
            "remote_shell": False,
            "bounded_adapter_only": True,
        },
    }]
    by_capability = {
        item["capability"]: item
        for item in MINERAL_REGISTRY
        if item["capability"] in EXECUTABLE_CAPABILITIES
    }
    for capability in sorted(EXECUTABLE_CAPABILITIES):
        item = by_capability[capability]
        offers.append({
            "kind": "ghot.offer",
            "version": "0",
            "capability": capability,
            "available": True,
            "executor": "ghot.mineral-native",
            "limits": {
                "remote_shell": False,
                "bounded_adapter_only": True,
                "deterministic": True,
                "verification_contract": item["verification_contract"],
                "mineral_id": item["mineral_id"],
            },
        })
    return offers


def _int(value: Any, label: str, lo: int, hi: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    result = int(value)
    if result < lo or result > hi:
        raise ValueError(f"{label} must be between {lo} and {hi}")
    return result


def _fraction(value: Any, label: str) -> Fraction:
    try:
        result = Fraction(str(value))
    except Exception as exc:
        raise ValueError(f"{label} must be a rational value") from exc
    return result


def _mandelbrot_tile(payload: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    width = _int(payload.get("width", 64), "width", 1, 2048)
    height = _int(payload.get("height", 64), "height", 1, 2048)
    max_iter = _int(payload.get("max_iter", 64), "max_iter", 1, 4096)
    xmin = float(payload.get("xmin", -2.0))
    xmax = float(payload.get("xmax", 1.0))
    ymin = float(payload.get("ymin", -1.5))
    ymax = float(payload.get("ymax", 1.5))
    if not (xmin < xmax and ymin < ymax):
        raise ValueError("invalid fractal bounds")

    pixels = bytearray(width * height)
    for y in range(height):
        ci = ymin if height == 1 else ymax - (ymax - ymin) * y / (height - 1)
        for x in range(width):
            cr = xmin if width == 1 else xmin + (xmax - xmin) * x / (width - 1)
            zr = 0.0
            zi = 0.0
            used = max_iter
            for step in range(max_iter):
                if zr * zr + zi * zi > 4.0:
                    used = step
                    break
                zr, zi = zr * zr - zi * zi + cr, 2.0 * zr * zi + ci
            pixels[y * width + x] = (
                0 if used == max_iter else max(1, 255 - round(255 * used / max_iter))
            )
    artifact = f"P5\n{width} {height}\n255\n".encode("ascii") + bytes(pixels)
    spec = {
        "kernel": "mandelbrot-escape-time/v0",
        "width": width,
        "height": height,
        "max_iter": max_iter,
        "bounds": {
            "xmin": repr(xmin),
            "xmax": repr(xmax),
            "ymin": repr(ymin),
            "ymax": repr(ymax),
        },
    }
    return artifact, spec


def _optimization_landscape(payload: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    xmin = _int(payload.get("xmin", -4), "xmin", -1000, 1000)
    xmax = _int(payload.get("xmax", 4), "xmax", -1000, 1000)
    ymin = _int(payload.get("ymin", -4), "ymin", -1000, 1000)
    ymax = _int(payload.get("ymax", 4), "ymax", -1000, 1000)
    if xmin > xmax or ymin > ymax:
        raise ValueError("invalid optimization bounds")
    if (xmax - xmin + 1) * (ymax - ymin + 1) > 1_000_000:
        raise ValueError("optimization grid too large")

    rows = []
    minimum = None
    for y in range(ymin, ymax + 1):
        row = []
        for x in range(xmin, xmax + 1):
            # Integer Rosenbrock: (1-x)^2 + 100*(y-x^2)^2.
            value = (1 - x) ** 2 + 100 * (y - x * x) ** 2
            row.append(value)
            candidate = (value, x, y)
            if minimum is None or candidate < minimum:
                minimum = candidate
        rows.append(row)
    result = {
        "kernel": "rosenbrock-integer/v0",
        "bounds": {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax},
        "values": rows,
        "minimum": {
            "value": minimum[0],
            "x": minimum[1],
            "y": minimum[2],
        },
    }
    return canonical_bytes(result), result


def _parameter_sweep(payload: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    r_values = payload.get("r_values", ["2", "5/2", "3", "7/2"])
    if not isinstance(r_values, list) or not r_values or len(r_values) > 128:
        raise ValueError("r_values must be a nonempty array of at most 128 items")
    x0 = _fraction(payload.get("x0", "1/2"), "x0")
    steps = _int(payload.get("steps", 8), "steps", 1, 64)

    rows = []
    for raw_r in r_values:
        r = _fraction(raw_r, "r")
        x = x0
        path = []
        for _ in range(steps):
            x = r * x * (1 - x)
            path.append(f"{x.numerator}/{x.denominator}")
        rows.append({
            "r": f"{r.numerator}/{r.denominator}",
            "final": path[-1],
            "path": path,
        })
    result = {
        "kernel": "logistic-rational/v0",
        "x0": f"{x0.numerator}/{x0.denominator}",
        "steps": steps,
        "rows": rows,
    }
    return canonical_bytes(result), result


def _procedural_world(payload: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    seed = str(payload.get("seed", "static"))
    chunk_x = _int(payload.get("chunk_x", 0), "chunk_x", -1_000_000, 1_000_000)
    chunk_y = _int(payload.get("chunk_y", 0), "chunk_y", -1_000_000, 1_000_000)
    size = _int(payload.get("size", 16), "size", 1, 256)
    heights = []
    for local_y in range(size):
        row = []
        for local_x in range(size):
            world_x = chunk_x * size + local_x
            world_y = chunk_y * size + local_y
            digest = hashlib.sha256(
                f"{seed}|{world_x}|{world_y}".encode("utf-8")
            ).digest()
            row.append(digest[0])
        heights.append(row)
    result = {
        "kernel": "sha256-heightfield/v0",
        "seed": seed,
        "chunk": {"x": chunk_x, "y": chunk_y, "size": size},
        "heights": heights,
    }
    return canonical_bytes(result), result


def _native_compute(
    capability: str,
    payload: dict[str, Any],
) -> tuple[bytes, dict[str, Any], str]:
    if capability == FRACTAL_CAPABILITY:
        artifact, spec = _mandelbrot_tile(payload)
        return artifact, spec, "P5-PGM"
    if capability == OPTIMIZATION_CAPABILITY:
        artifact, spec = _optimization_landscape(payload)
        return artifact, spec, "canonical-json"
    if capability == PARAMETER_SWEEP_CAPABILITY:
        artifact, spec = _parameter_sweep(payload)
        return artifact, spec, "canonical-json"
    if capability == PROCEDURAL_WORLD_CAPABILITY:
        artifact, spec = _procedural_world(payload)
        return artifact, spec, "canonical-json"
    raise ValueError(f"not an executable native mineral: {capability}")


def execute_mineral_capability(
    capability: str,
    payload: Any,
    *,
    worker_root: Path,
) -> dict[str, Any]:
    if capability == REGISTRY_CAPABILITY:
        return registry()
    if capability not in EXECUTABLE_CAPABILITIES:
        raise ValueError(f"mineral capability is not executable: {capability}")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("mineral payload must be an object")

    artifact, spec, encoding = _native_compute(capability, payload)
    work = {
        "kind": "ghot.mineral-work",
        "version": "0",
        "capability": capability,
        "spec": spec,
    }
    work_address = content_address(work)
    artifact_address = content_address(artifact)
    result_body = {
        "kind": "ghot.mineral-result",
        "version": "0",
        "capability": capability,
        "work_address": work_address,
        "artifact_address": artifact_address,
        "artifact_encoding": encoding,
        "verification_contract": next(
            item["verification_contract"]
            for item in MINERAL_REGISTRY
            if item["capability"] == capability
        ),
        "execution_claim": "deterministic-native-computation/v0",
        "verification_status": "UNVERIFIED",
        "laws": [
            "EXECUTION != VERIFICATION",
            "CONTENT ADDRESS != DOMAIN TRUTH",
        ],
    }
    result_id = content_address(result_body)
    base = worker_root.resolve() / "minerals" / "outgoing" / result_id.replace(":", "_")
    base.mkdir(parents=True, exist_ok=True)
    artifact_path = base / ("artifact.pgm" if encoding == "P5-PGM" else "artifact.json")
    artifact_path.write_bytes(artifact)
    result_path = base / "result.v0.json"
    result = {
        **result_body,
        "result_id": result_id,
        "artifact_path": str(artifact_path),
        "result_path": str(result_path),
    }
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


__all__ = [
    "EXECUTABLE_CAPABILITIES",
    "FRACTAL_CAPABILITY",
    "MINERAL_REGISTRY",
    "OPTIMIZATION_CAPABILITY",
    "PARAMETER_SWEEP_CAPABILITY",
    "PROCEDURAL_WORLD_CAPABILITY",
    "REGISTRY_CAPABILITY",
    "capability_offers",
    "execute_mineral_capability",
    "registry",
]
