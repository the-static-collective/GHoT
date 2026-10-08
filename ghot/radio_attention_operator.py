#!/usr/bin/env python3
"""Owner-facing staged RADIO-ATTENTION-003 CLI; no automated transmission."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from instrument_rack import build_instrument_rack
from radio_attention import (
    APPROVAL, autodisco_comparison_request, compare_and_propose,
    native_autodisco_comparison, next_attention, plan_focus, plan_survey,
    run_focus, run_survey, validate_spec,
)


def read(path: str) -> dict:
    content = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ValueError("RADIO_ATTENTION_JSON_OBJECT_REQUIRED")
    return content


def output(path: str, data: dict) -> None:
    """Exclusive private write. Preserve previous evidence instead of overwriting."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(payload)


def execute(argv: list[str]) -> dict:
    parser = argparse.ArgumentParser(description="Explicit, receive-only two-index SDR attention")
    parser.add_argument("operation", choices=(
        "plan-survey", "run-survey", "plan-focus", "run-focus", "compare", "prepare-autodisco",
    ))
    parser.add_argument("--spec-file")
    parser.add_argument("--plan-file")
    parser.add_argument("--survey-file")
    parser.add_argument("--focus-file")
    parser.add_argument("--out", required=True)
    parser.add_argument("--approve-receive-only", action="store_true")
    parser.add_argument("--operator")
    parser.add_argument("--autodisco-script")
    args = parser.parse_args(argv)

    if args.operation not in {"run-survey", "run-focus"}:
        if args.approve_receive_only or args.operator:
            raise ValueError("NO_APPROVAL_ON_NON_EXECUTING_OPERATION")

    if args.operation == "plan-survey":
        if not args.spec_file:
            raise ValueError("SPEC_FILE_REQUIRED")
        proposal = plan_survey(validate_spec(read(args.spec_file)), build_instrument_rack())
        return {"schema": "ghot.radio-attention-plan-file/v0", "plan": proposal}

    if args.operation == "run-survey":
        if not all((args.spec_file, args.plan_file, args.operator)) or not args.approve_receive_only:
            raise ValueError("EXPLICIT_SURVEY_APPROVAL_REQUIRED")
        spec = validate_spec(read(args.spec_file))
        planfile = read(args.plan_file)
        expected = plan_survey(spec, build_instrument_rack())
        if planfile != {"schema": "ghot.radio-attention-plan-file/v0", "plan": expected}:
            raise ValueError("SURVEY_PLAN_STALE_OR_TAMPERED")
        result = run_survey(
            spec, build_instrument_rack(), expected,
            approval={"schema": APPROVAL, "approved": True, "plan_id": expected["plan_id"], "purpose": "survey"},
            operator=args.operator,
        )
        return result

    if args.operation in {"plan-focus", "run-focus", "compare", "prepare-autodisco"}:
        if not args.survey_file:
            raise ValueError("SURVEY_FILE_REQUIRED")
        survey = read(args.survey_file)
        if args.operation == "plan-focus":
            return {
                "schema": "ghot.radio-attention-plan-file/v0",
                "plan": plan_focus(survey, build_instrument_rack()),
            }
        if args.operation == "run-focus":
            if not all((args.plan_file, args.operator)) or not args.approve_receive_only:
                raise ValueError("EXPLICIT_FOCUS_APPROVAL_REQUIRED")
            expected = plan_focus(survey, build_instrument_rack())
            if read(args.plan_file) != {"schema": "ghot.radio-attention-plan-file/v0", "plan": expected}:
                raise ValueError("FOCUS_PLAN_STALE_OR_TAMPERED")
            return run_focus(
                survey, build_instrument_rack(), expected,
                approval={"schema": APPROVAL, "approved": True, "plan_id": expected["plan_id"], "purpose": "focus"},
                operator=args.operator,
            )
        if not args.focus_file:
            raise ValueError("FOCUS_FILE_REQUIRED")
        focus = read(args.focus_file)
        if args.operation == "compare":
            return {
                "schema": "ghot.radio-attention-comparison-result/v0",
                "comparison": compare_and_propose(survey, focus),
                "next_proposal": next_attention(survey, focus),
                "autodisco_prepare": autodisco_comparison_request(survey, focus),
                "automatic_next_capture": False,
            }
        if not args.autodisco_script:
            raise ValueError("NATIVE_AUTODISCO_SCRIPT_REQUIRED")
        pair = native_autodisco_comparison(survey, focus, args.autodisco_script)
        return {
            "schema": "ghot.radio-attention-autodisco-packet-pair/v0",
            "pair_id": pair["pair_id"],
            "packet_ids": [packet["packet_id"] for packet in pair["packets"]],
            "status": "FIRST_LISTEN_PACKETS_ONLY",
            "ai_responses": False,
        }
    raise ValueError("RADIO_ATTENTION_OPERATION_NOT_SUPPORTED")


def main() -> int:
    try:
        parser_message = execute(sys.argv[1:])
        path = sys.argv[sys.argv.index("--out") + 1]
        output(path, parser_message)
        print(json.dumps({"status": "WRITTEN_PRIVATELY", "path": str(Path(path).resolve()),
                          "transmission": "NONE", "automatic_next_capture": False}))
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {str(exc)[:220]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
