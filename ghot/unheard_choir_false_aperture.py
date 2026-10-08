#!/usr/bin/env python3
"""UNHEARD CHOIR 003 — The False Aperture.

Treat vendor aperture claims as hostile. A separately supplied, owner-accepted
fixture registry and digest-bound historical *simulations* constrain what may
be proposed. Replay 002 simulated probes as evidence; count only newly
disclosed source IDs, never advertised gain. All approvals remain test-only.
No hardware, network, source-owner authentication, or signed crossing.
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from unheard_choir import ID, InvalidWorld, canonical, digest
from unheard_choir_blindspot import (
    propose as propose_002, simulate as simulate_002,
    validate_field,
)

CLAIMS_SCHEMA = "ghot.unheard-choir-untrusted-catalog/v0"
REGISTRY_SCHEMA = "ghot.unheard-choir-owner-registry-fixture/v0"
HISTORY_SCHEMA = "ghot.unheard-choir-reviewed-history-fixture/v0"
PLAN_SCHEMA = "ghot.unheard-choir-false-aperture-plan/v0"
RECEIPT_SCHEMA = "ghot.unheard-choir-false-aperture-receipt/v0"


def strict(value: Any, keys: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != keys:
        raise InvalidWorld(f"{label}: missing or extra keys")


def ident(value: Any, label: str) -> None:
    if type(value) is not str or not ID.fullmatch(value):
        raise InvalidWorld(f"{label}: invalid identifier")


def number(value: Any, low: int, high: int, label: str) -> None:
    if type(value) is not int or not low <= value <= high:
        raise InvalidWorld(f"{label}: integer out of bounds")


def isolated(field: dict[str, Any], aperture: dict[str, Any]) -> dict[str, Any]:
    return {**field, "apertures": [aperture]}


def validate_inputs(
    world: Any, field: Any, claims: Any, registry: Any, history: Any,
) -> None:
    validate_field(world, field)
    strict(claims, {"schema", "cut_id", "claims"}, "catalog")
    if claims["schema"] != CLAIMS_SCHEMA or claims["cut_id"] != world["cut_id"]:
        raise InvalidWorld("untrusted catalogue wrong cut or schema")
    if type(claims["claims"]) is not list or not 1 <= len(claims["claims"]) <= 64:
        raise InvalidWorld("catalogue needs 1..64 claims")
    ids = set()
    for claim in claims["claims"]:
        strict(claim, {
            "claim_id", "aperture_id", "instrument_id",
            "claimed_owner_epoch", "advertised_gain", "claim_status",
        }, "claim")
        for k in ("claim_id", "aperture_id", "instrument_id"):
            ident(claim[k], k)
        if claim["claim_id"] in ids:
            raise InvalidWorld("duplicate claim identity")
        ids.add(claim["claim_id"])
        number(claim["claimed_owner_epoch"], 0, 999999, "claimed_owner_epoch")
        number(claim["advertised_gain"], 0, 1000000, "advertised_gain")
        if claim["claim_status"] != "UNVERIFIED_VENDOR_ASSERTION":
            raise InvalidWorld("catalogue may not claim verified ground truth")

    strict(history, {"schema", "cut_id", "trials"}, "history")
    if history["schema"] != HISTORY_SCHEMA or history["cut_id"] != world["cut_id"]:
        raise InvalidWorld("history wrong cut/schema")
    if type(history["trials"]) is not list or len(history["trials"]) > 32:
        raise InvalidWorld("history trial count invalid")
    seen_trials = set()
    for trial in history["trials"]:
        strict(trial, {"trial_id", "aperture_id", "oracle"}, "trial")
        ident(trial["trial_id"], "trial_id")
        ident(trial["aperture_id"], "trial aperture_id")
        if trial["trial_id"] in seen_trials:
            raise InvalidWorld("duplicate historical trial")
        seen_trials.add(trial["trial_id"])

    strict(registry, {
        "schema", "cut_id", "source_world_digest", "source_field_digest",
        "accepted_history_digest", "scope", "entries",
    }, "registry")
    if registry["schema"] != REGISTRY_SCHEMA or registry["cut_id"] != world["cut_id"]:
        raise InvalidWorld("registry cut/schema mismatch")
    if registry["source_world_digest"] != digest(world) or registry["source_field_digest"] != digest(field):
        raise InvalidWorld("owner registry does not match current source/field cut")
    if registry["accepted_history_digest"] != digest(history):
        raise InvalidWorld("historical fixture changed since owner-accepted digest")
    if registry["scope"] != "SIMULATION_ONLY_NO_EXTERNAL_AUTHORITY":
        raise InvalidWorld("registry cannot grant external execution")
    if type(registry["entries"]) is not list or not 1 <= len(registry["entries"]) <= 16:
        raise InvalidWorld("invalid owner registry entries")
    seen = set()
    current = {a["aperture_id"]: a for a in field["apertures"]}
    for entry in registry["entries"]:
        strict(entry, {
            "aperture_id", "instrument_id", "owner_epoch",
            "owner_allows_proposal", "review_class", "privacy_scope",
        }, "registry entry")
        ident(entry["aperture_id"], "registry aperture")
        ident(entry["instrument_id"], "registry instrument")
        if entry["aperture_id"] in seen:
            raise InvalidWorld("duplicate registry aperture")
        seen.add(entry["aperture_id"])
        number(entry["owner_epoch"], 0, 999999, "registry owner_epoch")
        if type(entry["owner_allows_proposal"]) is not bool:
            raise InvalidWorld("owner_allows_proposal must be boolean")
        if entry["privacy_scope"] != "DECLARED_FIXTURE_ONLY":
            raise InvalidWorld("registry privacy scope not allowed")
        a = current.get(entry["aperture_id"])
        if (a is None or a["instrument_id"] != entry["instrument_id"]
            or a["owner_epoch"] != entry["owner_epoch"]
            or a["review_class"] != entry["review_class"]):
            raise InvalidWorld("registry entry not current for owner's declared instrument")


def historical_outcomes(world: dict, field: dict, history: dict) -> dict[str, dict]:
    by_aperture = {a["aperture_id"]: a for a in field["apertures"]}
    outcomes = {}
    for trial in sorted(history["trials"], key=lambda t: t["trial_id"]):
        aperture = by_aperture.get(trial["aperture_id"])
        if aperture is None:
            raise InvalidWorld("historical trial unknown aperture")
        # Reconstruct from the actual parent-002 simulator. History is a
        # locally accepted archive fixture, NOT a source signature.
        subfield = isolated(field, aperture)
        plan = propose_002(world, subfield)
        if plan["selected"] is None:
            raise InvalidWorld("historical trial has no eligible simulated instrument")
        try:
            receipt = simulate_002(
                world, subfield, plan, trial["oracle"],
                approve_proposal=plan["proposal_digest"],
                approve_aperture=aperture["aperture_id"],
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise InvalidWorld("invalid or stale historical trial: " + trial["trial_id"]) from exc
        before = {s["signal_id"] for s in receipt["source_attention_before"]["witness"]}
        after = {s["signal_id"] for s in receipt["source_attention_after"]["witness"]}
        novel = len(after - before)
        if novel not in (0, 1):
            raise InvalidWorld("unexpected historical fixture novelty")
        state = outcomes.setdefault(aperture["aperture_id"], {
            "trial_count": 0, "new_source_count": 0, "receipts": [],
        })
        state["trial_count"] += 1
        state["new_source_count"] += novel
        state["receipts"].append({
            "trial_id": trial["trial_id"],
            "002_simulation_receipt_digest": receipt["receipt_digest"],
            "novel_source_ids_count": novel,
            "outcome": receipt["simulation_outcome"],
        })
    return outcomes


def propose(world: dict, field: dict, claims: dict, registry: dict, history: dict) -> dict:
    validate_inputs(world, field, claims, registry, history)
    evidence = historical_outcomes(world, field, history)
    available = {a["aperture_id"]: a for a in field["apertures"]}
    permitted = {e["aperture_id"]: e for e in registry["entries"]}
    by_target = {}
    for claim in claims["claims"]:
        by_target.setdefault(claim["aperture_id"], []).append(claim)
    witnesses, candidates = [], []
    for claim in sorted(claims["claims"], key=lambda c: c["claim_id"]):
        aperture_id = claim["aperture_id"]
        a, e = available.get(aperture_id), permitted.get(aperture_id)
        proof = evidence.get(aperture_id)
        if len(by_target[aperture_id]) != 1:
            reason = "CONFLICTING_VENDOR_CLAIMS"
        elif a is None:
            reason = "UNDECLARED_APERTURE"
        elif claim["instrument_id"] != a["instrument_id"]:
            reason = "INSTRUMENT_ID_MISMATCH"
        elif claim["claimed_owner_epoch"] != a["owner_epoch"]:
            reason = "STALE_OWNER_EPOCH"
        elif not a["available"]:
            reason = "WITHDRAWN_INSTRUMENT"
        elif a["inspection_cost"] > field["exploration_budget"]:
            reason = "UNAFFORDABLE_INSTRUMENT"
        elif e is None or not e["owner_allows_proposal"]:
            reason = "OWNER_DID_NOT_ALLOW_PROPOSAL"
        elif proof is None or proof["trial_count"] == 0:
            reason = "NO_ACCEPTED_SIMULATION_HISTORY"
        elif proof["new_source_count"] == 0:
            reason = "NO_MEASURED_SIMULATED_NOVELTY"
        else:
            reason = "CANDIDATE_BY_ACCEPTED_SIMULATED_NOVELTY"
            candidates.append((claim, a, e, proof))
        witnesses.append({
            "claim_id": claim["claim_id"], "aperture_id": aperture_id,
            "advertised_gain_untrusted": claim["advertised_gain"],
            "decision": reason,
            "historical_new_source_count": proof["new_source_count"] if proof else None,
            "historical_trial_count": proof["trial_count"] if proof else None,
        })
    candidates.sort(key=lambda c: (
        -Fraction(c[3]["new_source_count"], c[3]["trial_count"] * c[1]["inspection_cost"]),
        c[1]["inspection_cost"], c[1]["aperture_id"],
    ))
    selected = None
    if candidates:
        claim, a, e, proof = candidates[0]
        selected = {
            "claim_id": claim["claim_id"],
            "aperture_id": a["aperture_id"],
            "instrument_id": a["instrument_id"],
            "owner_epoch": a["owner_epoch"],
            "review_class": a["review_class"],
            "inspection_cost": a["inspection_cost"],
            "historical_new_source_count": proof["new_source_count"],
            "historical_trial_count": proof["trial_count"],
            "evidence_receipts": proof["receipts"],
            "requires_fresh_simulation_approval": True,
            "proposed_question": (
                "Does a fresh bounded simulated inspection of " + a["aperture_id"]
                + " produce new attributable source IDs?"
            ),
        }
    report = {
        "schema": PLAN_SCHEMA, "cut_id": world["cut_id"],
        "world_digest": digest(world), "field_digest": digest(field),
        "catalog_digest": digest(claims), "registry_digest": digest(registry),
        "history_digest": digest(history),
        "budget": field["exploration_budget"],
        "selected": selected,
        "hold_reason": None if selected else "HOLD_NO_EVIDENCED_PERMITTED_INSTRUMENT",
        "claim_witness": witnesses,
        "archive_is_independently_authenticated": False,
        "vendor_gain_used_for_selection": False,
        "actual_information_utility_measured": False,
        "future_oracle_read": False, "external_execution": False,
        "authority": "NONE", "signed": False, "effects": [],
    }
    report["proposal_digest"] = digest(report)
    return report


def check_approval(world: dict, field: dict, claims: dict, registry: dict,
                   history: dict, proposal: Any, approved_id: Any,
                   approved_aperture: Any) -> dict:
    expected = propose(world, field, claims, registry, history)
    if type(proposal) is not dict or canonical(proposal) != canonical(expected):
        raise InvalidWorld("stale or forged 003 proposal")
    selected = expected["selected"]
    if selected is None:
        raise InvalidWorld("HOLD cannot execute any inspection")
    if type(approved_id) is not str or approved_id != expected["proposal_digest"]:
        raise InvalidWorld("exact proposal simulation approval missing")
    if type(approved_aperture) is not str or approved_aperture != selected["aperture_id"]:
        raise InvalidWorld("exact aperture simulation approval missing")
    return selected


def simulate(world: dict, field: dict, claims: dict, registry: dict,
             history: dict, proposal: dict, future_oracle: Any, *,
             approved_id: Any, approved_aperture: Any) -> dict:
    selected = check_approval(world, field, claims, registry, history,
                              proposal, approved_id, approved_aperture)
    aperture = next(a for a in field["apertures"] if a["aperture_id"] == selected["aperture_id"])
    subfield = isolated(field, aperture)
    parent_plan = propose_002(world, subfield)
    parent_receipt = simulate_002(
        world, subfield, parent_plan, future_oracle,
        approve_proposal=parent_plan["proposal_digest"],
        approve_aperture=selected["aperture_id"],
    )
    before = {s["signal_id"] for s in parent_receipt["source_attention_before"]["witness"]}
    after = {s["signal_id"] for s in parent_receipt["source_attention_after"]["witness"]}
    newly_seen = sorted(after - before)
    output = {
        "schema": RECEIPT,
        "proposal_digest": proposal["proposal_digest"],
        "selected_aperture": selected["aperture_id"],
        "field_digest": digest(field), "world_digest": digest(world),
        "history_digest": digest(history), "registry_digest": digest(registry),
        "future_oracle_digest": digest(future_oracle),
        "parent_002_receipt": parent_receipt,
        "measured_novel_simulated_source_ids": newly_seen,
        "measured_novel_simulated_source_count": len(newly_seen),
        "advertised_gain_trusted": False,
        "novelty_is_human_benefit": False,
        "owner_identity_authenticated": False,
        "real_world_observed": False,
        "external_execution": False, "authority": "NONE",
        "signed": False, "effects": [],
        "note": "Test-only isolated 002 simulated observation; measured novelty is not information value",
    }
    output["receipt_digest"] = digest(output)
    return output


def verify(world: dict, field: dict, claims: dict, registry: dict, history: dict,
           proposal: dict, future_oracle: dict, receipt: Any, *,
           approved_id: Any, approved_aperture: Any) -> bool:
    if type(receipt) is not dict or type(receipt.get("receipt_digest")) is not str:
        return False
    try:
        raw = {k: v for k, v in receipt.items() if k != "receipt_digest"}
        return receipt["receipt_digest"] == digest(raw) and canonical(receipt) == canonical(
            simulate(world, field, claims, registry, history, proposal,
                     future_oracle, approved_id=approved_id,
                     approved_aperture=approved_aperture)
        )
    except (InvalidWorld, KeyError, ValueError, TypeError):
        return False


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("plan", "simulate", "verify"))
    for name in ("world", "field", "claims", "registry", "history"):
        p.add_argument("--" + name, type=Path, required=True)
    for name in ("plan", "oracle", "receipt"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--approve-proposal")
    p.add_argument("--approve-aperture")
    a = p.parse_args()
    try:
        args = [read(getattr(a, n)) for n in ("world", "field", "claims", "registry", "history")]
        if a.command == "plan":
            result = propose(*args)
        else:
            if a.plan is None or a.oracle is None:
                p.error("simulate/verify need --plan and --oracle")
            plan = read(a.plan)
            # Exact test permission checked before opening the future oracle file.
            check_approval(*args, plan, a.approve_proposal, a.approve_aperture)
            future = read(a.oracle)
            if a.command == "simulate":
                result = simulate(*args, plan, future,
                                  approved_id=a.approve_proposal,
                                  approved_aperture=a.approve_aperture)
            else:
                if a.receipt is None:
                    p.error("verify also needs --receipt")
                result = {"verified": verify(*args, plan, future, read(a.receipt),
                    approved_id=a.approve_proposal, approved_aperture=a.approve_aperture)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if a.command != "verify" or result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
