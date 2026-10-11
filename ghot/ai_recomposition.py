#!/usr/bin/env python3
"""AI RECOMPOSITION 001: two genuinely different, explicitly selected GHoT organs.

A capability adapter is invoked only by the existing Instrument Rack.
The operator-facing CLI never executes during planning or verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ADAPTER_ID = "ghot-ai-recomposition-001"
PROFILE = "analysis.text.profile"
INFER = "ai.text.infer.local"
INPUT_SCHEMA = "ghot.ai-recomposition-input/v0"
PLAN_SCHEMA = "ghot.ai-recomposition-plan/v0"
REPORT_SCHEMA = "ghot.ai-recomposition-report/v0"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checked_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != INPUT_SCHEMA:
        raise ValueError("INVALID_INPUT_SCHEMA")
    text = value.get("text")
    if not isinstance(text, str) or not 1 <= len(text.encode("utf-8")) <= 8192 or "\x00" in text:
        raise ValueError("INVALID_TEXT_SIZE")
    tokens = value.get("max_output_tokens", 96)
    if isinstance(tokens, bool) or not isinstance(tokens, int) or not 1 <= tokens <= 192:
        raise ValueError("INVALID_TOKEN_LIMIT")
    if set(value) - {"schema", "text", "max_output_tokens"}:
        raise ValueError("UNDECLARED_INPUT_FIELDS")
    return {"schema": INPUT_SCHEMA, "text": text, "max_output_tokens": tokens}


def model_ready() -> bool:
    model = os.environ.get("GHOT_AI_MODEL_PATH", "")
    return bool(model and Path(model).is_file() and shutil.which("llama-cli"))


def model_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def adapter_execute(capability: str, payload: Any) -> dict[str, Any]:
    value = checked_input(payload)
    text = value["text"]
    common = {"schema": "ghot.ai-recomposition-result/v0", "capability": capability,
              "source_text_sha256": text_sha(text), "authority": "NONE",
              "evaluation": "UNASSESSED"}
    if capability == PROFILE:
        words = re.findall(r"\b\w+\b", text.casefold(), flags=re.UNICODE)
        freq: dict[str, int] = {}
        for word in words:
            freq[word] = freq.get(word, 0) + 1
        return {**common, "method": "deterministic-unicode-word-profile",
                "word_count": len(words), "unique_words": len(freq),
                "top_words": sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:12],
                "character_count": len(text), "line_count": len(text.splitlines())}
    if capability != INFER:
        raise ValueError("UNDECLARED_CAPABILITY")
    if not model_ready():
        raise RuntimeError("LOCAL_LLAMA_CLI_AND_MODEL_REQUIRED")
    model = Path(os.environ["GHOT_AI_MODEL_PATH"]).resolve(strict=True)
    executable = shutil.which("llama-cli")
    if not executable:
        raise RuntimeError("LOCAL_LLAMA_CLI_REQUIRED")
    # Prompt is written to a private temporary file, not exposed on argv.
    prompt = ("Analyze the following text. Separate observations from interpretations. "
              "Propose possible themes and state uncertainty. Do not claim verification.\n\n"
              + text + "\n\nAnalysis:")
    with tempfile.TemporaryDirectory(prefix="ghot-ai001-") as tmp:
        file = Path(tmp) / "prompt.txt"
        file.write_text(prompt, encoding="utf-8")
        file.chmod(0o600)
        proc = subprocess.run(
            [executable, "-m", str(model), "-f", str(file),
             "-n", str(value["max_output_tokens"]), "--temp", "0"],
            capture_output=True, text=True, timeout=80, check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError("LOCAL_LLAMA_INFERENCE_FAILED")
    result = proc.stdout.strip()
    if not result or len(result.encode("utf-8")) > 32000:
        raise RuntimeError("LOCAL_LLAMA_OUTPUT_INVALID")
    return {**common, "method": "local-llama-cli", "model_content_sha256": model_sha256(model),
            "generation_parameters": {"max_output_tokens": value["max_output_tokens"],
                                      "temperature": 0},
            "output_text": result,
            "note": "Model interpretation only; native CLI formatting may vary."}


def run_adapter() -> None:
    try:
        capability = os.environ.get("GHOT_EXTERNAL_CAPABILITY", "")
        if capability not in (PROFILE, INFER):
            raise ValueError("NOT_AN_OPTED_IN_CAPABILITY")
        payload = json.load(sys.stdin)
        print(canonical(adapter_execute(capability, payload)))
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(type(exc).__name__ + ": " + str(exc)[:160], file=sys.stderr)
        sys.exit(1)


def rack():
    sys.path.insert(0, str(HERE))
    from instrument_rack import build_instrument_rack
    return build_instrument_rack()


def chosen_cards() -> dict[str, dict[str, Any]]:
    matches = [c for c in rack()["cards"] if c["adapter_id"] == ADAPTER_ID]
    cards = {c["capability"]: c for c in matches}
    if len(matches) != len(cards) or set(cards) != {PROFILE, INFER}:
        raise ValueError("OPT_IN_BOTH_AI_RECOMPOSITION_INSTRUMENTS")
    return cards


def make_plan(text: str, mode: str) -> dict[str, Any]:
    inp = checked_input({"schema": INPUT_SCHEMA, "text": text})
    if mode not in ("profile", "both"):
        raise ValueError("INVALID_MODE")
    cards = chosen_cards()
    if mode == "both" and not model_ready():
        raise ValueError("LOCAL_INFERENCE_NOT_READY")
    selected = [PROFILE] + ([INFER] if mode == "both" else [])
    selected_cards = [cards[c] for c in selected]
    if any(c["available"] is not True for c in selected_cards):
        raise ValueError("SELECTED_CARD_UNAVAILABLE")
    body = {"schema": PLAN_SCHEMA, "mode": mode,
            "input_sha256": text_sha(inp["text"]), "input_size": len(inp["text"].encode("utf-8")),
            "selected_cards": selected_cards, "selection": "OPERATOR_REQUIRED",
            "execution": False, "semantic_effect": "none"}
    return {**body, "plan_id": "ai-recomposition-plan-v0:" + digest(body)}


def validate_plan(plan: Any) -> None:
    if not isinstance(plan, dict):
        raise ValueError("INVALID_PLAN")
    copy = {k: v for k, v in plan.items() if k != "plan_id"}
    if plan.get("plan_id") != "ai-recomposition-plan-v0:" + digest(copy):
        raise ValueError("TAMPERED_PLAN")


def execute_plan(plan: dict[str, Any], text: str, dispatch_source: str) -> dict[str, Any]:
    validate_plan(plan)
    if canonical(plan) != canonical(make_plan(text, plan["mode"])):
        raise ValueError("STALE_PLAN_OR_DIFFERENT_INPUT")
    if not dispatch_source.strip():
        raise ValueError("EXPLICIT_DISPATCH_SOURCE_REQUIRED")
    sys.path.insert(0, str(HERE))
    from instrument_rack import dispatch_instrument_card
    payload = checked_input({"schema": INPUT_SCHEMA, "text": text})
    results = []
    for card in plan["selected_cards"]:
        attempt = dispatch_instrument_card(card, payload, dispatch_source=dispatch_source)
        results.append(attempt)
    report_body = {"schema": REPORT_SCHEMA, "plan_id": plan["plan_id"],
                   "input_sha256": text_sha(text),
                   "attempts": results,
                   "comparison": [{"capability": r["capability"], "status": r["status"],
                                   "receipt_id": r["signed_receipt"]["receipt_id"],
                                   "packet_id": (r["packet"] or {}).get("packet_id")}
                                  for r in results],
                   "quality_assessment": "NOT_PERFORMED",
                   "admission": False, "publication": False,
                   "native_receiver_hold": False}
    return {**report_body, "report_id": "ai-recomposition-report-v0:" + digest(report_body)}


def verify_report(report: Any) -> bool:
    if not isinstance(report, dict) or report.get("schema") != REPORT_SCHEMA:
        raise ValueError("INVALID_REPORT")
    body = {k: v for k, v in report.items() if k != "report_id"}
    if report.get("report_id") != "ai-recomposition-report-v0:" + digest(body):
        raise ValueError("TAMPERED_REPORT")
    sys.path.insert(0, str(HERE))
    from instrument_rack import _validate_packet
    from relatte_identity import verify_receipt
    attempts = report.get("attempts")
    if not isinstance(attempts, list) or len(attempts) not in (1, 2):
        raise ValueError("INVALID_ATTEMPTS")
    if [r.get("capability") for r in attempts] != [PROFILE, INFER][:len(attempts)]:
        raise ValueError("INVALID_ATTEMPT_ORDER")
    for r in attempts:
        signed = r.get("signed_receipt")
        if not isinstance(signed, dict) or not verify_receipt(signed):
            raise ValueError("INVALID_SIGNED_RECEIPT")
        packet = r.get("packet")
        if r.get("status") == "EXECUTED":
            _validate_packet(packet)
            if packet["input_sha256"] != digest({"schema": INPUT_SCHEMA,
                                                  "text": r["task"]["input"]["text"],
                                                  "max_output_tokens": 96}):
                raise ValueError("INPUT_BINDING_MISMATCH")
            if text_sha(r["task"]["input"]["text"]) != report["input_sha256"]:
                raise ValueError("TEXT_BINDING_MISMATCH")
            if packet["source_card_id"] != r["card_id"]:
                raise ValueError("CARD_BINDING_MISMATCH")
        elif packet is not None:
            raise ValueError("ERROR_HAS_SEED_PACKET")
    if body.get("admission") is not False or body.get("native_receiver_hold") is not False:
        raise ValueError("INVALID_ADMISSION_CLAIM")
    return True


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "adapter":
        run_adapter()
        return
    parser = argparse.ArgumentParser(description="GHoT AI Recomposition 001")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--text-file", required=True)
        if name == "plan":
            cmd.add_argument("--mode", choices=("profile", "both"), default="profile")
            cmd.add_argument("--out", required=True)
        else:
            cmd.add_argument("--plan-file", required=True)
            cmd.add_argument("--out", required=True)
            cmd.add_argument("--approve-exact-plan", action="store_true")
            cmd.add_argument("--dispatch-source", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--report-file", required=True)
    args = parser.parse_args()
    if args.cmd == "verify":
        report = json.loads(Path(args.report_file).read_text(encoding="utf-8"))
        verify_report(report)
        print(canonical({"verified": True, "report_id": report["report_id"],
                         "kind": "LOCAL_INSTRUMENT_EVIDENCE_ONLY"}))
        return
    text = Path(args.text_file).read_text(encoding="utf-8")
    checked_input({"schema": INPUT_SCHEMA, "text": text})
    if args.cmd == "plan":
        result = make_plan(text, args.mode)
    else:
        if not args.approve_exact_plan:
            raise ValueError("EXPLICIT_PLAN_APPROVAL_REQUIRED")
        plan = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
        result = execute_plan(plan, text, args.dispatch_source)
    dest = Path(args.out)
    if dest.exists():
        raise FileExistsError("REFUSE_TO_OVERWRITE_EVIDENCE")
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(canonical({"output": str(dest), "id": result.get("plan_id") or result.get("report_id")}))


if __name__ == "__main__":
    main()
