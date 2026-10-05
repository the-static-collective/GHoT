#!/usr/bin/env python3
"""Cross-repository bridge between GHoT Mineral Field and GrO.

The bridge exposes two bounded operations for executable specimens:

- mine-ice: produce one Dogram-verified Ice Cube mineral.
- mine-native: produce one deterministic native mineral plus exact-recompute receipt.

It exists only to make cross-repository integration tests explicit. It grants
no admission authority to GrO.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ice_cube import build_work, content_address as ice_content_address, dogram_receipt_for, mine_ice_cube
from mineral_registry import (
    EXECUTABLE_CAPABILITIES,
    execute_mineral_capability,
    verify_native_mineral_result,
)


def _json_arg(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("payload must decode to a JSON object")
    return parsed


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    ice = sub.add_parser("mine-ice")
    ice.add_argument("--root", type=Path, required=True)
    ice.add_argument("--dogram-repo", type=Path, required=True)
    ice.add_argument("--lucas-index", type=int, default=2)
    ice.add_argument("--width", type=int, default=12)
    ice.add_argument("--height", type=int, default=12)
    ice.add_argument("--max-halley-iter", type=int, default=8)

    native = sub.add_parser("mine-native")
    native.add_argument("--root", type=Path, required=True)
    native.add_argument("--capability", required=True)
    native.add_argument("--payload", type=_json_arg, default={})

    verify = sub.add_parser("verify-native")
    verify.add_argument("--result", type=Path, required=True)
    verify.add_argument("--artifact", type=Path, required=True)

    verify_ice = sub.add_parser("verify-ice")
    verify_ice.add_argument("--result", type=Path, required=True)
    verify_ice.add_argument("--artifact", type=Path, required=True)
    verify_ice.add_argument("--dogram-repo", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "mine-ice":
        work = build_work(
            lucas_index=args.lucas_index,
            width=args.width,
            height=args.height,
            max_halley_iter=args.max_halley_iter,
        )
        mined = mine_ice_cube(
            worker_root=args.root,
            dogram_repo=args.dogram_repo,
            work=work,
        )
        output = {
            "kind": "ghot.gro-mineral-bridge-result",
            "version": "0",
            "mineral_id": "math.topology.mapping-torus/v0",
            "capability": "ghot.ice-cube/v0",
            "result_path": str(mined["result_path"]),
            "artifact_path": str(mined["render_path"]),
            "work_address": mined["result"]["work_address"],
            "artifact_address": mined["result"]["render_address"],
            "verification": {
                "kind": "Dogram",
                "status": mined["dogram_receipt"]["status"],
                "claim_scope": mined["dogram_receipt"]["result"]["claim_scope"],
                "receipt": mined["dogram_receipt"],
            },
        }
        print(json.dumps(output))
        return 0

    if args.command == "mine-native":
        if args.capability not in EXECUTABLE_CAPABILITIES:
            raise SystemExit("capability is not a native executable mineral")
        result = execute_mineral_capability(
            args.capability,
            args.payload,
            worker_root=args.root,
        )
        artifact_path = Path(result["artifact_path"])
        verification = verify_native_mineral_result(
            result,
            artifact_path.read_bytes(),
        )
        verification_path = Path(result["result_path"]).parent / "verification.v0.json"
        _write(verification_path, verification)
        output = {
            "kind": "ghot.gro-mineral-bridge-result",
            "version": "0",
            "mineral_id": next(
                item["mineral_id"]
                for item in __import__("mineral_registry").MINERAL_REGISTRY
                if item["capability"] == args.capability
            ),
            "capability": args.capability,
            "result_path": result["result_path"],
            "artifact_path": result["artifact_path"],
            "work_address": result["work_address"],
            "artifact_address": result["artifact_address"],
            "verification_path": str(verification_path),
            "verification": verification,
        }
        print(json.dumps(output))
        return 0

    if args.command == "verify-native":
        result = json.loads(args.result.read_text(encoding="utf-8"))
        verification = verify_native_mineral_result(
            result,
            args.artifact.read_bytes(),
        )
        print(json.dumps(verification))
        return 0 if verification.get("status") == "OK" else 1

    if args.command == "verify-ice":
        result = json.loads(args.result.read_text(encoding="utf-8"))
        artifact = args.artifact.read_bytes()
        if result.get("kind") != "ghot.ice-cube-result":
            raise SystemExit("not an Ice Cube result")
        if ice_content_address(artifact) != result.get("render_address"):
            raise SystemExit("Ice Cube artifact address mismatch")
        receipt = dogram_receipt_for(
            args.dogram_repo,
            result["specimen"],
            artifact,
        )
        if receipt.get("status") != "OK":
            print(json.dumps(receipt))
            return 1
        output = {
            "kind": "ghot.gro-mineral-verification",
            "version": "0",
            "status": "OK",
            "claim_scope": receipt["result"]["claim_scope"],
            "verifier": "Dogram",
            "work_address": result["work_address"],
            "artifact_address": result["render_address"],
            "receipt": receipt,
        }
        print(json.dumps(output))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
