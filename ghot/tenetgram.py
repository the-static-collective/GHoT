#!/usr/bin/env python3
"""TenetGram 040 — consequential possibility propagation.

A TenetGram has two faces:

    BACK  = an attributable consequence that already happened
    FRONT = one or more dormant possibility seeds in explicitly connected fields

The base protocol intentionally does not infer a new skill, recommendation,
task, obligation, price, rank, or notification from the consequence.

Founding law:

    CONSEQUENCE -> POSSIBILITY
    POSSIBILITY != REQUEST
    POSSIBILITY != RECOMMENDATION
    POSSIBILITY != OBLIGATION
    SEED != NOTIFICATION
    RELATION != BROADCAST
    TRANSPORT != ADMISSION

A valid TenetGram MUST have at least one explicit forward field link. This is
the bounded meaning of "using it always seeds future possibility somewhere
connected to you."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any


TENETGRAM_FORMAT = "ghot.tenetgram"
TENETGRAM_VERSION = 1
SEED_FORMAT = "ghot.possibility-seed"
SEED_VERSION = 1
FIELD_LINK_FORMAT = "ghot.explicit-field-link"
FIELD_LINK_VERSION = 1

SUPPORTED_CONSEQUENCE_FORMATS = {
    "full-measure.warm-thread-residue",
}

FORBIDDEN_SEED_FIELDS = {
    "score",
    "rank",
    "recommendation",
    "priority",
    "price",
    "exchange_rate",
    "common_unit",
    "human_worth",
}


class TenetGramError(ValueError):
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
        raise TenetGramError(f"{name} must be a non-empty string")
    return value


def _scan_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_SEED_FIELDS:
                raise TenetGramError(f"forbidden field at {path}.{key}")
            _scan_forbidden(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_forbidden(item, f"{path}[{index}]")


def make_field_link(
    *,
    actor: str,
    field_id: str,
    relation: str,
    seed_kinds: list[str] | None = None,
) -> dict[str, Any]:
    """Create one explicit actor -> field possibility-routing edge."""
    body = {
        "format": FIELD_LINK_FORMAT,
        "version": FIELD_LINK_VERSION,
        "actor": _nonempty(actor, "actor"),
        "field_id": _nonempty(field_id, "field_id"),
        "relation": _nonempty(relation, "relation"),
        "seed_kinds": seed_kinds or ["consequence-follow-on"],
        "allows_seed_delivery": True,
        "allows_notification": False,
        "allows_request": False,
        "allows_execution": False,
        "authority": "routing-consent-only",
    }
    if not all(isinstance(kind, str) and kind for kind in body["seed_kinds"]):
        raise TenetGramError("seed_kinds must contain non-empty strings")
    body["field_link_id"] = _address("tenetgram-field-link", body)
    return body


def _verify_field_link(link: dict[str, Any]) -> bool:
    try:
        if not isinstance(link, dict):
            return False
        if link.get("format") != FIELD_LINK_FORMAT or link.get("version") != FIELD_LINK_VERSION:
            return False
        if link.get("allows_seed_delivery") is not True:
            return False
        if link.get("allows_notification") is not False:
            return False
        if link.get("allows_request") is not False:
            return False
        if link.get("allows_execution") is not False:
            return False
        if link.get("authority") != "routing-consent-only":
            return False
        body = {key: value for key, value in link.items() if key != "field_link_id"}
        return link.get("field_link_id") == _address("tenetgram-field-link", body)
    except (TypeError, ValueError):
        return False


def _consequence_participants(consequence: dict[str, Any]) -> set[str]:
    participants: set[str] = set()

    for item in consequence.get("residue") or []:
        if isinstance(item, dict):
            actor = item.get("actor")
            if isinstance(actor, str) and actor:
                participants.add(actor)

    need = consequence.get("remainingNeed")
    if isinstance(need, dict):
        actor = need.get("actor")
        if isinstance(actor, str) and actor:
            participants.add(actor)

    return participants


def _validate_consequence(consequence: dict[str, Any]) -> None:
    if not isinstance(consequence, dict):
        raise TenetGramError("consequence must be an object")
    if consequence.get("format") not in SUPPORTED_CONSEQUENCE_FORMATS:
        raise TenetGramError("unsupported consequence format")
    if consequence.get("version") != 1:
        raise TenetGramError("unsupported consequence version")
    if consequence.get("authority") != "observation-only":
        raise TenetGramError("consequence must remain observation-only")
    if consequence.get("humanWorthJudgment") is not None:
        raise TenetGramError("human-worth judgment cannot seed possibility")
    if consequence.get("score") is not None:
        raise TenetGramError("score cannot seed possibility")
    if consequence.get("sharedWorldChanged") is not False:
        raise TenetGramError("shared-world mutation claim is outside this seam")
    if not _consequence_participants(consequence):
        raise TenetGramError("consequence exposes no attributable participant")


def _make_seed(
    *,
    consequence_ref: str,
    issuer_actor: str,
    field_link: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "format": SEED_FORMAT,
        "version": SEED_VERSION,
        "kind": "consequence-follow-on",
        "source_consequence_ref": consequence_ref,
        "issuer_actor": issuer_actor,
        "target_field": field_link["field_id"],
        "relation": field_link["relation"],
        "field_link_id": field_link["field_link_id"],
        "question": "What becomes possible next from this consequence?",
        "status": "dormant",
        "authority": "possibility-only",
        "requires_local_admission": True,
        "notification_requested": False,
        "request_requested": False,
        "execution_requested": False,
        "specific_claims": [],
        "laws": [
            "SEED != NOTIFICATION",
            "SEED != REQUEST",
            "SEED != RECOMMENDATION",
            "SEED != OBLIGATION",
            "RELATION != BROADCAST",
        ],
    }
    _scan_forbidden(body)
    body["seed_id"] = _address("tenetgram-seed", body)
    return body


def emit_tenetgram(
    consequence: dict[str, Any],
    *,
    issuer_actor: str,
    field_links: list[dict[str, Any]],
) -> dict[str, Any]:
    """Emit one TenetGram from an attributable consequence.

    Every valid result has at least one dormant seed addressed through an
    explicit field link owned by the issuing participant.
    """
    _validate_consequence(consequence)
    issuer_actor = _nonempty(issuer_actor, "issuer_actor")
    participants = _consequence_participants(consequence)
    if issuer_actor not in participants:
        raise TenetGramError("issuer is not attributable in the consequence")

    eligible: list[dict[str, Any]] = []
    for link in field_links:
        if not _verify_field_link(link):
            raise TenetGramError("invalid explicit field link")
        if link.get("actor") != issuer_actor:
            continue
        if "consequence-follow-on" not in (link.get("seed_kinds") or []):
            continue
        eligible.append(link)

    if not eligible:
        raise TenetGramError(
            "TenetGram requires at least one explicit connected field for the issuer"
        )

    eligible.sort(key=lambda item: (str(item["field_id"]), str(item["relation"])))
    consequence_ref = _address("tenetgram-consequence", consequence)
    seeds = [
        _make_seed(
            consequence_ref=consequence_ref,
            issuer_actor=issuer_actor,
            field_link=link,
        )
        for link in eligible
    ]

    back = {
        "consequence_ref": consequence_ref,
        "source_format": consequence["format"],
        "source_phase": consequence.get("phase"),
        "warm_thread_id": consequence.get("warmThreadId"),
        "completed_steps": list(consequence.get("completedSteps") or []),
        "unresolved_relation": consequence.get("unresolvedRelation"),
    }

    body = {
        "format": TENETGRAM_FORMAT,
        "version": TENETGRAM_VERSION,
        "issuer_actor": issuer_actor,
        "back": back,
        "front": {
            "seed_count": len(seeds),
            "seeds": seeds,
        },
        "authority": "carriage-only",
        "transport": "portable",
        "automatic_delivery": False,
        "automatic_notification": False,
        "automatic_request": False,
        "automatic_execution": False,
        "laws": [
            "CONSEQUENCE -> POSSIBILITY",
            "POSSIBILITY != REQUEST",
            "POSSIBILITY != RECOMMENDATION",
            "POSSIBILITY != OBLIGATION",
            "SEED != NOTIFICATION",
            "RELATION != BROADCAST",
            "TRANSPORT != ADMISSION",
        ],
    }
    _scan_forbidden(body)
    body["tenetgram_id"] = _address("tenetgram", body)
    return body


def receive_seed(
    tenetgram: dict[str, Any],
    *,
    field_id: str,
    seed_id: str,
) -> dict[str, Any]:
    """Project one seed into a target field without admitting or acting on it."""
    if tenetgram.get("format") != TENETGRAM_FORMAT:
        raise TenetGramError("unsupported TenetGram")
    field_id = _nonempty(field_id, "field_id")
    seed_id = _nonempty(seed_id, "seed_id")
    seed = next(
        (
            item
            for item in ((tenetgram.get("front") or {}).get("seeds") or [])
            if item.get("seed_id") == seed_id
        ),
        None,
    )
    if seed is None:
        raise TenetGramError("seed not found")
    if seed.get("target_field") != field_id:
        raise TenetGramError("seed addressed to another field")

    return {
        "format": "ghot.possibility-seed-projection",
        "version": 1,
        "seed_id": seed_id,
        "field_id": field_id,
        "question": seed["question"],
        "status": "visible-dormant",
        "admitted": False,
        "requested": False,
        "notified": False,
        "executed": False,
        "authority": "projection-only",
    }


def specimen_consequence() -> dict[str, Any]:
    """Frozen consequence shaped like Full Measure Warm Thread residue."""
    return {
        "format": "full-measure.warm-thread-residue",
        "version": 1,
        "warmThreadId": "warm-thread:dead-tree-001",
        "phase": "held-residual",
        "completedSteps": ["release-tree", "cut-tree"],
        "unresolvedRelation": "haul-firewood",
        "remainingNeed": {
            "kind": "home-heat",
            "actor": "david",
            "status": "open",
            "urgency": "tonight",
            "exactAddress": "withheld-from-shared-state",
        },
        "resources": {
            "tree": {"state": "transformed-to-cut-firewood"},
            "cutter": {"minutesAvailable": 0},
            "truck": {"loadsAvailable": 1, "radiusMiles": 8},
            "firewood": {"state": "cut-at-source"},
        },
        "residue": [
            {
                "sequence": 0,
                "stepId": "release-tree",
                "actor": "alice",
                "outcome": "SUCCEEDED",
                "remainingNeed": "open",
                "recompositionGap": "firewood-feedstock",
                "note": None,
                "humanWorthJudgment": None,
                "authority": "observation-only",
            },
            {
                "sequence": 1,
                "stepId": "cut-tree",
                "actor": "bob",
                "outcome": "SUCCEEDED",
                "remainingNeed": "open",
                "recompositionGap": "cut-wood",
                "note": None,
                "humanWorthJudgment": None,
                "authority": "observation-only",
            },
            {
                "sequence": 2,
                "stepId": "haul-load",
                "actor": "cara",
                "outcome": "REFUSED",
                "remainingNeed": "open",
                "recompositionGap": "haul-firewood",
                "note": "truck unavailable after all",
                "humanWorthJudgment": None,
                "authority": "observation-only",
            },
        ],
        "authority": "observation-only",
        "humanWorthJudgment": None,
        "score": None,
        "sharedWorldChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["specimen", "emit"])
    parser.add_argument("--issuer", default="alice")
    parser.add_argument("--field", default="neighborhood-a")
    parser.add_argument("--relation", default="local-neighbor")
    args = parser.parse_args()

    consequence = specimen_consequence() if args.command == "specimen" else json.load(sys.stdin)
    link = make_field_link(
        actor=args.issuer,
        field_id=args.field,
        relation=args.relation,
    )
    gram = emit_tenetgram(
        consequence,
        issuer_actor=args.issuer,
        field_links=[link],
    )
    print(json.dumps(gram, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
