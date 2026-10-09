#!/usr/bin/env python3
"""WORLD-ASKS-BACK-001: signed, fixture-only discovery-to-work composition.

No hardware, network, RF, printer, payments, or outside-world effects.
Three local fixture identities are separate owners; signatures attest claims,
not their truth. Uses GHoT's reLATTE v0 signing profile, not a live receiver.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from ghot.relatte_identity import (
        IdentityKey, jcs_bytes, particular_for_public_key, sign_crossing,
        sign_receipt, verify_crossing, verify_p256, verify_receipt,
    )
except ModuleNotFoundError:
    from relatte_identity import (
        IdentityKey, jcs_bytes, particular_for_public_key, sign_crossing,
        sign_receipt, verify_crossing, verify_p256, verify_receipt,
    )

SCHEMA = "ghot.world-asks-back/v0"
EPOCH = 1
SIMULATED_TIME = "2026-01-01T00:00:00.000Z"  # fixture clock, not wall-clock evidence
CLAIM_DOMAIN = b"GHOT-WAB001-CLAIM|"
GRANT_DOMAIN = b"GHOT-WAB001-GRANT|"
ROLES = ("household", "fabricator", "stockist")
SCOPES = {
    "household": "simulate-repair-my-hinge",
    "fabricator": "simulate-printer-and-design-use",
    "stockist": "simulate-material-consumption",
}
# Instruments are read-only projections from signed local fixture declarations,
# NOT sensors, not listening devices, not hardware discovery.
INSTRUMENTS = (
    ("condition", "household", "asset"),
    ("fit", "household", "fit"),
    ("priority", "household", "urgency"),
    ("privacy", "household", "privacy"),
    ("acceptance", "household", "acceptance"),
    ("printer", "fabricator", "printer"),
    ("energy", "fabricator", "energy_units"),
    ("designs", "fabricator", "designs"),
    ("material", "stockist", "stock"),
    ("source", "stockist", "sources"),
    ("route", "stockist", "routes"),
)
MODES = ("print", "reuse", "borrow", "buy", "weld", "cut", "glue",
         "mill", "cast", "wait", "report")
MASS_G = 12
ENERGY_UNITS = 3


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(jcs_bytes(value)).hexdigest()


def signed_claim(role: str, state: dict, key: IdentityKey) -> dict:
    body = {
        "schema": "ghot.wab-claim/v0", "node": role, "epoch": EPOCH,
        "state": copy.deepcopy(state), "public_key": key.public_jwk(),
    }
    return {**body, "signature": key.sign(CLAIM_DOMAIN + jcs_bytes(body))}


def checked_claim(claim: dict, role: str, pinned: dict) -> dict:
    if not isinstance(claim, dict) or set(claim) != {
        "schema", "node", "epoch", "state", "public_key", "signature"
    }:
        raise ValueError("INVALID_CLAIM_SHAPE")
    if claim["schema"] != "ghot.wab-claim/v0" or claim["node"] != role or claim["epoch"] != EPOCH:
        raise ValueError("WRONG_CLAIM_CUT")
    if claim["public_key"] != pinned[role]:
        raise ValueError("CLAIM_SIGNER_NOT_PINNED")
    body = {k: v for k, v in claim.items() if k != "signature"}
    if not verify_p256(pinned[role], CLAIM_DOMAIN + jcs_bytes(body), claim["signature"]):
        raise ValueError("BAD_CLAIM_SIGNATURE")
    if not isinstance(claim["state"], dict):
        raise ValueError("INVALID_STATE")
    return claim["state"]


def observe(claims: dict, pinned: dict) -> dict:
    if not isinstance(claims, dict) or set(claims) != set(ROLES):
        raise ValueError("THREE_NODES_REQUIRED")
    if not isinstance(pinned, dict) or set(pinned) != set(ROLES):
        raise ValueError("THREE_OWNER_PINS_REQUIRED")
    if len({digest(pinned[r]) for r in ROLES}) != len(ROLES):
        raise ValueError("SIGNERS_MUST_BE_INDEPENDENT")
    states = {r: checked_claim(claims[r], r, pinned) for r in ROLES}
    try:
        lenses = [
            {"instrument": name, "source": role, "value": copy.deepcopy(states[role][field])}
            for name, role, field in INSTRUMENTS
        ]
    except KeyError as exc:
        raise ValueError("MISSING_INSTRUMENT_SOURCE") from exc
    return {"cut": digest({"claims": claims, "pins": pinned}),
            "instruments": lenses, "states": states}


def compose(claims: dict, pinned: dict) -> dict:
    observed = observe(claims, pinned)
    h, f, s = (observed["states"][r] for r in ROLES)
    feasible = (
        h["asset"] == {"part": "hinge-a", "state": "missing"}
        and h["fit"] == "hinge-a" and h["privacy"] == "local-only"
        and h["acceptance"] == "fixture-geometry-check"
        and isinstance(h["urgency"], int) and not isinstance(h["urgency"], bool)
        and h["urgency"] > 0
        and f["printer"] == "idle"
        and isinstance(f["energy_units"], int) and not isinstance(f["energy_units"], bool)
        and f["energy_units"] >= ENERGY_UNITS
        and isinstance(f["designs"], list) and "hinge-a" in f["designs"]
        and isinstance(s["stock"], dict)
        and isinstance(s["stock"].get("PLA"), int)
        and not isinstance(s["stock"]["PLA"], bool)
        and s["stock"]["PLA"] >= MASS_G
        and "PLA-local" in s["sources"]
        and "local-pickup" in s["routes"]
    )
    # Generate eleven possible responses. Ten require capabilities not offered
    # by this cut, and cannot win merely because they sound helpful.
    options = [
        {"mode": mode, "eligible": bool(feasible and mode == "print"),
         "why": "all-eleven-readings-support-fixture-print"
                if feasible and mode == "print" else "capability-or-constraint-not-established"}
        for mode in MODES
    ]
    selected = next((opt["mode"] for opt in options if opt["eligible"]), None)
    proposal_body = {
        "schema": "ghot.wab-proposal/v0", "cut": observed["cut"],
        "origin": "inferred-from-condition-not-assigned-task",
        "task_request_present": False,
        "status": "PROPOSED" if selected else "HOLD",
        "selected": selected,
        "asset": "hinge-a", "material": "PLA", "mass_g": MASS_G,
        "energy_units": ENERGY_UNITS,
        "options": options,
        "instrument_digest": digest(observed["instruments"]),
        "semantic_effect": "none",
    }
    return {**proposal_body, "proposal_id": "wab-proposal:" + digest(proposal_body)}


def grant(role: str, proposal: dict, key: IdentityKey) -> dict:
    if role not in ROLES:
        raise ValueError("UNKNOWN_GRANT_ROLE")
    body = {
        "schema": "ghot.wab-grant/v0", "role": role, "epoch": EPOCH,
        "proposal_id": proposal["proposal_id"], "cut": proposal["cut"],
        "scope": SCOPES[role], "decision": "APPROVE_SIMULATION",
        "public_key": key.public_jwk(),
    }
    return {**body, "signature": key.sign(GRANT_DOMAIN + jcs_bytes(body))}


def checked_grants(grants: dict, proposal: dict, pinned: dict) -> None:
    if not isinstance(grants, dict) or set(grants) != set(ROLES):
        raise ValueError("THREE_EXACT_GRANTS_REQUIRED")
    for role in ROLES:
        g = grants[role]
        if not isinstance(g, dict) or set(g) != {
            "schema", "role", "epoch", "proposal_id", "cut", "scope",
            "decision", "public_key", "signature",
        }:
            raise ValueError("INVALID_GRANT_SHAPE")
        if (g["schema"] != "ghot.wab-grant/v0" or g["role"] != role
                or g["epoch"] != EPOCH or g["proposal_id"] != proposal["proposal_id"]
                or g["cut"] != proposal["cut"] or g["scope"] != SCOPES[role]
                or g["decision"] != "APPROVE_SIMULATION" or g["public_key"] != pinned[role]):
            raise ValueError("GRANT_NOT_EXACT_OR_CURRENT")
        body = {k: v for k, v in g.items() if k != "signature"}
        if not verify_p256(pinned[role], GRANT_DOMAIN + jcs_bytes(body), g["signature"]):
            raise ValueError("BAD_GRANT_SIGNATURE")


def expected_artifact(proposal: dict, states: dict) -> dict:
    return {
        "schema": "ghot.wab-virtual-part/v0",
        "simulated": True, "source_proposal": proposal["proposal_id"],
        "part": "hinge-a", "material": "PLA",
        "virtual_printed_mass_g": MASS_G,
        "virtual_remaining_stock_g": states["stockist"]["stock"]["PLA"] - MASS_G,
        "virtual_energy_remaining": states["fabricator"]["energy_units"] - ENERGY_UNITS,
        "fixture_fit_check": "PASS",
        "physical_part_produced": False,
        "physical_repair_completed": False,
        "economic_credit": 0,
    }


def make_receipt(crossing: dict, key: IdentityKey, kind: str,
                 effect: str, post: str | None = None) -> dict:
    return sign_receipt({
        "schema": "relatte.receipt/v0",
        "crossing_id": crossing["crossing_id"],
        "world_id": "world:ghot:synthetic-fabricator",
        "receiver_particular": key.particular(),
        "kind": kind, "semantic_effect": effect,
        "post_state_ref": post,
        "created_at": SIMULATED_TIME,
        "note": "WORLD-ASKS-BACK-001 fixture only; no physical work",
        "extensions": {"world_asks_back": {"synthetic": True,
                        "physical_execution": False,
                        "economic_credit": 0}},
    }, key)


def assemble(claims: dict, pinned: dict, keys: dict, grants: dict) -> dict:
    proposal = compose(claims, pinned)
    if proposal["selected"] is None:
        return {"schema": SCHEMA, "status": "HOLD_NO_FEASIBLE_WORK",
                "proposal": proposal, "claims": claims, "pinned": pinned,
                "grants": grants}
    crossing = sign_crossing({
        "schema": "relatte.crossing-envelope/v0", "protocol_version": "0",
        "source_particular": keys["household"].particular(),
        "source_world": "world:ghot:synthetic-household",
        "declared_kind": "synthetic-repair-proposal",
        "payload_refs": [{"address": digest(proposal), "role": "proposal"}],
        "requested_effect": {"action": "simulate-hinge-print", "scope": "fixture-only"},
        "created_at": SIMULATED_TIME,
        "extensions": {"world_asks_back": {"synthetic": True,
                        "proposal_id": proposal["proposal_id"], "cut": proposal["cut"]}},
    }, keys["household"])
    received = make_receipt(crossing, keys["fabricator"], "RECEIVED", "none")
    packet = {
        "schema": SCHEMA, "status": "HOLD_AWAITING_GRANTS",
        "claims": claims, "pinned": pinned, "proposal": proposal,
        "grants": grants, "crossing": crossing, "received": received,
        "disposition": make_receipt(crossing, keys["fabricator"], "HELD", "none"),
        "artifact": None,
    }
    try:
        checked_grants(grants, proposal, pinned)
    except ValueError:
        return packet
    artifact = expected_artifact(proposal, observe(claims, pinned)["states"])
    packet.update({
        "status": "SIMULATED_PART_CREATED",
        "artifact": artifact,
        "disposition": make_receipt(crossing, keys["fabricator"], "EXECUTED",
                                     "artifact-created", digest(artifact)),
    })
    return packet


def verify(packet: dict) -> bool:
    """Cold verifier uses public evidence only; never accepts self-asserted success."""
    if not isinstance(packet, dict) or packet.get("schema") != SCHEMA:
        raise ValueError("WRONG_PACKET_SCHEMA")
    proposal = compose(packet["claims"], packet["pinned"])
    if packet["proposal"] != proposal:
        raise ValueError("FORGED_OR_STALE_PROPOSAL")
    if proposal["selected"] is None:
        if (packet.get("status") != "HOLD_NO_FEASIBLE_WORK"
                or set(packet) != {"schema", "status", "proposal", "claims", "pinned", "grants"}):
            raise ValueError("INFEASIBLE_WORK_CANNOT_EXECUTE")
        return True
    if set(packet) != {
        "schema", "status", "claims", "pinned", "proposal", "grants",
        "crossing", "received", "disposition", "artifact",
    }:
        raise ValueError("INVALID_PACKET_SHAPE")
    crossing = packet["crossing"]
    if (not verify_crossing(crossing)
            or crossing["signing"]["public_key"] != packet["pinned"]["household"]
            or crossing["source_particular"] != particular_for_public_key(packet["pinned"]["household"])
            or crossing["source_world"] != "world:ghot:synthetic-household"
            or crossing["declared_kind"] != "synthetic-repair-proposal"
            or crossing["requested_effect"] != {"action": "simulate-hinge-print", "scope": "fixture-only"}
            or crossing["payload_refs"] != [{"address": digest(proposal), "role": "proposal"}]
            or crossing.get("extensions") != {"world_asks_back": {
                "synthetic": True, "proposal_id": proposal["proposal_id"], "cut": proposal["cut"]}}):
        raise ValueError("CROSSING_IDENTITY_OR_INTENT_FAILURE")
    for r in (packet["received"], packet["disposition"]):
        if (not verify_receipt(r,
                    expected_public_key=packet["pinned"]["fabricator"],
                    expected_receiver_particular=particular_for_public_key(packet["pinned"]["fabricator"]))
                or r["crossing_id"] != crossing["crossing_id"]
                or r["world_id"] != "world:ghot:synthetic-fabricator"
                or r.get("extensions") != {"world_asks_back": {
                    "synthetic": True, "physical_execution": False, "economic_credit": 0}}):
            raise ValueError("RECEIPT_NOT_BOUND_TO_RECEIVER")
    if (packet["received"]["kind"], packet["received"]["semantic_effect"]) != ("RECEIVED", "none"):
        raise ValueError("RECEIVE_IS_NOT_EXECUTION")
    try:
        checked_grants(packet["grants"], proposal, packet["pinned"])
        approved = True
    except ValueError:
        approved = False
    receipt = packet["disposition"]
    if not approved:
        if (packet["status"] != "HOLD_AWAITING_GRANTS" or packet["artifact"] is not None
                or (receipt["kind"], receipt["semantic_effect"]) != ("HELD", "none")
                or receipt.get("post_state_ref") is not None):
            raise ValueError("UNAUTHORIZED_EFFECT")
        return True
    artifact = expected_artifact(proposal, observe(packet["claims"], packet["pinned"])["states"])
    if (packet["status"] != "SIMULATED_PART_CREATED"
            or packet["artifact"] != artifact
            or (receipt["kind"], receipt["semantic_effect"]) != ("EXECUTED", "artifact-created")
            or receipt.get("post_state_ref") != digest(artifact)):
        raise ValueError("VIRTUAL_CONSEQUENCE_MISMATCH")
    return True


def demo(home: Path, *, approve: bool = True, stock: int = 30) -> dict:
    """Fixture setup simulates human owners signing exact grants only on opt-in."""
    home.mkdir(parents=True, exist_ok=True)
    keys = {role: IdentityKey.load_or_create(home / (role + ".pem")) for role in ROLES}
    pinned = {role: keys[role].public_jwk() for role in ROLES}
    states = {
        "household": {"asset": {"part": "hinge-a", "state": "missing"},
                      "fit": "hinge-a", "urgency": 2, "privacy": "local-only",
                      "acceptance": "fixture-geometry-check"},
        "fabricator": {"printer": "idle", "energy_units": 5, "designs": ["hinge-a"]},
        "stockist": {"stock": {"PLA": stock}, "sources": ["PLA-local"],
                     "routes": ["local-pickup"]},
    }
    claims = {r: signed_claim(r, states[r], keys[r]) for r in ROLES}
    proposal = compose(claims, pinned)
    grants = ({r: grant(r, proposal, keys[r]) for r in ROLES}
              if approve and proposal["selected"] is not None else {})
    packet = assemble(claims, pinned, keys, grants)
    verify(packet)
    return packet


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "verify" and len(argv) == 3:
        packet = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        verify(packet)
        print(json.dumps({"verified": True, "status": packet["status"]}))
        return 0
    if len(argv) >= 2 and argv[1] == "demo":
        if len(argv) > 4 or any(a not in ("--hold",) for a in argv[2:]):
            raise ValueError("usage: demo [--hold]")
        with tempfile.TemporaryDirectory() as tmp:
            packet = demo(Path(tmp), approve="--hold" not in argv)
            # Key material is destroyed when the temporary directory closes.
            print(json.dumps(packet, sort_keys=True, indent=2))
        return 0
    raise ValueError("usage: world_asks_back.py demo [--hold] | verify <packet.json>")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
