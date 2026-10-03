#!/usr/bin/env python3
"""Smoke test for explicit body choice."""

from __future__ import annotations

import json

from body_choice import assign, discover_offer


def main() -> int:
    offer = discover_offer("system.hash", timeout=0.01)
    assert offer["kind"] == "ghot.body-choice.offer"
    assert "selected" not in offer
    assert offer["offer_id"].startswith("ghot-body-offer-v0:")

    eligible = [item for item in offer["candidates"] if item["eligible"]]
    assert eligible, "local body should offer system.hash"
    local = next(item for item in eligible if item["location"] == "local")

    payload = {"hello": "house"}
    result = assign(
        offer,
        local["node_id"],
        payload,
        timeout=0.01,
        selection_source="simulation-explicit",
    )
    assert result["kind"] == "ghot.body-choice.result"
    assert result["assignment"]["selected_node_id"] == local["node_id"]
    assert result["assignment"]["offer_id"] == offer["offer_id"]
    assert result["status"] == "ok"
    receipt = result["execution"]["receipt"]
    assert receipt["executor_node_id"] == local["node_id"]
    assert receipt["capability"] == "system.hash"
    assert receipt["output"]["sha256"]

    replay = assign(
        offer,
        local["node_id"],
        payload,
        timeout=0.01,
        selection_source="simulation-explicit",
    )
    assert replay["assignment"]["assignment_id"] == result["assignment"]["assignment_id"]
    assert replay["execution"]["receipt"]["receipt_id"] == receipt["receipt_id"]

    try:
        assign(
            offer,
            "node-not-in-offer",
            "nope",
            timeout=0.01,
        )
        raise AssertionError("assignment to an unoffered body must fail")
    except ValueError:
        pass

    print(json.dumps({
        "offer_id": offer["offer_id"],
        "eligible_bodies": [item["node_id"] for item in eligible],
        "assignment_id": result["assignment"]["assignment_id"],
        "receipt_id": receipt["receipt_id"],
        "status": result["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
