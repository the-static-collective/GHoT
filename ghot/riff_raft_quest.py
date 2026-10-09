"""RIFF-RAFT-004 — GHoT bounded dynamic game-quest proposer.

An explicit fictional field *priority*, not an autonomous decision or sensor,
selects one of two permitted Minecraft repeater-fault experiments.
The proposal can be admitted into a Minecraft sandbox by reLATTE later;
nothing here commands a game server, hardware, land, or GHoT scheduler.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "ghot.riff-raft-terraform-quest/v0"
TERRAFORMER_DONOR = "a63624f1be6a533f5ab927b1e4e8b1a629f1ba53"
STAGES = (
    "READ_FIELD", "LAY_BONES", "CATCH_WATER", "MAKE_SHADE",
    "MAKE_GROUND", "SEED_NUCLEUS", "FEED_FIELD",
    "WITNESS_DELTA", "ONE_METER_OUTWARD",
)
# Exactly two allowed 'single missing repeater' probes in the existing
# 9-lamp Minecraft circuit. The quest does not manufacture terrain effects.
SCENARIOS = {
    "rain-retention": {"fault_x": -13, "upstream_lit": 3,
                       "question": "What persists when the water-stage link withdraws?"},
    "biomass-return": {"fault_x": 17, "upstream_lit": 6,
                       "question": "What persists when the biomass-stage link withdraws?"},
}
EXPECTED = {("A", "381654729"): "rain-retention",
            ("B", "918273645"): "biomass-return"}


class QuestHold(ValueError):
    pass


def require(ok: bool, cause: str) -> None:
    if not ok:
        raise QuestHold(cause)


def canon(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def propose(world: str, seed: str, priority: str) -> dict[str, Any]:
    require(world in {"A", "B"}, "WORLD_NOT_ALLOWED")
    require(type(seed) is str and seed.isdigit() and 1 <= len(seed) <= 12,
            "SEED_NOT_BOUNDED")
    require(priority in SCENARIOS, "PRIORITY_NOT_ALLOWED")
    require(EXPECTED.get((world, seed)) == priority,
            "SELECTION_NOT_EXPLICITLY_AUTHORIZED_FOR_SCENARIO")
    option = SCENARIOS[priority]
    body = {
        "schema": SCHEMA,
        "source_project": "the-static-collective/GHoT",
        "source_donor_commit": TERRAFORMER_DONOR,
        "mode": "synthetic-game-proposal-only",
        "world_id": world,
        "world_seed": seed,
        "selection": "explicit-scenario-proposal",
        "priority": priority,
        "question": option["question"],
        "intervention": "remove-one-redstone-repeater-then-restore",
        "fault_repeater_position": {"x": option["fault_x"], "y": 66, "z": 46},
        "expected_lit_during_fault": [i < option["upstream_lit"] for i in range(9)],
        "expected_lit_initial": [False] * 9,
        "expected_lit_reset": [False] * 9,
        "expected_lit_repaired": [True] * 9,
        "station_labels": list(STAGES),
        "sandbox": "official-vanilla-minecraft-localhost",
        "operator_must_select": True,
        "simulator_can_trigger": False,
        "game_execution_observed": False,
        "actual_soil_change_verified": False,
        "ghot_resource_transfer": False,
        "owner_admission": False,
        "authority_effect": "none",
    }
    return {**body, "quest_sha256": hashlib.sha256(canon(body)).hexdigest()}


def validate(quest: Any) -> dict[str, Any]:
    require(isinstance(quest, dict) and "quest_sha256" in quest,
            "QUEST_NOT_OBJECT")
    require(set(quest) == set(propose("A", "381654729", "rain-retention")),
            "QUEST_FIELDS_CHANGED")
    world, seed, priority = quest["world_id"], quest["world_seed"], quest["priority"]
    required = propose(world, seed, priority)
    require(quest == required, "QUEST_DIFFERENT_FROM_BOUND_GHOT_PROPOSAL")
    return quest


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--world", required=True)
    p.add_argument("--seed", required=True)
    p.add_argument("--priority", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    quest = validate(propose(args.world, args.seed, args.priority))
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(quest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"world_id": quest["world_id"], "priority": quest["priority"],
                      "fault_repeater_x": quest["fault_repeater_position"]["x"],
                      "quest_sha256": quest["quest_sha256"],
                      "proposed_only": True}, indent=2))


if __name__ == "__main__":
    main()
