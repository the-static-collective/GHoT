#!/usr/bin/env python3
"""Deterministic proof for CARRIED-INTENT-DISPATCH-001."""

from __future__ import annotations

import json
from pathlib import Path

from carried_intent_assignment import assign, offer
from carried_intent_dispatch import (
    DISPATCH_STATE_SCHEMA,
    _dispatch_state_path,
    _load_assignment,
    _write_json,
    dispatch,
    status,
)
from field_reseed_receiver import admit, receive
from field_reseed_receiver_sim import relatte, reseed
from relatte_identity import verify_crossing, verify_receipt


def execution_records(home: Path) -> list[Path]:
    records = home / "records"
    if not records.is_dir():
        return []
    return sorted(
        path for path in records.iterdir()
        if "-task-" in path.name or "-receipt-" in path.name
    )


def setup_intent(note_suffix: str) -> tuple[str, dict]:
    seed = reseed()
    seed["human_note"] = "carry the exact possibility " + note_suffix

    # Recompute deterministic donor identity after changing the note.
    from field_reseed_receiver import _digest
    body = {key: value for key, value in seed.items() if key != "reseed_id"}
    seed["reseed_id"] = "field-reseed-v0:" + _digest(body)

    crossing = relatte(seed)
    held = receive(seed, crossing)
    admitted = admit(held["hold_id"], "human-explicit")
    intent_id = admitted["intent"]["intent_id"]

    offered = offer(intent_id, timeout=0.01)
    local = next(
        body for body in offered["bodies"]
        if body.get("location") == "local"
    )
    selected = next(
        item for item in local["offers"]
        if item.get("capability") == "system.hash"
        and item.get("eligible") is True
    )
    assigned = assign(
        intent_id,
        offered,
        local["node_id"],
        selected["capability"],
        "simulation-human-explicit",
        timeout=0.01,
    )
    return intent_id, assigned


def main() -> int:
    import os
    home = Path(os.environ["GHOT_HOME"])

    intent_id, assigned = setup_intent("dispatch-ok")
    before = execution_records(home)

    result = dispatch(
        intent_id,
        dispatch_source="simulation-human-dispatch",
        timeout=0.01,
    )
    assert result["schema"] == "ghot.carried-intent-dispatch-result/v0"
    assert result["status"] == "EXECUTED"
    assert result["semantic_effect"] == "receiver-local-consequence"
    assert result["assignment_id"] == assigned["assignment_id"]
    assert result["selected_node_id"] == assigned["selected_node_id"]
    assert result["capability"] == "system.hash"

    crossing = result["crossing"]
    signed_receipt = result["signed_receipt"]
    assert verify_crossing(crossing)
    assert verify_receipt(signed_receipt)
    assert signed_receipt["crossing_id"] == crossing["crossing_id"]
    assert signed_receipt["kind"] == "EXECUTED"
    assert signed_receipt["semantic_effect"] == "bounded-capability-attempt"

    execution = result["execution"]
    task = execution["task"]
    receipt = execution["receipt"]
    assert task["capability"] == "system.hash"
    assert receipt["capability"] == "system.hash"
    assert receipt["status"] == "ok"
    assert receipt["output"]["sha256"]
    assert task["constraints"]["assignment_id"] == assigned["assignment_id"]
    assert (
        task["constraints"]["dispatch_crossing_id"]
        == crossing["crossing_id"]
    )
    assert verify_crossing(task["constraints"]["signed_dispatch_crossing"])

    after = execution_records(home)
    assert len(after) == len(before) + 2

    # Completed dispatch is idempotent: replay returns the exact result.
    replay = dispatch(
        intent_id,
        dispatch_source="simulation-human-dispatch",
        timeout=0.01,
    )
    assert replay["dispatch_crossing_id"] == result["dispatch_crossing_id"]
    assert replay["execution"]["task"]["task_id"] == task["task_id"]
    assert replay["execution"]["receipt"]["receipt_id"] == receipt["receipt_id"]
    assert execution_records(home) == after

    current = status(intent_id)
    assert current["status"] == "EXECUTED"

    # A separately assigned intent with a prepared-but-unfinished crossing must
    # refuse automatic retry because its execution outcome is unknowable.
    ambiguous_intent, ambiguous_assignment = setup_intent("dispatch-ambiguous")
    entry, _admission, _intent, _assignment = _load_assignment(ambiguous_intent)
    _write_json(
        _dispatch_state_path(entry),
        {
            "schema": DISPATCH_STATE_SCHEMA,
            "state": "prepared",
            "assignment_id": ambiguous_assignment["assignment_id"],
            "intent_id": ambiguous_intent,
            "crossing_id": "relatte-crossing-v0:" + "a" * 64,
            "payload_sha256": "b" * 64,
            "dispatch_source": "simulation-ambiguous",
            "prepared_at": "2026-10-03T16:59:00.000Z",
            "crossing": {},
        },
    )
    try:
        dispatch(
            ambiguous_intent,
            dispatch_source="simulation-human-dispatch",
            timeout=0.01,
        )
        raise AssertionError("prepared unknown dispatch must not auto-retry")
    except RuntimeError as exc:
        assert "DISPATCH_OUTCOME_UNKNOWN" in str(exc)

    ambiguous_status = status(ambiguous_intent)
    assert ambiguous_status["status"] == "DISPATCH_OUTCOME_UNKNOWN"

    print(json.dumps({
        "status": "ok",
        "intent_id": intent_id,
        "assignment_id": assigned["assignment_id"],
        "dispatch_crossing_id": crossing["crossing_id"],
        "task_id": task["task_id"],
        "execution_receipt_id": receipt["receipt_id"],
        "signed_receipt_id": signed_receipt["receipt_id"],
        "ambiguous_retry": "refused",
        "law": "ASSIGNMENT != EXECUTION",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
