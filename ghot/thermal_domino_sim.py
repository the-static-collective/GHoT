#!/usr/bin/env python3
"""GHoT / THERMAL-DOMINO-HOUSE-001.

OFFLINE, READ-ONLY, DETERMINISTIC energy-budget demonstration.
No network, GPIO, relay writes, heater/chimney controls, pumps, valves,
combustion-air controls, steam, or physical hardware interfaces.
Not a heat-loss calculation, system sizing tool, or safety controller.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Scenario:
    wood_kg: float = 10.0
    assumed_wood_kwh_per_kg: float = 4.0
    assumed_useful_heat_fraction: float = 0.75
    assumed_mass_storage_fraction: float = 0.70
    house_heat_demand_kw: float = 1.0
    teg_watts_while_firing: float = 20.0
    firing_hours: float = 2.0
    charge_path_efficiency: float = 0.90
    battery_initial_wh: float = 30.0
    battery_capacity_wh: float = 100.0
    reserved_battery_wh: float = 30.0
    essential_monitor_watts: float = 3.0
    essential_monitor_hours: float = 8.0
    optional_task_wh: float = 60.0


def _validated(s: Scenario) -> None:
    numeric = asdict(s)
    import math
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in numeric.values()):
        raise ValueError("Scenario fields must be finite numbers.")
    if any(v < 0 for v in numeric.values()):
        raise ValueError("Negative energy, mass, duration or demand is not meaningful.")
    if not 0 <= s.assumed_useful_heat_fraction <= 1:
        raise ValueError("Useful heat fraction must be 0..1.")
    if not 0 <= s.assumed_mass_storage_fraction <= 1:
        raise ValueError("Stored heat fraction must be 0..1.")
    if not 0 <= s.charge_path_efficiency <= 1:
        raise ValueError("Charge path efficiency must be 0..1.")
    if s.battery_initial_wh > s.battery_capacity_wh or s.reserved_battery_wh > s.battery_capacity_wh:
        raise ValueError("Battery constraints inconsistent.")
    if s.wood_kg > 0 and s.assumed_wood_kwh_per_kg == 0:
        raise ValueError("Heating value missing.")
    if s.house_heat_demand_kw <= 0:
        raise ValueError("House heat demand must be positive.")


def simulate(s: Scenario = Scenario()) -> dict:
    """Illustrative arithmetic, not performance prediction or controls."""
    _validated(s)
    wood_kwh = s.wood_kg * s.assumed_wood_kwh_per_kg
    useful_heat_kwh = wood_kwh * s.assumed_useful_heat_fraction
    generated_wh = s.teg_watts_while_firing * s.firing_hours
    # First-law guard: electricity cannot exceed the assumed usable heat input.
    if generated_wh > useful_heat_kwh * 1000:
        raise ValueError("TEG claim exceeds modeled energy budget.")
    # Conservative accounting: count harvested electricity as a diversion
    # from available delivered room heat; in reality heat paths are coupled.
    delivered_heat_kwh = useful_heat_kwh - generated_wh / 1000
    bank_kwh = delivered_heat_kwh * s.assumed_mass_storage_fraction
    direct_heat_kwh = delivered_heat_kwh - bank_kwh
    harvested_battery_wh = generated_wh * s.charge_path_efficiency
    available_charge_wh = min(
        s.battery_capacity_wh - s.battery_initial_wh, harvested_battery_wh
    )
    stored_battery_wh = s.battery_initial_wh + available_charge_wh
    essential_wh = s.essential_monitor_watts * s.essential_monitor_hours
    after_essential_wh = max(0.0, stored_battery_wh - essential_wh)
    spendable_wh = max(0.0, after_essential_wh - s.reserved_battery_wh)
    # This is an advisory scheduling choice. No actual electrical switch.
    optional_action = "RUN_ELIGIBLE" if s.optional_task_wh <= spendable_wh else "HOLD"
    duration_hours = bank_kwh / s.house_heat_demand_kw
    return {
        "schema": "ghot.thermal-domino-budget/v0",
        "mode": "offline_hypothetical_only",
        "scope": "advisory_compute_routing_not_heater_control",
        "inputs": asdict(s),
        "thermal_budget": {
            "wood_energy_kwh": round(wood_kwh, 3),
            "assumed_useful_heat_kwh": round(useful_heat_kwh, 3),
            "assumed_heat_to_room_after_electric_diversion_kwh": round(delivered_heat_kwh, 3),
            "assumed_mass_stored_kwh": round(bank_kwh, 3),
            "assumed_immediate_heat_kwh": round(direct_heat_kwh, 3),
            "bank_duration_at_assumed_load_h": round(duration_hours, 2),
            "not_prediction": "Building heat loss, chimney losses, and thermal time curves are not modeled."
        },
        "electric_budget": {
            "assumed_teg_raw_wh": round(generated_wh, 2),
            "assumed_battery_harvest_wh": round(available_charge_wh, 2),
            "battery_after_charge_wh": round(stored_battery_wh, 2),
            "essential_monitor_demand_wh": round(essential_wh, 2),
            "battery_after_essential_wh": round(after_essential_wh, 2),
            "battery_above_reserve_wh": round(spendable_wh, 2),
            "optional_compute": optional_action,
        },
        "ghot_observations": {
            "power_source": "experimental_wood_heat_teg",
            "renewable_surplus": False,
            "renewable_claim": "not_inferred_from_wood_combustion",
            "sensor_trust": "hypothetical_input_not_measured",
            "willingness": "undetermined_until_real_battery_controller_measurement",
            "proposed_capabilities": [
                "sensor.room_temperature.read",
                "sensor.mass_surface_temperature.read",
                "sensor.charge_controller_power.read",
                "sensor.battery_state.read",
            ],
            "forbidden": [
                "actuator.flue_damper.set",
                "actuator.combustion_air.set",
                "actuator.pressure_relief.set",
                "actuator.steam_valve.set",
                "actuator.heater_safety_override.set"
            ],
        },
        "safety_boundary": (
            "Independent certified heating appliance, chimney, smoke/CO alarms, "
            "overtemperature protection, proper permits and qualified installation. "
            "No experimental pressure vessel or automatic heater safety control. "
            "GHoT may observe and schedule optional compute only."
        )
    }


if __name__ == "__main__":
    print(json.dumps(simulate(), indent=2, sort_keys=True))
