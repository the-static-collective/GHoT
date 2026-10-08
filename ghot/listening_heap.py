#!/usr/bin/env python3
"""LISTENING-HEAP-001: attention proposals over GHoT's owner-selected Instrument Rack.

The planner never dispatches. A separately supplied, exact local selection may
dispatch ONE receive-only card using INSTRUMENT-RACK-001's existing signed
reLATTE-shaped crossing and replay-safe execution path.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from instrument_rack import build_instrument_rack, dispatch_instrument_card

SURVEY = "ghot.listening-survey/v0"
PROPOSAL = "ghot.listening-attention-proposal/v0"
OBSERVATION = "ghot.listening-observation/v0"
CAPABILITY_PREFIX = "radio.rx.simulated."
BANDS = {
    "weather": "radio.rx.simulated.weather",
    "ism": "radio.rx.simulated.ism",
}
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _obj(value: Any, keys: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(code)
    return value


def validate_survey(value: Any) -> dict[str, Any]:
    s = _obj(value, {"schema", "source", "windows"}, "INVALID_SURVEY")
    if s["schema"] != SURVEY or s["source"] != "SIMULATION":
        raise ValueError("NOT_AN_AUTHENTIC_RF_SURVEY")
    windows = s["windows"]
    if not isinstance(windows, list) or len(windows) != len(BANDS):
        raise ValueError("INVALID_SURVEY_WINDOWS")
    bands = set()
    for window in windows:
        w = _obj(window, {"band", "activity", "novelty", "uncertainty"}, "INVALID_WINDOW")
        if w["band"] not in BANDS or w["band"] in bands:
            raise ValueError("INVALID_OR_DUPLICATE_BAND")
        bands.add(w["band"])
        for key in ("activity", "novelty", "uncertainty"):
            if type(w[key]) is not int or not 0 <= w[key] <= 5:
                raise ValueError("INVALID_SURVEY_METRIC")
    return s


def _eligible(card: Any) -> bool:
    return (
        isinstance(card, dict)
        and card.get("schema") == "ghot.instrument-card/v0"
        and card.get("status") == "PROPOSAL_ONLY"
        and card.get("semantic_effect") == "none"
        and card.get("available") is True
        and card.get("capability") in BANDS.values()
        and card.get("limits", {}).get("transmit") is False
        and card.get("limits", {}).get("network") is False
        and card.get("limits", {}).get("simulation_only") is True
        and isinstance(card.get("card_id"), str)
    )


def plan_attention(survey: Any, rack: Any, *, budget: int = 3) -> dict[str, Any]:
    """Produce a PROPOSAL, never execute or open a radio."""
    s = validate_survey(survey)
    if type(budget) is not int or not 1 <= budget <= 10:
        raise ValueError("INVALID_BUDGET")
    if not isinstance(rack, dict) or rack.get("schema") != "ghot.instrument-rack/v0":
        raise ValueError("INVALID_RACK")
    cards = rack.get("cards")
    if not isinstance(cards, list):
        raise ValueError("INVALID_RACK_CARDS")

    choices = []
    for window in s["windows"]:
        for card in cards:
            if not _eligible(card) or card["capability"] != BANDS[window["band"]]:
                continue
            cost = card["limits"].get("attention_cost")
            if type(cost) is not int or cost <= 0 or cost > budget:
                continue
            # Predeclared heuristic. No oracle/ground-truth content enters planning.
            score = 5 * window["novelty"] + 3 * window["uncertainty"] + window["activity"] - cost
            choices.append({
                "band": window["band"],
                "card_id": card["card_id"],
                "capability": card["capability"],
                "cost": cost,
                "score": score,
            })
    if not choices:
        raise ValueError("NO_ELIGIBLE_RECEIVE_CAPABILITY")
    choices.sort(key=lambda c: (-c["score"], c["band"], c["card_id"]))
    selected = choices[0]
    body = {
        "schema": PROPOSAL,
        "survey_sha256": sha(s),
        "rack_id": rack.get("rack_id"),
        "selected": selected,
        "alternative_count": len(choices) - 1,
        "budget": budget,
        "status": "PROPOSAL_ONLY",
        "semantic_effect": "none",
        "transmission": "FORBIDDEN",
        "source_kind": "SIMULATION",
        "laws": [
            "ATTENTION != OBSERVATION",
            "PROPOSAL != EXECUTION",
            "SIMULATED SIGNAL != PHYSICAL RECEPTION",
            "RX PERMISSION != TX PERMISSION",
        ],
    }
    return {**body, "proposal_id": "listening-proposal-v0:" + sha(body)}


def _verify_proposal(p: Any) -> dict[str, Any]:
    if not isinstance(p, dict):
        raise ValueError("INVALID_ATTENTION_PROPOSAL")
    core = {k: v for k, v in p.items() if k != "proposal_id"}
    if (
        p.get("schema") != PROPOSAL
        or p.get("proposal_id") != "listening-proposal-v0:" + sha(core)
        or p.get("status") != "PROPOSAL_ONLY"
        or p.get("transmission") != "FORBIDDEN"
        or p.get("source_kind") != "SIMULATION"
    ):
        raise ValueError("INVALID_ATTENTION_PROPOSAL")
    return p


def explicit_listen(
    proposal: Any, survey: Any, rack: Any, *,
    selection: dict[str, Any],
    dispatch_source: str,
) -> dict[str, Any]:
    """Exactly one explicit owner-selected, RX-only simulation through GHoT."""
    p = _verify_proposal(proposal)
    if p["survey_sha256"] != sha(validate_survey(survey)):
        raise ValueError("STALE_SURVEY")
    if not isinstance(rack, dict) or rack.get("rack_id") != p["rack_id"]:
        raise ValueError("STALE_RACK")
    if not isinstance(dispatch_source, str) or not dispatch_source.strip():
        raise ValueError("OPERATOR_SOURCE_REQUIRED")
    _obj(selection, {"kind", "approved", "proposal_id", "card_id"}, "INVALID_SELECTION")
    if (
        selection["kind"] != "operator-explicit-listen/v0"
        or selection["approved"] is not True
        or selection["proposal_id"] != p["proposal_id"]
        or selection["card_id"] != p["selected"]["card_id"]
    ):
        raise ValueError("NOT_EXPLICITLY_SELECTED")
    selected = next(
        (card for card in rack["cards"] if card.get("card_id") == p["selected"]["card_id"]),
        None,
    )
    if not _eligible(selected) or selected["capability"] != p["selected"]["capability"]:
        raise ValueError("NOT_RECEIVE_ONLY")
    # The actual Rack repeats manifest/card freshness verification immediately
    # before dispatch; its signed crossing and receipt remain GHoT-owned.
    payload = {"action": "receive_simulation", "band": p["selected"]["band"]}
    result = dispatch_instrument_card(selected, payload, dispatch_source=dispatch_source)
    if result.get("status") != "EXECUTED" or not isinstance(result.get("packet"), dict):
        raise RuntimeError("NO_SUCCESSFUL_CAPTURE_PACKET")
    packet = result["packet"]
    envelope = packet.get("donor_result") or {}
    donor = envelope.get("result") if isinstance(envelope, dict) else None
    if (
        not isinstance(donor, dict)
        or donor.get("schema") != "simulation.rf-window/v0"
        or donor.get("source") != "SIMULATION"
        or donor.get("mode") != "RECEIVE_ONLY"
        or donor.get("band") != p["selected"]["band"]
        or donor.get("status") != "ok"
    ):
        raise RuntimeError("INVALID_SIMULATED_OBSERVATION")
    bins = donor.get("bins")
    if not isinstance(bins, list) or len(bins) != 8 or any(
        type(v) is not int or not 0 <= v <= 20 for v in bins
    ):
        raise RuntimeError("INVALID_SIMULATED_BINS")
    body = {
        "schema": OBSERVATION,
        "proposal_id": p["proposal_id"],
        "selection": selection,
        "dispatch_id": result["dispatch_id"],
        "crossing_id": packet["dispatch_crossing_id"],
        "portable_packet_id": packet["packet_id"],
        "band": donor["band"],
        "bins": bins,
        "source": "SIMULATION",
        "status": "SIMULATED_OBSERVATION_ONLY",
        "authority": "none",
    }
    return {**body, "observation_id": "listening-observation-v0:" + sha(body)}


def autodisco_prepare_request(observation: Any) -> dict[str, Any]:
    """Produce an exact native LOOK-TWICE SVG prepare request, NOT AI responses."""
    if not isinstance(observation, dict):
        raise ValueError("INVALID_OBSERVATION")
    core = {k: v for k, v in observation.items() if k != "observation_id"}
    if (
        observation.get("schema") != OBSERVATION
        or observation.get("observation_id") != "listening-observation-v0:" + sha(core)
        or observation.get("source") != "SIMULATION"
        or observation.get("status") != "SIMULATED_OBSERVATION_ONLY"
    ):
        raise ValueError("INVALID_OBSERVATION")
    bins = observation.get("bins")
    if not isinstance(bins, list) or len(bins) != 8 or any(
        type(v) is not int or v < 0 or v > 20 for v in bins
    ):
        raise ValueError("INVALID_SPECTRUM")
    bars = "".join(
        f'<rect x="{20 + i*34}" y="{170 - v*6}" width="18" height="{v*6}" fill="#16658a"/>'
        for i, v in enumerate(bins)
    )
    # Labels identify this as a *simulation*. No actual RF recording is claimed.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 205">'
        '<rect width="320" height="205" fill="#f3f6f8"/>'
        '<text x="15" y="23" font-size="12">SIMULATED RF BINS / NOT A CAPTURE</text>'
        f'{bars}'
        '<path d="M12 170H308" stroke="#222"/></svg>'
    )
    digest = hashlib.sha256(svg.encode("utf-8")).hexdigest()
    return {
        "schema": "autodisco.look-twice-prepare-request/v0",
        "artifact": {"media_type": "image/svg+xml", "sha256": digest, "text": svg},
    }


def prepare_via_native_autodisco(request: dict[str, Any], script: str) -> dict[str, Any]:
    """Optional native Autodisco v20 invocation. No model call or dialogue."""
    path = Path(script).resolve(strict=True)
    completed = subprocess.run(
        ["node", str(path)], input=json.dumps({"action": "prepare", "request": request}),
        text=True, capture_output=True, timeout=15, check=False,
    )
    if completed.returncode:
        raise RuntimeError("AUTODISCO_PREPARE_REFUSED: " + completed.stderr[:500])
    pair = json.loads(completed.stdout)
    if (
        pair.get("schema") != "autodisco.look-twice-pair/v0"
        or pair.get("source", {}).get("sha256") != request["artifact"]["sha256"]
        or len(pair.get("packets", [])) != 2
    ):
        raise RuntimeError("AUTODISCO_PREPARE_BINDING_FAILED")
    return pair


def demo_survey() -> dict[str, Any]:
    return {
        "schema": SURVEY,
        "source": "SIMULATION",
        "windows": [
            {"band": "weather", "activity": 2, "novelty": 1, "uncertainty": 1},
            {"band": "ism", "activity": 4, "novelty": 4, "uncertainty": 4},
        ],
    }
