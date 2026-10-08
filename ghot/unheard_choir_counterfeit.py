#!/usr/bin/env python3
"""UNHEARD CHOIR 006 — counterfeit instrument / declared multimodal custody.

A correctly signed but corrupted primary fixture can be contradicted by a
separately keyed, differently mapped simulated modality with independently
signed *claims* of custody. Shared declared dependencies force HOLD. This is
not physical sensor verification, secure hardware attestation, custody proof,
owner authentication, or authority to act.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_collusion import (
    assess as assess_005, make_anchor, signed_precommit, signed_measurement,
)
from unheard_choir_lying_witness import (
    ROLES, make_challenge, roster_for, sign_statement, check_challenge,
)
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk,
    particular_for_public_key, verify_p256,
)

PIN_SCHEMA = "ghot.unheard-choir-006-owner-pinset/v0"
CUSTODY_SCHEMA = "ghot.unheard-choir-006-custody-claim/v0"
SECOND_SCHEMA = "ghot.unheard-choir-006-secondary-sample/v0"
REPORT_SCHEMA = "ghot.unheard-choir-006-counterfeit-assessment/v0"
PIN_DOMAIN = b"GHOT-UNHEARD-CHOIR-006-PINS-v0|"
CUSTODY_DOMAIN = b"GHOT-UNHEARD-CHOIR-006-CUSTODY-v0|"
SECOND_DOMAIN = b"GHOT-UNHEARD-CHOIR-006-SECOND-v0|"
A_MODALITY = "SIMULATED_OCCUPANCY_ANY_NONZERO_V0"
B_MODALITY = "SIMULATED_THERMAL_TWO_FRAMES_ABOVE_127_V0"
DOMAINS = ("primary", "secondary")


def exact(value: Any, fields: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != fields:
        raise InvalidWorld(f"{label}: missing or extra keys")


def integer(value: Any, minimum: int, maximum: int, label: str) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidWorld(f"{label}: integer outside allowed range")


def jwk(value: Any) -> dict[str, str]:
    try:
        return normalize_public_jwk(value)
    except (IdentityProfileError, TypeError, ValueError) as exc:
        raise InvalidWorld("invalid P-256 key") from exc


def particular(key: Any) -> str:
    return particular_for_public_key(jwk(key))


def verify_signature(key: Any, domain: bytes, body: dict, signed: Any, label: str) -> None:
    if type(signed) is not str or not verify_p256(jwk(key), domain + jcs_bytes(body), signed):
        raise InvalidWorld(label + ": invalid P-256 signature")


def dependencies(value: Any) -> list[str]:
    if type(value) is not list or not 1 <= len(value) <= 8:
        raise InvalidWorld("dependencies: 1..8 declared roots required")
    if any(type(x) is not str or not x.startswith("fixture-") or
           len(x) > 48 or not all(c.islower() or c.isdigit() or c == "-" for c in x)
           for x in value):
        raise InvalidWorld("invalid simulated dependency root")
    if len(set(value)) != len(value) or value != sorted(value):
        raise InvalidWorld("dependency roots must be unique and sorted")
    return value


def validate_frames(frames: Any) -> None:
    if type(frames) is not list or len(frames) != 8:
        raise InvalidWorld("secondary frame profile requires exactly eight values")
    for value in frames:
        integer(value, 0, 255, "secondary raw frame")


def map_secondary(frames: list[int]) -> str:
    """Different deliberately invented calibration from 005 ANY_NONZERO."""
    validate_frames(frames)
    return "PRESENT" if sum(value >= 128 for value in frames) >= 2 else "EMPTY"


def make_pinset(parent: dict, roster: dict, challenge: dict, primary_anchor: dict,
                owner: IdentityKey, primary_custodian: IdentityKey,
                secondary_custodian: IdentityKey, secondary_sensor: IdentityKey,
                *, primary_roots: list[str], secondary_roots: list[str],
                secondary_epoch: int = 2) -> dict:
    check_challenge(parent, roster, challenge, challenge["issued_at"])
    integer(secondary_epoch, 0, 999999, "secondary epoch")
    primary_roots, secondary_roots = dependencies(primary_roots), dependencies(secondary_roots)
    if jwk(owner.public_jwk()) != jwk(roster["owner_public_key"]):
        raise InvalidWorld("owner pinset signature key not current")
    actor_keys = [roster["owner_public_key"]] + [roster["actors"][r] for r in ROLES]
    primary_key = primary_anchor["instrument_public_key"]
    identity_keys = actor_keys + [primary_key, primary_custodian.public_jwk(),
                                  secondary_custodian.public_jwk(), secondary_sensor.public_jwk()]
    if len({particular(x) for x in identity_keys}) != len(identity_keys):
        raise InvalidWorld("pinset keys must be different from every prior role")
    body = {
        "schema": PIN_SCHEMA, "scope": "SIMULATION_ONLY_NOT_HARDWARE_ATTESTATION",
        "parent_proposal_digest": parent["proposal_digest"],
        "challenge_digest": digest(challenge),
        "004_roster_digest": digest(roster),
        "005_primary_anchor_digest": digest(primary_anchor),
        "channels": {
            "primary": {
                "modality": A_MODALITY,
                "instrument_id": primary_anchor["instrument_id"],
                "instrument_epoch": primary_anchor["instrument_epoch"],
                "instrument_public_key": primary_key,
                "custodian_public_key": primary_custodian.public_jwk(),
                "dependency_roots": primary_roots,
            },
            "secondary": {
                "modality": B_MODALITY,
                "instrument_id": "thermal-simulation-fixture",
                "instrument_epoch": secondary_epoch,
                "instrument_public_key": secondary_sensor.public_jwk(),
                "custodian_public_key": secondary_custodian.public_jwk(),
                "dependency_roots": secondary_roots,
            },
        },
    }
    return {**body, "signature": owner.sign(PIN_DOMAIN + jcs_bytes(body))}


def validate_pinset(parent: dict, roster: dict, challenge: dict,
                    primary_anchor: dict, pinset: Any) -> None:
    check_challenge(parent, roster, challenge, challenge["issued_at"])
    exact(pinset, {
        "schema", "scope", "parent_proposal_digest", "challenge_digest",
        "004_roster_digest", "005_primary_anchor_digest", "channels", "signature",
    }, "pinset")
    if (pinset["schema"] != PIN_SCHEMA
        or pinset["scope"] != "SIMULATION_ONLY_NOT_HARDWARE_ATTESTATION"
        or pinset["parent_proposal_digest"] != parent["proposal_digest"]
        or pinset["challenge_digest"] != digest(challenge)
        or pinset["004_roster_digest"] != digest(roster)
        or pinset["005_primary_anchor_digest"] != digest(primary_anchor)):
        raise InvalidWorld("pinset not bound to exact owner challenge/roster/005 anchor")
    exact(pinset["channels"], set(DOMAINS), "pinset channels")
    p, s = pinset["channels"]["primary"], pinset["channels"]["secondary"]
    fields = {"modality", "instrument_id", "instrument_epoch", "instrument_public_key",
              "custodian_public_key", "dependency_roots"}
    exact(p, fields, "primary pin")
    exact(s, fields, "secondary pin")
    if (p["modality"] != A_MODALITY or s["modality"] != B_MODALITY
        or p["instrument_id"] != primary_anchor["instrument_id"]
        or p["instrument_epoch"] != primary_anchor["instrument_epoch"]
        or p["instrument_public_key"] != primary_anchor["instrument_public_key"]
        or s["instrument_id"] != "thermal-simulation-fixture"):
        raise InvalidWorld("instrument pins or modalities wrong")
    for item in (p, s):
        integer(item["instrument_epoch"], 0, 999999, "instrument epoch")
        dependencies(item["dependency_roots"])
    actor_keys = [roster["owner_public_key"]] + [roster["actors"][r] for r in ROLES]
    all_keys = actor_keys + [p["instrument_public_key"], s["instrument_public_key"],
                             p["custodian_public_key"], s["custodian_public_key"]]
    if len({particular(x) for x in all_keys}) != len(all_keys):
        raise InvalidWorld("two instruments and two custodians must have distinct pinned keys")
    body = {k: v for k, v in pinset.items() if k != "signature"}
    verify_signature(roster["owner_public_key"], PIN_DOMAIN, body, pinset["signature"],
                     "pinset owner")


def sign_custody(pinset: dict, challenge: dict, channel: str,
                 measurement_digest: str, custodian: IdentityKey,
                 *, declared_acquired_at: int) -> dict:
    if channel not in DOMAINS:
        raise InvalidWorld("invalid custody channel")
    integer(declared_acquired_at, 1, 10**12, "declared acquisition time")
    pin = pinset["channels"][channel]
    if jwk(custodian.public_jwk()) != jwk(pin["custodian_public_key"]):
        raise InvalidWorld("custody signer not pinned")
    body = {
        "schema": CUSTODY_SCHEMA, "scope": "SIGNED_SIMULATION_CUSTODY_CLAIM_ONLY",
        "challenge_digest": digest(challenge), "pinset_digest": digest(pinset),
        "channel": channel, "modality": pin["modality"],
        "instrument_id": pin["instrument_id"],
        "instrument_epoch": pin["instrument_epoch"],
        "instrument_public_key": pin["instrument_public_key"],
        "measurement_digest": measurement_digest,
        "dependency_roots": pin["dependency_roots"],
        "declared_acquired_at": declared_acquired_at,
    }
    return {**body, "signature": custodian.sign(CUSTODY_DOMAIN + jcs_bytes(body))}


def check_custody(pinset: dict, challenge: dict, channel: str,
                  measurement_digest: str, custody: Any) -> None:
    if channel not in DOMAINS:
        raise InvalidWorld("unknown custody channel")
    exact(custody, {
        "schema", "scope", "challenge_digest", "pinset_digest",
        "channel", "modality", "instrument_id", "instrument_epoch",
        "instrument_public_key", "measurement_digest", "dependency_roots",
        "declared_acquired_at", "signature",
    }, "custody claim")
    p = pinset["channels"][channel]
    expected = {
        "schema": CUSTODY_SCHEMA, "scope": "SIGNED_SIMULATION_CUSTODY_CLAIM_ONLY",
        "challenge_digest": digest(challenge), "pinset_digest": digest(pinset),
        "channel": channel, "modality": p["modality"],
        "instrument_id": p["instrument_id"], "instrument_epoch": p["instrument_epoch"],
        "instrument_public_key": p["instrument_public_key"],
        "measurement_digest": measurement_digest,
        "dependency_roots": p["dependency_roots"],
    }
    for k, v in expected.items():
        if custody[k] != v:
            raise InvalidWorld("custody assertion cannot be rebound to other evidence")
    integer(custody["declared_acquired_at"], 1, 10**12, "custody acquired_at")
    if custody["declared_acquired_at"] > challenge["expires_at"]:
        raise InvalidWorld("custody timing outside bounded challenge window")
    body = {k: v for k, v in custody.items() if k != "signature"}
    verify_signature(p["custodian_public_key"], CUSTODY_DOMAIN, body,
                     custody["signature"], "custody")


def sign_secondary(pinset: dict, challenge: dict, frames: list[int],
                   instrument: IdentityKey) -> dict:
    validate_frames(frames)
    p = pinset["channels"]["secondary"]
    if jwk(instrument.public_jwk()) != jwk(p["instrument_public_key"]):
        raise InvalidWorld("secondary signer not pinned")
    body = {
        "schema": SECOND_SCHEMA, "scope": "SIGNED_SIMULATED_THERMAL_FRAMES_ONLY",
        "challenge_digest": digest(challenge), "pinset_digest": digest(pinset),
        "instrument_id": p["instrument_id"],
        "instrument_epoch": p["instrument_epoch"],
        "modality": p["modality"], "frames": frames, "frame_digest": digest(frames),
        "claimed_outcome": map_secondary(frames),
    }
    return {**body, "signature": instrument.sign(SECOND_DOMAIN + jcs_bytes(body))}


def check_secondary(pinset: dict, challenge: dict, measurement: Any) -> str:
    exact(measurement, {
        "schema", "scope", "challenge_digest", "pinset_digest",
        "instrument_id", "instrument_epoch", "modality",
        "frames", "frame_digest", "claimed_outcome", "signature",
    }, "secondary measurement")
    frames = measurement["frames"]
    mapped = map_secondary(frames)
    p = pinset["channels"]["secondary"]
    expected = {
        "schema": SECOND_SCHEMA, "scope": "SIGNED_SIMULATED_THERMAL_FRAMES_ONLY",
        "challenge_digest": digest(challenge), "pinset_digest": digest(pinset),
        "instrument_id": p["instrument_id"], "instrument_epoch": p["instrument_epoch"],
        "modality": p["modality"], "frame_digest": digest(frames),
        "claimed_outcome": mapped,
    }
    for k, v in expected.items():
        if measurement[k] != v:
            raise InvalidWorld("secondary evidence has forged binding or calibration")
    body = {k: v for k, v in measurement.items() if k != "signature"}
    verify_signature(p["instrument_public_key"], SECOND_DOMAIN, body,
                     measurement["signature"], "secondary instrument")
    return mapped


def assess(parent: dict, roster: dict, challenge: dict, statements: list,
           primary_anchor: dict, primary_precommit: dict, primary_measurement: dict,
           pinset: dict | None, primary_custody: dict | None,
           secondary_custody: dict | None, secondary_measurement: dict | None,
           *, now: int) -> dict:
    # The parent engine validates signed claimants and primary measurement.
    inherited = assess_005(parent, roster, challenge, statements, primary_anchor,
                           primary_precommit, primary_measurement, now=now)
    if all(v is None for v in (pinset, primary_custody, secondary_custody,
                               secondary_measurement)):
        status = "HOLD_NO_INDEPENDENT_CUSTODY_OR_SECONDARY_MODALITY"
        secondary_result = None
        roots_p, roots_s = [], []
        custody_digests = []
        secondary_digest = None
        custody_verified = False
    else:
        if any(v is None for v in (pinset, primary_custody, secondary_custody,
                                   secondary_measurement)):
            raise InvalidWorld("partial counterfeit-instrument evidence not admissible")
        validate_pinset(parent, roster, challenge, primary_anchor, pinset)
        check_custody(pinset, challenge, "primary", digest(primary_measurement),
                      primary_custody)
        check_custody(pinset, challenge, "secondary", digest(secondary_measurement),
                      secondary_custody)
        secondary_result = check_secondary(pinset, challenge, secondary_measurement)
        roots_p = pinset["channels"]["primary"]["dependency_roots"]
        roots_s = pinset["channels"]["secondary"]["dependency_roots"]
        custody_digests = [digest(primary_custody), digest(secondary_custody)]
        secondary_digest = digest(secondary_measurement)
        custody_verified = True
        if set(roots_p).intersection(roots_s):
            status = "HOLD_DECLARED_SHARED_DEPENDENCY"
        elif inherited["disposition"] != "REVIEW_MATCHES_SIMULATED_MEASUREMENT_NOT_ADMITTED":
            status = "HOLD_PARENT005_EVIDENCE_OR_CLAIM"
        elif inherited["recomputed_simulation_outcome"] != secondary_result:
            status = "HOLD_COUNTERFEIT_OR_CALIBRATION_CONFLICT_UNRESOLVED"
        else:
            status = "REVIEW_DECLARED_DISTINCT_MODALITIES_CONCORDANT_NOT_ADMITTED"
    report = {
        "schema": REPORT_SCHEMA, "parent_proposal_digest": parent["proposal_digest"],
        "challenge_digest": digest(challenge),
        "005_assessment_digest": inherited["assessment_digest"],
        "005_disposition": inherited["disposition"],
        "primary_simulated_outcome": inherited["recomputed_simulation_outcome"],
        "secondary_simulated_outcome": secondary_result,
        "pinset_digest": digest(pinset) if pinset is not None else None,
        "custody_claim_digests": custody_digests,
        "secondary_measurement_digest": secondary_digest,
        "declared_primary_dependencies": roots_p,
        "declared_secondary_dependencies": roots_s,
        "signed_custody_claims_verified": custody_verified,
        "decision": status,
        "signed_receipts_are_physical_custody_proof": False,
        "two_distinct_keys_are_physical_independence": False,
        "compromised_sensor_identified": False,
        "physical_truth_established": False,
        "independent_custody_proven": False,
        "native_relatte_signed_crossing": False,
        "external_execution": False, "authority": "NONE", "effects": [],
        "note": "Conflicting or agreeing toy modalities cannot authenticate hardware, independence or world truth.",
    }
    report["assessment_digest"] = digest(report)
    return report


def verify_replay(parent: dict, roster: dict, challenge: dict, statements: list,
                  primary_anchor: dict, primary_precommit: dict, primary_measurement: dict,
                  pinset: dict | None, primary_custody: dict | None,
                  secondary_custody: dict | None, secondary_measurement: dict | None,
                  report: Any, *, now: int) -> bool:
    if type(report) is not dict or type(report.get("assessment_digest")) is not str:
        return False
    try:
        return canonical(report) == canonical(assess(
            parent, roster, challenge, statements, primary_anchor,
            primary_precommit, primary_measurement, pinset, primary_custody,
            secondary_custody, secondary_measurement, now=now,
        ))
    except (ValueError, TypeError, KeyError, IdentityProfileError):
        return False


def demo() -> dict:
    """Fixture-only adversary knows the primary sensor's real signing key."""
    from unheard_choir_false_aperture import propose as parent_propose
    root = Path(__file__).resolve().parents[1] / "fixtures"
    files = [root / x for x in (
        "unheard-choir-002/observed-world.json",
        "unheard-choir-003/field.json",
        "unheard-choir-003/untrusted-catalog.json",
        "unheard-choir-003/owner-registry.json",
        "unheard-choir-003/reviewed-history.json",
    )]
    parent = parent_propose(*(json.loads(x.read_text(encoding="utf-8")) for x in files))
    with tempfile.TemporaryDirectory() as tmp:
        names = ("owner", "source", "observer-east", "observer-west",
                 "primary-instrument", "primary-custodian",
                 "secondary-instrument", "secondary-custodian")
        keys = {n: IdentityKey.load_or_create(Path(tmp) / (n + ".pem")) for n in names}
        roster = roster_for(parent, keys["owner"], {r: keys[r] for r in ROLES})
        ch = make_challenge(parent, roster, keys["owner"], issued_at=1000, nonce="a" * 32)
        claims = [sign_statement(ch, r, "PRESENT", keys[r]) for r in ROLES]
        primary_anchor = make_anchor(parent, roster, keys["primary-instrument"])
        # Attacker controls primary private key: validly signs counterfeit PRESENT samples.
        counterfeit = [1] * 8
        prior = signed_precommit(parent, roster, primary_anchor,
                                 keys["primary-instrument"], samples=counterfeit, captured_at=900)
        primary = signed_measurement(ch, prior, counterfeit, keys["primary-instrument"])
        pins = make_pinset(parent, roster, ch, primary_anchor, keys["owner"],
                           keys["primary-custodian"], keys["secondary-custodian"],
                           keys["secondary-instrument"],
                           primary_roots=["fixture-bus-primary"],
                           secondary_roots=["fixture-source-secondary"])
        measured_secondary = sign_secondary(pins, ch, [0] * 8, keys["secondary-instrument"])
        held_primary = sign_custody(pins, ch, "primary", digest(primary),
                                    keys["primary-custodian"], declared_acquired_at=1000)
        held_secondary = sign_custody(pins, ch, "secondary", digest(measured_secondary),
                                      keys["secondary-custodian"], declared_acquired_at=1000)
        args = (parent, roster, ch, claims, primary_anchor, prior, primary,
                pins, held_primary, held_secondary, measured_secondary)
        report = assess(*args, now=1001)
        return {
            "simulated_primary_compromised_key_used": True,
            "signed_claimants": "PRESENT", "primary_sensor": "PRESENT",
            "secondary_sensor": "EMPTY",
            "primary_custody_signature_valid": True,
            "secondary_custody_signature_valid": True,
            "decision": report["decision"], "review": "HOLD",
            "real_world_truth_proven": report["physical_truth_established"],
            "independent_custody_proven": report["independent_custody_proven"],
            "external_execution": report["external_execution"],
            "cold_replay_verified": verify_replay(*args, report, now=1001),
        }


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "verify"))
    fields = ("parent", "roster", "challenge", "statements", "primary_anchor",
              "primary_precommit", "primary_measurement", "pinset",
              "primary_custody", "secondary_custody", "secondary_measurement")
    for item in fields + ("receipt",):
        parser.add_argument("--" + item.replace("_", "-"), type=Path)
    parser.add_argument("--now", type=int)
    args = parser.parse_args()
    try:
        if args.command == "demo":
            result = demo()
        else:
            required = fields[:7]
            if any(getattr(args, x) is None for x in required) or args.now is None:
                parser.error("assess/verify require first seven evidence files and --now")
            args0 = [read(getattr(args, x)) for x in required]
            optional = [getattr(args, x) for x in fields[7:]]
            if sum(x is not None for x in optional) not in (0, 4):
                parser.error("all four 006 inputs or none required")
            args0 += [read(x) for x in optional] if all(optional) else [None] * 4
            if args.command == "assess":
                result = assess(*args0, now=args.now)
            else:
                if args.receipt is None:
                    parser.error("verify needs --receipt")
                result = {"verified": verify_replay(*args0, read(args.receipt), now=args.now)}
    except (ValueError, OSError, KeyError, TypeError, IdentityProfileError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if args.command != "verify" or result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
