"""RIFF-RAFT-005 — evidence-derived counterfactual game-quest proposals.

Inspect a *real*, signed, previously run RIFF-RAFT-004 game-observation bundle
using GHoT's independent P-256 receiver. A bounded policy proposes the next
per-world repeater fault based on the **observed** number of powered lamps.
This code NEVER admits either previous results or future proposals.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from riff_raft_dynamic_return import receive, ReturnHold, sha, STAGES

SCHEMA = "ghot.riff-raft-counterfactual-quest/v0"
DONOR = "a63624f1be6a533f5ab927b1e4e8b1a629f1ba53"
SOURCE_CROSSING = "relatte-crossing-v0:0b61b9476c0ab3e2b57a5090781d2591e8c1145ac84c2eea2f67efb301d54fa3"
SOURCE_RECEIPT = "relatte-receipt-v0:5ad43d10051e60ce2f5d52fca00808027785b55bc31c70ff75a88f2496a06d11"
SOURCE_PACKET = "9956d0887a5f65495cb777a5ba06aa03451946c46285930d8d96eeaa2a7d0a17"
REPEATERS = (-28, -13, 2, 17, 32)
LAMPS = (-40, -30, -20, -10, 0, 10, 20, 30, 40)
# The policy deliberately has no unrestricted choice or game commands.
# A: test whether moving the failure later preserves two additional stations.
# B: test whether moving it earlier interrupts four more stations.
POLICY = {"A": {"name": "shift-downstream-by-two-stages", "delta": 2},
          "B": {"name": "shift-upstream-by-four-stages", "delta": -4}}
SEEDS = {"A": "381654729", "B": "918273645"}


class CounterfactualHold(ValueError):
    pass


def check(ok: bool, reason: str) -> None:
    if not ok:
        raise CounterfactualHold(reason)


def encoded(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def select_after_observation(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # Verification is a necessary condition but not an authority grant.
    verified = receive(bundle)
    check(verified["disposition"] == "HOLD" and
          verified["world_count"] == 2 and
          verified["crossing_signature_valid"] is True and
          verified["receipt_signature_valid"] is True and
          verified["remote_work_dispatch"] is False and
          verified["physical_actuation"] is False, "SOURCE_NOT_SOVEREIGN_HOLD")
    source = json.loads(bundle["packet_json"])
    check(bundle["crossing"]["crossing_id"] == SOURCE_CROSSING and
          bundle["receipt"]["receipt_id"] == SOURCE_RECEIPT and
          sha(bundle["packet_json"].encode("utf-8")) == SOURCE_PACKET,
          "REPLAY_ANCHOR_NOT_APPROVED_SOURCE")
    check(source["ghot_donor_commit"] == DONOR and
          source["recommended_gHot_disposition"] == "HOLD" and
          source["biological_restoration_verified"] is False,
          "SOURCE_ESCALATED")
    out: dict[str, dict[str, Any]] = {}
    for world in source["worlds"]:
        label = world["world_id"]
        check(label in POLICY and label not in out and
              world["server_seed"] == SEEDS[label], "WORLD_SEED_OR_ROLE_CHANGED")
        states = world["causal_signature"]
        observed = states["broken"]
        check(type(observed) is list and len(observed) == 9 and
              all(type(v) is bool for v in observed), "NOT_OBSERVED_BOOLEAN_STATES")
        original_count = sum(observed)
        old_fault = world["quest_fault_x"]
        check(old_fault in REPEATERS and
              original_count == sum(x < old_fault for x in LAMPS),
              "SOURCE_CAUSALITY_NOT_MATCHING_REPEATER")
        policy = POLICY[label]
        next_count = original_count + policy["delta"]
        candidates = [r for r in REPEATERS
                      if sum(x < r for x in LAMPS) == next_count]
        check(len(candidates) == 1 and candidates[0] != old_fault,
              "NO_BOUND_COUNTERFACTUAL_FOR_OBSERVED_RESULT")
        position = candidates[0]
        body = {
            "schema": SCHEMA,
            "source_project": "the-static-collective/GHoT",
            "source_donor_commit": DONOR,
            "mode": "observed-source-counterfactual-proposal-only",
            "world_id": label,
            "world_seed": world["server_seed"],
            "policy": policy["name"],
            "previous_fault_x": old_fault,
            "previous_fault_lit": original_count,
            "source_004_crossing_id": SOURCE_CROSSING,
            "source_004_receipt_id": SOURCE_RECEIPT,
            "source_004_packet_sha256": SOURCE_PACKET,
            "source_004_instance_id": world["instance_id"],
            "source_004_candidate_crossing_id": world["candidate_crossing_id"],
            "source_004_observed_state_sha256": world["observed_state_sha256"],
            "source_004_quest_sha256": world["quest_sha256"],
            "reason": "bounded-counterfactual-relative-to-observed-lamp-count",
            "fault_repeater_position": {"x": position, "y": 66, "z": 46},
            "expected_lit_during_fault": [x < position for x in LAMPS],
            "expected_lit_initial": [False] * 9,
            "expected_lit_reset": [False] * 9,
            "expected_lit_repaired": [True] * 9,
            "station_labels": list(STAGES),
            "permitted_operation": "remove-one-redstone-repeater-then-restore",
            "sandbox": "official-vanilla-minecraft-localhost",
            "operator_must_select": True,
            "source_verified_as_game_evidence": True,
            "future_game_execution_observed": False,
            "real_soil_improvement_verified": False,
            "ghot_resource_moved": False,
            "owner_admission": False,
            "auto_dispatch": False,
            "authority_effect": "none",
        }
        out[label] = {**body,
                      "quest_sha256": hashlib.sha256(encoded(body)).hexdigest()}
    check(set(out) == {"A", "B"} and
          out["A"]["fault_repeater_position"]["x"] == 2 and
          out["B"]["fault_repeater_position"]["x"] == -28 and
          out["A"]["quest_sha256"] != out["B"]["quest_sha256"],
          "EXPERIMENTAL_DELTA_NOT_DISTINCT")
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: riff_raft_counterfactual.py <source-004-bundle.json> <output-directory>",
              file=sys.stderr)
        return 2
    bundle_bytes = Path(sys.argv[1]).read_bytes()
    check(len(bundle_bytes) <= 8 * 1024 * 1024, "SOURCE_OVERSIZE")
    proposals = select_after_observation(json.loads(bundle_bytes))
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    for key, value in proposals.items():
        (output / ("counterfactual-" + key + ".json")).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: {
        "previous_fault_lit":value["previous_fault_lit"],
        "proposed_fault_lit":sum(value["expected_lit_during_fault"]),
        "new_fault_x":value["fault_repeater_position"]["x"],
        "source_004_candidate_crossing_id": value["source_004_candidate_crossing_id"],
        "quest_sha256":value["quest_sha256"],"disposition":"PROPOSAL_ONLY"
    } for key,value in proposals.items()}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CounterfactualHold, ReturnHold, KeyError, TypeError, ValueError) as exc:
        print("COUNTERFACTUAL_HELD:" + str(exc),file=sys.stderr)
        raise SystemExit(1)
