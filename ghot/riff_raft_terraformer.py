"""RIFF-RAFT-002 / THE RUBE GOLDBERG TERRAFORMER.

Excavated from MAKE GROUND and Lay the Bones, Wake the Soil (2026-10-03).
Nine bounded, operator-selected simulation cues form a physical-process
rehearsal. No sensors, irrigation, earthworks, seed release, or actuators run.

The GHoT Riff-Raft ecology plan supplies ONLY a simulated information-route
offer. A cue can expose the next door but cannot open it automatically.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ecology_router import Hold, digest, integer, require
from riff_raft import PLAN_SCHEMA

FIELD_SCHEMA = "ghot.riff-raft-terraform-field/v0"
TURN_SCHEMA = "ghot.riff-raft-terraform-cue/v0"
RECEIPT_SCHEMA = "ghot.riff-raft-terraform-receipt/v0"
PLAN_SCHEMA_TERRA = "ghot.riff-raft-terraform-plan/v0"

STAGES = (
    "READ_FIELD",
    "LAY_BONES",
    "CATCH_WATER",
    "MAKE_SHADE",
    "MAKE_GROUND",
    "SEED_NUCLEUS",
    "FEED_FIELD",
    "WITNESS_DELTA",
    "ONE_METER_OUTWARD",
)
MECHANICAL_CUES = {
    "READ_FIELD": "An orchard-coil signal rings the observation bell",
    "LAY_BONES": "A proposed brush baffle creates a rain-catching pocket",
    "CATCH_WATER": "Rain tips a gutter cup; a float reports captured water",
    "MAKE_SHADE": "The float proposes a pulley-drawn shade flap",
    "MAKE_GROUND": "A wick proposes moving banked water to amended soil",
    "SEED_NUCLEUS": "A seed-pocket cue proposes native pioneer placement",
    "FEED_FIELD": "A screened biomass tumbler returns mulch and compost",
    "WITNESS_DELTA": "A measuring dial asks reality for an outside reading",
    "ONE_METER_OUTWARD": "A boundary marker opens a candidate adjacent patch",
}
STOCKS = (
    "rain_ml", "banked_ml", "runoff_ml", "soil_water_ml",
    "brush_g", "structure_brush_g", "compost_g", "soil_amendment_g",
    "imported_biomass_g", "mulch_g", "biomass_loss_g",
    "native_seeds", "seeds_sown",
)
PERMISSIONS = (
    "land_steward_consented",
    "erosion_plan_reviewed",
    "native_seed_origin_checked",
    "water_path_reviewed",
    "biological_contamination_absent",
)
FLAGS = (
    "field_read", "catchment_ready", "shade_ready",
    "soil_prepared", "seeds_sown_as_attempt", "adjacent_candidate",
)


def valid_plan(plan: Any) -> dict[str, Any]:
    require(isinstance(plan, dict), "GHoT proposal plan required")
    require(plan.get("schema") == PLAN_SCHEMA and
            plan.get("mode") == "simulation-only" and
            plan.get("physical_transfer_performed") is False and
            plan.get("source_or_destination_admission") is False and
            plan.get("automatic_dispatch") is False and
            plan.get("signed_relatte_crossing") is False,
            "GHoT plan claims physical operation or authority")
    routes = plan.get("routes")
    require(isinstance(routes, list) and
            any(isinstance(p, dict) and
                p.get("load_id") == "orchard-wind-music" and
                p.get("decision") == "PROPOSE" and
                p.get("resource") == "information" and
                p.get("unit") == "events" for p in routes),
            "orchard information route unavailable")
    return plan


def balances(stocks: dict[str, int]) -> dict[str, int]:
    return {
        "water_ml": sum(stocks[k] for k in (
            "rain_ml", "banked_ml", "runoff_ml", "soil_water_ml")),
        "biomass_g": sum(stocks[k] for k in (
            "brush_g", "structure_brush_g", "compost_g",
            "soil_amendment_g", "imported_biomass_g",
            "mulch_g", "biomass_loss_g")),
        "seed_count": stocks["native_seeds"] + stocks["seeds_sown"],
    }


def _state_body(state: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in state.items() if k != "state_sha256"}


def _seal(state: dict[str, Any]) -> dict[str, Any]:
    state["state_sha256"] = digest(_state_body(state))
    return state


def validate_state(state: Any, ghot_plan: dict[str, Any]) -> dict[str, Any]:
    valid_plan(ghot_plan)
    require(isinstance(state, dict) and set(state) == {
        "schema", "mode", "field_id", "owner_id", "ghot_plan_sha256",
        "permissions", "stocks", "initial_balances", "flags", "completed",
        "receipts", "state_sha256",
    }, "field state fields changed")
    require(state["schema"] == FIELD_SCHEMA and
            state["mode"] == "simulation-only", "field not a simulation")
    require(state["ghot_plan_sha256"] == digest(ghot_plan),
            "upstream GHoT plan changed")
    require(state["state_sha256"] == digest(_state_body(state)),
            "field state hash mismatch")
    for name in ("field_id", "owner_id"):
        require(isinstance(state[name], str) and bool(state[name]), f"{name} required")
    permissions = state["permissions"]
    require(isinstance(permissions, dict) and set(permissions) == set(PERMISSIONS)
            and all(type(x) is bool for x in permissions.values()),
            "permissions malformed")
    stocks = state["stocks"]
    require(isinstance(stocks, dict) and set(stocks) == set(STOCKS),
            "stock schema malformed")
    for k, v in stocks.items():
        integer(v, k)
    original = state["initial_balances"]
    require(isinstance(original, dict) and set(original) == {
        "water_ml", "biomass_g", "seed_count",
    }, "initial conservation bounds malformed")
    for k, v in original.items():
        integer(v, k)
    require(balances(stocks) == original,
            "water, biomass or seed balance violated")
    flags = state["flags"]
    require(isinstance(flags, dict) and set(flags) == set(FLAGS) and
            all(type(x) is bool for x in flags.values()),
            "field flags malformed")
    completed = state["completed"]
    receipts = state["receipts"]
    require(isinstance(completed, list) and completed == list(STAGES[:len(completed)]),
            "missing, repeated or out-of-order stage")
    require(isinstance(receipts, list) and len(receipts) == len(completed),
            "receipt history missing")
    ids = set()
    for idx, r in enumerate(receipts):
        require(isinstance(r, dict) and set(r) == {
            "schema", "turn_id", "cue", "previous_state_sha256",
            "next_state_sha256", "ghot_plan_sha256", "balances_before",
            "balances_after", "simulated_only", "physical_actuation",
            "independent_field_witness", "authority_effect", "automatic_next",
            "receipt_sha256",
        }, "receipt fields changed")
        require(r["schema"] == RECEIPT_SCHEMA and r["cue"] == completed[idx],
                "receipt stage mismatch")
        require(isinstance(r["turn_id"], str) and r["turn_id"] not in ids,
                "receipt turn duplicate")
        ids.add(r["turn_id"])
        body = {k: v for k, v in r.items() if k != "receipt_sha256"}
        require(r["receipt_sha256"] == digest(body), "receipt checksum changed")
        require(r["ghot_plan_sha256"] == digest(ghot_plan) and
                r["simulated_only"] is True and
                r["physical_actuation"] is False and
                r["independent_field_witness"] is False and
                r["authority_effect"] == "none" and
                r["automatic_next"] is False, "receipt claims unearned effects")
        require(r["balances_before"] == original and
                r["balances_after"] == original, "receipt conceals matter imbalance")
    return state


def bootstrap(ghot_plan: dict[str, Any], configuration: dict[str, Any]) -> dict[str, Any]:
    valid_plan(ghot_plan)
    require(isinstance(configuration, dict) and set(configuration) == {
        "field_id", "owner_id", "permissions", "stocks",
    }, "configuration fields changed")
    # Deliberately use freshly materialized copies; never mutate a donor plan.
    p = deepcopy(configuration["permissions"])
    s = deepcopy(configuration["stocks"])
    field = {
        "schema": FIELD_SCHEMA, "mode": "simulation-only",
        "field_id": configuration["field_id"],
        "owner_id": configuration["owner_id"],
        "ghot_plan_sha256": digest(ghot_plan),
        "permissions": p, "stocks": s,
        "initial_balances": balances(s),
        "flags": {key: False for key in FLAGS},
        "completed": [], "receipts": [],
    }
    return validate_state(_seal(field), ghot_plan)


def next_door(field: dict[str, Any], ghot_plan: dict[str, Any]) -> dict[str, Any]:
    validate_state(field, ghot_plan)
    ix = len(field["completed"])
    if ix == len(STAGES):
        return {
            "stage": None, "decision": "COMPLETE_REHEARSAL_ONLY",
            "physical_delta_verified": False, "fertility_delta_verified": False,
            "open_berth": "Find an independent field witness before any expansion",
        }
    stage = STAGES[ix]
    reasons = []
    p = field["permissions"]
    if p["land_steward_consented"] is not True:
        reasons.append("LAND_STEWARD_CONSENT_MISSING")
    if stage in {"LAY_BONES", "CATCH_WATER"} and not p["erosion_plan_reviewed"]:
        reasons.append("EROSION_REVIEW_MISSING")
    if stage in {"CATCH_WATER", "MAKE_GROUND"} and not p["water_path_reviewed"]:
        reasons.append("WATER_PATH_REVIEW_MISSING")
    if stage in {"MAKE_GROUND", "SEED_NUCLEUS", "FEED_FIELD"} and not p["biological_contamination_absent"]:
        reasons.append("CONTAMINATION_SCREEN_MISSING")
    if stage == "SEED_NUCLEUS" and not p["native_seed_origin_checked"]:
        reasons.append("NATIVE_ORIGIN_REVIEW_MISSING")
    s = field["stocks"]
    required = {
        "LAY_BONES": ("brush_g", 600),
        "CATCH_WATER": ("rain_ml", 1200),
        "MAKE_SHADE": ("brush_g", 300),
        "MAKE_GROUND": ("compost_g", 300),
        "SEED_NUCLEUS": ("native_seeds", 5),
        "FEED_FIELD": ("imported_biomass_g", 400),
    }
    if stage in required:
        name, amount = required[stage]
        if s[name] < amount:
            reasons.append("INPUT_NOT_AVAILABLE:" + name)
    if stage == "MAKE_GROUND" and s["banked_ml"] < 400:
        reasons.append("BANKED_WATER_NOT_AVAILABLE")
    if stage == "ONE_METER_OUTWARD":
        # An explicit candidate for the next meter is all this stage can provide.
        # No independent ecological growth was witnessed by this simulation.
        pass
    return {
        "stage": stage, "decision": "HOLD" if reasons else "PROPOSE",
        "mechanical_cue": MECHANICAL_CUES[stage],
        "reasons": sorted(reasons),
        "requires_new_operator_selection": True,
        "physical_actuation": False,
        "independent_field_witness": False,
        "simulated_only": True,
    }


def simulate_one(field: dict[str, Any], ghot_plan: dict[str, Any],
                 request: Any) -> dict[str, Any]:
    """Exactly one selected cue: no hidden next step or real-world claim."""
    validate_state(field, ghot_plan)
    require(isinstance(request, dict) and set(request) == {
        "schema", "turn_id", "cue", "operator_id",
        "selection", "authority_request", "admission_request",
    }, "cue request fields changed")
    require(request["schema"] == TURN_SCHEMA, "unknown cue request schema")
    require(isinstance(request["turn_id"], str) and bool(request["turn_id"]),
            "turn id required")
    require(all(r["turn_id"] != request["turn_id"] for r in field["receipts"]),
            "turn already consumed")
    require(request["operator_id"] == field["owner_id"] and
            request["selection"] == "explicit" and
            request["authority_request"] == "none" and
            request["admission_request"] == "none",
            "cue cannot impersonate owner or grant authority")
    door = next_door(field, ghot_plan)
    require(door.get("stage") is not None, "field rehearsal already complete")
    require(request["cue"] == door["stage"], "cue order or hidden chaining refused")
    require(door["decision"] == "PROPOSE", "cue is HOLD: " + ", ".join(door["reasons"]))

    updated = deepcopy(field)
    s, f = updated["stocks"], updated["flags"]
    stage = request["cue"]
    if stage == "READ_FIELD":
        f["field_read"] = True
    elif stage == "LAY_BONES":
        s["brush_g"] -= 600
        s["structure_brush_g"] += 600
        f["catchment_ready"] = True
    elif stage == "CATCH_WATER":
        s["rain_ml"] -= 1200
        s["banked_ml"] += 900
        s["runoff_ml"] += 300
    elif stage == "MAKE_SHADE":
        s["brush_g"] -= 300
        s["structure_brush_g"] += 300
        f["shade_ready"] = True
    elif stage == "MAKE_GROUND":
        s["compost_g"] -= 300
        s["soil_amendment_g"] += 300
        s["banked_ml"] -= 400
        s["soil_water_ml"] += 400
        f["soil_prepared"] = True
    elif stage == "SEED_NUCLEUS":
        s["native_seeds"] -= 5
        s["seeds_sown"] += 5
        f["seeds_sown_as_attempt"] = True
    elif stage == "FEED_FIELD":
        s["imported_biomass_g"] -= 400
        s["mulch_g"] += 240
        s["compost_g"] += 120
        s["biomass_loss_g"] += 40
    elif stage == "WITNESS_DELTA":
        # A simulator cannot call itself an independent physical witness.
        pass
    elif stage == "ONE_METER_OUTWARD":
        # Only a candidate aperture, NOT evidence that another meter was restored.
        f["adjacent_candidate"] = True
    else:
        raise Hold("unrecognized stage")

    require(balances(s) == field["initial_balances"],
            "resource conservation broke")
    updated["completed"].append(stage)
    before_sha = field["state_sha256"]
    # next-state hash excludes the receipt list to avoid a circular hash
    after_effect_sha = digest({
        "completed": updated["completed"], "stocks": updated["stocks"],
        "flags": updated["flags"], "field_id": updated["field_id"],
    })
    receipt = {
        "schema": RECEIPT_SCHEMA, "turn_id": request["turn_id"], "cue": stage,
        "previous_state_sha256": before_sha,
        "next_state_sha256": after_effect_sha,
        "ghot_plan_sha256": digest(ghot_plan),
        "balances_before": field["initial_balances"],
        "balances_after": balances(s),
        "simulated_only": True, "physical_actuation": False,
        "independent_field_witness": False, "authority_effect": "none",
        "automatic_next": False,
    }
    receipt["receipt_sha256"] = digest(receipt)
    updated["receipts"].append(receipt)
    updated = validate_state(_seal(updated), ghot_plan)
    return {
        "field": updated, "receipt": receipt,
        "next_door": next_door(updated, ghot_plan),
        "physical_field_effect": False, "fertility_delta_verified": False,
        "automatic_next": False,
    }
