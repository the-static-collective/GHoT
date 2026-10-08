#!/usr/bin/env python3
"""THE UNHEARD CHOIR 001: bounded question discovery from declared observations.

Standalone, deterministic simulation. No microphone, SDR, network, inference
model, real-world classification, signing, crossing, or external execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "ghot.unheard-choir-world/v0"
RECEIPT = "ghot.unheard-choir-attention-receipt/v0"
POLICIES = ("loudest", "protected")
KINDS = {"radio", "system", "material", "research", "human_need"}
CUES = {"repetition", "anomaly", "available", "unanswered", "unmet_need"}
QUESTIONS = {
    "repetition": ("What explains the recurring pattern in {id}?", "compare-bounded-cuts"),
    "anomaly": ("Which fresh measurement could explain the anomaly at {id}?", "propose-fresh-observation"),
    "available": ("Could the offered resource at {id} address an admitted need?", "ask-resource-owner"),
    "unanswered": ("Which bounded test would distinguish interpretations of {id}?", "propose-discriminator"),
    "unmet_need": ("Could an authorized participant respond to the need represented by {id}?", "ask-need-owner"),
}
EXPECTED_CUE = {
    "radio": "repetition",
    "system": "anomaly",
    "material": "available",
    "research": "unanswered",
    "human_need": "unmet_need",
}
ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class InvalidWorld(ValueError):
    pass


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def _integer(value: Any, low: int, high: int, name: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise InvalidWorld(f"{name} must be an integer in [{low},{high}]")
    return value


def validate(world: Any) -> dict[str, Any]:
    if type(world) is not dict or set(world) != {
        "schema", "cut_id", "attention_units", "injected_signal_id", "signals"
    }:
        raise InvalidWorld("world must have exactly the declared root fields")
    if world["schema"] != SCHEMA or not isinstance(world["cut_id"], str) or not ID.fullmatch(world["cut_id"]):
        raise InvalidWorld("invalid schema or cut_id")
    _integer(world["attention_units"], 1, 11, "attention_units")
    signals = world["signals"]
    if type(signals) is not list or not 1 <= len(signals) <= 64:
        raise InvalidWorld("signals must have 1..64 entries")
    seen = set()
    for signal in signals:
        if type(signal) is not dict or set(signal) != {
            "signal_id", "kind", "cue", "salience", "attention_cost",
            "source_ref", "consent_to_review", "evidence_status"
        }:
            raise InvalidWorld("signal contains missing or extra fields")
        sid = signal["signal_id"]
        if type(sid) is not str or not ID.fullmatch(sid) or sid in seen:
            raise InvalidWorld("invalid or duplicate signal_id")
        seen.add(sid)
        kind = signal["kind"]
        if kind not in KINDS or signal["cue"] != EXPECTED_CUE[kind]:
            raise InvalidWorld("kind/cue mismatch")
        _integer(signal["salience"], 0, 11, "salience")
        _integer(signal["attention_cost"], 1, 11, "attention_cost")
        if signal["evidence_status"] != "SIMULATED_OBSERVED":
            raise InvalidWorld("this specimen accepts simulated observations only")
        if type(signal["source_ref"]) is not str or signal["source_ref"] != "simulated:" + sid:
            raise InvalidWorld("source_ref must bind the simulated signal_id")
        if type(signal["consent_to_review"]) is not bool:
            raise InvalidWorld("consent_to_review must be boolean")
        if kind != "human_need" and signal["consent_to_review"] is not False:
            raise InvalidWorld("consent flag applies only to a declared human_need")
    injected = world["injected_signal_id"]
    if injected is not None:
        if type(injected) is not str or injected not in seen:
            raise InvalidWorld("injected_signal_id must name a signal")
        if next(s for s in signals if s["signal_id"] == injected)["kind"] != "human_need":
            raise InvalidWorld("injected signal must be a declared human_need")
    return world


def run(world: dict[str, Any], policy: str) -> dict[str, Any]:
    validate(world)
    if policy not in POLICIES:
        raise InvalidWorld("unsupported policy")
    capacity = world["attention_units"]
    signals = world["signals"]
    # Sorting deliberately ignores source order; ties are stable and attributable.
    ordered = sorted(signals, key=lambda s: (-s["salience"], s["attention_cost"], s["signal_id"]))
    eligible = [s for s in ordered if s["kind"] != "human_need" or s["consent_to_review"]]
    picks: list[tuple[dict[str, Any], str]] = []
    used = 0
    if policy == "protected":
        # Reserve ONE attention slot for an explicitly declared, opted-in need.
        needs = [s for s in eligible if s["kind"] == "human_need" and s["attention_cost"] <= capacity]
        if needs:
            chosen = needs[0]
            picks.append((chosen, "DECLARED_NEED_PROTECTED_SLOT"))
            used += chosen["attention_cost"]
    selected_ids = {s["signal_id"] for s, _ in picks}
    for signal in eligible:
        if signal["signal_id"] in selected_ids:
            continue
        if used + signal["attention_cost"] <= capacity:
            picks.append((signal, "SALIENCE_GREEDY"))
            selected_ids.add(signal["signal_id"])
            used += signal["attention_cost"]

    picked = {s["signal_id"]: reason for s, reason in picks}
    witness = []
    for signal in sorted(signals, key=lambda s: s["signal_id"]):
        sid = signal["signal_id"]
        if sid in picked:
            disposition, reason = "ATTENDED", picked[sid]
        elif signal["kind"] == "human_need" and not signal["consent_to_review"]:
            disposition, reason = "HELD_UNREVIEWED", "CONSENT_NOT_GIVEN"
        elif signal["attention_cost"] > capacity:
            disposition, reason = "OBSERVED_NOT_ATTENDED", "COST_EXCEEDS_TOTAL_BUDGET"
        else:
            disposition, reason = "OBSERVED_NOT_ATTENDED", "FINITE_BUDGET_OR_ORDER"
        witness.append({
            "signal_id": sid, "source_ref": signal["source_ref"],
            "evidence_status": signal["evidence_status"], "kind": signal["kind"],
            "salience": signal["salience"], "attention_cost": signal["attention_cost"],
            "disposition": disposition, "reason": reason
        })

    questions = []
    for signal, reason in picks:
        template, probe = QUESTIONS[signal["cue"]]
        questions.append({
            "source_signal_id": signal["signal_id"],
            "question": template.format(id=signal["signal_id"]),
            "proposed_probe": probe, "attention_reason": reason,
            "requires_fresh_owner_admission": True,
            "executed": False
        })

    report = {
        "schema": RECEIPT, "cut_id": world["cut_id"], "source_digest": digest(world),
        "policy": policy, "attention_budget": capacity, "attention_spent": used,
        "attention_unspent": capacity - used,
        "selection_order": [s["signal_id"] for s, _ in picks],
        "witness": witness, "questions": questions,
        "next_question": questions[0] if questions else None,
        "authority": "NONE", "effects": [], "signed": False,
        "coverage": {
            "simulated_observed_count": len(signals),
            "attended_count": len(picks),
            "unobserved_reality": "UNKNOWN",
            "actual_human_need_verified": False,
            "actual_rf_received": False,
        },
    }
    report["receipt_digest"] = digest(report)
    return report


def verify(world: dict[str, Any], receipt: dict[str, Any]) -> bool:
    if type(receipt) is not dict or type(receipt.get("receipt_digest")) is not str:
        return False
    try:
        raw = {k: v for k, v in receipt.items() if k != "receipt_digest"}
        return (
            receipt["receipt_digest"] == digest(raw)
            and canonical(receipt) == canonical(run(world, receipt["policy"]))
        )
    except (KeyError, InvalidWorld, TypeError, ValueError):
        return False


def compare(world: dict[str, Any]) -> dict[str, Any]:
    validate(world)
    injected = world["injected_signal_id"]
    if injected is None:
        raise InvalidWorld("comparison requires injected_signal_id")
    initial = {
        **world,
        "injected_signal_id": None,
        "signals": [s for s in world["signals"] if s["signal_id"] != injected],
    }
    if not initial["signals"]:
        raise InvalidWorld("comparison needs an initial world")
    return {
        "schema": "ghot.unheard-choir-comparison/v0",
        "initial_loudest": run(initial, "loudest"),
        "after_loudest": run(world, "loudest"),
        "after_protected": run(world, "protected"),
        "injected_signal_id": injected,
        "interpretation": "policy contrast only; no inferred real-world utility or welfare outcome",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "compare", "verify"))
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--policy", choices=POLICIES, default="protected")
    parser.add_argument("--receipt", type=Path, help="for verify")
    args = parser.parse_args()
    try:
        world = json.loads(args.fixture.read_text(encoding="utf-8"))
        if args.command == "run":
            result = run(world, args.policy)
        elif args.command == "compare":
            result = compare(world)
        else:
            if args.receipt is None:
                parser.error("verify requires --receipt")
            result = {"verified": verify(world, json.loads(args.receipt.read_text(encoding="utf-8")))}
    except (InvalidWorld, ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if args.command != "verify" or result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
