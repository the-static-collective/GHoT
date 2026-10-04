#!/usr/bin/env python3
"""Deterministic witness for Warm Thread 039."""

from copy import deepcopy

from warm_thread import (
    WarmThreadError,
    authorize_step,
    compose,
    dead_tree_specimen,
    execution_readiness,
)


def expect_error(fn, phrase: str) -> None:
    try:
        fn()
    except WarmThreadError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"expected WarmThreadError containing {phrase!r}")


def main() -> int:
    specimen = dead_tree_specimen()
    proposal = specimen["proposal"]

    assert proposal["status"] == "composable"
    assert proposal["economics"]["required"] is False
    assert proposal["privacy"]["exact_household_address"] == "withheld"
    assert proposal["nonclaims"]["execution_authorized"] is False
    assert [step["step_id"] for step in proposal["steps"]] == [
        "release-tree",
        "cut-tree",
        "haul-load",
        "accept-delivery",
    ]
    assert all(step["authorization"] == "required-separately" for step in proposal["steps"])
    assert not any(key in proposal for key in ("score", "rank", "price", "common_unit"))

    missing_truck = [
        record for record in specimen["records"]
        if record["record_id"] != "can-haul-001"
    ]
    gap = compose(missing_truck)
    assert gap["status"] == "gap"
    assert gap["missing_relations"] == ["haul-firewood"]
    assert gap["steps"] == []

    alice = authorize_step(
        proposal,
        step_id="release-tree",
        actor="alice",
        phrase="ACT",
    )
    readiness = execution_readiness(proposal, [alice])
    assert readiness["status"] == "HOLD"
    assert readiness["authorized_steps"] == ["release-tree"]
    assert "cut-tree" in readiness["missing_authorizations"]

    expect_error(
        lambda: authorize_step(
            proposal,
            step_id="cut-tree",
            actor="alice",
            phrase="ACT",
        ),
        "does not own",
    )
    expect_error(
        lambda: authorize_step(
            proposal,
            step_id="cut-tree",
            actor="bob",
            phrase="yes",
        ),
        "explicit ACT",
    )

    authorizations = [
        alice,
        authorize_step(proposal, step_id="cut-tree", actor="bob", phrase="ACT"),
        authorize_step(proposal, step_id="haul-load", actor="cara", phrase="ACT"),
        authorize_step(proposal, step_id="accept-delivery", actor="david", phrase="ACT"),
    ]
    ready = execution_readiness(proposal, authorizations)
    assert ready["status"] == "READY"
    assert ready["execution_performed"] is False

    tampered = deepcopy(authorizations[-1])
    tampered["actor"] = "mallory"
    expect_error(
        lambda: execution_readiness(proposal, authorizations[:-1] + [tampered]),
        "actor/step mismatch",
    )

    print("WARM THREAD 039: VERIFIED")
    print("candidate path composed without price/rank")
    print("missing truck -> durable gap")
    print("Alice ACT does not authorize Bob")
    print("all four ACTs -> READY, execution still false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
