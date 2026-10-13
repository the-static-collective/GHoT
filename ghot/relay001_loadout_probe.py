#!/usr/bin/env python3
"""RELAY-001: LOADOUT BIND -> native GHoT media.probe.

Requires *both* project source checkouts. No fallback executor, network,
publication, arbitrary shell, or signed-receipt claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

CAPABILITY = "media.probe"
EFFECTS = ["filesystem.read", "process.spawn.ffprobe"]
MAX_SIZE = 200 * 1024 * 1024


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_record(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def save(directory: Path, name: str, value: dict) -> None:
    (directory / name).write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run(source: Path, expected_sha: str, loadout_src: Path, ghot_root: Path,
        output: Path, *, fence: list[str] | None = None, dry_run: bool = False) -> dict:
    source = source.expanduser().resolve(strict=True)
    expected = expected_sha.lower().removeprefix("sha256:")
    if len(expected) != 64 or any(x not in "0123456789abcdef" for x in expected):
        raise ValueError("expected sha256 must contain exactly 64 hex digits")
    if not source.is_file() or source.stat().st_size > MAX_SIZE:
        raise ValueError("source must be a regular file under the v0 size limit")
    before = sha_file(source)
    if before != expected:
        raise ValueError("SOURCE_HASH_MISMATCH_BEFORE_EXECUTION")

    loadout_src = loadout_src.resolve(strict=True)
    if not (loadout_src / "loadout" / "bind.py").is_file():
        raise FileNotFoundError("native LOADOUT src/loadout/bind.py required")
    sys.path.insert(0, str(loadout_src))
    from loadout.bind import evaluate_binding, validate_execution_attempt

    params = {"path": str(source), "source_sha256": before, "capability": CAPABILITY}
    effective_fence = list(EFFECTS if fence is None else fence)
    requirement = {"capability": CAPABILITY, "parameters": params,
                   "reachable_effects": EFFECTS}
    binding = evaluate_binding(requirement, effective_fence)
    preflight = validate_execution_attempt(binding, params)
    if binding["disposition"] != "BIND" or preflight["disposition"] != "BIND":
        raise PermissionError("LOADOUT_REFUSAL: " +
                              str(binding.get("reason_code") or preflight.get("reason_code")))
    if binding.get("unfenced_effects") or sorted(binding.get("reachable_effects") or []) != sorted(EFFECTS):
        raise PermissionError("unexpected/unfenced effect")

    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    save(output, "loadout-binding.json", binding)
    save(output, "loadout-parameters.json", params)
    result = {
        "schema": "static-relay/loadout-ghot-media-probe/v0",
        "source_sha256": before,
        "loadout_binding_digest": sha_record(binding),
        "loadout_parameter_digest": binding["parameter_digest"],
        "signed": False,
        "published": False,
        "canon_admitted": False,
    }
    if dry_run:
        result.update(status="BOUND_NOT_EXECUTED", ghot_invoked=False)
        save(output, "relay-crossing.json", result)
        return result

    ghot_dir = ghot_root.expanduser().resolve(strict=True) / "ghot"
    if not (ghot_dir / "reference_node.py").is_file():
        raise FileNotFoundError("native GHoT ghot/reference_node.py required")
    sys.path.insert(0, str(ghot_dir))
    import reference_node

    offer, _ = reference_node._current_offer(CAPABILITY)
    if not offer or offer.get("available") is not True or offer.get("executor") != "ffprobe":
        raise RuntimeError("GHoT media.probe not currently offered by ffprobe")

    task, receipt = reference_node.execute(
        CAPABILITY, str(source),
        constraints={"network": "not-required", "source_sha256": before,
                     "loadout_parameter_digest": binding["parameter_digest"],
                     "effect_fence": effective_fence},
    )
    after = sha_file(source)
    save(output, "ghot-task.json", task)
    save(output, "ghot-receipt.json", receipt)
    valid_output = (receipt.get("output") is not None
                    and receipt.get("output_sha256") == reference_node.sha256_json(receipt["output"]))
    success = receipt["status"] == "ok" and before == after and valid_output
    result.update(
        status="PROBED_NATIVE_GHOT" if success else "FAILED_OR_SOURCE_CHANGED",
        occurred_at=datetime.now(timezone.utc).isoformat(),
        source_sha256_after=after, source_unchanged=(before == after),
        ghot_task_id=task["task_id"], ghot_receipt_id=receipt["receipt_id"],
        ghot_receipt_digest=sha_record(receipt),
        ghot_native_status=receipt["status"], ghot_output_sha256_valid=valid_output,
        owner_disposition="LOCAL_OBSERVATION_ONLY",
    )
    save(output, "relay-crossing.json", result)
    if not success:
        raise RuntimeError("GHoT failed, source changed, or output hash invalid")
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--sha256", required=True)
    p.add_argument("--loadout-src", required=True, type=Path)
    p.add_argument("--ghot-root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--fence", action="append", default=None,
                   help="exactly declared reachable effect (repeatable)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        result = run(args.source, args.sha256, args.loadout_src, args.ghot_root,
                     args.out, fence=args.fence, dry_run=args.dry_run)
    except Exception as exc:
        print(json.dumps({"status": "REFUSED_OR_FAILED", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
