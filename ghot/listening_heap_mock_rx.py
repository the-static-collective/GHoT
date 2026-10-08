#!/usr/bin/env python3
"""Deliberately synthetic RX-only donor. No hardware, tuner or network access."""
from __future__ import annotations

import json
import os
import sys

CAPABILITIES = {
    "radio.rx.simulated.weather": ("weather", [1, 1, 0, 0, 1, 0, 1, 0]),
    "radio.rx.simulated.ism": ("ism", [0, 3, 8, 2, 7, 1, 6, 0]),
}


def run(payload: object, capability: str) -> dict:
    if type(payload) is not dict or set(payload) != {"action", "band"}:
        raise ValueError("SIMULATED_RX_REQUIRES_EXACT_INPUT")
    if payload["action"] != "receive_simulation":
        raise ValueError("TRANSMISSION_FORBIDDEN")
    if capability not in CAPABILITIES:
        raise ValueError("UNKNOWN_SIMULATED_RX_CAPABILITY")
    band, bins = CAPABILITIES[capability]
    if payload["band"] != band:
        raise ValueError("SIMULATED_BAND_CAPABILITY_MISMATCH")
    return {
        "schema": "simulation.rf-window/v0",
        "status": "ok",
        "source": "SIMULATION",
        "mode": "RECEIVE_ONLY",
        "band": band,
        "bins": bins,
        "hardware_observed": False,
        "physical_emission": False,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        capability = os.environ.get("GHOT_EXTERNAL_CAPABILITY", "")
        print(json.dumps(run(payload, capability), sort_keys=True))
        return 0
    except (ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
