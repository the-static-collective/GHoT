#!/usr/bin/env python3
"""THERMAL-FLOW-FEEDBACK-003 · deterministic read-only finite-energy flow.

The hot-stage conversion is computed by thermal_cascade_sim.py (002).
This simulation unfolds that output in time: passive masonry heat release,
building heat capture, optional electronic-work waste heat, and GHoT's
ADVISORY compute scheduling with battery reserve.

NO combustion, chimney, pressure, heat-exchanger, fluid pump, valve, thermostat,
home HVAC, life-safety, grid, or hardware actuation. No equipment is controlled.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
import math

from thermal_cascade_sim import Scenario as CascadeScenario
from thermal_cascade_sim import simulate as cascade_simulate


@dataclass(frozen=True)
class FlowPolicy:
    hours: int = 24
    passive_mass_release_per_hour: float = 0.065
    mass_release_captured_indoors: float = 0.90
    house_heat_demand_kwh_per_hour: float = 1.0
    battery_reserve_kwh: float = 0.20
    optional_task_electric_kwh: float = 0.06
    electronics_heat_captured_indoors: float = 0.90
    task_allowed_if_heat_deficit_at_least_kwh: float = 0.02


def _check(p: FlowPolicy) -> None:
    d = asdict(p)
    if type(p.hours) is not int or not 1 <= p.hours <= 168:
        raise ValueError("Hours must be an integer in [1,168].")
    for key, v in d.items():
        if key == "hours":
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError("Policies must have finite, nonnegative numeric values.")
    for key in ("passive_mass_release_per_hour", "mass_release_captured_indoors",
                "electronics_heat_captured_indoors"):
        if d[key] > 1:
            raise ValueError(f"{key} cannot exceed 100%.")
    if p.house_heat_demand_kwh_per_hour <= 0:
        raise ValueError("House heat demand must be positive.")
    if p.optional_task_electric_kwh <= 0:
        raise ValueError("Optional task must consume a positive finite energy quantity.")


def simulate(p: FlowPolicy = FlowPolicy(), source: CascadeScenario = CascadeScenario()) -> dict:
    """A heat/motion/electricity ledger; hypothetical energy quantities only."""
    _check(p)
    upstream = cascade_simulate(source)["first_law_kwh"]
    bank = upstream["heat_to_mass_bank"]
    battery = upstream["battery_energy_after_conversion"]
    work_buffer = upstream["potential_delivered_work_from_buffer"]
    direct_heat = upstream["direct_heat"]
    previous_losses = upstream["unutilized_energy"]
    initial_fuel = upstream["fuel_input"]

    delivered_from_mass = 0.0
    escaped_from_mass = 0.0
    delivered_electronics_heat = 0.0
    escaped_electronics_heat = 0.0
    spent_optional_electric = 0.0
    unmet_heating = 0.0
    excessive_heating = 0.0
    rows: list[dict] = []

    for hour in range(p.hours):
        # Passive masonry heat flow is determined by a fixed, illustrative
        # thermal-transfer assumption, never by GHoT valve or damper control.
        released = bank * p.passive_mass_release_per_hour
        bank -= released
        room_from_mass = released * p.mass_release_captured_indoors
        outdoor_mass_loss = released - room_from_mass
        delivered_from_mass += room_from_mass
        escaped_from_mass += outdoor_mass_loss
        needed_after_mass = max(0.0, p.house_heat_demand_kwh_per_hour - room_from_mass)

        # Control feedback is INFORMATION ONLY: given modeled battery
        # state and heat demand, suggest an optional compute task or HOLD.
        # The calculation cannot act on a heater, generator, valve or pump.
        has_budget = (
            battery + 1e-12 >=
            p.battery_reserve_kwh + p.optional_task_electric_kwh
        )
        wants_heat = needed_after_mass + 1e-12 >= p.task_allowed_if_heat_deficit_at_least_kwh
        run = has_budget and wants_heat

        captured_compute_heat = 0.0
        if run:
            battery -= p.optional_task_electric_kwh
            spent_optional_electric += p.optional_task_electric_kwh
            captured_compute_heat = (
                p.optional_task_electric_kwh * p.electronics_heat_captured_indoors
            )
            delivered_electronics_heat += captured_compute_heat
            escaped_electronics_heat += p.optional_task_electric_kwh - captured_compute_heat

        to_room = room_from_mass + captured_compute_heat
        unmet = max(0.0, p.house_heat_demand_kwh_per_hour - to_room)
        excess = max(0.0, to_room - p.house_heat_demand_kwh_per_hour)
        unmet_heating += unmet
        excessive_heating += excess

        rows.append({
            "hour": hour + 1,
            "sensor_data": "synthetic_model_only",
            "mass_bank_kwh_after": round(bank, 6),
            "battery_kwh_after": round(battery, 6),
            "heat_passively_delivered_to_room_kwh": round(room_from_mass, 6),
            "optional_computing_heat_to_room_kwh": round(captured_compute_heat, 6),
            "hourly_unmet_heat_kwh": round(unmet, 6),
            "hourly_excess_room_heat_kwh": round(excess, 6),
            "ghot_optional_compute_advice": "RUN_ELIGIBLE" if run else "HOLD",
            "feedback_inputs": {
                "available_battery_kwh_before": round(
                    battery + (p.optional_task_electric_kwh if run else 0), 6
                ),
                "room_heat_need_after_passive_release_kwh": round(needed_after_mass, 6),
            },
        })

    # Energy sent to room, outdoors, or remaining in storage can be counted
    # EXACTLY ONCE. Neither unmet demand nor 'tasks run' creates energy.
    tally = (
        direct_heat + previous_losses + work_buffer
        + bank + battery + delivered_from_mass + escaped_from_mass
        + delivered_electronics_heat + escaped_electronics_heat
    )
    imbalance = initial_fuel - tally
    if not math.isclose(imbalance, 0.0, rel_tol=0, abs_tol=1.0e-5):
        raise AssertionError(f"Non-conservative energy graph: {imbalance} kWh.")

    return {
        "schema": "ghot.thermal-flow-feedback/v0",
        "mode": "offline_only_synthetic_no_controls",
        "cascade_input": asdict(source),
        "feedback_policy": asdict(p),
        "initial_energy_kwh": {
            "fuel": initial_fuel,
            "room_direct_heat_from_burn": direct_heat,
            "mass_bank": upstream["heat_to_mass_bank"],
            "battery": upstream["battery_energy_after_conversion"],
            "mechanical_buffer_unspent": work_buffer,
            "upstream_losses": previous_losses,
        },
        "cumulative_energy_kwh": {
            "room_direct_heat_from_burn": round(direct_heat, 6),
            "room_heat_from_mass": round(delivered_from_mass, 6),
            "room_heat_from_electronics": round(delivered_electronics_heat, 6),
            "mass_heat_lost_outdoors": round(escaped_from_mass, 6),
            "electronics_heat_lost_outdoors": round(escaped_electronics_heat, 6),
            "upstream_losses": round(previous_losses, 6),
            "remaining_mass_bank": round(bank, 6),
            "remaining_battery": round(battery, 6),
            "remaining_mechanical_buffer": round(work_buffer, 6),
            "total_ledger_energy": round(tally, 6),
            "energy_closure_error": round(imbalance, 7),
        },
        "service_feedback_not_energy": {
            "optional_tasks_run": sum(
                row["ghot_optional_compute_advice"] == "RUN_ELIGIBLE"
                for row in rows
            ),
            "optional_electric_spent_kwh": round(spent_optional_electric, 6),
            "heat_demand_unmet_during_modeled_hours_kwh": round(unmet_heating, 6),
            "room_heat_excess_during_modeled_hours_kwh": round(excessive_heating, 6),
            "note": "Initial direct burn-period heat is reported separately from subsequent hourly house demand."
        },
        "read_only_loops": [
            {
                "name": "heat_cascade",
                "edge": "upstream rejected heat -> masonry mass -> room -> outdoors",
                "energy_gain": False,
                "control": "passive / qualified independent appliance only",
            },
            {
                "name": "electrical_return",
                "edge": "work -> generator -> battery -> optional computing -> low-grade room heat",
                "energy_gain": False,
                "control": "GHoT can advise optional compute only",
            },
            {
                "name": "sensor_decision_feedback",
                "edge": "synthetic battery + heat need -> GHoT advice -> optional task -> new battery reading",
                "energy_gain": False,
                "control": "no combustion/valves/pumps/pressure/HVAC/safety authority",
            },
        ],
        "physics": {
            "heat_does_not_flow_uphill_without_work": True,
            "fluid_circulation_does_not_multiply_heat": True,
            "pressure_buffer_is_not_extra_fuel": True,
            "mass_discharge_is_not_programmable_by_ghot": True,
            "electricity_used_indoors_eventually_becomes_low_grade_heat": True,
            "recovered_heat_is_never_double_counted": True,
        },
        "hours": rows,
    }


if __name__ == "__main__":
    print(json.dumps(simulate(), indent=2, sort_keys=True))
