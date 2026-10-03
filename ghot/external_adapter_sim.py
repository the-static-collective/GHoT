#!/usr/bin/env python3
"""Simulation for the generic external adapter manifest surface."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from executor_pantry import derive_offers, execute_adapter, probe_executors


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ghot-external-adapter-") as raw:
        root = Path(raw)
        script = root / "adapter.py"
        manifest = root / "adapter-manifest.json"
        script.write_text(
            "import json,sys\n"
            "payload=json.load(sys.stdin)\n"
            "print(json.dumps({'status':'ok','echo':payload}))\n",
            encoding="utf-8",
        )
        manifest.write_text(json.dumps({
            "schema": "ghot.external-adapter-manifest/v0",
            "adapter_id": "simulation.echo",
            "capabilities": [{
                "capability": "creative.simulation.echo",
                "protocol": "stdin-json/stdout-json-v0",
                "command": "python3",
                "args": ["adapter.py"],
                "timeout_seconds": 5,
                "limits": {
                    "network": False,
                    "arbitrary_shell": False,
                },
            }],
        }), encoding="utf-8")

        old = os.environ.get("GHOT_ADAPTER_MANIFESTS")
        os.environ["GHOT_ADAPTER_MANIFESTS"] = str(manifest)
        try:
            executors = probe_executors()
            external = next(
                item for item in executors
                if item["name"] == "external:simulation.echo"
            )
            assert external["available"] is True
            assert external["capabilities"] == ["creative.simulation.echo"]
            offers = derive_offers(executors)
            offer = next(
                item for item in offers
                if item["capability"] == "creative.simulation.echo"
            )
            assert offer["limits"]["network"] is False
            assert offer["limits"]["remote_shell"] is False

            output = execute_adapter(
                "creative.simulation.echo",
                {"seed": "house"},
            )
            assert output["adapter_id"] == "simulation.echo"
            assert output["result"]["status"] == "ok"
            assert output["result"]["echo"] == {"seed": "house"}
        finally:
            if old is None:
                os.environ.pop("GHOT_ADAPTER_MANIFESTS", None)
            else:
                os.environ["GHOT_ADAPTER_MANIFESTS"] = old

    print(json.dumps({
        "status": "ok",
        "law": "GHOT != DONOR SEMANTICS",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
