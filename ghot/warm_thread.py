#!/usr/bin/env python3
"""Warm Thread 039 — compose stranded usefulness toward present need.

This experiment does not execute physical work and does not infer truth,
ownership, safety, or obligation from a declared offer.

It composes a bounded candidate path:

    HAVE -> CAN -> NEAR -> NOW -> CROSS

while preserving:

    CAPACITY != OBLIGATION
    CANDIDATE != AUTHORIZATION
    AUTHORIZATION N != AUTHORIZATION N+1
    NEED VISIBLE != ENTITLEMENT
    PROPOSAL != EXECUTION
    ECONOMIC LAYER != REQUIRED PATH
"""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

FORMAT = "ghot.warm-thread-proposal"
VERSION = 1
AUTH_FORMAT = "ghot.warm-thread-step-authorization"
PLAN_FORMAT = "ghot.warm-thread-execution-readiness"

FORBIDDEN_COLLAPSE_FIELDS = {
    "score",
    "rank",
    "price",
    "exchange_rate",
    "common_unit",
    "human_worth",
    "automatic_execution",
}

REQUIRED_STEP_KINDS = (
    "release-resource",
    "transform-resource",
    "transport-resource",
    "accept-resource",
)


class WarmThreadError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _address(prefix: str, value: Any) -> str:
    return f"{prefix}:{hashlib.sha256(_canonical(value)).hexdigest()}"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WarmThreadError(f"{name} must be a non-empty string")
    return value


def _check_no_collapse(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_COLLAPSE_FIELDS:
                raise WarmThreadError(f"forbidden collapse field at {path}.{key}")
            _check_no_collapse(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_no_collapse(item, f"{path}[{i}]")


def make_record(
    *,
    record_id: str,
    kind: str,
    actor: str,
    subject: str,
    relation: str,
    window: str,
    locality: str,
    claims: dict[str, Any] | None = None,
    privacy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "record_id": _nonempty(record_id, "record_id"),
        "kind": _nonempty(kind, "kind"),
        "actor": _nonempty(actor, "actor"),
        "subject": _nonempty(subject, "subject"),
        "relation": _nonempty(relation, "relation"),
        "window": _nonempty(window, "window"),
        "locality": _nonempty(locality, "locality"),
        "claims": claims or {},
        "privacy": privacy or {},
        "authority": "self-declared-candidate-input",
    }
    _check_no_collapse(body)
    return body


def _find(records: list[dict[str, Any]], *, kind: str, relation: str) -> dict[str, Any] | None:
    for record in records:
        if record.get("kind") == kind and record.get("relation") == relation:
            return record
    return None


def compose(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(records, list) or not records:
        raise WarmThreadError("records must be a non-empty list")
    for record in records:
        if not isinstance(record, dict):
            raise WarmThreadError("every record must be an object")
        _check_no_collapse(record)

    tree = _find(records, kind="have", relation="firewood-feedstock")
    cutter = _find(records, kind="can", relation="cut-wood")
    hauler = _find(records, kind="can", relation="haul-firewood")
    heat = _find(records, kind="need", relation="heat-home")

    required = [
        ("firewood-feedstock", tree),
        ("cut-wood", cutter),
        ("haul-firewood", hauler),
        ("heat-home", heat),
    ]
    missing = [name for name, record in required if record is None]

    base = {
        "format": FORMAT,
        "version": VERSION,
        "authority": "proposal-only",
        "externalAuthority": "none",
        "sourceVerification": "self-declared-inputs-unverified",
        "status": "gap" if missing else "composable",
        "missing_relations": missing,
        "source_record_ids": sorted(str(r.get("record_id")) for r in records),
        "economics": {
            "required": False,
            "settlement": None,
            "orientation": "optional-after-useful-path",
            "universal_total": None,
        },
        "privacy": {
            "exact_household_address": "withheld",
            "minimum_necessary_release": True,
        },
        "nonclaims": {
            "physical_existence_verified": False,
            "ownership_verified": False,
            "safety_verified": False,
            "human_identity_verified": False,
            "execution_authorized": False,
        },
        "laws": [
            "CAPACITY != OBLIGATION",
            "CANDIDATE != AUTHORIZATION",
            "AUTHORIZATION N != AUTHORIZATION N+1",
            "NEED VISIBLE != ENTITLEMENT",
            "PROPOSAL != EXECUTION",
            "ECONOMIC LAYER != REQUIRED PATH",
            "LOCATION KNOWN != LOCATION RELEASED",
        ],
    }

    if missing:
        base["steps"] = []
        base["warm_thread_id"] = _address("warm-thread", base)
        return base

    assert tree and cutter and hauler and heat
    actors = {
        "tree_owner": tree["actor"],
        "cutter": cutter["actor"],
        "hauler": hauler["actor"],
        "receiver": heat["actor"],
    }

    steps = [
        {
            "step_id": "release-tree",
            "kind": REQUIRED_STEP_KINDS[0],
            "actor": actors["tree_owner"],
            "subject": tree["subject"],
            "requested_effect": "release-for-firewood-chain",
            "authorization": "required-separately",
            "consumes_future_authority": False,
        },
        {
            "step_id": "cut-tree",
            "kind": REQUIRED_STEP_KINDS[1],
            "actor": actors["cutter"],
            "subject": tree["subject"],
            "requested_effect": "dead-tree-to-cut-firewood",
            "authorization": "required-separately",
            "consumes_future_authority": False,
        },
        {
            "step_id": "haul-load",
            "kind": REQUIRED_STEP_KINDS[2],
            "actor": actors["hauler"],
            "subject": "cut-firewood",
            "requested_effect": "move-one-load-within-declared-radius",
            "authorization": "required-separately",
            "consumes_future_authority": False,
        },
        {
            "step_id": "accept-delivery",
            "kind": REQUIRED_STEP_KINDS[3],
            "actor": actors["receiver"],
            "subject": "one-firewood-load",
            "requested_effect": "accept-firewood-for-home-heat",
            "authorization": "required-separately",
            "consumes_future_authority": False,
        },
    ]

    proposal = {
        **base,
        "thread": {
            "have": tree["record_id"],
            "can_cut": cutter["record_id"],
            "can_haul": hauler["record_id"],
            "need": heat["record_id"],
            "locality": sorted({tree["locality"], cutter["locality"], hauler["locality"], heat["locality"]}),
            "time_windows": [tree["window"], cutter["window"], hauler["window"], heat["window"]],
        },
        "steps": steps,
        "requested_effect": {
            "operation": "consider-warm-thread",
            "automatic_execution_requested": False,
            "automatic_location_release_requested": False,
            "automatic_settlement_requested": False,
        },
    }
    _check_no_collapse(proposal)
    proposal["warm_thread_id"] = _address("warm-thread", proposal)
    return proposal


def authorize_step(
    proposal: dict[str, Any],
    *,
    step_id: str,
    actor: str,
    phrase: str,
) -> dict[str, Any]:
    if proposal.get("format") != FORMAT or proposal.get("status") != "composable":
        raise WarmThreadError("a composable Warm Thread proposal is required")
    if phrase != "ACT":
        raise WarmThreadError("explicit ACT is required")
    step = next((s for s in proposal.get("steps", []) if s.get("step_id") == step_id), None)
    if step is None:
        raise WarmThreadError("unknown step")
    if step.get("actor") != actor:
        raise WarmThreadError("actor does not own this step")
    body = {
        "format": AUTH_FORMAT,
        "version": 1,
        "warm_thread_id": proposal["warm_thread_id"],
        "step_id": step_id,
        "actor": actor,
        "scope": step["requested_effect"],
        "one_attempt": True,
        "delegates_next_step": False,
        "human_identity_proven": False,
    }
    body["authorization_id"] = _address("warm-thread-auth", body)
    return body


def execution_readiness(
    proposal: dict[str, Any],
    authorizations: list[dict[str, Any]],
) -> dict[str, Any]:
    if proposal.get("format") != FORMAT or proposal.get("status") != "composable":
        raise WarmThreadError("a composable Warm Thread proposal is required")
    by_step: dict[str, dict[str, Any]] = {}
    for auth in authorizations:
        if auth.get("format") != AUTH_FORMAT:
            raise WarmThreadError("unknown authorization format")
        if auth.get("warm_thread_id") != proposal["warm_thread_id"]:
            raise WarmThreadError("authorization belongs to another thread")
        step_id = str(auth.get("step_id"))
        if step_id in by_step:
            raise WarmThreadError("duplicate step authorization")
        expected = next((s for s in proposal["steps"] if s["step_id"] == step_id), None)
        if expected is None or auth.get("actor") != expected["actor"]:
            raise WarmThreadError("authorization actor/step mismatch")
        check = {k: v for k, v in auth.items() if k != "authorization_id"}
        if auth.get("authorization_id") != _address("warm-thread-auth", check):
            raise WarmThreadError("authorization identity mismatch")
        by_step[step_id] = auth

    missing = [s["step_id"] for s in proposal["steps"] if s["step_id"] not in by_step]
    return {
        "format": PLAN_FORMAT,
        "version": 1,
        "warm_thread_id": proposal["warm_thread_id"],
        "status": "READY" if not missing else "HOLD",
        "authorized_steps": [s["step_id"] for s in proposal["steps"] if s["step_id"] in by_step],
        "missing_authorizations": missing,
        "execution_performed": False,
        "authority": "readiness-only",
    }


def dead_tree_specimen() -> dict[str, Any]:
    records = [
        make_record(
            record_id="have-tree-001",
            kind="have",
            actor="alice",
            subject="fallen-ash-tree",
            relation="firewood-feedstock",
            window="today",
            locality="neighborhood-a",
            claims={"condition": "dead-tree", "desired_outcome": "removed"},
            privacy={"exact_address": "withheld-until-bounded-release"},
        ),
        make_record(
            record_id="can-cut-001",
            kind="can",
            actor="bob",
            subject="chainsaw-and-labor",
            relation="cut-wood",
            window="16:00-18:00",
            locality="neighborhood-a",
            claims={"capacity": "45-minutes", "safety": "not-verified-by-protocol"},
        ),
        make_record(
            record_id="can-haul-001",
            kind="can",
            actor="cara",
            subject="pickup-truck",
            relation="haul-firewood",
            window="17:00-19:00",
            locality="neighborhood-a",
            claims={"capacity": "one-load", "radius": "8-miles"},
        ),
        make_record(
            record_id="need-heat-001",
            kind="need",
            actor="david",
            subject="home-heat",
            relation="heat-home",
            window="tonight",
            locality="neighborhood-a",
            claims={"need": "firewood", "urgency": "today"},
            privacy={"exact_address": "withheld-until-delivery-step"},
        ),
    ]
    proposal = compose(records)
    return {
        "format": "ghot.warm-thread-specimen",
        "version": 1,
        "name": "dead-tree-to-warm-house",
        "records": records,
        "proposal": proposal,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["specimen", "proposal"])
    args = parser.parse_args()
    specimen = dead_tree_specimen()
    value = specimen if args.command == "specimen" else specimen["proposal"]
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
