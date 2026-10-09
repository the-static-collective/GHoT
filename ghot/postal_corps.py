#!/usr/bin/env python3
"""POSTAL-CORPS-001 — two-carrier *simulated* custody claims.

Reads a native LemonPRESS Dispatch Gate 001 un-tendered *fixture*, issues an
independently signed proposal, and records role-pinned, chain-linked event
claims. Full Measure and PENNY outputs are explicitly PROPOSALS, never source
ledgers, deeds, custody proofs, financial accounts or tokens.

No names, addresses, payments, carrier offers, shipping or printer effects.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from relatte_identity import (
    IdentityKey, jcs_bytes, normalize_public_jwk, timestamp_now, verify_p256,
)

ROUTE = "postemahhn.postal-corps-route/v0"
EVENT = "postemahhn.postal-corps-event/v0"
DOMAIN_ROUTE = b"PostEmahh-n-Postal-Corps-001-Route|"
DOMAIN_EVENT = b"PostEmahh-n-Postal-Corps-001-Event|"
HASH = re.compile(r"^[0-9a-f]{64}$")
REF = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
ROLES = ("origin", "carrier1", "relay", "carrier2", "recipient", "witness")
RULES = {
    "ACCEPT_LEG1": (("OFFERED",), "LEG1_ACCEPTED", ("carrier1",)),
    "PICKUP_LEG1": (("LEG1_ACCEPTED",), "LEG1_MOVING_CLAIM", ("origin", "carrier1")),
    "HANDOFF_RELAY": (("LEG1_MOVING_CLAIM",), "RELAY_HELD_CLAIM", ("carrier1", "relay")),
    "ACCEPT_LEG2": (("RELAY_HELD_CLAIM",), "LEG2_ACCEPTED", ("carrier2",)),
    "PICKUP_LEG2": (("LEG2_ACCEPTED",), "LEG2_MOVING_CLAIM", ("relay", "carrier2")),
    "DELIVER_RECIPIENT": (("LEG2_MOVING_CLAIM",), "DELIVERY_CLAIM", ("carrier2", "recipient")),
    "REPORT_LEG1": (("DELIVERY_CLAIM",), "LEG1_REPORTED", ("carrier1",)),
    "REPORT_LEG2": (("LEG1_REPORTED",), "BOTH_REPORTED", ("carrier2",)),
    "WITNESS_LEG1": (("BOTH_REPORTED",), "LEG1_WITNESSED_CLAIM", ("witness",)),
    "WITNESS_LEG2": (("LEG1_WITNESSED_CLAIM",), "WORK_REVIEW_READY", ("witness",)),
    "REFUSE_LEG1": (("OFFERED",), "REFUSED", ("carrier1",)),
    "REFUSE_LEG2": (("RELAY_HELD_CLAIM",), "REFUSED_AT_RELAY", ("carrier2",)),
    "LOST_LEG1": (("LEG1_MOVING_CLAIM",), "LOSS_REPORTED", ("carrier1",)),
    "LOST_LEG2": (("LEG2_MOVING_CLAIM",), "LOSS_REPORTED", ("carrier2",)),
    "DISPUTE": (
        ("DELIVERY_CLAIM", "LEG1_REPORTED", "BOTH_REPORTED",
         "LEG1_WITNESSED_CLAIM", "WORK_REVIEW_READY"),
        "DISPUTED", ("recipient",),
    ),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def dispatch_gate_candidate(record: dict[str, Any]) -> dict[str, str]:
    """Accept ONLY a source-format simulated, un-postaged, un-tendered record.

    Requires real LemonPRESS Dispatch Gate's field structure. This is a
    source-format contract check, not an independently signed Lemon record.
    """
    require(isinstance(record, dict), "dispatch must be an object")
    require(set(record) == {
        "dispatch_version", "packet_id", "work_id", "edition_id",
        "recipient_id", "packet_manifest_sha256", "carrier_selection",
        "postage", "state", "events", "privacy", "law",
    }, "dispatch structure mismatch")
    require(record["dispatch_version"] == "dispatch-gate-001",
            "dispatch must use LemonPRESS version")
    require(record["state"] == "service_selected" and record["postage"] is None,
            "dispatch must be un-postaged and un-tendered")
    require(isinstance(record["packet_id"], str) and REF.fullmatch(record["packet_id"]),
            "fixture parcel identifier invalid")
    require(isinstance(record["recipient_id"], str)
            and record["recipient_id"].startswith("specimen:"),
            "real recipient data prohibited")
    require(isinstance(record["packet_manifest_sha256"], str)
            and HASH.fullmatch(record["packet_manifest_sha256"]),
            "invalid packet-manifest hash")
    selection = record["carrier_selection"]
    require(isinstance(selection, dict)
            and selection.get("carrier") == "POSTAL-CORPS-SIMULATION"
            and selection.get("service") == "offline-specimen"
            and selection.get("state") == "human_selected",
            "not an explicitly simulated carrier service")
    require(isinstance(record["events"], list)
            and len(record["events"]) == 1
            and record["events"][0].get("event") == "service_selected",
            "unexpected already-tendered dispatch history")
    require(isinstance(record["privacy"], dict)
            and record["privacy"].get("record_disposition") == "local_only",
            "private dispatch must remain local")
    return {
        "packet_id": record["packet_id"],
        "source_dispatch_sha256": sha(jcs_bytes(record)),
        "source_manifest_sha256": record["packet_manifest_sha256"],
        "state": "service_selected",
    }


def route_body(route: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in route.items() if k != "source_signature"}


def make_route(record: dict[str, Any], parcel_sha256: str, signers: dict[str, IdentityKey],
               route_id: str = "route-specimen-001") -> dict[str, Any]:
    source = dispatch_gate_candidate(record)
    require(isinstance(parcel_sha256, str) and HASH.fullmatch(parcel_sha256),
            "parcel hash required")
    require(isinstance(route_id, str) and REF.fullmatch(route_id),
            "route id invalid")
    require(set(signers) == set(ROLES), "exactly six independent roles required")
    pins = {role: signers[role].public_jwk() for role in ROLES}
    require(len({jcs_bytes(pin) for pin in pins.values()}) == len(ROLES),
            "role keys cannot be reused")
    route = {
        "schema": ROUTE, "route_id": route_id,
        "parcel_id": source["packet_id"],
        "parcel_sha256": parcel_sha256,
        "source_dispatch_sha256": source["source_dispatch_sha256"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "source_dispatch_state": source["state"],
        "classification": "synthetic_parcel_no_real_carriage",
        "role_pins": pins, "source_signature": "",
    }
    route["source_signature"] = signers["origin"].sign(DOMAIN_ROUTE+jcs_bytes(route_body(route)))
    return route


def verify_route(route: dict[str, Any], dispatch: dict[str, Any]) -> None:
    require(isinstance(route, dict) and set(route) == {
        "schema", "route_id", "parcel_id", "parcel_sha256",
        "source_dispatch_sha256", "source_manifest_sha256",
        "source_dispatch_state", "classification", "role_pins", "source_signature",
    }, "route structure changed")
    require(route["schema"] == ROUTE and REF.fullmatch(route["route_id"]),
            "route schema or id invalid")
    source = dispatch_gate_candidate(dispatch)
    require(route["parcel_id"] == source["packet_id"]
            and route["source_dispatch_sha256"] == source["source_dispatch_sha256"]
            and route["source_manifest_sha256"] == source["source_manifest_sha256"]
            and route["source_dispatch_state"] == source["state"],
            "source LemonPRESS dispatch changed")
    require(route["classification"] == "synthetic_parcel_no_real_carriage",
            "real carriage not admitted")
    require(isinstance(route["parcel_sha256"], str) and HASH.fullmatch(route["parcel_sha256"]),
            "parcel SHA invalid")
    pins = route["role_pins"]
    require(isinstance(pins, dict) and set(pins) == set(ROLES),
            "role registry differs")
    normalized = {role: normalize_public_jwk(pins[role]) for role in ROLES}
    require(len({jcs_bytes(pin) for pin in normalized.values()}) == len(ROLES),
            "independent role pins required")
    require(all(normalized[r] == pins[r] for r in ROLES), "role key not canonical")
    require(verify_p256(pins["origin"], DOMAIN_ROUTE+jcs_bytes(route_body(route)),
                        route["source_signature"]),
            "source route signature invalid")


def event_body(seq: int, prev: str | None, route_id: str,
               state_before: str, action: str, evidence_sha256: str) -> dict[str, Any]:
    return {
        "schema": EVENT, "seq": seq, "prior_event_sha256": prev,
        "route_id": route_id, "state_before": state_before,
        "action": action, "evidence_sha256": evidence_sha256,
    }


def replay(route: dict[str, Any], dispatch: dict[str, Any],
           events: list[dict[str, Any]]) -> dict[str, Any]:
    verify_route(route, dispatch)
    require(isinstance(events, list) and len(events) <= 32, "bounded event list required")
    state, prev = "OFFERED", None
    history = []
    for i, packet in enumerate(events, 1):
        require(isinstance(packet, dict) and set(packet) == {"body", "signatures"},
                "carrier event shape invalid")
        b, proofs = packet["body"], packet["signatures"]
        require(isinstance(b, dict) and set(b) == {
            "schema", "seq", "prior_event_sha256", "route_id", "state_before",
            "action", "evidence_sha256",
        }, "carrier event body invalid")
        action = b["action"]
        require(action in RULES, "unrecognized carrier action")
        before, after, roles = RULES[action]
        require(b["schema"] == EVENT and b["seq"] == i
                and b["prior_event_sha256"] == prev
                and b["route_id"] == route["route_id"]
                and b["state_before"] == state
                and state in before,
                "impossible, stale or duplicate carrier transition")
        require(isinstance(b["evidence_sha256"], str)
                and HASH.fullmatch(b["evidence_sha256"]),
                "evidence fingerprint required")
        require(isinstance(proofs, dict) and set(proofs) == set(roles),
                "missing or extra independent handoff signer")
        for role in roles:
            require(verify_p256(route["role_pins"][role],
                                DOMAIN_EVENT+jcs_bytes(b), proofs[role]),
                    "invalid " + role + " signature")
        state = after
        prev = sha(jcs_bytes(packet))
        history.append(action)
    return {
        "state": state, "event_count": len(events),
        "history_head": prev, "actions": history,
        "source_dispatch_sha256": route["source_dispatch_sha256"],
        "parcel_sha256": route["parcel_sha256"],
    }


def act(route: dict[str, Any], dispatch: dict[str, Any],
        events: list[dict[str, Any]], action: str,
        role_signers: dict[str, IdentityKey],
        evidence_sha256: str) -> list[dict[str, Any]]:
    before = replay(route, dispatch, events)
    require(action in RULES, "unknown action")
    eligible, _, roles = RULES[action]
    require(before["state"] in eligible, "action not admitted in current state")
    require(set(role_signers) == set(roles), "wrong signing roles")
    require(isinstance(evidence_sha256, str) and HASH.fullmatch(evidence_sha256),
            "exact evidence digest required")
    for role in roles:
        require(role_signers[role].public_jwk() == route["role_pins"][role],
                "wrong independent signing identity")
    body = event_body(len(events)+1, before["history_head"],route["route_id"],
                      before["state"],action,evidence_sha256)
    pkt = {
        "body": body,
        "signatures": {
            role: role_signers[role].sign(DOMAIN_EVENT+jcs_bytes(body))
            for role in roles
        },
    }
    result = events + [pkt]
    replay(route, dispatch, result)
    return result


def output_proposals(route: dict[str, Any], dispatch: dict[str, Any],
                     events: list[dict[str, Any]]) -> dict[str, Any]:
    state = replay(route, dispatch, events)
    eligible = state["state"] == "WORK_REVIEW_READY"
    # This is not a Full Measure native Deed and never calls its authoritative store.
    garden = {
        "schema": "full-measure.postal-quest-draft/v0",
        "route_id": route["route_id"], "parcel_sha256": route["parcel_sha256"],
        "status": "LOCAL_PROPOSAL_ONLY",
        "eligible_for_human_review": eligible,
        "self_reported": "YES" if "REPORT_LEG2" in state["actions"] else "NOT_COMPLETE",
        "human_claims_present": "WITNESS_LEG2" in state["actions"],
        "deed_state": "NOT_AWARDED",
        "official_full_measure_event_created": False,
        "history_sha256": state["history_head"],
    }
    candidate = []
    if eligible:
        for index, role in enumerate(("carrier1", "carrier2"), 1):
            candidate.append({
                "workId": "postal-"+route["route_id"]+"-leg-"+str(index),
                "holderId": "person:synthetic-"+role,
                "quantity": 1,
                "termsRef": "terms:illustrative-carriage-not-compensation",
                "evidenceHash": state["history_head"],
                "completedAt": timestamp_now(),
            })
    penny = {
        "schema": "jubilee.penny-postal-work-proposal-only/v0",
        "route_id": route["route_id"],
        "candidate_work_payloads": candidate,
        "work_witness_proof": None,
        "status": "NO_TREASURY_EVENT",
        "book_coins": 0, "released_units": 0, "active_units": 0,
        "real_payment_occurred": False, "human_wage_agreement": False,
        "ledger_touched": False,
        "history_sha256": state["history_head"],
    }
    return {"carrier": state, "full_measure": garden, "penny": penny}


def specimen(signers: dict[str, IdentityKey], dispatch: dict[str, Any],
             pdf: bytes) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    route = make_route(dispatch, sha(pdf), signers)
    events: list[dict[str, Any]] = []
    for index, action in enumerate((
        "ACCEPT_LEG1", "PICKUP_LEG1", "HANDOFF_RELAY", "ACCEPT_LEG2",
        "PICKUP_LEG2", "DELIVER_RECIPIENT", "REPORT_LEG1", "REPORT_LEG2",
        "WITNESS_LEG1", "WITNESS_LEG2",
    )):
        roles = RULES[action][2]
        events = act(route, dispatch, events, action,
                     {role: signers[role] for role in roles},
                     sha(("synthetic-evidence-"+str(index)).encode()))
    return route, events, output_proposals(route, dispatch, events)
