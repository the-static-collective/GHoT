#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 007."""

from __future__ import annotations

import json

from power_field import apply_power_policy, derive_willingness


OFFERS = [
    {"capability": "system.echo", "available": True},
    {"capability": "sensor.temperature.read", "available": True},
    {"capability": "llm.infer.small", "available": True},
    {"capability": "llm.infer.large", "available": True},
    {"capability": "render.video", "available": True},
]


def powered(power: dict) -> dict:
    state, reasons = derive_willingness(power)
    record = {**power, "willingness": state, "willingness_reasons": reasons}
    adjusted = apply_power_policy(OFFERS, record)
    return {
        "power": record,
        "offers": {
            offer["capability"]: offer["available"]
            for offer in adjusted
        },
    }


def main() -> int:
    solar = powered({
        "battery_percent": 91,
        "source": "solar",
        "charging": True,
        "renewable_surplus": True,
        "temperature_c": 52,
        "load_per_cpu_1m": 0.3,
    })
    conserve = powered({
        "battery_percent": 21,
        "source": "battery",
        "charging": False,
        "renewable_surplus": False,
        "temperature_c": 55,
        "load_per_cpu_1m": 0.4,
    })
    critical = powered({
        "battery_percent": 8,
        "source": "battery",
        "charging": False,
        "renewable_surplus": False,
        "temperature_c": 58,
        "load_per_cpu_1m": 0.2,
    })
    hot = powered({
        "battery_percent": 88,
        "source": "ac",
        "charging": True,
        "renewable_surplus": False,
        "temperature_c": 89,
        "load_per_cpu_1m": 0.5,
    })

    passed = (
        solar["power"]["willingness"] == "abundant"
        and solar["offers"]["render.video"] is True
        and conserve["power"]["willingness"] == "conserve"
        and conserve["offers"]["render.video"] is False
        and conserve["offers"]["llm.infer.small"] is True
        and critical["power"]["willingness"] == "critical"
        and critical["offers"]["system.echo"] is True
        and critical["offers"]["sensor.temperature.read"] is True
        and critical["offers"]["llm.infer.small"] is False
        and hot["power"]["willingness"] == "conserve"
        and hot["offers"]["llm.infer.large"] is False
    )

    print(json.dumps({
        "simulation_passed": passed,
        "solar_surplus": solar,
        "battery_conserve": conserve,
        "battery_critical": critical,
        "thermal_pressure": hot,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
