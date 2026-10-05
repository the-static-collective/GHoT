#!/usr/bin/env python3
"""GHoT ↔ GrO Mineral bridge smoke proof."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_bridge(script: Path, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    script = repo / "ghot" / "gro_mineral_bridge.py"
    dogram = repo / "_dogram_ice"

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        native = run_bridge(
            script,
            "mine-native",
            "--root",
            str(base / "native"),
            "--capability",
            "mineral.parameter-sweep/v0",
            "--payload",
            json.dumps({
                "r_values": ["3", "13/4", "7/2"],
                "x0": "1/2",
                "steps": 7,
            }),
        )
        assert native["verification"]["status"] == "OK"

        native_recheck = run_bridge(
            script,
            "verify-native",
            "--result",
            native["result_path"],
            "--artifact",
            native["artifact_path"],
        )
        assert native_recheck == native["verification"]

        damaged = base / "damaged-artifact.json"
        raw = bytearray(Path(native["artifact_path"]).read_bytes())
        raw[-1] ^= 0x01
        damaged.write_bytes(bytes(raw))
        refused = subprocess.run(
            [
                sys.executable,
                str(script),
                "verify-native",
                "--result",
                native["result_path"],
                "--artifact",
                str(damaged),
            ],
            text=True,
            capture_output=True,
        )
        assert refused.returncode == 1
        refused_receipt = json.loads(
            [line for line in refused.stdout.splitlines() if line.strip()][-1]
        )
        assert refused_receipt["status"] == "REFUSED"

        ice = run_bridge(
            script,
            "mine-ice",
            "--root",
            str(base / "ice"),
            "--dogram-repo",
            str(dogram),
            "--lucas-index",
            "2",
            "--width",
            "10",
            "--height",
            "10",
            "--max-halley-iter",
            "8",
        )
        assert ice["verification"]["status"] == "OK"

        ice_recheck = run_bridge(
            script,
            "verify-ice",
            "--result",
            ice["result_path"],
            "--artifact",
            ice["artifact_path"],
            "--dogram-repo",
            str(dogram),
        )
        assert ice_recheck["status"] == "OK"
        assert ice_recheck["receipt"] == ice["verification"]["receipt"]

        print(json.dumps({
            "simulation_passed": True,
            "native": {
                "capability": native["capability"],
                "verification": native["verification"]["status"],
                "exact_receipt_reproduced": True,
                "corrupted_artifact_refused": True,
            },
            "ice": {
                "capability": ice["capability"],
                "verification": ice["verification"]["status"],
                "dogram_receipt_reproduced": True,
            },
            "laws": [
                "EXECUTION != VERIFICATION",
                "EXACT RECOMPUTE != UNIVERSAL VALUE",
                "VERIFICATION != ADMISSION",
            ],
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
