#!/usr/bin/env python3
"""POSTAL-CORPS-002: offline QR handoff receipts and crash-resumable local journal.

Experimental synthetic custody CLAIMS only. No real parcels, carrier dispatch,
financial benefits, or proof a person physically possessed an item.

Native GHoT postal_corps/v0 signatures remain authoritative for route order.
Each QR handshake is additionally nonce-, expiration-, and exact-route-bound.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from relatte_identity import IdentityKey, jcs_bytes, verify_p256
from postal_corps import (
    DOMAIN_EVENT, DOMAIN_ROUTE, EVENT, HASH, REF, ROLES, ROUTE, RULES,
    dispatch_gate_candidate, event_body, replay, require, route_body, sha,
    verify_route,
)
from relatte_identity import normalize_public_jwk

CHALLENGE_SCHEMA = "postemahhn.carrier-pocket-challenge/v0"
RESPONSE_SCHEMA = "postemahhn.carrier-pocket-response/v0"
DOMAIN_CHALLENGE = b"PostEmahh-n-Carrier-Pocket-Challenge-v0|"
DOMAIN_RESPONSE = b"PostEmahh-n-Carrier-Pocket-Response-v0|"
ALLOWED_HANDOFFS = {
    "PICKUP_LEG1", "HANDOFF_RELAY", "PICKUP_LEG2", "DELIVER_RECIPIENT",
}
MAX_QR_JSON = 4500
MAX_EVENTS = 32


def canonical(value: Any) -> str:
    return jcs_bytes(value).decode("utf-8")


def obj(raw: Any, keys: set[str], reason: str) -> dict[str, Any]:
    require(isinstance(raw, dict) and set(raw) == keys, reason)
    return raw


def challenge_id(challenge: dict[str, Any]) -> str:
    return sha(jcs_bytes(challenge))


def make_route_from_pins(
    dispatch: dict[str, Any], parcel_sha256: str,
    role_pins: dict[str, dict[str, Any]], origin: IdentityKey,
    route_id: str = "route-specimen-001",
) -> dict[str, Any]:
    """Enroll browser public role keys WITHOUT exporting their private keys.

    Origin separately signs the complete registry. Site must independently
    verify who controls each claimed public key; this API cannot do that.
    """
    src = dispatch_gate_candidate(dispatch)
    require(isinstance(parcel_sha256, str) and HASH.fullmatch(parcel_sha256),
            "parcel hash invalid")
    require(isinstance(route_id, str) and REF.fullmatch(route_id), "route ID invalid")
    require(isinstance(role_pins, dict) and set(role_pins) == set(ROLES),
            "exact six enrolled roles required")
    pins = {role: normalize_public_jwk(role_pins[role]) for role in ROLES}
    require(len({jcs_bytes(key) for key in pins.values()}) == len(ROLES),
            "role keys must be independently held")
    require(origin.public_jwk() == pins["origin"], "origin signer key mismatch")
    route = {
        "schema": ROUTE, "route_id": route_id,
        "parcel_id": src["packet_id"], "parcel_sha256": parcel_sha256,
        "source_dispatch_sha256": src["source_dispatch_sha256"],
        "source_manifest_sha256": src["source_manifest_sha256"],
        "source_dispatch_state": src["state"],
        "classification": "synthetic_parcel_no_real_carriage",
        "role_pins": pins, "source_signature": "",
    }
    route["source_signature"] = origin.sign(DOMAIN_ROUTE + jcs_bytes(route_body(route)))
    verify_route(route, dispatch)
    return route


def make_challenge(
    route: dict[str, Any], dispatch: dict[str, Any], events: list,
    action: str, source: IdentityKey, evidence_sha256: str,
    ttl_seconds: int = 180, now: int | None = None,
) -> dict[str, Any]:
    state = replay(route, dispatch, events)
    require(action in ALLOWED_HANDOFFS, "QR handoff action not supported")
    allowed, _, roles = RULES[action]
    require(state["state"] in allowed, "handoff not permitted from current state")
    require(source.public_jwk() == route["role_pins"][roles[0]], "wrong QR initiator")
    require(type(ttl_seconds) is int and 1 <= ttl_seconds <= 300,
            "handoff TTL outside bounds")
    require(isinstance(evidence_sha256, str) and len(evidence_sha256) == 64
            and all(c in "0123456789abcdef" for c in evidence_sha256),
            "evidence SHA-256 missing")
    ts = int(time.time()) if now is None else now
    require(type(ts) is int and ts > 0, "clock required")
    evt = event_body(
        len(events) + 1, state["history_head"], route["route_id"],
        state["state"], action, evidence_sha256,
    )
    body = {
        "schema": CHALLENGE_SCHEMA, "route_hash": sha(jcs_bytes(route)),
        "parcel_sha256": route["parcel_sha256"], "event": evt,
        "initiator": roles[0], "responder": roles[1],
        "nonce": secrets.token_hex(16), "issued_at": ts,
        "expires_at": ts + ttl_seconds,
        "scope": "SYNTHETIC_CUSTODY_CLAIM_ONLY",
    }
    result = {
        "body": body,
        "initiator_proof": source.sign(DOMAIN_CHALLENGE + jcs_bytes(body)),
        "event_proof": source.sign(DOMAIN_EVENT + jcs_bytes(evt)),
    }
    require(len(jcs_bytes(result)) <= MAX_QR_JSON, "QR payload too large")
    return result


def verify_challenge(
    route: dict[str, Any], dispatch: dict[str, Any], challenge: dict[str, Any],
    events: list | None = None, now: int | None = None,
) -> dict[str, Any]:
    verify_route(route, dispatch)
    obj(challenge, {"body", "initiator_proof", "event_proof"}, "QR challenge shape")
    body = obj(challenge["body"], {
        "schema", "route_hash", "parcel_sha256", "event", "initiator",
        "responder", "nonce", "issued_at", "expires_at", "scope",
    }, "QR body shape")
    evt = obj(body["event"], {
        "schema", "seq", "prior_event_sha256", "route_id", "state_before",
        "action", "evidence_sha256",
    }, "QR event body shape")
    action = evt["action"]
    require(body["schema"] == CHALLENGE_SCHEMA
            and body["scope"] == "SYNTHETIC_CUSTODY_CLAIM_ONLY"
            and action in ALLOWED_HANDOFFS
            and body["route_hash"] == sha(jcs_bytes(route))
            and body["parcel_sha256"] == route["parcel_sha256"]
            and evt["route_id"] == route["route_id"]
            and evt["schema"] == EVENT, "QR route or effect mismatch")
    roles = RULES[action][2]
    require((body["initiator"], body["responder"]) == roles,
            "QR signer role order mismatch")
    require(isinstance(body["nonce"], str) and len(body["nonce"]) == 32
            and all(c in "0123456789abcdef" for c in body["nonce"]),
            "bad QR nonce")
    start, end = body["issued_at"], body["expires_at"]
    ts = int(time.time()) if now is None else now
    require(type(start) is int and type(end) is int and type(ts) is int
            and 1 <= end-start <= 300 and start-60 <= ts <= end,
            "QR expired or from the future")
    require(verify_p256(route["role_pins"][roles[0]],
                       DOMAIN_CHALLENGE + jcs_bytes(body),
                       challenge["initiator_proof"]), "QR signature invalid")
    require(verify_p256(route["role_pins"][roles[0]],
                       DOMAIN_EVENT + jcs_bytes(evt),
                       challenge["event_proof"]), "initiator event proof invalid")
    if events is not None:
        state = replay(route, dispatch, events)
        require(evt["seq"] == len(events) + 1
                and evt["prior_event_sha256"] == state["history_head"]
                and evt["state_before"] == state["state"]
                and state["state"] in RULES[action][0],
                "QR stale, out of order, or conflicting history")
    return body


def make_response(
    route: dict[str, Any], dispatch: dict[str, Any], events: list,
    challenge: dict[str, Any], responder: IdentityKey, now: int | None = None,
) -> dict[str, Any]:
    body = verify_challenge(route, dispatch, challenge, events, now)
    role = body["responder"]
    require(responder.public_jwk() == route["role_pins"][role],
            "response signing key does not match role")
    response_body = {
        "schema": RESPONSE_SCHEMA,
        "challenge_sha256": challenge_id(challenge),
        "nonce": body["nonce"],
        "event_sha256": sha(jcs_bytes(body["event"])),
        "responder": role,
        "scope": "SYNTHETIC_CUSTODY_CLAIM_ONLY",
    }
    return {
        "challenge": challenge,
        "response_body": response_body,
        "response_proof": responder.sign(DOMAIN_RESPONSE + jcs_bytes(response_body)),
        "event_proof": responder.sign(DOMAIN_EVENT + jcs_bytes(body["event"])),
    }


def verify_response(
    route: dict[str, Any], dispatch: dict[str, Any],
    response: dict[str, Any], events: list | None = None,
    now: int | None = None,
) -> tuple[str, dict[str, Any]]:
    obj(response, {
        "challenge", "response_body", "response_proof", "event_proof",
    }, "response shape")
    body = verify_challenge(route, dispatch, response["challenge"], events, now)
    proof = obj(response["response_body"], {
        "schema", "challenge_sha256", "nonce", "event_sha256", "responder", "scope",
    }, "response body shape")
    require(proof == {
        "schema": RESPONSE_SCHEMA,
        "challenge_sha256": challenge_id(response["challenge"]),
        "nonce": body["nonce"], "event_sha256": sha(jcs_bytes(body["event"])),
        "responder": body["responder"], "scope": "SYNTHETIC_CUSTODY_CLAIM_ONLY",
    }, "response does not acknowledge exact QR")
    key = route["role_pins"][body["responder"]]
    require(verify_p256(key, DOMAIN_RESPONSE + jcs_bytes(proof),
                        response["response_proof"]), "response acknowledgment invalid")
    require(verify_p256(key, DOMAIN_EVENT + jcs_bytes(body["event"]),
                        response["event_proof"]), "responder event signature invalid")
    pkt = {
        "body": body["event"],
        "signatures": {
            body["initiator"]: response["challenge"]["event_proof"],
            body["responder"]: response["event_proof"],
        },
    }
    return body["nonce"], pkt


class PocketJournal:
    """One trusted local SQLite WAL; no network authority or fund effects."""

    def __init__(self, path: Path, route: dict[str, Any],
                 dispatch: dict[str, Any]) -> None:
        verify_route(route, dispatch)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError("journal symlink refused")
        self.route, self.dispatch = route, dispatch
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY CHECK(id=1), route_hash TEXT NOT NULL, dispatch_hash TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, nonce TEXT UNIQUE NOT NULL, json TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS challenges (nonce TEXT PRIMARY KEY, json TEXT NOT NULL, status TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS outbox (nonce TEXT PRIMARY KEY, json TEXT NOT NULL)")
        row = self.db.execute("SELECT route_hash, dispatch_hash FROM identity WHERE id=1").fetchone()
        expected = (sha(jcs_bytes(route)), sha(jcs_bytes(dispatch)))
        if row is None:
            self.db.execute("INSERT INTO identity VALUES (1,?,?)", expected)
        elif row != expected:
            raise ValueError("journal belongs to a different route/dispatch")
        self.events()  # fail on corruption on every reopen

    def close(self):
        self.db.close()

    def events(self) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT seq,json FROM events ORDER BY seq").fetchall()
        require(all(seq == i for i, (seq, _) in enumerate(rows, 1)),
                "noncontiguous event journal")
        events = [json.loads(j) for _, j in rows]
        replay(self.route, self.dispatch, events)
        return events

    def state(self) -> dict[str, Any]:
        state = replay(self.route, self.dispatch, self.events())
        state["pending_issued"] = self.db.execute(
            "SELECT COUNT(*) FROM challenges WHERE status='PREPARED'").fetchone()[0]
        state["outgoing_unsynced"] = self.db.execute(
            "SELECT COUNT(*) FROM outbox").fetchone()[0]
        state["physical_parcel_observed"] = False
        state["deed_awarded"] = False
        state["penny_released"] = 0
        return state

    def issue(self, action: str, signer: IdentityKey,
              evidence_sha256: str, now: int | None = None,
              ttl: int = 180) -> dict[str, Any]:
        challenge = make_challenge(self.route, self.dispatch, self.events(),
                                   action, signer, evidence_sha256, ttl, now)
        nonce = challenge["body"]["nonce"]
        self.db.execute(
            "INSERT INTO challenges VALUES (?,?,?)",
            (nonce, canonical(challenge), "PREPARED"),
        )
        return challenge

    def respond(self, challenge: dict[str, Any], signer: IdentityKey,
                now: int | None = None) -> dict[str, Any]:
        nonce = challenge["body"]["nonce"]
        row = self.db.execute("SELECT json FROM outbox WHERE nonce=?", (nonce,)).fetchone()
        if row:
            response = json.loads(row[0])
            require(response["challenge"] == challenge, "conflicting QR reuse")
            require(signer.public_jwk() == self.route["role_pins"][challenge["body"]["responder"]],
                    "wrong responder replay key")
            verify_response(self.route, self.dispatch, response, self.events(), now)
            return response
        response = make_response(self.route, self.dispatch, self.events(),
                                 challenge, signer, now)
        self.db.execute("INSERT INTO outbox VALUES (?,?)",
                        (nonce, canonical(response)))
        return response

    def recover_outbox(self, nonce: str) -> dict[str, Any]:
        row = self.db.execute("SELECT json FROM outbox WHERE nonce=?", (nonce,)).fetchone()
        require(row is not None, "outgoing receipt missing")
        return json.loads(row[0])

    def commit(self, response: dict[str, Any], now: int | None = None) -> dict[str, Any]:
        nonce, pkt = verify_response(self.route, self.dispatch, response, None, now)
        row = self.db.execute("SELECT json,status FROM challenges WHERE nonce=?",
                              (nonce,)).fetchone()
        require(row is not None and json.loads(row[0]) == response["challenge"],
                "QR never issued by this journal")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if row[1] == "COMMITTED":
                event_row = self.db.execute("SELECT json FROM events WHERE nonce=?",
                                            (nonce,)).fetchone()
                require(event_row and json.loads(event_row[0]) == pkt,
                        "conflicting repeated acknowledgment")
                self.db.execute("COMMIT")
                return pkt
            events = self.events()
            _, pkt = verify_response(self.route, self.dispatch, response, events, now)
            next_events = events + [pkt]
            require(len(next_events) <= MAX_EVENTS, "event journal quota exceeded")
            replay(self.route, self.dispatch, next_events)
            self.db.execute("INSERT INTO events VALUES (?,?,?)",
                            (len(next_events), nonce, canonical(pkt)))
            self.db.execute("UPDATE challenges SET status='COMMITTED' WHERE nonce=?",
                            (nonce,))
            self.db.execute("COMMIT")
            return pkt
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def export_history(self) -> dict[str, Any]:
        return {
            "schema": "postemahhn.carrier-pocket-history/v0",
            "route_hash": sha(jcs_bytes(self.route)),
            "events": self.events(),
            "effect": "SYNTHETIC_CUSTODY_CLAIM_ONLY",
        }

    def sync_history(self, envelope: dict[str, Any]) -> int:
        obj(envelope, {"schema", "route_hash", "events", "effect"}, "history envelope")
        require(envelope["schema"] == "postemahhn.carrier-pocket-history/v0"
                and envelope["route_hash"] == sha(jcs_bytes(self.route))
                and envelope["effect"] == "SYNTHETIC_CUSTODY_CLAIM_ONLY",
                "wrong route or authority")
        incoming = envelope["events"]
        require(isinstance(incoming, list) and len(incoming) <= MAX_EVENTS,
                "history too large")
        replay(self.route, self.dispatch, incoming)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            mine = self.events()
            require(incoming[:len(mine)] == mine,
                    "HOLD_FORK: different signed histories")
            for i, pkt in enumerate(incoming[len(mine):], len(mine)+1):
                # The imported packet has two exact independent signatures and
                # replays under the original role/state constraints.
                nonce = "import-"+sha(jcs_bytes(pkt))
                self.db.execute("INSERT INTO events VALUES (?,?,?)",
                                (i, nonce, canonical(pkt)))
            self.db.execute("COMMIT")
            return len(incoming)-len(mine)
        except Exception:
            self.db.execute("ROLLBACK")
            raise


def main() -> None:
    p = argparse.ArgumentParser(description="Offline PostEmahh'n carrier pocket proof")
    p.add_argument("--route", required=True, type=Path)
    p.add_argument("--dispatch", required=True, type=Path)
    p.add_argument("--db", required=True, type=Path)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("issue")
    a.add_argument("--action", required=True, choices=sorted(ALLOWED_HANDOFFS))
    a.add_argument("--key", required=True, type=Path)
    a.add_argument("--evidence-sha256", required=True)
    a.add_argument("--out", required=True, type=Path)
    a = sub.add_parser("respond")
    a.add_argument("--qr", required=True, type=Path)
    a.add_argument("--key", required=True, type=Path)
    a.add_argument("--out", required=True, type=Path)
    a = sub.add_parser("commit")
    a.add_argument("--response", required=True, type=Path)
    a = sub.add_parser("recover")
    a.add_argument("--nonce", required=True)
    a.add_argument("--out", required=True, type=Path)
    a = sub.add_parser("export-history")
    a.add_argument("--out", required=True, type=Path)
    a = sub.add_parser("sync-history")
    a.add_argument("--from-file", required=True, type=Path)
    sub.add_parser("status")
    args = p.parse_args()
    route = json.loads(args.route.read_text())
    dispatch = json.loads(args.dispatch.read_text())
    journal = PocketJournal(args.db, route, dispatch)
    try:
        if args.cmd == "issue":
            data = journal.issue(args.action, IdentityKey(args.key), args.evidence_sha256)
        elif args.cmd == "respond":
            data = journal.respond(json.loads(args.qr.read_text()), IdentityKey(args.key))
        elif args.cmd == "commit":
            journal.commit(json.loads(args.response.read_text()))
            data = journal.state()
        elif args.cmd == "recover":
            data = journal.recover_outbox(args.nonce)
        elif args.cmd == "export-history":
            data = journal.export_history()
        elif args.cmd == "sync-history":
            data = {"imported": journal.sync_history(json.loads(args.from_file.read_text()))}
        else:
            data = journal.state()
        if hasattr(args, "out"):
            if args.out.exists():
                raise ValueError("output exists")
            args.out.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n")
            print(str(args.out))
        else:
            print(json.dumps(data, indent=2, sort_keys=True))
    finally:
        journal.close()


if __name__ == "__main__":
    main()
