#!/usr/bin/env python3
"""UNHEARD CHOIR 004 — a valid signature does not make a statement true.

No real devices, observation, GHoT dispatch, reLATTE crossing or owner identity
attestation. Uses existing GHoT P-256 verification for *real cryptographic*
signatures over explicitly fictional, simulation-only claims. Local pinning
is a supplied test trust policy, not a public-key infrastructure.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_false_aperture import propose as parent_propose
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk,
    verify_p256, particular_for_public_key,
)

ROSTER_SCHEMA = "ghot.unheard-choir-004-roster/v0"
CHALLENGE_SCHEMA = "ghot.unheard-choir-004-challenge/v0"
STATEMENT_SCHEMA = "ghot.unheard-choir-004-statement/v0"
REVIEW_SCHEMA = "ghot.unheard-choir-004-assessment/v0"
ROLES = ("source", "observer-east", "observer-west")
OUTCOMES = ("PRESENT", "EMPTY")
CHALLENGE_DOMAIN = b"GHOT-UNHEARD-CHOIR-004-CHALLENGE-v0|"
STATEMENT_DOMAIN = b"GHOT-UNHEARD-CHOIR-004-STATEMENT-v0|"
MAX_TTL = 120


def exact(value: Any, fields: set[str], what: str) -> None:
    if type(value) is not dict or set(value) != fields:
        raise InvalidWorld(f"{what}: unknown or missing fields")


def integer(value: Any, a: int, b: int, name: str) -> None:
    if type(value) is not int or not a <= value <= b:
        raise InvalidWorld(f"{name}: invalid integer")


def public_key(jwk: Any) -> dict[str, str]:
    try:
        return normalize_public_jwk(jwk)
    except (IdentityProfileError, TypeError) as err:
        raise InvalidWorld("invalid pinned P-256 key") from err


def roster_for(parent: dict, owner: IdentityKey, actors: dict[str, IdentityKey]) -> dict:
    """Only for test-local setup; does not assert human identity or permission."""
    if set(actors) != set(ROLES):
        raise InvalidWorld("exact source and two observer keys are required")
    return {
        "schema": ROSTER_SCHEMA,
        "parent_proposal_digest": parent["proposal_digest"],
        "owner_public_key": owner.public_jwk(),
        "actors": {role: actors[role].public_jwk() for role in ROLES},
        "scope": "LOCAL_SIMULATION_ONLY",
    }


def check_roster(parent: dict, roster: Any) -> None:
    exact(roster, {"schema", "parent_proposal_digest", "owner_public_key",
                   "actors", "scope"}, "roster")
    if roster["schema"] != ROSTER_SCHEMA or roster["scope"] != "LOCAL_SIMULATION_ONLY":
        raise InvalidWorld("roster cannot grant physical or native capability")
    if roster["parent_proposal_digest"] != parent["proposal_digest"]:
        raise InvalidWorld("roster does not bind current 003 proposal")
    exact(roster["actors"], set(ROLES), "pinned actors")
    identities = [public_key(roster["owner_public_key"])] + [
        public_key(roster["actors"][role]) for role in ROLES
    ]
    particulars = [particular_for_public_key(key) for key in identities]
    if len(set(particulars)) != len(particulars):
        raise InvalidWorld("source, witnesses and owner must have distinct key identities")


def make_challenge(parent: dict, roster: dict, owner_key: IdentityKey, *,
                   issued_at: int, nonce: str | None = None, ttl: int = 60) -> dict:
    check_roster(parent, roster)
    integer(issued_at, 1, 10**12, "issued_at")
    integer(ttl, 1, MAX_TTL, "ttl")
    if public_key(owner_key.public_jwk()) != public_key(roster["owner_public_key"]):
        raise InvalidWorld("issuer is not pinned challenge owner")
    token = secrets.token_hex(16) if nonce is None else nonce
    if type(token) is not str or len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        raise InvalidWorld("nonce must be a lowercase 128-bit hex challenge token")
    selected = parent["selected"]
    if selected is None:
        raise InvalidWorld("003 HOLD cannot be challenged")
    body = {
        "schema": CHALLENGE_SCHEMA,
        "parent_proposal_digest": parent["proposal_digest"],
        "roster_digest": digest(roster),
        "nonce": token, "issued_at": issued_at, "expires_at": issued_at + ttl,
        "aperture_id": selected["aperture_id"],
        "instrument_id": selected["instrument_id"],
        "owner_epoch": selected["owner_epoch"],
        "scope": "SIMULATED_CHALLENGE_ONLY",
    }
    return {**body, "signature": owner_key.sign(CHALLENGE_DOMAIN + jcs_bytes(body))}


def check_challenge(parent: dict, roster: dict, challenge: Any, now: int) -> None:
    check_roster(parent, roster)
    exact(challenge, {"schema", "parent_proposal_digest", "roster_digest",
                      "nonce", "issued_at", "expires_at", "aperture_id",
                      "instrument_id", "owner_epoch", "scope", "signature"}, "challenge")
    integer(now, 1, 10**12, "now")
    if challenge["schema"] != CHALLENGE_SCHEMA or challenge["scope"] != "SIMULATED_CHALLENGE_ONLY":
        raise InvalidWorld("challenge schema/scope mismatch")
    if type(challenge["nonce"]) is not str or len(challenge["nonce"]) != 32 or any(
        c not in "0123456789abcdef" for c in challenge["nonce"]
    ):
        raise InvalidWorld("invalid challenge nonce")
    integer(challenge["issued_at"], 1, 10**12, "challenge issued_at")
    integer(challenge["expires_at"], 1, 10**12, "challenge expires_at")
    if (challenge["expires_at"] - challenge["issued_at"] < 1
        or challenge["expires_at"] - challenge["issued_at"] > MAX_TTL
        or not challenge["issued_at"] <= now <= challenge["expires_at"]):
        raise InvalidWorld("challenge expired, future, or otherwise not fresh")
    selected = parent["selected"]
    if selected is None or (
        challenge["aperture_id"], challenge["instrument_id"], challenge["owner_epoch"]
    ) != (selected["aperture_id"], selected["instrument_id"], selected["owner_epoch"]):
        raise InvalidWorld("challenge does not bind current selected instrument incarnation")
    if challenge["parent_proposal_digest"] != parent["proposal_digest"] or challenge["roster_digest"] != digest(roster):
        raise InvalidWorld("challenge is for a different world, proposal or roster")
    body = {k: v for k, v in challenge.items() if k != "signature"}
    if type(challenge["signature"]) is not str or not verify_p256(
        roster["owner_public_key"], CHALLENGE_DOMAIN + jcs_bytes(body),
        challenge["signature"],
    ):
        raise InvalidWorld("owner challenge signature invalid")


def sign_statement(challenge: dict, role: str, outcome: str,
                   key: IdentityKey) -> dict:
    if role not in ROLES or outcome not in OUTCOMES:
        raise InvalidWorld("invalid witness role or outcome")
    body = {
        "schema": STATEMENT_SCHEMA,
        "role": role, "challenge_digest": digest(challenge),
        "outcome": outcome, "evidence_kind": "SIMULATED_SELF_REPORTED",
        "sample_ref": "simulated:" + role,
    }
    return {**body, "public_key": key.public_jwk(),
            "signature": key.sign(STATEMENT_DOMAIN + jcs_bytes(body))}


def check_statement(challenge: dict, roster: dict, statement: Any) -> dict:
    exact(statement, {"schema", "role", "challenge_digest", "outcome",
                      "evidence_kind", "sample_ref", "public_key", "signature"}, "statement")
    role = statement["role"]
    if type(role) is not str or role not in ROLES:
        raise InvalidWorld("unknown role")
    if statement["schema"] != STATEMENT_SCHEMA or statement["challenge_digest"] != digest(challenge):
        raise InvalidWorld("witness statement bound to wrong challenge")
    if statement["outcome"] not in OUTCOMES or statement["evidence_kind"] != "SIMULATED_SELF_REPORTED":
        raise InvalidWorld("unsupported evidence type/outcome")
    if statement["sample_ref"] != "simulated:" + role:
        raise InvalidWorld("unsupported or unbound sample reference")
    if public_key(statement["public_key"]) != public_key(roster["actors"][role]):
        raise InvalidWorld("untrusted signer not pinned for claimed role")
    body = {k: v for k, v in statement.items() if k not in ("public_key", "signature")}
    if type(statement["signature"]) is not str or not verify_p256(
        roster["actors"][role], STATEMENT_DOMAIN + jcs_bytes(body), statement["signature"]
    ):
        raise InvalidWorld("witness signature invalid")
    return {"role": role, "outcome": statement["outcome"],
            "source_statement_digest": digest(statement), "signature_valid": True,
            "verified_kind": "PINNED_KEY_ASSERTED_SIMULATED_OUTCOME"}


def assess(parent: dict, roster: dict, challenge: dict,
           statements: Any, *, now: int) -> dict:
    check_challenge(parent, roster, challenge, now)
    if type(statements) is not list or len(statements) > 3:
        raise InvalidWorld("too many or incorrectly shaped witness statements")
    seen: dict[str, dict] = {}
    for statement in statements:
        verified = check_statement(challenge, roster, statement)
        if verified["role"] in seen:
            raise InvalidWorld("duplicate witness role")
        seen[verified["role"]] = verified
    if len(seen) < 3:
        status = "HOLD_MISSING_INDEPENDENT_WITNESSES"
    elif seen["observer-east"]["outcome"] != seen["observer-west"]["outcome"]:
        status = "HOLD_OBSERVER_DISAGREEMENT"
    elif seen["source"]["outcome"] != seen["observer-east"]["outcome"]:
        status = "HOLD_AUTHENTIC_BUT_CONTRADICTED_SOURCE"
    else:
        status = "REVIEW_CANDIDATE_NOT_ADMITTED"
    report = {
        "schema": REVIEW_SCHEMA,
        "parent_proposal_digest": parent["proposal_digest"],
        "roster_digest": digest(roster),
        "challenge_digest": digest(challenge),
        "witnesses": [seen[role] for role in ROLES if role in seen],
        "source_signed": "source" in seen,
        "independent_observer_keys": len({particular_for_public_key(roster["actors"][role])
                                          for role in ("observer-east", "observer-west")}),
        "disposition": status,
        "source_claim_proven_true": False,
        "physical_independence_proven": False,
        "owner_identity_independently_proven": False,
        "external_execution": False, "authority": "NONE",
        "native_relattes_signed_receipt": False, "effects": [],
        "note": "Signature authenticates only attributed fictional assertion, not physical truth",
    }
    report["assessment_digest"] = digest(report)
    return report


def record_once(dbpath: Path, assessment: dict) -> dict:
    """Durable owner-local *review occurrence*, not GHoT dispatch or reLATTE admission.

    Unique challenge digest enforces one successful local recording. A fresh
    owner challenge is required for a new attempt. Repeated read-only assess
    remains available for historical reconstruction.
    """
    exact(assessment, {"schema", "parent_proposal_digest", "roster_digest",
                       "challenge_digest", "witnesses", "source_signed",
                       "independent_observer_keys", "disposition", "source_claim_proven_true",
                       "physical_independence_proven", "owner_identity_independently_proven",
                       "external_execution", "authority", "native_relattes_signed_receipt",
                       "effects", "note", "assessment_digest"}, "assessment")
    if assessment["schema"] != REVIEW_SCHEMA or assessment["assessment_digest"] != digest(
        {k: v for k, v in assessment.items() if k != "assessment_digest"}
    ):
        raise InvalidWorld("invalid assessment digest")
    if assessment["authority"] != "NONE" or assessment["effects"] != [] or assessment["external_execution"]:
        raise InvalidWorld("cannot record effectful or authoritative statement")
    with sqlite3.connect(str(dbpath), timeout=3) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS choir004_reviews "
                     "(challenge_digest TEXT PRIMARY KEY, assessment_digest TEXT NOT NULL, "
                     "disposition TEXT NOT NULL)")
        try:
            with conn:
                conn.execute("INSERT INTO choir004_reviews VALUES (?, ?, ?)",
                             (assessment["challenge_digest"], assessment["assessment_digest"],
                              assessment["disposition"]))
        except sqlite3.IntegrityError as exc:
            raise InvalidWorld("challenge already used for one local review occurrence") from exc
    return {
        "schema": "ghot.unheard-choir-004-local-review-record/v0",
        "challenge_digest": assessment["challenge_digest"],
        "assessment_digest": assessment["assessment_digest"],
        "recorded_disposition": assessment["disposition"],
        "native_effect": "NONE",
    }


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def demo() -> dict:
    """Self-contained ephemeral-key example. No identity/secret files emitted."""
    from unheard_choir_false_aperture import propose as parent_propose
    root = Path(__file__).resolve().parents[1] / "fixtures"
    p2 = root / "unheard-choir-002"
    p3 = root / "unheard-choir-003"
    args = [load(f) for f in (
        p2 / "observed-world.json", p3 / "field.json",
        p3 / "untrusted-catalog.json", p3 / "owner-registry.json",
        p3 / "reviewed-history.json",
    )]
    parent = parent_propose(*args)
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        owner = IdentityKey.load_or_create(directory / "owner.pem")
        source = IdentityKey.load_or_create(directory / "source.pem")
        east = IdentityKey.load_or_create(directory / "east.pem")
        west = IdentityKey.load_or_create(directory / "west.pem")
        roster = roster_for(parent, owner, dict(zip(ROLES, (source, east, west))))
        ch = make_challenge(parent, roster, owner, issued_at=1000, nonce="a" * 32)
        signed = [sign_statement(ch, role, result, key) for role, result, key in
                  (("source", "PRESENT", source), ("observer-east", "EMPTY", east),
                   ("observer-west", "EMPTY", west))]
        report = assess(parent, roster, ch, signed, now=1001)
        record = record_once(directory / "review.sqlite", report)
        replay_refused = False
        try:
            record_once(directory / "review.sqlite", report)
        except InvalidWorld:
            replay_refused = True
        return {
            "simulation_only": True, "p256_signatures_cryptographically_valid": 4,
            "source_stated": "PRESENT", "observers_stated": ["EMPTY", "EMPTY"],
            "disposition": report["disposition"],
            "false_claim_recognized_as_contested": True,
            "signature_proves_truth": False,
            "independent_hardware_proven": False,
            "local_replay_blocked": replay_refused,
            "signed_native_crossing": False,
            "external_execution": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "record"))
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--challenge", type=Path)
    parser.add_argument("--statements", type=Path)
    parser.add_argument("--now", type=int)
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "demo":
            result = demo()
        else:
            if any(getattr(args, x) is None for x in
                   ("parent", "roster", "challenge", "statements", "now")):
                parser.error("assess/record require --parent, --roster, --challenge, --statements and --now")
            report = assess(load(args.parent), load(args.roster), load(args.challenge),
                            load(args.statements), now=args.now)
            if args.command == "record":
                if args.db is None:
                    parser.error("record requires --db")
                result = record_once(args.db, report)
            else:
                result = report
    except (InvalidWorld, ValueError, OSError, TypeError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
