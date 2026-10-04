#!/usr/bin/env python3
"""GHoT Ice Cube 001 producer.

Experiment 030 turns deferrable CPU time into a content-addressed mathematical
artifact. The worker renders a Halley basin for periodic points of the
Mandelbrot quadratic family at a Lucas-selected period, binds the render to an
SL(2,Z) Fibonacci/Lucas torus monodromy, asks Dogram for a bounded independent
verification receipt, and emits reLATTE-shaped work/execution witnesses.

The producer owns computation, not truth:
    GHOT EXECUTION RECEIPT != DOGRAM VERIFICATION RECEIPT
    BOTH != OWNER-LOCAL ADMISSION
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import json
import math
import sys
import uuid
from pathlib import Path
from typing import Any

from relatte_identity import (
    IdentityKey,
    identity_safe,
    sign_crossing,
    sign_receipt,
    timestamp_now,
    verify_crossing,
    verify_receipt,
)


FAMILY = "lucas-halley-mandelbrot-mapping-torus/v0"
WORK_KIND = "ghot.ice-cube-work"
WORK_VERSION = "0"
RESULT_KIND = "ghot.ice-cube-result"
RESULT_VERSION = "0"
CAPABILITY_REF = "ghot.ice-cube/v0"
EXECUTION_CONTRACT = "ghot.ice-cube-worker@0"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_address(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical_bytes(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def lucas(index: int) -> int:
    if index < 0:
        raise ValueError("lucas_index must be non-negative")
    a, b = 2, 1
    if index == 0:
        return a
    for _ in range(1, index):
        a, b = b, a + b
    return b


def mat_mul(a, b):
    return (
        (
            a[0][0] * b[0][0] + a[0][1] * b[1][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1],
        ),
        (
            a[1][0] * b[0][0] + a[1][1] * b[1][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1],
        ),
    )


def fibonacci_matrix_power(power: int):
    result = ((1, 0), (0, 1))
    base = ((1, 1), (1, 0))
    n = power
    while n:
        if n & 1:
            result = mat_mul(result, base)
        base = mat_mul(base, base)
        n >>= 1
    return result


def period_terms(z: complex, c: complex, period: int):
    value = z
    d1 = 1 + 0j
    d2 = 0 + 0j
    for _ in range(period):
        d2 = 2 * (d1 * d1 + value * d2)
        d1 = 2 * value * d1
        value = value * value + c
    return value - z, d1 - 1, d2


def residual(z: complex, c: complex, period: int) -> float:
    try:
        g, _g1, _g2 = period_terms(z, c, period)
        value = abs(g)
        return value if math.isfinite(value) else float("inf")
    except OverflowError:
        return float("inf")


def halley_step(z: complex, c: complex, period: int) -> complex | None:
    try:
        g, g1, g2 = period_terms(z, c, period)
        denominator = 2 * g1 * g1 - g * g2
        if (
            not math.isfinite(denominator.real)
            or not math.isfinite(denominator.imag)
            or abs(denominator) < 1e-30
        ):
            return None
        candidate = z - (2 * g * g1) / denominator
        if not math.isfinite(candidate.real) or not math.isfinite(candidate.imag):
            return None
        return candidate
    except (OverflowError, ZeroDivisionError):
        return None


def halley_iterate(z: complex, c: complex, period: int, steps: int) -> complex:
    current = z
    for _ in range(steps):
        next_value = halley_step(current, c, period)
        if next_value is None:
            break
        current = next_value
    return current


def build_work(
    *,
    lucas_index: int = 5,
    c_re: str = "0",
    c_im: str = "0",
    width: int = 96,
    height: int = 96,
    max_halley_iter: int = 12,
    tolerance: str = "1e-9",
    fiber_count: int = 72,
) -> dict[str, Any]:
    period = lucas(lucas_index)
    return {
        "kind": WORK_KIND,
        "version": WORK_VERSION,
        "family": FAMILY,
        "lucas_index": lucas_index,
        "period": period,
        "c": {"re": str(c_re), "im": str(c_im)},
        "halley": {
            "tolerance": str(tolerance),
            "witness_steps": 12,
        },
        "mapping_torus": {
            "fiber_count": fiber_count,
        },
        "render": {
            "format": "P5-PGM",
            "width": width,
            "height": height,
            "xmin": "-1.2",
            "xmax": "1.2",
            "ymin": "-1.2",
            "ymax": "1.2",
            "max_halley_iter": max_halley_iter,
            "challenge_count": 16,
        },
    }


def work_address(work: dict[str, Any]) -> str:
    return content_address(work)


def challenge_coordinates(work: dict[str, Any], count: int) -> list[tuple[int, int]]:
    width = int(work["render"]["width"])
    height = int(work["render"]["height"])
    seed = hashlib.sha256(canonical_bytes(work)).digest()
    coords: list[tuple[int, int]] = []
    counter = 0
    while len(coords) < min(count, width * height):
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        item = (
            int.from_bytes(block[:8], "big") % width,
            int.from_bytes(block[8:16], "big") % height,
        )
        if item not in coords:
            coords.append(item)
        counter += 1
    return coords


def pixel_for(work: dict[str, Any], x: int, y: int) -> int:
    render = work["render"]
    width = int(render["width"])
    height = int(render["height"])
    xmin = float(render["xmin"])
    xmax = float(render["xmax"])
    ymin = float(render["ymin"])
    ymax = float(render["ymax"])
    max_iter = int(render["max_halley_iter"])
    tolerance = float(work["halley"]["tolerance"])
    period = int(work["period"])
    c = complex(float(work["c"]["re"]), float(work["c"]["im"]))

    re = xmin if width == 1 else xmin + (xmax - xmin) * x / (width - 1)
    im = ymin if height == 1 else ymax - (ymax - ymin) * y / (height - 1)
    z = complex(re, im)

    used = max_iter
    for step in range(max_iter + 1):
        if residual(z, c, period) <= tolerance:
            used = step
            break
        if step == max_iter:
            break
        next_value = halley_step(z, c, period)
        if next_value is None:
            break
        z = next_value

    if max_iter <= 0:
        return 255
    return max(0, min(255, 255 - round(255 * used / max_iter)))


def render_pgm(work: dict[str, Any]) -> tuple[bytes, list[dict[str, int]]]:
    width = int(work["render"]["width"])
    height = int(work["render"]["height"])
    pixels = bytearray(width * height)
    for y in range(height):
        row = y * width
        for x in range(width):
            pixels[row + x] = pixel_for(work, x, y)
    header = f"P5\n{width} {height}\n255\n".encode("ascii")
    data = header + bytes(pixels)
    coords = challenge_coordinates(work, int(work["render"]["challenge_count"]))
    challenges = [
        {"x": x, "y": y, "value": int(pixels[y * width + x])}
        for x, y in coords
    ]
    return data, challenges


def make_halley_witnesses(work: dict[str, Any]) -> list[dict[str, Any]]:
    c = complex(float(work["c"]["re"]), float(work["c"]["im"]))
    period = int(work["period"])
    tolerance = float(work["halley"]["tolerance"])
    steps = int(work["halley"]["witness_steps"])
    seeds = [
        0.10 + 0.05j,
        -0.10 + 0.05j,
        0.20 - 0.10j,
        -0.20 - 0.10j,
        0.35 + 0.12j,
        -0.35 + 0.12j,
        0.55 - 0.15j,
        -0.55 - 0.15j,
    ]
    witnesses: list[dict[str, Any]] = []
    for z0 in seeds:
        final = halley_iterate(z0, c, period, steps)
        if residual(final, c, period) > tolerance:
            continue
        witnesses.append({
            "z0": {
                "re": format(z0.real, ".17g"),
                "im": format(z0.imag, ".17g"),
            },
            "steps": steps,
            "final": {
                "re": format(final.real, ".17g"),
                "im": format(final.imag, ".17g"),
            },
        })
    if len(witnesses) < 4:
        raise RuntimeError("not enough converged Halley witnesses")
    return witnesses


def make_work_crossing(
    work: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    address = work_address(work)
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "GHOT_ICE_CUBE_WORK",
        "payload_refs": [address],
        "requested_effect": identity_safe({
            "operation": "mine-ice-cube",
            "work_address": address,
            "family": FAMILY,
            "deferrable": True,
        }),
        "capability_ref": CAPABILITY_REF,
        "privacy_policy": {
            "transport": "replaceable",
            "payload_encryption": False,
        },
        "audience_policy": {
            "capability": CAPABILITY_REF,
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "ice-cube-work/v0",
            "relatte_core_semantics_required": False,
        },
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    crossing = sign_crossing(envelope, signer)
    if not verify_crossing(crossing):
        raise RuntimeError("new Ice Cube work crossing failed verification")
    return crossing


def make_execution_receipt(
    work_crossing: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
    specimen_address: str,
    render_address: str,
    dogram_receipt_address: str,
) -> dict[str, Any]:
    receipt = {
        "schema": "relatte.receipt/v0",
        "receipt_id": "",
        "crossing_id": work_crossing["crossing_id"],
        "world_id": f"ghot-node:{node_id}",
        "receiver_particular": signer.particular(),
        "kind": "EXECUTED",
        "semantic_effect": "artifact-produced",
        "contract_ref": EXECUTION_CONTRACT,
        "pre_state_ref": None,
        "post_state_ref": specimen_address,
        "descendant_refs": [
            specimen_address,
            render_address,
            dogram_receipt_address,
        ],
        "residual_refs": [],
        "note": "Ice Cube computation completed; Dogram verification remains a separate claim.",
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "ghot_profile": "ice-cube-execution/v0",
            "specimen_address": specimen_address,
            "render_address": render_address,
            "dogram_receipt_address": dogram_receipt_address,
            "execution_is_not_verification": True,
        }),
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    signed = sign_receipt(receipt, signer)
    if not verify_receipt(signed):
        raise RuntimeError("new Ice Cube execution receipt failed verification")
    return signed


def _node_id_at(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "node-id"
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return path.read_text(encoding="utf-8").strip()
    node_id = f"node-{uuid.uuid4()}"
    path.write_text(node_id + "\n", encoding="utf-8")
    return node_id


def verify_with_dogram(
    dogram_repo: Path,
    specimen: dict[str, Any],
    render_bytes: bytes,
) -> dict[str, Any]:
    dogram_repo = dogram_repo.resolve()
    module_path = dogram_repo / "dogram" / "ice_cube.py"
    if not module_path.exists():
        raise RuntimeError(
            "Dogram Ice Cube verifier not found; use Dogram branch impl/ice-cube-001"
        )
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(dogram_repo))
        importlib.invalidate_caches()
        module = importlib.import_module("dogram.ice_cube")
        origin = Path(module.__file__).resolve()
        if dogram_repo not in origin.parents:
            raise RuntimeError(f"wrong Dogram module loaded: {origin}")
        receipt = module.verify_ice_cube(specimen, render_bytes)
    finally:
        sys.path[:] = old_path
    if receipt.get("status") != "OK":
        raise RuntimeError(
            "Dogram refused Ice Cube specimen: "
            + "; ".join(str(x) for x in receipt.get("residuals") or [])
        )
    return receipt


def mine_ice_cube(
    *,
    worker_root: Path,
    dogram_repo: Path,
    work: dict[str, Any],
) -> dict[str, Any]:
    worker_root = worker_root.resolve()
    node_id = _node_id_at(worker_root)
    signer = IdentityKey.load_or_create(
        worker_root / "identity" / "body-p256.pem"
    )
    crossing = make_work_crossing(work, signer=signer, node_id=node_id)

    render_bytes, pixel_challenges = render_pgm(work)
    render_address = content_address(render_bytes)
    matrix_power = 2 * int(work["lucas_index"])
    matrix = fibonacci_matrix_power(matrix_power)
    trace = matrix[0][0] + matrix[1][1]
    determinant = (
        matrix[0][0] * matrix[1][1]
        - matrix[0][1] * matrix[1][0]
    )
    fiber_count = int(work["mapping_torus"]["fiber_count"])
    shift = trace % fiber_count
    components = math.gcd(fiber_count, shift)

    specimen_core = {
        "family": FAMILY,
        "work_address": work_address(work),
        "render_address": render_address,
        "monodromy_trace": trace,
    }
    specimen_id = "ice-cube-v0:" + hashlib.sha256(
        canonical_bytes(specimen_core)
    ).hexdigest()

    specimen = {
        "schema": "static.ice-cube-specimen/v0",
        "specimen_id": specimen_id,
        "family": FAMILY,
        "work": work,
        "work_address": work_address(work),
        "lucas_value": lucas(int(work["lucas_index"])),
        "monodromy": {
            "power": matrix_power,
            "matrix": [list(matrix[0]), list(matrix[1])],
            "trace": trace,
            "determinant": determinant,
        },
        "mapping_torus": {
            "fiber_count": fiber_count,
            "shift": shift,
            "normalized_shift": shift % fiber_count,
            "components": components,
            "orbit_length": fiber_count // components,
        },
        "halley_witnesses": make_halley_witnesses(work),
        "render": {
            "address": render_address,
            "challenge_count": len(pixel_challenges),
            "pixel_challenges": pixel_challenges,
        },
    }
    specimen_address = content_address(specimen)

    dogram_receipt = verify_with_dogram(
        dogram_repo,
        specimen,
        render_bytes,
    )
    dogram_receipt_address = content_address(dogram_receipt)
    execution_receipt = make_execution_receipt(
        crossing,
        signer=signer,
        node_id=node_id,
        specimen_address=specimen_address,
        render_address=render_address,
        dogram_receipt_address=dogram_receipt_address,
    )

    base = worker_root / "ice-cubes" / "outgoing" / specimen_id.replace(":", "_")
    base.mkdir(parents=True, exist_ok=True)
    render_path = base / "render.pgm"
    specimen_path = base / "specimen.json"
    dogram_path = base / "dogram.receipt.json"
    work_crossing_path = base / "work.crossing.json"
    execution_path = base / "execution.receipt.json"
    result_path = base / "result.v0.json"

    render_path.write_bytes(render_bytes)
    for path, value in (
        (specimen_path, specimen),
        (dogram_path, dogram_receipt),
        (work_crossing_path, crossing),
        (execution_path, execution_receipt),
    ):
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    result = {
        "kind": RESULT_KIND,
        "version": RESULT_VERSION,
        "specimen_id": specimen_id,
        "family": FAMILY,
        "work_address": work_address(work),
        "specimen_address": specimen_address,
        "render_address": render_address,
        "dogram_receipt_address": dogram_receipt_address,
        "dogram_status": dogram_receipt["status"],
        "execution_receipt_id": execution_receipt["receipt_id"],
        "work_crossing_id": crossing["crossing_id"],
        "render_encoding": "base64",
        "render_base64": base64.b64encode(render_bytes).decode("ascii"),
        "specimen": specimen,
        "dogram_receipt": dogram_receipt,
    }
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "work": work,
        "work_crossing": crossing,
        "render_bytes": render_bytes,
        "render_path": render_path,
        "specimen": specimen,
        "specimen_address": specimen_address,
        "dogram_receipt": dogram_receipt,
        "dogram_receipt_address": dogram_receipt_address,
        "execution_receipt": execution_receipt,
        "result": result,
        "result_path": result_path,
        "result_relative_path": str(result_path.relative_to(worker_root)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine one Lucas/Halley/Mandelbrot mapping-torus Ice Cube."
    )
    parser.add_argument("--root", type=Path, default=Path(".ghot"))
    parser.add_argument("--dogram-repo", type=Path, required=True)
    parser.add_argument("--lucas-index", type=int, default=5)
    parser.add_argument("--width", type=int, default=96)
    parser.add_argument("--height", type=int, default=96)
    parser.add_argument("--max-halley-iter", type=int, default=12)
    parser.add_argument("--c-re", default="0")
    parser.add_argument("--c-im", default="0")
    args = parser.parse_args()

    work = build_work(
        lucas_index=args.lucas_index,
        c_re=args.c_re,
        c_im=args.c_im,
        width=args.width,
        height=args.height,
        max_halley_iter=args.max_halley_iter,
    )
    mined = mine_ice_cube(
        worker_root=args.root,
        dogram_repo=args.dogram_repo,
        work=work,
    )
    print(json.dumps({
        "specimen_id": mined["specimen"]["specimen_id"],
        "work_crossing_id": mined["work_crossing"]["crossing_id"],
        "execution_receipt_id": mined["execution_receipt"]["receipt_id"],
        "dogram_status": mined["dogram_receipt"]["status"],
        "specimen_address": mined["specimen_address"],
        "render_address": mined["specimen"]["render"]["address"],
        "result_path": str(mined["result_path"]),
        "render_path": str(mined["render_path"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
