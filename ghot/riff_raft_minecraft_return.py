"""RIFF-RAFT-003 — read-only signed reLATTE Minecraft replay receiver for GHoT.

Accepts *portable* two-runner evidence, verifies P-256 reLATTE envelope and
receipt locally through GHoT's existing OpenSSL profile, checks the referenced
native evidence, and ALWAYS returns a local HOLD. No organ is started.
Ephemeral self-signed keys establish cryptographic integrity, NOT trusted
organizational identity or ownership of a world.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from relatte_identity import verify_crossing, verify_receipt

BUNDLE = "ghot.riff-raft-minecraft-return-bundle/v0"
SCHEMA = "ghot.riff-raft-minecraft-return/v0"
CORE = "c0e4d2c59481e0fb2a4bf4bb294f373907fd2b76"
DONOR = "a63624f1be6a533f5ab927b1e4e8b1a629f1ba53"
STAGES = (
    "READ_FIELD", "LAY_BONES", "CATCH_WATER", "MAKE_SHADE",
    "MAKE_GROUND", "SEED_NUCLEUS", "FEED_FIELD", "WITNESS_DELTA",
    "ONE_METER_OUTWARD",
)
EXPECTED = {
    "before": [False] * 9,
    "broken": [True] * 3 + [False] * 6,
    "reset": [False] * 9,
    "final": [True] * 9,
}
MAX_BUNDLE_BYTES = 8 * 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class ReturnHold(ValueError):
    pass


def check(condition: Any, reason: str) -> None:
    if not condition:
        raise ReturnHold(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def js_bytes(obj: Any) -> bytes:
    # Preserves JSON insertion order, compact JSON strings, and UTF-8.
    # Used only for bounded objects with booleans / strings / integers.
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()


def exact_hash(value: Any) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def check_sig(crossing: Any, receipt: Any, payload: bytes) -> None:
    check(isinstance(crossing, dict) and isinstance(receipt, dict),
          "MISSING_SIGNED_CROSSING")
    check(verify_crossing(crossing), "CROSSING_SIGNATURE_INVALID")
    check(verify_receipt(receipt), "RECEIPT_SIGNATURE_INVALID")
    check(receipt.get("crossing_id") == crossing.get("crossing_id"),
          "RECEIPT_NOT_BOUND")
    refs = crossing.get("payload_refs")
    check(isinstance(refs, list) and len(refs) == 1 and
          refs[0].get("address") == "sha256:" + sha(payload),
          "PAYLOAD_DIGEST_NOT_BOUND")
    check(receipt.get("kind") in ("R3_ADMIT", "R3_HOLD"),
          "UNSUPPORTED_RECEIPT")


def _states(rows: Any, label: str) -> list[bool]:
    check(isinstance(rows, list) and len(rows) == 9, f"{label}_LENGTH")
    check([r.get("cue") for r in rows] == list(STAGES), f"{label}_ORDER")
    result = [r.get("lit") for r in rows]
    check(all(type(v) is bool for v in result), f"{label}_NOT_BOOLEAN")
    return result


def _source_world(item: dict[str, Any],
                  raw_pair: dict[str, str]) -> dict[str, Any]:
    label = item.get("world_id")
    check(label in ("A", "B"), "UNKNOWN_WORLD")
    check(isinstance(raw_pair, dict) and set(raw_pair) == {
        "composition_json", "runtime_json",
    }, "SOURCE_FILES_MISSING")
    eb = raw_pair["composition_json"].encode("utf-8")
    rb = raw_pair["runtime_json"].encode("utf-8")
    check(len(eb) < 3_000_000 and len(rb) < 3_000_000, "SOURCE_TOO_LARGE")
    check(item.get("source_composition_bytes_sha256") == sha(eb) and
          item.get("source_runtime_bytes_sha256") == sha(rb),
          "SOURCE_BYTES_MUTATED")
    e, r = json.loads(eb), json.loads(rb)
    check(e.get("schema") == "relatte.composition-instance-001-evidence/v0" and
          r.get("schema") == "relatte.vanilla-worldbuilder-006-evidence/v0",
          "WRONG_SOURCE_EVIDENCE_SCHEMA")
    spec, result = e["spec"], e["result"]
    check(spec["goal"] == "MAKE GROUND IN A REHEARSAL WORLD" and
          spec["runtime_id"] == "minecraft-vanilla-worldbuilder-006" and
          spec["governing_snapshot"]["normative_src_tree"] == CORE and
          spec["extensions"].get("riff_raft_two_world_label") == label and
          spec["extensions"].get("riff_raft_two_world_replay") is True and
          spec["extensions"].get("fault_control") is True,
          "COMPOSITION_SCOPE_NOT_PINNED")
    check(str(r["server_seed"]) == item["server_seed"] and
          "seed:" + str(r["server_seed"]) in spec["base_snapshot_ref"],
          "SEED_OR_RUNTIME_MISMATCH")
    check(r["version"]["id"] == "26.1.1" and
          r["version"]["server_sha1"] == item["server_jar_sha1"] ==
          spec["extensions"]["server_jar_sha1"], "MINECRAFT_VERSION_DRIFT")
    check(r["plan"]["riff_raft"]["source_commit"] == DONOR and
          [s["cue"] for s in r["plan"]["riff_raft_redstone"]["stages"]] ==
          list(STAGES), "GHOT_SOURCE_OR_STAGE_DRIFT")
    launch, candidate = e["launch"], e["candidate"]
    check_sig(launch["crossing"], launch["receipt"], js_bytes(spec))
    check_sig(candidate["crossing"], candidate["receipt"], js_bytes(result))
    check(launch["receipt"]["kind"] == "R3_ADMIT" and
          candidate["receipt"]["kind"] == result["result_disposition"] ==
          "R3_HOLD", "UNEXPECTED_SOURCE_DISPOSITION")
    check(candidate["crossing"].get("parents") == [
        launch["crossing"]["crossing_id"]] and
        result["launch_crossing_id"] == launch["crossing"]["crossing_id"],
        "INSTANCE_TO_CANDIDATE_ANCESTRY_BROKEN")
    check(item["instance_id"] == result["instance_id"] == e["instance_id"] and
          item["launch_crossing_id"] == launch["crossing"]["crossing_id"] and
          item["candidate_crossing_id"] == candidate["crossing"]["crossing_id"],
          "INSTANCE_IDENTITY_MISMATCH")
    check(result["author_session_id"] != result["observer_session_id"] and
          result["author_session_id"] == item["author_session_id"] and
          result["observer_session_id"] == item["observer_session_id"] and
          r["bot"]["fresh_observer_operator"] is False and
          r["bot"]["username"] != r["bot"]["fresh_observer_username"],
          "AUTHOR_OBSERVER_COLLAPSE")
    p = r.get("redstone", {})
    check(p.get("schema") == "relatte.riff-raft-redstone-execution/v0" and
          p.get("source_ghot_commit") == DONOR and
          p.get("redstone_circuit_actuated_in_game") is True and
          p.get("physical_field_improvement_verified") is False and
          p.get("ghot_resource_moved") is False, "CAUSE_CLASS_ESCALATED")
    signatures = {
        "before": _states(p["original_unpowered_states"], "before"),
        "broken": _states(p["broken_link_trial"], "broken"),
        "reset": _states(p["reset_states"], "reset"),
        "final": _states(p["powered_states"], "final"),
    }
    check(signatures == EXPECTED and
          signatures == item["causal_signature"], "CAUSAL_REPLAY_DISAGREEMENT")
    obs = p.get("final_observer", {})
    observed = obs.get("stages")
    check(obs.get("independent_fresh_client") is True and
          obs.get("physical_field_evidence") is False and
          obs.get("observer") == r["bot"]["fresh_observer_username"] and
          isinstance(observed, list) and len(observed) == 9 and
          [o["cue"] for o in observed] == list(STAGES) and
          all(o.get("observer_name") == "redstone_lamp" and
              o.get("observer_properties", {}).get("lit") is True and
              o.get("server_lit") is True for o in observed),
          "FRESH_OBSERVER_NOT_CONFIRMED")
    obs_hash = sha(js_bytes(observed))
    check(obs.get("observed_state_sha256") == obs_hash ==
          item["redstone_observed_sha256"], "REDSTONE_STATE_HASH_MISMATCH")
    scan = r["scan"]["field_sha256"]
    check(exact_hash(scan) and scan == item["vanilla_field_sha256"] and
          p["circuit_plan_sha256"] == r["plan"]["plan_sha256"],
          "WORLD_SCAN_PLAN_CHANGED")
    composite = sha(js_bytes({
        "vanilla_block_field_sha256": scan,
        "independently_observed_redstone_state_sha256": obs_hash,
    }))
    check(composite == result["observed_state_sha256"] ==
          e["runtime"]["observed_state_sha256"] ==
          item["observed_state_sha256"], "COMPOSITE_STATE_NOT_BOUND")
    check(result["observed_state_ref"] == "sha256:" + composite and
          result["runtime_claims"].get("riff_raft_game_and_field_conflation") is False and
          result["runtime_claims"].get("real_soil_fertility_verified") is False and
          result["runtime_claims"].get("ghot_python_simulation_executed_here") is False,
          "PHYSICAL_OR_AUTHORITY_CLAIM_FORGED")
    check(item["candidate_disposition"] == "R3_HOLD" and
          item["real_world_effect"] is False, "SOURCE_CLAIM_ESCALATED")
    return {"world_id": label, "source_verified": True,
            "instance_id": e["instance_id"],
            "observed_state_sha256": composite}


def receive(bundle: Any) -> dict[str, Any]:
    check(isinstance(bundle, dict) and set(bundle) == {
        "schema", "packet_json", "crossing", "receipt", "world_evidence",
    }, "BUNDLE_FIELDS_CHANGED")
    check(bundle["schema"] == BUNDLE, "UNSUPPORTED_BUNDLE")
    raw_packet = bundle["packet_json"]
    check(isinstance(raw_packet, str) and
          0 < len(raw_packet.encode("utf-8")) < MAX_BUNDLE_BYTES,
          "PACKET_SIZE_INVALID")
    crossing, receipt = bundle["crossing"], bundle["receipt"]
    check_sig(crossing, receipt, raw_packet.encode("utf-8"))
    check(receipt["kind"] == "R3_HOLD" and
          receipt.get("semantic_effect") == "local-only" and
          crossing.get("source_world") == "polyglot:composition-instance" and
          crossing.get("requested_effect") == {
              "kind": "candidate-ingress", "authority": "receiver-local",
          }, "RETURN_CANNOT_MINT_AUTHORITY")
    packet = json.loads(raw_packet)
    check(isinstance(packet, dict) and packet.get("schema") == SCHEMA and
          packet.get("source_project") == "the-static-collective/reLATTE" and
          packet.get("receiving_project") == "the-static-collective/GHoT" and
          packet.get("ghot_donor_commit") == DONOR and
          packet.get("evidence_class") == "two-isolated-minecraft-runner-results" and
          packet.get("selected_game_runtime") == "official-vanilla-26.1.1",
          "RETURN_CONTEXT_NOT_BOUND")
    check(packet.get("recommended_gHot_disposition") == "HOLD" and
          packet.get("no_direct_game_or_physical_actuation") is True and
          packet.get("biological_restoration_verified") is False and
          packet.get("ghot_energy_or_water_received") is False and
          packet.get("owner_admission") is False and
          packet.get("signed_sender_identity_is_not_trusted_org_authority") is True,
          "RETURN_IMPERSONATES_AUTHORITY")
    worlds = packet.get("worlds")
    traces = bundle.get("world_evidence")
    check(isinstance(worlds, list) and len(worlds) == 2 and
          [x.get("world_id") for x in worlds] == ["A", "B"] and
          isinstance(traces, dict) and set(traces) == {"A", "B"},
          "WORLD_PAIR_NOT_INDEPENDENT")
    checked = [_source_world(w, traces[w["world_id"]]) for w in worlds]
    left, right = worlds
    check(left["server_seed"] != right["server_seed"] and
          left["server_jar_sha1"] == right["server_jar_sha1"] and
          left["instance_id"] != right["instance_id"] and
          left["launch_crossing_id"] != right["launch_crossing_id"] and
          left["candidate_crossing_id"] != right["candidate_crossing_id"] and
          left["vanilla_field_sha256"] != right["vanilla_field_sha256"] and
          left["observed_state_sha256"] != right["observed_state_sha256"] and
          left["causal_signature"] == right["causal_signature"] == EXPECTED,
          "COMPARISON_NOT_REPLAYABLE")
    check(packet.get("comparison") == {
        "independent_provisioning": "two-matrix-runners-and-distinct-world-seeds",
        "distinct_instances": True,
        "matching_fault_reset_repair": True,
        "raw_world_states_intentionally_distinct": True,
    }, "COMPARISON_CLAIM_CHANGED")
    return {
        "schema": "ghot.riff-raft-minecraft-return-reception/v0",
        "disposition": "HOLD",
        "reason": "SIGNED_TWO_WORLD_GAME_EVIDENCE_NOT_PHYSICAL_AUTHORITY",
        "crossing_signature_valid": True,
        "receipt_signature_valid": True,
        "world_count": 2,
        "verified_sources": checked,
        "return_payload_sha256": sha(raw_packet.encode("utf-8")),
        "crossing_id": crossing["crossing_id"],
        "receipt_id": receipt["receipt_id"],
        "remote_work_dispatch": False,
        "physical_actuation": False,
        "owner_admitted": False,
        "ghot_energy_or_water_moved": False,
        "source_organization_authenticated": False,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 ghot/riff_raft_minecraft_return.py <signed-bundle.json>",
              file=sys.stderr)
        return 2
    data = Path(sys.argv[1]).read_bytes()
    check(len(data) <= MAX_BUNDLE_BYTES, "BUNDLE_TOO_LARGE")
    result = receive(json.loads(data))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReturnHold, KeyError, TypeError, ValueError) as exc:
        print("RIFF_RAFT_RETURN_REFUSED:" + str(exc), file=sys.stderr)
        raise SystemExit(1)
