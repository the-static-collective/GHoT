#!/usr/bin/env python3
"""RADIO-EAR-002 bridge: exact GHoT RX selection to native Autodisco preparation."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from instrument_rack import _validate_packet, dispatch_instrument_card
from listening_heap import prepare_via_native_autodisco
from radio_ear import CAPABILITY, REQUEST_SCHEMA, validate_request, verify_capture

PROPOSAL_SCHEMA = "ghot.radio-ear-capture-proposal/v0"
SUMMARY_SCHEMA = "ghot.radio-ear-observation-summary/v0"


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def eligible_card(card: Any) -> bool:
    if not isinstance(card, dict):
        return False
    limits = card.get("limits")
    return (
        card.get("schema") == "ghot.instrument-card/v0"
        and card.get("capability") == CAPABILITY
        and card.get("available") is True
        and card.get("status") == "PROPOSAL_ONLY"
        and card.get("semantic_effect") == "none"
        and isinstance(card.get("card_id"), str)
        and isinstance(limits, dict)
        and limits.get("transmit") is False
        and limits.get("network") is False
        and limits.get("receive_only") is True
        and limits.get("simulation_only") is False
        and limits.get("max_complex_samples") == 65536
    )


def make_proposal(rack: Any, capture_request: Any) -> dict[str, Any]:
    request = validate_request(capture_request)
    if not isinstance(rack, dict) or rack.get("schema") != "ghot.instrument-rack/v0":
        raise ValueError("RADIO_EAR_INVALID_RACK")
    cards = rack.get("cards")
    if not isinstance(cards, list):
        raise ValueError("RADIO_EAR_INVALID_CARDS")
    eligible = [c for c in cards if eligible_card(c)]
    if len(eligible) != 1:
        raise ValueError("RADIO_EAR_EXPECT_EXACTLY_ONE_RECEIVER_CARD")
    body = {
        "schema": PROPOSAL_SCHEMA,
        "rack_id": rack["rack_id"],
        "card_id": eligible[0]["card_id"],
        "capture_request_sha256": _hash(request),
        "status": "PROPOSAL_ONLY",
        "source_scope": "host-reported-receive-only",
        "semantic_effect": "none",
        "transmission": "FORBIDDEN",
    }
    return {**body, "proposal_id": "radio-ear-proposal-v0:" + _hash(body)}


def execute_selected_capture(
    proposal: Any, capture_request: Any, rack: Any, *,
    selection: Any,
    dispatch_source: str,
) -> dict[str, Any]:
    expected = make_proposal(rack, capture_request)
    if not isinstance(proposal, dict) or proposal != expected:
        raise ValueError("RADIO_EAR_STALE_PROPOSAL")
    if not isinstance(selection, dict) or set(selection) != {
        "kind", "approved", "proposal_id", "card_id",
    }:
        raise ValueError("RADIO_EAR_EXPLICIT_SELECTION_REQUIRED")
    if (
        selection["kind"] != "operator-explicit-radio-rx/v0"
        or selection["approved"] is not True
        or selection["proposal_id"] != expected["proposal_id"]
        or selection["card_id"] != expected["card_id"]
    ):
        raise ValueError("RADIO_EAR_NOT_SELECTED")
    if not isinstance(dispatch_source, str) or not dispatch_source.strip():
        raise ValueError("RADIO_EAR_OPERATOR_REQUIRED")
    card = next(c for c in rack["cards"] if c.get("card_id") == expected["card_id"])
    # Native GHoT Instrument Rack revalidates the exact card *again* at dispatch.
    result = dispatch_instrument_card(
        card, capture_request, dispatch_source=dispatch_source
    )
    if result.get("status") != "EXECUTED" or not isinstance(result.get("packet"), dict):
        raise RuntimeError("RADIO_EAR_CAPTURE_NOT_SUCCESSFUL")
    packet = _validate_packet(result["packet"])
    if packet.get("capability") != CAPABILITY or packet.get("source_card_id") != card["card_id"]:
        raise RuntimeError("RADIO_EAR_WRONG_NATIVE_CAPABILITY")
    enveloped = packet.get("donor_result")
    if not isinstance(enveloped, dict) or enveloped.get("capability") != CAPABILITY:
        raise RuntimeError("RADIO_EAR_WRONG_DONOR")
    capture = verify_capture(enveloped.get("result"))
    if capture.get("request") != validate_request(capture_request):
        raise RuntimeError("RADIO_EAR_RESULT_SCOPE_MISMATCH")

    body = {
        "schema": SUMMARY_SCHEMA,
        "proposal_id": proposal["proposal_id"],
        "selection": selection,
        "dispatch_id": result["dispatch_id"],
        "crossing_id": packet["dispatch_crossing_id"],
        "portable_packet_id": packet["packet_id"],
        "source": "HOST_REPORTED_RTLSDR_UNVERIFIED_PHYSICAL_ORIGIN",
        "mode": "RECEIVE_ONLY",
        "frequency_hz": capture_request["frequency_hz"],
        "sample_rate_hz": capture_request["sample_rate_hz"],
        "complex_samples": capture_request["complex_samples"],
        "iq_sha256": capture["iq_sha256"],
        "amplitude_windows": capture["amplitude_windows"],
        "gap_status": capture["gap_status"],
        "clock_uncertainty": capture["clock_uncertainty"],
        "backend_sha256": capture["backend"]["sha256"],
        "physical_signal_verified": False,
        "transmission": "FORBIDDEN",
    }
    return {
        "summary": {**body, "summary_id": "radio-ear-summary-v0:" + _hash(body)},
        "portable_packet": packet,
    }


def native_autodisco_request(capture_and_summary: Any) -> dict[str, Any]:
    if not isinstance(capture_and_summary, dict) or set(capture_and_summary) != {
        "summary", "portable_packet",
    }:
        raise ValueError("RADIO_EAR_SUMMARY_PACKET_REQUIRED")
    summary = capture_and_summary["summary"]
    packet = _validate_packet(capture_and_summary["portable_packet"])
    if (
        not isinstance(summary, dict)
        or summary.get("schema") != SUMMARY_SCHEMA
        or summary.get("portable_packet_id") != packet["packet_id"]
        or summary.get("source") != "HOST_REPORTED_RTLSDR_UNVERIFIED_PHYSICAL_ORIGIN"
        or summary.get("physical_signal_verified") is not False
        or summary.get("transmission") != "FORBIDDEN"
        or summary.get("mode") != "RECEIVE_ONLY"
    ):
        raise ValueError("RADIO_EAR_UNVERIFIED_SUMMARY")
    core = {k: v for k, v in summary.items() if k != "summary_id"}
    if summary.get("summary_id") != "radio-ear-summary-v0:" + _hash(core):
        raise ValueError("RADIO_EAR_SUMMARY_ID_MISMATCH")
    donor = packet["donor_result"]["result"]
    capture = verify_capture(donor)
    if (
        capture["iq_sha256"] != summary.get("iq_sha256")
        or capture["amplitude_windows"] != summary.get("amplitude_windows")
        or capture["request"]["frequency_hz"] != summary.get("frequency_hz")
        or capture["request"]["sample_rate_hz"] != summary.get("sample_rate_hz")
        or capture["request"]["complex_samples"] != summary.get("complex_samples")
        or capture["backend"]["sha256"] != summary.get("backend_sha256")
    ):
        raise ValueError("RADIO_EAR_SUMMARY_NOT_GROUNDED_IN_IQ")
    bins = capture["amplitude_windows"]
    bars = "".join(
        f'<rect x="{20 + i*34}" y="{170 - v*6}" width="18" height="{v*6}" fill="#16658a"/>'
        for i, v in enumerate(bins)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 205">'
        '<rect width="320" height="205" fill="#f3f6f8"/>'
        '<text x="10" y="20" font-size="10">RTL-SDR HOST REPORT / NOT RF ORIGIN PROOF</text>'
        '<text x="10" y="34" font-size="9">UNCALIBRATED TIME AMPLITUDE / NOT SPECTRUM</text>'
        f'{bars}'
        '<path d="M12 170H308" stroke="#222"/></svg>'
    )
    return {
        "schema": "autodisco.look-twice-prepare-request/v0",
        "artifact": {
            "media_type": "image/svg+xml",
            "sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
            "text": svg,
        },
    }


def prepare_autodisco(capture_and_summary: Any, script: str) -> dict[str, Any]:
    return prepare_via_native_autodisco(native_autodisco_request(capture_and_summary), script)
