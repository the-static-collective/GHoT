#!/usr/bin/env python3
"""Isolated bridge to Dogram CONTRIBUTION-FIELD-001.

GHoT already loads the Ice Cube verifier from a different historical Dogram
branch. This bridge runs the contribution-field branch in a separate Python
process so the two Dogram snapshots cannot contaminate each other's imports.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


_PROGRAM = r"""
import json
import sys

from dogram.contribution_field import (
    build_cut,
    compare_measurements,
    measure_workmark,
    mint_workmark,
)

request = json.load(sys.stdin)
events = request["events"]
declared = tuple(request["declared_relation_kinds"])
birth_event_id = request["birth_event_id"]
birth_cut = request["birth_cut"]
before_cut = request["before_cut"]
after_cut = request["after_cut"]

workmark = mint_workmark(events, birth_event_id, birth_cut, declared)
before = measure_workmark(build_cut(events, before_cut, declared), workmark)
after = measure_workmark(build_cut(events, after_cut, declared), workmark)
delta = compare_measurements(before, after)

json.dump(
    {
        "workmark": workmark,
        "before": before,
        "after": after,
        "delta": delta,
    },
    sys.stdout,
    sort_keys=True,
)
"""


class DogramContributionBridgeError(RuntimeError):
    pass


def run_contribution_field(
    dogram_repo: Path,
    *,
    events: list[dict[str, Any]],
    declared_relation_kinds: tuple[str, ...],
    birth_event_id: str,
    birth_cut: int = 0,
    before_cut: int = 0,
    after_cut: int = 1,
) -> dict[str, Any]:
    repo = dogram_repo.resolve()
    module = repo / "dogram" / "contribution_field.py"
    if not module.is_file():
        raise DogramContributionBridgeError(
            "Dogram contribution field not found; use branch design/contribution-field-001"
        )

    request = {
        "events": events,
        "declared_relation_kinds": list(declared_relation_kinds),
        "birth_event_id": birth_event_id,
        "birth_cut": birth_cut,
        "before_cut": before_cut,
        "after_cut": after_cut,
    }

    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo) + (os.pathsep + existing if existing else "")

    completed = subprocess.run(
        [sys.executable, "-c", _PROGRAM],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise DogramContributionBridgeError(
            "Dogram contribution field refused the request: "
            + completed.stderr.strip()
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DogramContributionBridgeError(
            "Dogram contribution field returned non-JSON output"
        ) from exc
    if not isinstance(value, dict):
        raise DogramContributionBridgeError("Dogram contribution result must be an object")
    return value


__all__ = ["DogramContributionBridgeError", "run_contribution_field"]
