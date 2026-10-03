#!/usr/bin/env python3
"""Deterministic proof for CARRIED-INTENT-ASSIGNMENT-001."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from carried_intent_assignment import assign, offer, status
from field_reseed_receiver import admit, receive
from field_reseed_receiver_sim import relatte, reseed


def execution_records(home: Path) -> list[Path]:
    records = home / "records"
    if not records.is_dir():
        return []
    return sorted(
        path for path in records.iterdir()
        if "-task-" in path.name or "-receipt-" in path.name
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ghot-carried-intent-assignment-") as raw:
        home = Path(raw) / "ghot"
        os.environ["GHOT_HOME"] = str(home)

        seed = reseed()
        held = receive(seed, relatte(seed))
        admitted = admit(held["hold_id"], "human-explicit")
        intent_id = admitted["intent"]["intent_id"]

        before = execution_records(home)
        assert before == []

        offered = offer(intent_id, timeout=0.01)
        assert offered["schema"] == "ghot.carried-intent-assignment-offer/v0"
        assert offered["intent_id"] == intent_id
        assert "selected" not in offered
        assert '"score"' not in json.dumps(offered)

        local = next(
            body for body in offered["bodies"]
            if body.get("location") == "local"
        )
        system_hash = next(
            item for item in local["offers"]
            if item.get("capability") == "system.hash"
        )
        assert system_hash["eligible"] is True

        assigned = assign(
            intent_id,
            offered,
            local["node_id"],
            "system.hash",
            "simulation-human-explicit",
            timeout=0.01,
        )
        assert assigned["schema"] == "ghot.carried-intent-assignment/v0"
        assert assigned["status"] == "ASSIGNED_NOT_EXECUTED"
        assert assigned["semantic_effect"] == "assignment-only"
        assert assigned["selected_node_id"] == local["node_id"]
        assert assigned["capability"] == "system.hash"
        assert assigned["intent_id"] == intent_id
        assert "ASSIGNMENT != EXECUTION" in assigned["laws"]
        assert "DISPATCH REQUIRES A NEW EXPLICIT CROSSING" in assigned["laws"]

        after = execution_records(home)
        assert after == before, "assignment must not create task/receipt execution records"

        current = status(intent_id)
        assert current["status"] == "ASSIGNED_NOT_EXECUTED"
        assert current["assignment"]["assignment_id"] == assigned["assignment_id"]

        replay = assign(
            intent_id,
            offered,
            local["node_id"],
            "system.hash",
            "simulation-human-explicit",
            timeout=0.01,
        )
        assert replay["assignment_id"] == assigned["assignment_id"]
        assert execution_records(home) == before

        try:
            assign(
                intent_id,
                offered,
                local["node_id"],
                "system.echo",
                "simulation-human-explicit",
                timeout=0.01,
            )
            raise AssertionError("a carried intent must not be silently reassigned")
        except ValueError as exc:
            assert "ALREADY_ASSIGNED_DIFFERENTLY" in str(exc)

        try:
            offer(intent_id, timeout=0.01)
            raise AssertionError("assigned intent must not open a fresh offer")
        except ValueError as exc:
            assert "ALREADY_ASSIGNED" in str(exc)

    print(json.dumps({
        "status": "ok",
        "intent_id": intent_id,
        "offer_id": offered["offer_id"],
        "assignment_id": assigned["assignment_id"],
        "selected_node_id": assigned["selected_node_id"],
        "capability": assigned["capability"],
        "law": "ASSIGNMENT != EXECUTION",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
