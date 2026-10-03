#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 008."""

from __future__ import annotations

import json

from energy_scheduler import decide_from_candidates


def offer(capability: str, power_class: str = "heavy", available: bool = True) -> dict:
    return {
        "kind": "ghot.offer",
        "version": "0",
        "capability": capability,
        "available": available,
        "power": {
            "class": power_class,
            "willingness": "normal",
            "policy_reasons": [],
        },
    }


def candidate(
    node_id: str,
    *,
    location: str,
    willingness: str,
    source: str,
    renewable_surplus: bool,
    capability: str = "render.video",
    available: bool = True,
) -> dict:
    o = offer(capability, "heavy", available)
    o["power"]["willingness"] = willingness
    return {
        "node_id": node_id,
        "location": location,
        "url": None if location == "local" else f"http://{node_id}.invalid:7788",
        "field_state": "awake",
        "body": {
            "node_id": node_id,
            "power": {
                "willingness": willingness,
                "source": source,
                "charging": source != "battery",
                "renewable_surplus": renewable_surplus,
            },
            "offers": [o],
        },
    }


def main() -> int:
    battery_heap = [
        candidate(
            "body-local",
            location="local",
            willingness="normal",
            source="battery",
            renewable_surplus=False,
        ),
        candidate(
            "body-remote",
            location="remote",
            willingness="normal",
            source="battery",
            renewable_surplus=False,
        ),
    ]

    hold = decide_from_candidates(
        battery_heap,
        "render.video",
        urgency="background",
        deferrable=True,
        data_node_id=None,
    )

    immediate = decide_from_candidates(
        battery_heap,
        "render.video",
        urgency="immediate",
        deferrable=False,
        data_node_id=None,
    )

    solar_heap = battery_heap + [
        candidate(
            "body-solar",
            location="remote",
            willingness="abundant",
            source="solar",
            renewable_surplus=True,
        )
    ]
    solar = decide_from_candidates(
        solar_heap,
        "render.video",
        urgency="background",
        deferrable=True,
        data_node_id=None,
    )

    locality_heap = [
        candidate(
            "body-data",
            location="remote",
            willingness="normal",
            source="ac",
            renewable_surplus=False,
        ),
        candidate(
            "body-solar",
            location="remote",
            willingness="abundant",
            source="solar",
            renewable_surplus=True,
        ),
    ]
    locality = decide_from_candidates(
        locality_heap,
        "render.video",
        urgency="normal",
        deferrable=False,
        data_node_id="body-data",
    )

    withdrawn_heap = [
        candidate(
            "body-conserve",
            location="remote",
            willingness="conserve",
            source="battery",
            renewable_surplus=False,
            available=False,
        )
    ]
    withdrawn_heap[0]["body"]["offers"][0]["power"]["policy_reasons"] = [
        "withdrawn: heavy capability under conserve willingness"
    ]
    withdrawn = decide_from_candidates(
        withdrawn_heap,
        "render.video",
        urgency="background",
        deferrable=True,
        data_node_id=None,
    )

    passed = (
        hold["action"] == "hold"
        and immediate["action"] in {"run_here", "run_there"}
        and solar["action"] == "run_there"
        and solar["selected"]["node_id"] == "body-solar"
        and locality["action"] == "run_there"
        and locality["selected"]["node_id"] == "body-data"
        and withdrawn["action"] == "hold"
    )

    print(json.dumps({
        "simulation_passed": passed,
        "background_battery_only": hold,
        "immediate_battery_only": immediate,
        "background_with_solar": solar,
        "data_locality": locality,
        "power_withdrawn_deferrable": withdrawn,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
