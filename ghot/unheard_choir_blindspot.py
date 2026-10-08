#!/usr/bin/env python3
"""UNHEARD CHOIR 002: propose an instrument for an explicitly declared blind spot.

The proposal stage sees only an observed 001 world and an instrument aperture
catalogue. A *separate, hidden fixture* may be opened only by an explicitly
approved simulation. Nothing invokes hardware, RF, a native GHoT dispatch, or
a reLATTE crossing; approval strings are test inputs, not credentials.
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from unheard_choir import (
    ID, SCHEMA, InvalidWorld, digest, canonical, run as attend, validate as validate_world,
)

FIELD_SCHEMA = "ghot.unheard-choir-blindspot-field/v0"
PLAN_SCHEMA = "ghot.unheard-choir-instrument-proposal/v0"
ORACLE_SCHEMA = "ghot.unheard-choir-hidden-fixture/v0"
RECEIPT_SCHEMA = "ghot.unheard-choir-instrument-receipt/v0"
GROUPS = {"radio", "material", "community"}
CLASSES = {"ordinary", "owner-reviewed"}


def _exact(value: Any, keys: set[str], name: str) -> None:
    if type(value) is not dict or set(value) != keys:
        raise InvalidWorld(f"{name}: incorrect fields")


def _id(value: Any, name: str) -> None:
    if type(value) is not str or not ID.fullmatch(value):
        raise InvalidWorld(f"{name}: invalid id")


def _int(value: Any, low: int, high: int, name: str) -> None:
    if type(value) is not int or not low <= value <= high:
        raise InvalidWorld(f"{name}: integer must be in [{low}, {high}]")


def validate_field(world: Any, field: Any) -> None:
    validate_world(world)
    if world["injected_signal_id"] is not None:
        raise InvalidWorld("002 baseline must not contain an injected signal")
    _exact(field, {
        "schema", "cut_id", "source_world_digest", "exploration_budget",
        "observed_signal_count", "apertures",
    }, "field")
    if field["schema"] != FIELD_SCHEMA or field["cut_id"] != world["cut_id"]:
        raise InvalidWorld("field is not for this source cut")
    if field["source_world_digest"] != digest(world):
        raise InvalidWorld("field source digest mismatch")
    _int(field["exploration_budget"], 1, 11, "exploration_budget")
    if type(field["observed_signal_count"]) is not int or field["observed_signal_count"] != len(world["signals"]):
        raise InvalidWorld("observed_signal_count mismatch")
    apertures = field["apertures"]
    if type(apertures) is not list or not 1 <= len(apertures) <= 16:
        raise InvalidWorld("expected 1..16 declared apertures")
    seen, instruments = set(), set()
    for aperture in apertures:
        _exact(aperture, {
            "aperture_id", "group", "instrument_id", "inspection_cost",
            "expected_gain_proxy", "available", "owner_epoch", "review_class",
            "coverage_status",
        }, "aperture")
        _id(aperture["aperture_id"], "aperture_id")
        _id(aperture["instrument_id"], "instrument_id")
        if aperture["aperture_id"] in seen or aperture["instrument_id"] in instruments:
            raise InvalidWorld("duplicate aperture or instrument")
        seen.add(aperture["aperture_id"])
        instruments.add(aperture["instrument_id"])
        if type(aperture["group"]) is not str or aperture["group"] not in GROUPS:
            raise InvalidWorld("invalid declared aperture group")
        _int(aperture["inspection_cost"], 1, 11, "inspection_cost")
        _int(aperture["expected_gain_proxy"], 0, 11, "expected_gain_proxy")
        if type(aperture["available"]) is not bool:
            raise InvalidWorld("available must be a bool")
        _int(aperture["owner_epoch"], 0, 999999, "owner_epoch")
        if type(aperture["review_class"]) is not str or aperture["review_class"] not in CLASSES:
            raise InvalidWorld("invalid review class")
        if aperture["group"] == "community" and aperture["review_class"] != "owner-reviewed":
            raise InvalidWorld("community aperture requires owner review")
        if aperture["coverage_status"] != "DECLARED_UNOBSERVED":
            raise InvalidWorld("002 instrument may target only declared unobserved aperture")


def _score_key(aperture: dict[str, Any]) -> tuple:
    # Proxy chosen by fixture author, never an estimated real information gain.
    return (-Fraction(aperture["expected_gain_proxy"], aperture["inspection_cost"]),
            aperture["inspection_cost"], aperture["aperture_id"])


def propose(world: dict[str, Any], field: dict[str, Any]) -> dict[str, Any]:
    validate_field(world, field)
    budget = field["exploration_budget"]
    viable = [a for a in field["apertures"]
              if a["available"] and a["inspection_cost"] <= budget
              and a["expected_gain_proxy"] > 0]
    viable.sort(key=_score_key)
    chosen = viable[0] if viable else None
    if chosen is None:
        if all(not a["available"] for a in field["apertures"]):
            why_hold = "HOLD_ALL_INSTRUMENTS_WITHDRAWN"
        elif all(a["inspection_cost"] > budget or not a["available"] for a in field["apertures"]):
            why_hold = "HOLD_NO_AFFORDABLE_AVAILABLE_INSTRUMENT"
        else:
            why_hold = "HOLD_NO_POSITIVE_DECLARED_GAIN"
    else:
        why_hold = None
    witness = []
    for aperture in sorted(field["apertures"], key=lambda a: a["aperture_id"]):
        if chosen is not None and aperture["aperture_id"] == chosen["aperture_id"]:
            status = "INSTRUMENT_PROPOSED"
        elif not aperture["available"]:
            status = "INSTRUMENT_WITHDRAWN"
        elif aperture["inspection_cost"] > budget:
            status = "INSTRUMENT_UNAFFORDABLE"
        else:
            status = "INSTRUMENT_NOT_SELECTED"
        witness.append({
            "aperture_id": aperture["aperture_id"],
            "coverage_status": "DECLARED_UNOBSERVED",
            "decision": status,
            "inspection_cost": aperture["inspection_cost"],
            "expected_gain_proxy": aperture["expected_gain_proxy"],
        })
    selected = None if chosen is None else {
        "aperture_id": chosen["aperture_id"],
        "instrument_id": chosen["instrument_id"],
        "inspection_cost": chosen["inspection_cost"],
        "expected_gain_proxy": chosen["expected_gain_proxy"],
        "owner_epoch": chosen["owner_epoch"],
        "review_class": chosen["review_class"],
        "proposed_question": (
            "What, if anything, would one bounded simulated inspection of "
            + chosen["aperture_id"] + " actually observe?"
        ),
        "fresh_owner_review_required": True,
        "execution_approved": False,
    }
    base = {
        "schema": PLAN_SCHEMA, "cut_id": field["cut_id"],
        "source_world_digest": digest(world), "field_digest": digest(field),
        "source_attention_receipt_digest": attend(world, "protected")["receipt_digest"],
        "exploration_budget": budget,
        "source_observed_count": len(world["signals"]),
        "known_unobserved_apertures": len(field["apertures"]),
        "selected": selected, "hold_reason": why_hold, "aperture_witness": witness,
        "oracle_read": False, "simulated_measurement_performed": False,
        "external_execution": False, "authority": "NONE", "signed": False,
        "effects": [],
        "epistemic_note": (
            "An instrument's declared coverage gap is known; whether a source exists "
            "inside the gap is UNKNOWN. Proxy utility is not measured utility."
        ),
    }
    base["proposal_digest"] = digest(base)
    return base


def _approval_check(
    world: dict[str, Any], field: dict[str, Any], proposal: Any,
    approve_proposal: str | None, approve_aperture: str | None,
) -> dict[str, Any]:
    expected = propose(world, field)
    if type(proposal) is not dict or canonical(proposal) != canonical(expected):
        raise InvalidWorld("stale, forged, or mismatched proposal")
    selected = expected["selected"]
    if selected is None:
        raise InvalidWorld("HOLD cannot be executed")
    if type(approve_proposal) is not str or approve_proposal != expected["proposal_digest"]:
        raise InvalidWorld("explicit exact-proposal test approval missing")
    if type(approve_aperture) is not str or approve_aperture != selected["aperture_id"]:
        raise InvalidWorld("explicit exact-aperture test approval missing")
    return selected


def simulate(
    world: dict[str, Any], field: dict[str, Any], proposal: dict[str, Any],
    oracle: Any, *, approve_proposal: str | None, approve_aperture: str | None,
) -> dict[str, Any]:
    # No inspection of the hidden fixture until a valid fresh proposal and explicit
    # exact test approval have passed. This is NOT an owner-authentication system.
    selected = _approval_check(world, field, proposal, approve_proposal, approve_aperture)
    _exact(oracle, {
        "schema", "cut_id", "aperture_id", "instrument_id", "owner_epoch",
        "measurement_kind", "signal",
    }, "hidden fixture")
    if (oracle["schema"] != ORACLE_SCHEMA or oracle["cut_id"] != world["cut_id"]
        or oracle["aperture_id"] != selected["aperture_id"]
        or oracle["instrument_id"] != selected["instrument_id"]
        or type(oracle["owner_epoch"]) is not int
        or oracle["owner_epoch"] != selected["owner_epoch"]):
        raise InvalidWorld("hidden fixture must match current selected instrument and owner epoch")
    if oracle["measurement_kind"] not in ("SIMULATED_OBSERVATION", "SIMULATED_EMPTY_WINDOW"):
        raise InvalidWorld("unsupported synthetic measurement kind")
    signal = oracle["signal"]
    if oracle["measurement_kind"] == "SIMULATED_EMPTY_WINDOW":
        if signal is not None:
            raise InvalidWorld("empty simulation cannot contain a source")
        status, after, published_signal = "SIMULATED_EMPTY_WINDOW", attend(world, "protected"), None
    else:
        if type(signal) is not dict:
            raise InvalidWorld("simulated observation requires a valid source")
        # 001 validation enforces simulated-only status, source binding, and
        # declared human_need consent flag; no real-world identity is verified.
        child = {
            **world, "cut_id": "choir002-" + digest({
                "source": digest(world), "aperture": selected["aperture_id"],
                "fixture": digest(oracle)
            })[:28],
            "injected_signal_id": signal.get("signal_id") if signal.get("kind") == "human_need" else None,
            "signals": world["signals"] + [signal],
        }
        validate_world(child)
        aperture_group = next(a["group"] for a in field["apertures"]
                              if a["aperture_id"] == selected["aperture_id"])
        allowed_kinds = {
            "community": {"human_need"},
            "radio": {"radio"},
            "material": {"material"},
        }
        if signal["kind"] not in allowed_kinds[aperture_group]:
            raise InvalidWorld("source kind does not match selected instrument group")
        if signal["kind"] == "human_need" and not signal["consent_to_review"]:
            status, after, published_signal = "HELD_UNREVIEWED_DECLARED_CONSENT", attend(world, "protected"), None
        else:
            status, after, published_signal = "SIMULATED_OBSERVATION", attend(child, "protected"), signal
    result = {
        "schema": RECEIPT,
        "source_cut_id": world["cut_id"], "source_world_digest": digest(world),
        "field_digest": digest(field), "proposal_digest": proposal["proposal_digest"],
        "approved_aperture": selected["aperture_id"], "instrument_id": selected["instrument_id"],
        "owner_epoch": selected["owner_epoch"], "exploration_budget": field["exploration_budget"],
        "exploration_cost_spent_in_simulation": selected["inspection_cost"],
        "exploration_budget_remaining": field["exploration_budget"] - selected["inspection_cost"],
        "simulation_outcome": status,
        "synthetic_source_disclosed": published_signal,
        "source_attention_before": attend(world, "protected"),
        "source_attention_after": after,
        "oracle_fixture_digest": digest(oracle),
        "simulated_read_only_probe_performed": True,
        "external_execution": False, "real_world_observed": False,
        "human_need_independently_verified": False,
        "authority": "NONE", "signed": False, "effects": [],
        "note": "Fixture-only test approval and simulated disclosure; not a native GHoT or reLATTE admission",
    }
    result["receipt_digest"] = digest(result)
    return result


def verify_simulation(
    world: dict[str, Any], field: dict[str, Any], proposal: dict[str, Any],
    oracle: dict[str, Any], receipt: Any,
    *, approve_proposal: str | None, approve_aperture: str | None,
) -> bool:
    if type(receipt) is not dict or type(receipt.get("receipt_digest")) is not str:
        return False
    try:
        raw = {k: v for k, v in receipt.items() if k != "receipt_digest"}
        return receipt["receipt_digest"] == digest(raw) and canonical(receipt) == canonical(
            simulate(world, field, proposal, oracle,
                     approve_proposal=approve_proposal, approve_aperture=approve_aperture)
        )
    except (InvalidWorld, ValueError, TypeError, KeyError):
        return False


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "simulate", "verify"))
    parser.add_argument("--world", required=True, type=Path)
    parser.add_argument("--field", required=True, type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--oracle", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--approve-proposal")
    parser.add_argument("--approve-aperture")
    args = parser.parse_args()
    try:
        world, field = _read(args.world), _read(args.field)
        if args.command == "plan":
            output = propose(world, field)
        else:
            if args.plan is None or args.oracle is None:
                parser.error("simulate/verify require --plan and --oracle")
            proposal = _read(args.plan)
            # CLI approval gate runs *before* reading the fixture file.
            _approval_check(world, field, proposal,
                            args.approve_proposal, args.approve_aperture)
            if args.command == "simulate":
                output = simulate(world, field, proposal, _read(args.oracle),
                                  approve_proposal=args.approve_proposal,
                                  approve_aperture=args.approve_aperture)
            else:
                if args.receipt is None:
                    parser.error("verify requires --receipt")
                output = {"verified": verify_simulation(
                    world, field, proposal, _read(args.oracle), _read(args.receipt),
                    approve_proposal=args.approve_proposal,
                    approve_aperture=args.approve_aperture)}
    except (InvalidWorld, ValueError, TypeError, OSError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0 if args.command != "verify" or output["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
