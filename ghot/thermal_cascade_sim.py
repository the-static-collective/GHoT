#!/usr/bin/env python3
"""THERMAL-DOMINO-CASCADE-002: abstract work/heat/pressure ledger.

NO vessel pressures, volumes, temperatures, steam plumbing, valves,
combustion control, GPIO, networking, real equipment, or hardware actuators.
A proposed pressure-work buffer is accounted in kWh only. This model does
not assert an installation is permitted, safe, beneficial, or economical.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math


@dataclass(frozen=True)
class Scenario:
    fuel_kwh: float = 40.0
    heat_available_fraction: float = 0.75
    hot_stage_kwh: float = 8.0
    heat_engine_shaft_fraction: float = 0.10
    proposed_buffer_share_of_shaft: float = 0.25
    hypothetical_buffer_roundtrip_fraction: float = 0.65
    generator_fraction: float = 0.80
    battery_charge_fraction: float = 0.90
    reject_heat_recovery_fraction: float = 0.90
    heat_bank_fraction: float = 0.70
    house_load_kw: float = 1.0
    proposed_optional_compute_kwh: float = 0.50


def _validate(s: Scenario) -> None:
    data = asdict(s)
    if any(
        isinstance(v, bool) or not isinstance(v, (float, int)) or
        not math.isfinite(v) or v < 0 for v in data.values()
    ):
        raise ValueError("Inputs must be finite and nonnegative.")
    for field in (
        "heat_available_fraction", "heat_engine_shaft_fraction",
        "proposed_buffer_share_of_shaft", "hypothetical_buffer_roundtrip_fraction",
        "generator_fraction", "battery_charge_fraction",
        "reject_heat_recovery_fraction", "heat_bank_fraction"
    ):
        if data[field] > 1:
            raise ValueError(f"{field} must be in [0,1].")
    if s.house_load_kw <= 0:
        raise ValueError("House demand must be positive.")
    if s.hot_stage_kwh > s.fuel_kwh * s.heat_available_fraction:
        raise ValueError("Hot-stage heat cannot exceed available heat.")


def simulate(s: Scenario = Scenario()) -> dict:
    """Illustrative first-law ledger; NOT a heat-engine performance prediction."""
    _validate(s)
    usable = s.fuel_kwh * s.heat_available_fraction
    baseline_loss = s.fuel_kwh - usable
    bypass_heat = usable - s.hot_stage_kwh

    # Heat engine: expansion creates shaft work from a fraction of heat,
    # with rejected heat remaining for possible space-heating recovery.
    shaft = s.hot_stage_kwh * s.heat_engine_shaft_fraction
    rejected = s.hot_stage_kwh - shaft
    captured_reject = rejected * s.reject_heat_recovery_fraction
    unrecovered_reject = rejected - captured_reject

    # Optional hypothetical buffer means work already produced and stored.
    # A higher pressure isn't a new independent source of kWh. No sizing.
    buffer_input = shaft * s.proposed_buffer_share_of_shaft
    buffer_delivered = buffer_input * s.hypothetical_buffer_roundtrip_fraction
    buffer_loss = buffer_input - buffer_delivered

    shaft_to_generator = shaft - buffer_input
    electric_from_generator = shaft_to_generator * s.generator_fraction
    battery_electric = electric_from_generator * s.battery_charge_fraction
    electric_loss = shaft_to_generator - battery_electric

    total_thermal_use = bypass_heat + captured_reject
    heat_bank = total_thermal_use * s.heat_bank_fraction
    immediate_heat = total_thermal_use - heat_bank

    unutilized = baseline_loss + unrecovered_reject + buffer_loss + electric_loss
    useful = total_thermal_use + buffer_delivered + battery_electric
    # Do NOT let the simplified cascade invent energy by double-counting pressure.
    if not math.isclose(s.fuel_kwh, useful + unutilized, rel_tol=0, abs_tol=1e-8):
        raise AssertionError("Broken conservation: output energy exceeds fuel budget.")

    return {
        "schema": "ghot.thermal-domino-cascade/v0",
        "mode": "offline_hypothetical_only",
        "inputs": asdict(s),
        "first_law_kwh": {
            "fuel_input": round(s.fuel_kwh, 6),
            "heating_energy_available": round(usable, 6),
            "heat_engine_hot_stage": round(s.hot_stage_kwh, 6),
            "heat_engine_shaft_work": round(shaft, 6),
            "pressure_buffer_input_work_not_new_energy": round(buffer_input, 6),
            "potential_delivered_work_from_buffer": round(buffer_delivered, 6),
            "battery_energy_after_conversion": round(battery_electric, 6),
            "heat_to_home_after_work_extraction": round(total_thermal_use, 6),
            "heat_to_mass_bank": round(heat_bank, 6),
            "direct_heat": round(immediate_heat, 6),
            "unutilized_energy": round(unutilized, 6),
            "sum_of_useful_outputs": round(useful, 6),
            "energy_closure_error": round(s.fuel_kwh - useful - unutilized, 9),
        },
        "hypothetical_schedule": {
            "mass_bank_hours_at_constant_assumed_load": round(heat_bank/s.house_load_kw, 3),
            "optional_compute": (
                "RUN_ELIGIBLE" if battery_electric >= s.proposed_optional_compute_kwh
                else "HOLD"
            ),
            "source_is_measured": False,
            "pressure_is_a_second_fuel": False,
            "electricity_from_heat_is_free": False,
        },
        "non_goals": [
            "No calculations of vessel pressure, sizing, materials, relief valves or working-fluid inventory.",
            "No pump, boiler, heater, flue or combustion control.",
            "No GHoT authority over independent appliance and smoke/CO safety systems.",
            "No claim of real heat output, mechanical work, electricity, or residential suitability.",
        ],
        "integration": (
            "An independent, professionally qualified thermal/engine module may "
            "report validated net electrical output to GHoT power sensing; "
            "GHoT may schedule nonessential computation only."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(simulate(), indent=2, sort_keys=True))
