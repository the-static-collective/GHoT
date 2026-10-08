#!/usr/bin/env python3
"""Operator-facing plan/execute split for RADIO-EAR-002 (no auto TX or auto RX)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from instrument_rack import build_instrument_rack
from radio_ear_bridge import (
    execute_selected_capture, make_proposal, native_autodisco_request,
    prepare_autodisco,
)
from radio_ear import validate_request


def read_json(path: str) -> Any:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def cli(argv: list[str]) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="GHoT RTL-SDR receive-only plan and explicitly approved capture"
    )
    parser.add_argument("operation", choices=("plan", "capture"))
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--plan-file")
    parser.add_argument("--confirm-rx-only", action="store_true")
    parser.add_argument("--operator-label")
    parser.add_argument("--autodisco-script")
    opts = parser.parse_args(argv)

    request = validate_request(read_json(opts.request_file))
    rack = build_instrument_rack()
    proposal = make_proposal(rack, request)

    if opts.operation == "plan":
        if opts.confirm_rx_only or opts.autodisco_script:
            raise ValueError("PLANNING_HAS_NO_EXECUTION")
        return {"schema": "ghot.radio-ear-plan-output/v0", "proposal": proposal}

    # Capture cannot occur until a SECOND explicit operator action.
    if not opts.plan_file or not opts.confirm_rx_only:
        raise ValueError("CAPTURE_REQUIRES_SAVED_PLAN_AND_EXPLICIT_CONFIRMATION")
    if not isinstance(opts.operator_label, str) or not opts.operator_label.strip():
        raise ValueError("CAPTURE_REQUIRES_OPERATOR_LABEL")
    saved = read_json(opts.plan_file)
    if set(saved) != {"schema", "proposal"} or saved["schema"] != "ghot.radio-ear-plan-output/v0":
        raise ValueError("INVALID_SAVED_PLAN")
    if saved["proposal"] != proposal:
        raise ValueError("SAVED_PLAN_STALE_OR_MODIFIED")

    selection = {
        "kind": "operator-explicit-radio-rx/v0",
        "approved": True,
        "proposal_id": proposal["proposal_id"],
        "card_id": proposal["card_id"],
    }
    capture = execute_selected_capture(
        proposal, request, rack, selection=selection, dispatch_source=opts.operator_label
    )
    output = {
        "schema": "ghot.radio-ear-capture-output/v0",
        "summary": capture["summary"],
        "autodisco_prepare": native_autodisco_request(capture),
        "portable_raw_iq_location": "owner-local GHoT instrument dispatch; exact packet ID in summary",
        "warning": "HOST REPORTED capture, not independent RF-origin proof",
    }
    if opts.autodisco_script:
        pair = prepare_autodisco(capture, opts.autodisco_script)
        output["native_autodisco"] = {
            "pair_id": pair["pair_id"],
            "packet_ids": [packet["packet_id"] for packet in pair["packets"]],
            "status": "FIRST_LISTEN_PACKETS_ONLY",
        }
    return output


def main() -> int:
    try:
        print(json.dumps(cli(sys.argv[1:]), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {str(exc)[:250]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
