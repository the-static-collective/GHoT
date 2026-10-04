#!/usr/bin/env python3
"""Deterministic witness for TenetGram 040."""

from copy import deepcopy

from tenetgram import (
    TenetGramError,
    emit_tenetgram,
    make_field_link,
    receive_seed,
    specimen_consequence,
)


def expect_error(fn, phrase: str) -> None:
    try:
        fn()
    except TenetGramError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"expected TenetGramError containing {phrase!r}")


def main() -> int:
    consequence = specimen_consequence()

    neighborhood = make_field_link(
        actor="alice",
        field_id="neighborhood-a",
        relation="local-neighbor",
    )
    garden = make_field_link(
        actor="alice",
        field_id="garden-circle",
        relation="explicit-member",
    )
    bob_link = make_field_link(
        actor="bob",
        field_id="tool-circle",
        relation="explicit-member",
    )

    gram = emit_tenetgram(
        consequence,
        issuer_actor="alice",
        field_links=[garden, bob_link, neighborhood],
    )

    assert gram["format"] == "ghot.tenetgram"
    assert gram["authority"] == "carriage-only"
    assert gram["automatic_delivery"] is False
    assert gram["automatic_notification"] is False
    assert gram["automatic_request"] is False
    assert gram["automatic_execution"] is False
    assert gram["back"]["completed_steps"] == ["release-tree", "cut-tree"]
    assert gram["back"]["unresolved_relation"] == "haul-firewood"

    seeds = gram["front"]["seeds"]
    assert gram["front"]["seed_count"] == 2
    assert [seed["target_field"] for seed in seeds] == [
        "garden-circle",
        "neighborhood-a",
    ]
    assert all(seed["issuer_actor"] == "alice" for seed in seeds)
    assert all(seed["status"] == "dormant" for seed in seeds)
    assert all(seed["authority"] == "possibility-only" for seed in seeds)
    assert all(seed["notification_requested"] is False for seed in seeds)
    assert all(seed["request_requested"] is False for seed in seeds)
    assert all(seed["execution_requested"] is False for seed in seeds)
    assert all(seed["specific_claims"] == [] for seed in seeds)

    projection = receive_seed(
        gram,
        field_id="neighborhood-a",
        seed_id=next(
            seed["seed_id"]
            for seed in seeds
            if seed["target_field"] == "neighborhood-a"
        ),
    )
    assert projection["status"] == "visible-dormant"
    assert projection["admitted"] is False
    assert projection["requested"] is False
    assert projection["notified"] is False
    assert projection["executed"] is False

    expect_error(
        lambda: emit_tenetgram(
            consequence,
            issuer_actor="mallory",
            field_links=[neighborhood],
        ),
        "not attributable",
    )
    expect_error(
        lambda: emit_tenetgram(
            consequence,
            issuer_actor="alice",
            field_links=[bob_link],
        ),
        "at least one explicit connected field",
    )
    expect_error(
        lambda: receive_seed(
            gram,
            field_id="another-field",
            seed_id=seeds[0]["seed_id"],
        ),
        "another field",
    )

    scored = deepcopy(consequence)
    scored["score"] = 4
    expect_error(
        lambda: emit_tenetgram(
            scored,
            issuer_actor="alice",
            field_links=[neighborhood],
        ),
        "score cannot seed possibility",
    )

    changed = deepcopy(consequence)
    changed["residue"][-1]["note"] = "different real consequence"
    changed_gram = emit_tenetgram(
        changed,
        issuer_actor="alice",
        field_links=[neighborhood],
    )
    assert changed_gram["tenetgram_id"] != gram["tenetgram_id"]

    print("TENETGRAM 040: VERIFIED")
    print("consequence -> dormant future possibility")
    print("only explicit issuer field links receive seeds")
    print("seed != notification/request/recommendation/obligation")
    print("receiver projection remains non-admitted and non-executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
