#!/usr/bin/env python3
"""UNHEARD CHOIR 005 — The Colluding Observers.

Test whether three individually valid, agreeing signed claims can be challenged
by a separately pinned precommitted measurement of an explicitly SIMULATED
fixture. No physical sensor, identity attestation, broadcast, native GHoT
dispatch, reLATTE crossing or autonomous action.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_lying_witness import (
    ROLES, assess as assess_004, check_challenge, make_challenge,
    roster_for, sign_statement,
)
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk,
    particular_for_public_key, verify_p256,
)

ANCHOR_SCHEMA = "ghot.unheard-choir-005-instrument-anchor/v0"
COMMIT_SCHEMA = "ghot.unheard-choir-005-precommit/v0"
MEASURE_SCHEMA = "ghot.unheard-choir-005-fixture-measurement/v0"
ASSESS_SCHEMA = "ghot.unheard-choir-005-independent-evidence-assessment/v0"
COMMIT_DOMAIN = b"GHOT-UNHEARD-CHOIR-005-PRECOMMIT-v0|"
MEASURE_DOMAIN = b"GHOT-UNHEARD-CHOIR-005-MEASUREMENT-v0|"
PROFILE = "SIMULATED_OCCUPANCY_ANY_NONZERO_V0"


def exact(obj: Any, fields: set[str], where: str) -> None:
    if type(obj) is not dict or set(obj) != fields:
        raise InvalidWorld(f"{where}: missing or unknown fields")


def integer(value: Any, lo: int, hi: int, name: str) -> None:
    if type(value) is not int or not lo <= value <= hi:
        raise InvalidWorld(f"{name}: expected integer in [{lo}, {hi}]")


def jwk(value: Any) -> dict[str, str]:
    try:
        return normalize_public_jwk(value)
    except (IdentityProfileError, TypeError, ValueError) as err:
        raise InvalidWorld("invalid public key") from err


def validate_samples(samples: Any) -> None:
    if type(samples) is not list or len(samples) != 8:
        raise InvalidWorld("exactly 8 declared simulation frames required")
    for sample in samples:
        integer(sample, 0, 255, "simulation frame")


def compute_outcome(samples: list[int]) -> str:
    validate_samples(samples)
    return "PRESENT" if any(x > 0 for x in samples) else "EMPTY"


def make_anchor(parent: dict, roster: dict, instrument: IdentityKey) -> dict:
    instrument_jwk = jwk(instrument.public_jwk())
    present = [roster["owner_public_key"]] + [roster["actors"][r] for r in ROLES]
    if particular_for_public_key(instrument_jwk) in {
        particular_for_public_key(jwk(k)) for k in present
    }:
        raise InvalidWorld("instrument evidence key must differ from all claimant and owner keys")
    return {
        "schema": ANCHOR_SCHEMA, "scope": "PINNED_SIMULATION_ONLY",
        "instrument_id": "secondary-occupancy-fixture",
        "instrument_epoch": 3,
        "instrument_public_key": instrument_jwk,
        "parent_proposal_digest": parent["proposal_digest"],
    }


def validate_anchor(parent: dict, roster: dict, anchor: Any) -> None:
    exact(anchor, {"schema", "scope", "instrument_id", "instrument_epoch",
                   "instrument_public_key", "parent_proposal_digest"}, "anchor")
    if anchor["schema"] != ANCHOR_SCHEMA or anchor["scope"] != "PINNED_SIMULATION_ONLY":
        raise InvalidWorld("independent instrument anchor cannot grant external permission")
    if anchor["instrument_id"] != "secondary-occupancy-fixture":
        raise InvalidWorld("unrecognized simulated instrument")
    integer(anchor["instrument_epoch"], 0, 999999, "instrument epoch")
    if anchor["parent_proposal_digest"] != parent["proposal_digest"]:
        raise InvalidWorld("instrument anchor belongs to another 003 proposal")
    key = jwk(anchor["instrument_public_key"])
    others = [roster["owner_public_key"]] + [roster["actors"][r] for r in ROLES]
    if particular_for_public_key(key) in {particular_for_public_key(jwk(x)) for x in others}:
        raise InvalidWorld("measurement not independent by signing key")


def signed_precommit(parent: dict, roster: dict, anchor: dict, instrument: IdentityKey,
                     *, samples: list[int], captured_at: int) -> dict:
    validate_anchor(parent, roster, anchor)
    integer(captured_at, 1, 10**12, "capture time")
    validate_samples(samples)
    if jwk(instrument.public_jwk()) != jwk(anchor["instrument_public_key"]):
        raise InvalidWorld("cannot precommit with unpinned instrument key")
    body = {
        "schema": COMMIT_SCHEMA,
        "parent_proposal_digest": parent["proposal_digest"],
        "roster_digest": digest(roster),
        "anchor_digest": digest(anchor),
        "instrument_id": anchor["instrument_id"],
        "instrument_epoch": anchor["instrument_epoch"],
        "source_world_digest": parent["world_digest"],
        "captured_at": captured_at,
        "profile": PROFILE,
        "sample_digest": digest(samples),
        "data_scope": "SIMULATED_FIXTURE_BYTES_ONLY",
    }
    return {**body, "signature": instrument.sign(COMMIT_DOMAIN + jcs_bytes(body))}


def verify_precommit(parent: dict, roster: dict, anchor: dict, challenge: dict,
                     precommit: Any) -> None:
    validate_anchor(parent, roster, anchor)
    exact(precommit, {
        "schema", "parent_proposal_digest", "roster_digest", "anchor_digest",
        "instrument_id", "instrument_epoch", "source_world_digest",
        "captured_at", "profile", "sample_digest", "data_scope", "signature",
    }, "precommit")
    if (precommit["schema"] != COMMIT_SCHEMA
        or precommit["parent_proposal_digest"] != parent["proposal_digest"]
        or precommit["roster_digest"] != digest(roster)
        or precommit["anchor_digest"] != digest(anchor)
        or precommit["instrument_id"] != anchor["instrument_id"]
        or precommit["instrument_epoch"] != anchor["instrument_epoch"]
        or precommit["source_world_digest"] != parent["world_digest"]
        or precommit["profile"] != PROFILE
        or precommit["data_scope"] != "SIMULATED_FIXTURE_BYTES_ONLY"):
        raise InvalidWorld("precommit not bound to exact pinned simulation instrument and world")
    integer(precommit["captured_at"], 1, 10**12, "capture time")
    if precommit["captured_at"] >= challenge["issued_at"]:
        raise InvalidWorld("precommit must precede fresh owner challenge")
    if type(precommit["sample_digest"]) is not str or len(precommit["sample_digest"]) != 64 or any(
        c not in "0123456789abcdef" for c in precommit["sample_digest"]
    ):
        raise InvalidWorld("invalid sample digest")
    body = {k: v for k, v in precommit.items() if k != "signature"}
    if type(precommit["signature"]) is not str or not verify_p256(
        anchor["instrument_public_key"], COMMIT_DOMAIN + jcs_bytes(body), precommit["signature"]
    ):
        raise InvalidWorld("precommit P-256 signature invalid")


def signed_measurement(challenge: dict, precommit: dict, samples: list[int],
                       key: IdentityKey) -> dict:
    validate_samples(samples)
    if digest(samples) != precommit["sample_digest"]:
        raise InvalidWorld("raw fixture frames do not match the precommitted bytes")
    body = {
        "schema": MEASURE_SCHEMA, "challenge_digest": digest(challenge),
        "precommit_digest": digest(precommit),
        "samples": samples, "sample_digest": digest(samples),
        "derived_outcome": compute_outcome(samples),
        "profile": PROFILE, "measurement_scope": "SIMULATED_REDERIVED_NOT_PHYSICAL",
    }
    return {**body, "signature": key.sign(MEASURE_DOMAIN + jcs_bytes(body))}


def verify_measurement(challenge: dict, anchor: dict, precommit: dict,
                       measurement: Any) -> str:
    exact(measurement, {
        "schema", "challenge_digest", "precommit_digest", "samples",
        "sample_digest", "derived_outcome", "profile", "measurement_scope",
        "signature",
    }, "measurement")
    validate_samples(measurement["samples"])
    observed = compute_outcome(measurement["samples"])
    if (measurement["schema"] != MEASURE_SCHEMA
        or measurement["challenge_digest"] != digest(challenge)
        or measurement["precommit_digest"] != digest(precommit)
        or measurement["sample_digest"] != digest(measurement["samples"])
        or measurement["sample_digest"] != precommit["sample_digest"]
        or measurement["derived_outcome"] != observed
        or measurement["profile"] != PROFILE
        or measurement["measurement_scope"] != "SIMULATED_REDERIVED_NOT_PHYSICAL"):
        raise InvalidWorld("invalid or forged measurement result, cut or calibration profile")
    body = {k: v for k, v in measurement.items() if k != "signature"}
    if type(measurement["signature"]) is not str or not verify_p256(
        anchor["instrument_public_key"], MEASURE_DOMAIN + jcs_bytes(body), measurement["signature"]
    ):
        raise InvalidWorld("instrument measurement P-256 signature invalid")
    return observed


def assess(parent: dict, roster: dict, challenge: dict,
           statements: list, anchor: dict | None,
           precommit: dict | None, measurement: dict | None,
           *, now: int) -> dict:
    # Validate 004's actual pinned-key signed evidence before any 005 assertions.
    earlier = assess_004(parent, roster, challenge, statements, now=now)
    if anchor is None or precommit is None or measurement is None:
        if not (anchor is None and precommit is None and measurement is None):
            raise InvalidWorld("partial independently supplied evidence is not admissible")
        observed = None
        instrument_evidence = "MISSING"
    else:
        verify_precommit(parent, roster, anchor, challenge, precommit)
        observed = verify_measurement(challenge, anchor, precommit, measurement)
        instrument_evidence = "PRECOMMITTED_SIGNED_SIMULATED_RAW_SAMPLES"
    opinions = {w["role"]: w["outcome"] for w in earlier["witnesses"]}
    all_present = len(opinions) == 3
    consensus = all_present and len(set(opinions.values())) == 1
    claimed = next(iter(opinions.values())) if consensus else None
    if not consensus:
        decision = "HOLD_004_WITNESS_DISAGREEMENT_OR_MISSING"
    elif observed is None:
        decision = "HOLD_NO_PRECOMMITTED_DISTINCT_MEASUREMENT"
    elif claimed != observed:
        decision = "HOLD_COLLUDING_CLAIMS_CONFLICT_WITH_SIMULATED_MEASUREMENT"
    else:
        decision = "REVIEW_MATCHES_SIMULATED_MEASUREMENT_NOT_ADMITTED"
    result = {
        "schema": ASSESS_SCHEMA,
        "parent_proposal_digest": parent["proposal_digest"],
        "challenge_digest": digest(challenge),
        "004_assessment_digest": earlier["assessment_digest"],
        "004_disposition": earlier["disposition"],
        "source_and_observers_all_signed": all_present,
        "claimant_consensus": claimed,
        "pinned_independent_instrument_key": anchor is not None,
        "precommit_digest": digest(precommit) if precommit is not None else None,
        "measurement_digest": digest(measurement) if measurement is not None else None,
        "measurement_evidence": instrument_evidence,
        "recomputed_simulation_outcome": observed,
        "disposition": decision,
        "physical_sensor_independence_established": False,
        "independent_truth_established": False,
        "cryptographic_owner_identity_established": False,
        "owner_execution_authority": "NONE",
        "native_relatte_admission": False,
        "external_execution": False, "effects": [],
        "epistemic_note": (
            "Independent signature key plus precommitted synthetic frames checks "
            "fixture consistency, NOT real physical independence or external truth."
        ),
    }
    result["assessment_digest"] = digest(result)
    return result


def verify_replay(parent: dict, roster: dict, challenge: dict, statements: list,
                  anchor: dict | None, precommit: dict | None,
                  measurement: dict | None, receipt: Any, *, now: int) -> bool:
    if type(receipt) is not dict or type(receipt.get("assessment_digest")) is not str:
        return False
    try:
        return canonical(receipt) == canonical(
            assess(parent, roster, challenge, statements, anchor,
                   precommit, measurement, now=now)
        )
    except (ValueError, TypeError, KeyError, IdentityProfileError):
        return False


def demo() -> dict:
    """Creates ephemeral keys, never exports them and tests a signed consensus lie."""
    from unheard_choir_false_aperture import propose as parent_propose
    fixture = Path(__file__).resolve().parents[1] / "fixtures"
    parents = [fixture / x for x in (
        "unheard-choir-002/observed-world.json",
        "unheard-choir-003/field.json",
        "unheard-choir-003/untrusted-catalog.json",
        "unheard-choir-003/owner-registry.json",
        "unheard-choir-003/reviewed-history.json",
    )]
    parent = parent_propose(*(json.loads(x.read_text(encoding="utf-8")) for x in parents))
    with tempfile.TemporaryDirectory() as temp:
        names = ("owner", "source", "observer-east", "observer-west", "instrument")
        keys = {name: IdentityKey.load_or_create(Path(temp) / (name + ".pem"))
                for name in names}
        roster = roster_for(parent, keys["owner"],
                            {r: keys[r] for r in ROLES})
        anchor = make_anchor(parent, roster, keys["instrument"])
        samples = [0] * 8
        commit = signed_precommit(parent, roster, anchor, keys["instrument"],
                                  samples=samples, captured_at=900)
        challenge = make_challenge(parent, roster, keys["owner"],
                                   issued_at=1000, nonce="a" * 32)
        claims = [sign_statement(challenge, r, "PRESENT", keys[r]) for r in ROLES]
        measurement = signed_measurement(challenge, commit, samples, keys["instrument"])
        report = assess(parent, roster, challenge, claims, anchor, commit, measurement, now=1001)
        return {
            "sampled_fixture_values": samples,
            "claimants_say": "PRESENT",
            "synthetic_samples_compute": compute_outcome(samples),
            "signed_cryptographic_objects": 6,
            "disposition": report["disposition"],
            "fresh_challenge_verified": True,
            "signed_claimant_consensus": report["claimant_consensus"],
            "new_source_real_world_truth_proven": report["independent_truth_established"],
            "native_action_executed": report["external_execution"],
            "cold_replay_verified": verify_replay(
                parent, roster, challenge, claims, anchor, commit, measurement,
                report, now=1001),
        }


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "verify"))
    for item in ("parent", "roster", "challenge", "statements",
                 "anchor", "precommit", "measurement", "receipt"):
        parser.add_argument("--" + item, type=Path)
    parser.add_argument("--now", type=int)
    args = parser.parse_args()
    try:
        if args.command == "demo":
            result = demo()
        else:
            if any(getattr(args, item) is None for item in
                   ("parent", "roster", "challenge", "statements", "now")):
                parser.error("assess/verify require parent, roster, challenge, statements, now")
            base = [read(getattr(args, item)) for item in
                    ("parent", "roster", "challenge", "statements")]
            extra_paths = (args.anchor, args.precommit, args.measurement)
            if sum(item is not None for item in extra_paths) not in (0, 3):
                parser.error("provide all three evidence files or none")
            extra = [read(item) for item in extra_paths] if all(extra_paths) else [None] * 3
            if args.command == "assess":
                result = assess(*base, *extra, now=args.now)
            else:
                if args.receipt is None:
                    parser.error("verify requires --receipt")
                result = {"verified": verify_replay(*base, *extra, read(args.receipt), now=args.now)}
    except (ValueError, OSError, TypeError, KeyError, IdentityProfileError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if args.command != "verify" or result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
