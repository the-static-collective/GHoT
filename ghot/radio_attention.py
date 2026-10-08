#!/usr/bin/env python3
"""RADIO-ATTENTION-003: two-role, receive-only, owner-gated GHoT attention.

One *logical* device index surveys <=3 operator-chosen center frequencies;
a different device index inspects one proposed frequency. GHoT's native signed
instrument dispatch produces exact IQ evidence; a pinned Autodisco v20 producer
may prepare two isolated first-listen packets for a comparative visualization.
No RF origin, two physical devices, scientific information gain, real LLM
response or transmission is asserted by this module.
"""
from __future__ import annotations

import hashlib
import html
import json
from typing import Any

from instrument_rack import build_instrument_rack
from radio_ear import REQUEST_SCHEMA, validate_request
from radio_ear_bridge import (
    execute_selected_capture, make_proposal, native_autodisco_request,
)
from listening_heap import prepare_via_native_autodisco

SPEC = "ghot.radio-attention-field-spec/v0"
PLAN = "ghot.radio-attention-plan/v0"
SURVEY = "ghot.radio-attention-survey/v0"
FOCUS = "ghot.radio-attention-focus/v0"
COMPARISON = "ghot.radio-attention-comparison/v0"
NEXT = "ghot.radio-attention-next/v0"
APPROVAL = "operator-radio-attention-approval/v0"


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _seal(body: dict, suffix: str, prefix: str) -> dict:
    return {**body, suffix: prefix + _hash(body)}


def _verify_sealed(value: Any, schema: str, field: str, prefix: str) -> dict:
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise ValueError("RADIO_ATTENTION_INVALID_" + schema)
    if value.get(field) != prefix + _hash({k: v for k, v in value.items() if k != field}):
        raise ValueError("RADIO_ATTENTION_TAMPERED_" + field)
    return value


def validate_spec(spec: Any) -> dict:
    keys = {
        "schema", "surveyor_index", "listener_index", "frequencies_hz",
        "sample_rate_hz", "survey_complex_samples", "focus_complex_samples", "rx_scope",
    }
    if not isinstance(spec, dict) or set(spec) != keys or spec["schema"] != SPEC:
        raise ValueError("RADIO_ATTENTION_INVALID_SPEC")
    freqs = spec["frequencies_hz"]
    if (
        not isinstance(freqs, list) or not 2 <= len(freqs) <= 3
        or any(type(f) is not int for f in freqs)
        or len(set(freqs)) != len(freqs)
    ):
        raise ValueError("RADIO_ATTENTION_BAD_FREQUENCIES")
    if (
        type(spec["surveyor_index"]) is not int
        or type(spec["listener_index"]) is not int
        or spec["surveyor_index"] == spec["listener_index"]
    ):
        raise ValueError("RADIO_ATTENTION_DISTINCT_RECEIVER_INDICES_REQUIRED")
    for index in (spec["surveyor_index"], spec["listener_index"]):
        for frequency in freqs:
            _request(spec, index, frequency, "survey")
    _request(spec, spec["listener_index"], freqs[0], "focus")
    return spec


def _request(spec: dict, index: int, frequency: int, role: str) -> dict:
    return validate_request({
        "schema": REQUEST_SCHEMA,
        "action": "capture_rx_iq",
        "device_index": index,
        "frequency_hz": frequency,
        "sample_rate_hz": spec["sample_rate_hz"],
        "complex_samples": spec["survey_complex_samples"] if role == "survey" else spec["focus_complex_samples"],
        "rx_scope": spec["rx_scope"],
    })


def _rack_single(rack: Any) -> dict:
    if not isinstance(rack, dict) or rack.get("schema") != "ghot.instrument-rack/v0":
        raise ValueError("RADIO_ATTENTION_INVALID_RACK")
    card = [c for c in rack.get("cards", []) if c.get("capability") == "radio.rx.rtlsdr.capture"]
    if len(card) != 1 or card[0].get("available") is not True:
        raise ValueError("RADIO_ATTENTION_RX_CARD_REQUIRED")
    limits = card[0].get("limits") or {}
    if (
        limits.get("transmit") is not False or limits.get("receive_only") is not True
        or limits.get("network") is not False or limits.get("simulation_only") is not False
    ):
        raise ValueError("RADIO_ATTENTION_UNSAFE_CARD")
    return card[0]


def plan_survey(spec: Any, rack: Any) -> dict:
    validated = validate_spec(spec)
    card = _rack_single(rack)
    body = {
        "schema": PLAN,
        "purpose": "survey",
        "spec_sha256": _hash(validated),
        "rack_id": rack["rack_id"],
        "card_id": card["card_id"],
        "frequency_hz": None,
        "capture_count": len(validated["frequencies_hz"]),
        "status": "PROPOSAL_ONLY",
        "transmission": "FORBIDDEN",
    }
    return _seal(body, "plan_id", "radio-attention-plan-v0:")


def _approval(approval: Any, plan: dict, purpose: str, operator: str) -> None:
    if (
        not isinstance(approval, dict) or set(approval) != {"schema", "approved", "plan_id", "purpose"}
        or approval["schema"] != APPROVAL or approval["approved"] is not True
        or approval["plan_id"] != plan["plan_id"] or approval["purpose"] != purpose
        or not isinstance(operator, str) or not operator.strip()
    ):
        raise ValueError("RADIO_ATTENTION_EXPLICIT_OWNER_APPROVAL_REQUIRED")


def _capture(request: dict, rack: dict, *, dispatch_source: str) -> dict:
    proposal = make_proposal(rack, request)
    selection = {
        "kind": "operator-explicit-radio-rx/v0",
        "approved": True,
        "proposal_id": proposal["proposal_id"],
        "card_id": proposal["card_id"],
    }
    return execute_selected_capture(
        proposal, request, rack, selection=selection, dispatch_source=dispatch_source,
    )


def _validate_result(result: Any, spec: dict, *, index: int, freq: int, role: str) -> dict:
    # The existing native bridge verifies the portable signed packet, its exact
    # byte digest, the capture request and the bound summary.
    native_autodisco_request(result)
    summary = result["summary"]
    expected = _request(spec, index, freq, role)
    if (
        summary["frequency_hz"] != expected["frequency_hz"]
        or summary["sample_rate_hz"] != expected["sample_rate_hz"]
        or summary["complex_samples"] != expected["complex_samples"]
        or result["portable_packet"]["donor_result"]["result"]["request"] != expected
        or summary["physical_signal_verified"] is not False
    ):
        raise ValueError("RADIO_ATTENTION_CAPTURE_ROLE_MISMATCH")
    return summary


def run_survey(spec: Any, rack: Any, plan: Any, *, approval: Any, operator: str) -> dict:
    """One bounded approved sweep; each step has its own signed GHoT dispatch."""
    expected = plan_survey(spec, rack)
    if plan != expected:
        raise ValueError("RADIO_ATTENTION_STALE_SURVEY_PLAN")
    _approval(approval, expected, "survey", operator)
    observations = []
    for frequency in spec["frequencies_hz"]:
        request = _request(spec, spec["surveyor_index"], frequency, "survey")
        result = _capture(
            request, rack, dispatch_source=f"{operator}:attention-survey:{expected['plan_id']}:{frequency}",
        )
        summary = _validate_result(result, spec, index=spec["surveyor_index"], freq=frequency, role="survey")
        observations.append({"frequency_hz": frequency, "capture": result, "summary_id": summary["summary_id"]})
    body = {
        "schema": SURVEY,
        "spec": spec,
        "plan_id": expected["plan_id"],
        "observations": observations,
        "state": "OBSERVED_BUT_UNCALIBRATED",
        "capture_gap_between_frequencies": "UNOBSERVED",
        "hardware_identity_verified": False,
    }
    return _seal(body, "survey_id", "radio-attention-survey-v0:")


def verify_survey(value: Any) -> dict:
    survey = _verify_sealed(value, SURVEY, "survey_id", "radio-attention-survey-v0:")
    spec = validate_spec(survey["spec"])
    observations = survey.get("observations")
    if (
        survey.get("state") != "OBSERVED_BUT_UNCALIBRATED"
        or survey.get("capture_gap_between_frequencies") != "UNOBSERVED"
        or survey.get("hardware_identity_verified") is not False
        or not isinstance(observations, list)
        or len(observations) != len(spec["frequencies_hz"])
    ):
        raise ValueError("RADIO_ATTENTION_INVALID_SURVEY_EVIDENCE")
    for freq, observation in zip(spec["frequencies_hz"], observations):
        if not isinstance(observation, dict) or observation.get("frequency_hz") != freq:
            raise ValueError("RADIO_ATTENTION_UNORDERED_SURVEY_EVIDENCE")
        summary = _validate_result(
            observation["capture"], spec, index=spec["surveyor_index"], freq=freq, role="survey",
        )
        if observation.get("summary_id") != summary["summary_id"]:
            raise ValueError("RADIO_ATTENTION_INVALID_OBSERVATION_ID")
    if survey.get("plan_id") is None:
        raise ValueError("RADIO_ATTENTION_MISSING_SURVEY_PLAN")
    return survey


def rank_survey(survey: Any) -> list[dict]:
    """Uncalibrated ranking, not evidence that a frequency carries a station."""
    s = verify_survey(survey)
    scored = []
    for o in s["observations"]:
        bins = o["capture"]["summary"]["amplitude_windows"]
        scored.append({
            "frequency_hz": o["frequency_hz"],
            "amplitude_sum": sum(bins),
            "source_summary_id": o["summary_id"],
        })
    return sorted(scored, key=lambda x: (-x["amplitude_sum"], x["frequency_hz"]))


def plan_focus(survey: Any, rack: Any) -> dict:
    s = verify_survey(survey)
    card = _rack_single(rack)
    selected = rank_survey(s)[0]
    body = {
        "schema": PLAN,
        "purpose": "focus",
        "spec_sha256": _hash(s["spec"]),
        "rack_id": rack["rack_id"],
        "card_id": card["card_id"],
        "frequency_hz": selected["frequency_hz"],
        "survey_id": s["survey_id"],
        "selected_evidence_id": selected["source_summary_id"],
        "scoring": "sum-of-uncalibrated-time-window-amplitude",
        "capture_count": 1,
        "status": "PROPOSAL_ONLY",
        "transmission": "FORBIDDEN",
    }
    return _seal(body, "plan_id", "radio-attention-plan-v0:")


def run_focus(survey: Any, rack: Any, plan: Any, *, approval: Any, operator: str) -> dict:
    s = verify_survey(survey)
    expected = plan_focus(s, rack)
    if plan != expected:
        raise ValueError("RADIO_ATTENTION_STALE_FOCUS_PLAN")
    _approval(approval, expected, "focus", operator)
    freq = expected["frequency_hz"]
    spec = s["spec"]
    req = _request(spec, spec["listener_index"], freq, "focus")
    result = _capture(
        req, rack, dispatch_source=f"{operator}:attention-focus:{expected['plan_id']}:{freq}",
    )
    summary = _validate_result(result, spec, index=spec["listener_index"], freq=freq, role="focus")
    body = {
        "schema": FOCUS,
        "survey_id": s["survey_id"],
        "plan_id": expected["plan_id"],
        "frequency_hz": freq,
        "capture": result,
        "summary_id": summary["summary_id"],
        "physical_independence_verified": False,
        "status": "SECOND_DEVICE_INDEX_CAPTURE_UNCALIBRATED",
    }
    return _seal(body, "focus_id", "radio-attention-focus-v0:")


def verify_focus(survey: Any, focus: Any) -> dict:
    s = verify_survey(survey)
    f = _verify_sealed(focus, FOCUS, "focus_id", "radio-attention-focus-v0:")
    if (
        f.get("survey_id") != s["survey_id"]
        or f.get("physical_independence_verified") is not False
        or f.get("status") != "SECOND_DEVICE_INDEX_CAPTURE_UNCALIBRATED"
        or f.get("frequency_hz") not in s["spec"]["frequencies_hz"]
        or f.get("plan_id") is None
    ):
        raise ValueError("RADIO_ATTENTION_FOCUS_BINDING_FAILED")
    summary = _validate_result(
        f["capture"], s["spec"],
        index=s["spec"]["listener_index"], freq=f["frequency_hz"], role="focus",
    )
    if summary["summary_id"] != f.get("summary_id"):
        raise ValueError("RADIO_ATTENTION_FOCUS_ID_MISMATCH")
    return f


def compare_and_propose(survey: Any, focus: Any) -> dict:
    s = verify_survey(survey)
    f = verify_focus(s, focus)
    selected = next(x for x in s["observations"] if x["frequency_hz"] == f["frequency_hz"])
    a = selected["capture"]["summary"]["amplitude_windows"]
    b = f["capture"]["summary"]["amplitude_windows"]
    delta = abs(sum(a) - sum(b))
    disagreement = delta >= 16  # Fixed threshold, NOT statistically calibrated.
    body = {
        "schema": COMPARISON,
        "survey_id": s["survey_id"],
        "focus_id": f["focus_id"],
        "survey_summary_id": selected["summary_id"],
        "focus_summary_id": f["summary_id"],
        "frequency_hz": f["frequency_hz"],
        "survey_amplitude_sum": sum(a),
        "focus_amplitude_sum": sum(b),
        "delta": delta,
        "disagreement_flag": disagreement,
        "status": "DETERMINISTIC_HEURISTIC_NOT_AUTODISCO_MODEL_OUTPUT",
        "source": "HOST_REPORTED_UNCALIBRATED",
        "authority": "none",
    }
    return _seal(body, "comparison_id", "radio-attention-comparison-v0:")


def next_attention(survey: Any, focus: Any) -> dict:
    c = compare_and_propose(survey, focus)
    rank = rank_survey(survey)
    # Disagreement leads to repeat; otherwise probe the next ranked candidate.
    next_frequency = c["frequency_hz"] if c["disagreement_flag"] else next(
        item["frequency_hz"] for item in rank if item["frequency_hz"] != c["frequency_hz"]
    )
    body = {
        "schema": NEXT,
        "comparison_id": c["comparison_id"],
        "proposed_frequency_hz": next_frequency,
        "reason": "REPEAT_UNCALIBRATED_DISAGREEMENT" if c["disagreement_flag"] else "EXPLORE_NEXT_CANDIDATE",
        "status": "PROPOSAL_ONLY",
        "hardware_execution": "NONE",
        "transmission": "FORBIDDEN",
    }
    return _seal(body, "next_id", "radio-attention-next-v0:")


def autodisco_comparison_request(survey: Any, focus: Any) -> dict:
    """Exact native LOOK-TWICE *prepare* input over two verified GHoT receipts."""
    s = verify_survey(survey)
    f = verify_focus(s, focus)
    c = compare_and_propose(s, f)
    first = next(x for x in s["observations"] if x["frequency_hz"] == f["frequency_hz"])
    a = first["capture"]["summary"]["amplitude_windows"]
    b = f["capture"]["summary"]["amplitude_windows"]
    lines = []
    for idx, (label, series) in enumerate([("SURVEY INDEX", a), ("FOCUS INDEX", b)]):
        offset = idx * 110
        lines.append(f'<text x="12" y="{25+offset}" font-size="12">{label}</text>')
        lines.extend(
            f'<rect x="{20+j*35}" y="{85+offset-v*3}" width="19" height="{v*3}" fill="{["#246a90", "#ad6239"][idx]}"/>'
            for j, v in enumerate(series)
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 330 240">'
        '<rect width="330" height="240" fill="#f2f4f5"/>'
        + "".join(lines)
        + '<text x="9" y="224" font-size="9">TWO HOST-REPORTED UNCALIBRATED CAPTURES / NOT RF ORIGIN PROOF</text>'
        + '</svg>'
    )
    digest = hashlib.sha256(svg.encode("utf-8")).hexdigest()
    return {
        "schema": "autodisco.look-twice-prepare-request/v0",
        "artifact": {"media_type": "image/svg+xml", "sha256": digest, "text": svg},
    }


def native_autodisco_comparison(survey: Any, focus: Any, script: str) -> dict:
    """Run native Autodisco first-packet preparation; not actual model encounters."""
    return prepare_via_native_autodisco(autodisco_comparison_request(survey, focus), script)


def explicit_approval(plan: dict, purpose: str) -> dict:
    """Formatting convenience for a human *to inspect*, NOT itself an approval."""
    raise RuntimeError("APPROVAL_MUST_COME_FROM_EXTERNAL_OWNER_NOT_PLANNER")
