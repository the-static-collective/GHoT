#!/usr/bin/env python3
"""UNHEARD CHOIR 011 — The Vanishing Witness.

Bounded, signed *simulation-only* fork evidence delivery between 010 observers.
A persistent sender outbox survives dropped messages and a recipient inbox
returns a repeatable signed ACK after duplicate delivery. Signed inventory
supports anti-entropy without elevating a hint to proof of delivered custody.
No socket, transport, physical event, authority grant or native reLATTE action.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_gossip import (
    SITES, check_roster, compare_views, fork_fixture, make_package,
    observe_once, read_local, verify_package,
)
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk, verify_p256,
)

ENVELOPE = "ghot.unheard-choir-011-fork-envelope/v0"
ACK = "ghot.unheard-choir-011-owner-local-ack/v0"
INVENTORY = "ghot.unheard-choir-011-inbox-inventory/v0"
ASSESSMENT = "ghot.unheard-choir-011-delivery-assessment/v0"
ED = b"GHOT-CHOIR-011-ENVELOPE-v0|"
AD = b"GHOT-CHOIR-011-ACK-v0|"
ID = b"GHOT-CHOIR-011-INVENTORY-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-011-inbox-genesis/v0"})


def exact(value: Any, fields: tuple | set, name: str):
    if type(value) is not dict or set(value) != set(fields):
        raise InvalidWorld(name + ": missing or additional fields")


def jwk(value):
    try:
        return normalize_public_jwk(value)
    except (IdentityProfileError, TypeError, ValueError) as exc:
        raise InvalidWorld("invalid site P-256 public key") from exc


def sign(signer: IdentityKey, body: dict, domain: bytes):
    return signer.sign(domain + jcs_bytes(body))


def authenticated(signer_jwk: dict, body: dict, signature: Any, domain: bytes, name: str):
    if type(signature) is not str or not verify_p256(
        jwk(signer_jwk), domain + jcs_bytes(body), signature
    ):
        raise InvalidWorld(name + ": signed object not authenticated")


def verify_base(common: list, log_policy: dict, log_root: dict,
                roster: dict, gossip_root: dict):
    check_roster(common + [log_policy, log_root, [], []], roster, gossip_root)


def make_envelope(common: list, log_policy: dict, log_root: dict,
                  roster: dict, gossip_root: dict,
                  origin_package: dict, destination: str,
                  signer: IdentityKey, *, hop_limit: int = 1):
    verify_base(common, log_policy, log_root, roster, gossip_root)
    if destination not in SITES or type(hop_limit) is not int or hop_limit != 1:
        raise InvalidWorld("direct one-hop delivery only")
    sender = origin_package.get("site") if type(origin_package) is dict else None
    if sender not in SITES or sender == destination or jwk(signer.public_jwk()) != jwk(roster["sites"][sender]):
        raise InvalidWorld("origin and destination must be separate pinned 010 sites")
    verify_package(common, log_policy, log_root, roster, sender, origin_package, now=1001)
    body = {
        "schema": ENVELOPE, "scope": "SIGNED_FORK_EVIDENCE_NOT_PERMISSION",
        "roster_digest": digest(roster),
        "log_policy_digest": digest(log_policy),
        "sender": sender, "recipient": destination, "hop_limit": hop_limit,
        "origin_package": origin_package,
    }
    return {**body, "signature": sign(signer, body, ED)}


def verify_envelope(common: list, log_policy: dict, log_root: dict,
                    roster: dict, gossip_root: dict,
                    envelope: Any, *, now: int, expected_recipient: str | None = None):
    verify_base(common, log_policy, log_root, roster, gossip_root)
    exact(envelope, (
        "schema", "scope", "roster_digest", "log_policy_digest",
        "sender", "recipient", "hop_limit", "origin_package", "signature",
    ), "delivery envelope")
    if (envelope["schema"] != ENVELOPE
        or envelope["scope"] != "SIGNED_FORK_EVIDENCE_NOT_PERMISSION"
        or envelope["roster_digest"] != digest(roster)
        or envelope["log_policy_digest"] != digest(log_policy)
        or envelope["sender"] not in SITES or envelope["recipient"] not in SITES
        or envelope["sender"] == envelope["recipient"]
        or type(envelope["hop_limit"]) is not int or envelope["hop_limit"] != 1
        or (expected_recipient is not None and envelope["recipient"] != expected_recipient)):
        raise InvalidWorld("invalid or misrouted signed fork envelope")
    body = {k: v for k, v in envelope.items() if k != "signature"}
    authenticated(roster["sites"][envelope["sender"]], body, envelope["signature"], ED, "sender envelope")
    package = envelope["origin_package"]
    verify_package(common, log_policy, log_root, roster,
                   envelope["sender"], package, now=now)
    return digest(envelope)


def init_outbox(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS pending_shipments (
                delivery_id TEXT PRIMARY KEY,
                destination TEXT NOT NULL,
                envelope_json TEXT NOT NULL,
                acknowledgement_json TEXT
                )""")


def init_inbox(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS received_shipments (
                receipt_index INTEGER PRIMARY KEY,
                delivery_id TEXT NOT NULL UNIQUE,
                envelope_json TEXT NOT NULL,
                acknowledgement_json TEXT NOT NULL
                )""")


def read_outbox(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_outbox(db)
        rows = db.execute("SELECT envelope_json, acknowledgement_json FROM pending_shipments ORDER BY delivery_id").fetchall()
    return [{"envelope": json.loads(e), "ack": json.loads(a) if a is not None else None} for e, a in rows]


def read_inbox(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_inbox(db)
        rows = db.execute("SELECT envelope_json, acknowledgement_json FROM received_shipments ORDER BY receipt_index").fetchall()
    return [{"envelope": json.loads(e), "ack": json.loads(a)} for e, a in rows]


def verify_ack(common: list, log_policy: dict, log_root: dict,
               roster: dict, gossip_root: dict, envelope: dict,
               acknowledgement: Any, *, now: int):
    delivery_id = verify_envelope(common, log_policy, log_root, roster,
                                  gossip_root, envelope, now=now)
    exact(acknowledgement, (
        "schema", "scope", "roster_digest", "delivery_id", "sender", "recipient",
        "recipient_local_package", "comparison_digest", "comparison_decision",
        "receipt_index", "previous_receipt_digest", "signature",
    ), "acknowledgement")
    if (acknowledgement["schema"] != ACK
        or acknowledgement["scope"] != "SIGNED_OWNER_LOCAL_DELIVERY_RECEIPT_NO_EFFECT"
        or acknowledgement["roster_digest"] != digest(roster)
        or acknowledgement["delivery_id"] != delivery_id
        or acknowledgement["sender"] != envelope["sender"]
        or acknowledgement["recipient"] != envelope["recipient"]
        or type(acknowledgement["receipt_index"]) is not int
        or acknowledgement["receipt_index"] < 0
        or type(acknowledgement["previous_receipt_digest"]) is not str):
        raise InvalidWorld("acknowledgement not bound to sender, recipient and exact evidence")
    comparison = compare_views(
        common, log_policy, log_root, roster, gossip_root,
        acknowledgement["recipient_local_package"], envelope["origin_package"], now=now
    )
    if (comparison["local_site"] != envelope["recipient"]
        or comparison["decision"] != "HOLD_GOSSIP_REVEALS_UNSEEN_FORK"
        or acknowledgement["comparison_decision"] != comparison["decision"]
        or acknowledgement["comparison_digest"] != comparison["assessment_digest"]):
        raise InvalidWorld("ACK cannot assert a fork absent independently verified recipient comparison")
    body = {k: v for k, v in acknowledgement.items() if k != "signature"}
    authenticated(roster["sites"][envelope["recipient"]], body,
                  acknowledgement["signature"], AD, "recipient ACK")
    return comparison


def verify_inbox(common: list, log_policy: dict, log_root: dict,
                 roster: dict, gossip_root: dict,
                 rows: list, *, now: int, recipient: str):
    if type(rows) is not list or len(rows) > 64:
        raise InvalidWorld("bounded inbox exceeded")
    prior, used = GENESIS, set()
    for i, row in enumerate(rows):
        exact(row, ("envelope", "ack"), "inbox row")
        env, ack = row["envelope"], row["ack"]
        compare = verify_ack(common, log_policy, log_root, roster, gossip_root,
                             env, ack, now=now)
        if (env["recipient"] != recipient or ack["receipt_index"] != i
            or ack["previous_receipt_digest"] != prior
            or ack["delivery_id"] in used):
            raise InvalidWorld("inbox receipt order or predecessor corrupted")
        used.add(ack["delivery_id"])
        prior = digest(ack)
    return prior


def stage_once(outbox_path: Path, common: list, policy: dict, root: dict,
               roster: dict, gossip_root: dict, envelope: dict, *, now: int):
    delivery_id = verify_envelope(common, policy, root, roster, gossip_root,
                                  envelope, now=now)
    with sqlite3.connect(str(outbox_path), isolation_level=None, timeout=10) as db:
        init_outbox(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            exists = db.execute("SELECT envelope_json FROM pending_shipments WHERE delivery_id=?",
                                (delivery_id,)).fetchone()
            if exists:
                if json.loads(exists[0]) != envelope:
                    raise InvalidWorld("same delivery hash with different signed bytes")
                result = "ALREADY_STAGED"
            else:
                if db.execute("SELECT COUNT(*) FROM pending_shipments").fetchone()[0] >= 64:
                    raise InvalidWorld("bounded outbox capacity exceeded")
                db.execute("INSERT INTO pending_shipments VALUES (?,?,?,NULL)",
                           (delivery_id, envelope["recipient"], json.dumps(envelope, sort_keys=True, separators=(",", ":"))))
                result = "STAGED_DURABLY"
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return {"delivery_id": delivery_id, "status": result}


def receive_once(inbox_path: Path, common: list, policy: dict, root: dict,
                 roster: dict, gossip_root: dict,
                 envelope: dict, recipient_local_package: dict,
                 signer: IdentityKey, *, now: int):
    recipient = envelope.get("recipient") if type(envelope) is dict else None
    if recipient not in SITES or jwk(signer.public_jwk()) != jwk(roster["sites"][recipient]):
        raise InvalidWorld("only recipient can make its own acknowledgement")
    delivery_id = verify_envelope(common, policy, root, roster, gossip_root,
                                  envelope, now=now, expected_recipient=recipient)
    comparison = compare_views(common, policy, root, roster, gossip_root,
                               recipient_local_package, envelope["origin_package"], now=now)
    if comparison["local_site"] != recipient or comparison["decision"] != "HOLD_GOSSIP_REVEALS_UNSEEN_FORK":
        raise InvalidWorld("receive only cryptographically confirmed fork evidence")
    with sqlite3.connect(str(inbox_path), isolation_level=None, timeout=10) as db:
        init_inbox(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [{"envelope": json.loads(e), "ack": json.loads(a)} for e, a in
                    db.execute("SELECT envelope_json, acknowledgement_json FROM received_shipments ORDER BY receipt_index").fetchall()]
            prior = verify_inbox(common, policy, root, roster, gossip_root,
                                 rows, now=now, recipient=recipient)
            existing = next((x for x in rows if x["ack"]["delivery_id"] == delivery_id), None)
            if existing is not None:
                if existing["envelope"] != envelope:
                    raise InvalidWorld("duplicate delivery not byte-identical")
                acknowledgement = existing["ack"]
                status = "DUPLICATE_ALREADY_RECEIVED"
            else:
                if len(rows) >= 64:
                    raise InvalidWorld("bounded inbox capacity exceeded")
                body = {
                    "schema": ACK, "scope": "SIGNED_OWNER_LOCAL_DELIVERY_RECEIPT_NO_EFFECT",
                    "roster_digest": digest(roster), "delivery_id": delivery_id,
                    "sender": envelope["sender"], "recipient": recipient,
                    "recipient_local_package": recipient_local_package,
                    "comparison_digest": comparison["assessment_digest"],
                    "comparison_decision": comparison["decision"],
                    "receipt_index": len(rows), "previous_receipt_digest": prior,
                }
                acknowledgement = {**body, "signature": sign(signer, body, AD)}
                db.execute("INSERT INTO received_shipments VALUES (?,?,?,?)",
                           (len(rows), delivery_id,
                            json.dumps(envelope, sort_keys=True, separators=(",", ":")),
                            json.dumps(acknowledgement, sort_keys=True, separators=(",", ":"))))
                status = "RECEIVED_LOCALLY"
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return {"ack": acknowledgement, "status": status}


def confirm_once(outbox_path: Path, common: list, policy: dict, root: dict,
                 roster: dict, gossip_root: dict, acknowledgement: dict,
                 *, now: int):
    if type(acknowledgement) is not dict:
        raise InvalidWorld("acknowledgement not provided")
    delivery_id = acknowledgement.get("delivery_id")
    if type(delivery_id) is not str:
        raise InvalidWorld("unidentified signed ACK")
    with sqlite3.connect(str(outbox_path), isolation_level=None, timeout=10) as db:
        init_outbox(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT envelope_json, acknowledgement_json FROM pending_shipments WHERE delivery_id=?",
                             (delivery_id,)).fetchone()
            if row is None:
                raise InvalidWorld("ACK for nonexistent staged delivery")
            env = json.loads(row[0])
            verify_ack(common, policy, root, roster, gossip_root,
                       env, acknowledgement, now=now)
            old = json.loads(row[1]) if row[1] else None
            if old is not None and old != acknowledgement:
                raise InvalidWorld("ACK equivocation for one staged delivery")
            if old is None:
                db.execute("UPDATE pending_shipments SET acknowledgement_json=? WHERE delivery_id=?",
                           (json.dumps(acknowledgement, sort_keys=True, separators=(",", ":")), delivery_id))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return "ACKNOWLEDGED" if old is None else "ALREADY_ACKNOWLEDGED"


def make_inventory(inbox_path: Path, common: list, policy: dict, root: dict,
                   roster: dict, gossip_root: dict,
                   signer: IdentityKey, *, now: int):
    site = next((s for s in SITES if jwk(signer.public_jwk()) == jwk(roster["sites"][s])), None)
    if site is None:
        raise InvalidWorld("inventory signer is not a pinned site")
    rows = read_inbox(inbox_path)
    prior = verify_inbox(common, policy, root, roster, gossip_root,
                         rows, now=now, recipient=site)
    items = sorted(({"delivery_id": row["ack"]["delivery_id"],
                     "ack_digest": digest(row["ack"])} for row in rows),
                   key=lambda x: x["delivery_id"])
    body = {
        "schema": INVENTORY, "scope": "SIGNED_INBOX_HINT_NOT_RECEIPT_OF_DELIVERY",
        "roster_digest": digest(roster), "site": site, "receipt_count": len(rows),
        "signed_receipt_tail": prior, "items": items,
    }
    return {**body, "signature": sign(signer, body, ID)}


def verify_inventory(roster: dict, inventory: Any, expected_site: str):
    exact(inventory, (
        "schema", "scope", "roster_digest", "site", "receipt_count",
        "signed_receipt_tail", "items", "signature",
    ), "anti-entropy inventory")
    if (expected_site not in SITES or inventory["schema"] != INVENTORY
        or inventory["scope"] != "SIGNED_INBOX_HINT_NOT_RECEIPT_OF_DELIVERY"
        or inventory["site"] != expected_site or inventory["roster_digest"] != digest(roster)
        or type(inventory["receipt_count"]) is not int
        or inventory["receipt_count"] < 0 or inventory["receipt_count"] > 64
        or type(inventory["signed_receipt_tail"]) is not str
        or type(inventory["items"]) is not list
        or len(inventory["items"]) != inventory["receipt_count"]):
        raise InvalidWorld("inventory is wrong recipient, epoch or size")
    for item in inventory["items"]:
        exact(item, ("delivery_id", "ack_digest"), "inventory entry")
        if (type(item["delivery_id"]) is not str or type(item["ack_digest"]) is not str
            or len(item["delivery_id"]) != 64 or len(item["ack_digest"]) != 64):
            raise InvalidWorld("invalid inventory digest")
    if inventory["items"] != sorted(inventory["items"], key=lambda x: x["delivery_id"]) or len(
        {item["delivery_id"] for item in inventory["items"]}
    ) != len(inventory["items"]):
        raise InvalidWorld("duplicate or unsorted inventory IDs")
    body = {k: v for k, v in inventory.items() if k != "signature"}
    authenticated(roster["sites"][expected_site], body,
                  inventory["signature"], ID, "recipient inventory")


def reconcile(outbox_path: Path, roster: dict, inventory: dict | None = None):
    rows = read_outbox(outbox_path)
    if inventory is not None:
        site = inventory.get("site") if type(inventory) is dict else None
        verify_inventory(roster, inventory, site)
    items = {i["delivery_id"]: i["ack_digest"] for i in inventory["items"]} if inventory else {}
    result = {"pending_resend": [], "ack_recovery_needed": [],
              "acknowledged": [], "inventory_only_not_proof": True}
    for row in rows:
        id_ = digest(row["envelope"])
        if row["ack"] is not None:
            result["acknowledged"].append(id_)
        elif inventory is not None and row["envelope"]["recipient"] == inventory["site"] and id_ in items:
            result["ack_recovery_needed"].append(id_)
        else:
            result["pending_resend"].append(id_)
    for key_ in ("pending_resend", "ack_recovery_needed", "acknowledged"):
        result[key_].sort()
    return result


def demo():
    tmp, west, east, keys, roster = fork_fixture()
    try:
        root = keys["gossip-root"].public_jwk()
        west_observations = Path(tmp.name) / "west-observations.sqlite"
        east_observations = Path(tmp.name) / "east-observations.sqlite"
        observe_once(west_observations, west, roster, root, "west",
                     keys["gossip-west"], now=1001)
        observe_once(east_observations, east, roster, root, "east",
                     keys["gossip-east"], now=1001)
        pwest = make_package(west, roster, "west", west_observations)
        peast = make_package(east, roster, "east", east_observations)
        common, policy, log_root = west[:17], west[17], west[18]
        envelope = make_envelope(common, policy, log_root, roster, root,
                                 pwest, "east", keys["gossip-west"])
        outbox = Path(tmp.name) / "west-outbox.sqlite"
        inbox = Path(tmp.name) / "east-inbox.sqlite"
        staged = stage_once(outbox, common, policy, log_root,
                            roster, root, envelope, now=1001)
        dropped = reconcile(outbox, roster)  # first packet not transferred
        resumed = read_outbox(outbox)  # emulate restart with the already committed bytes
        deliver = receive_once(inbox, common, policy, log_root, roster, root,
                               resumed[0]["envelope"], peast,
                               keys["gossip-east"], now=1001)
        lost_ack = reconcile(outbox, roster)  # recipient receipt not yet at sender
        inventory = make_inventory(inbox, common, policy, log_root,
                                   roster, root, keys["gossip-east"], now=1001)
        hinted = reconcile(outbox, roster, inventory)
        inventory_had_no_ack = read_outbox(outbox)[0]["ack"] is None
        retry = receive_once(inbox, common, policy, log_root, roster, root,
                             resumed[0]["envelope"], peast,
                             keys["gossip-east"], now=1001)
        # Receiving duplicate yields the identical signed local ACK, not a new effect.
        acknowledged = confirm_once(outbox, common, policy, log_root, roster, root,
                                     retry["ack"], now=1001)
        report = compare_views(common, policy, log_root, roster, root,
                               peast, pwest, now=1001)
        return {
            "staged_durably": staged["status"] == "STAGED_DURABLY",
            "first_message_dropped_pending": len(dropped["pending_resend"]) == 1,
            "restored_from_outbox": len(resumed) == 1,
            "fork_detected_at_recipient": report["decision"],
            "first_receiver_result": deliver["status"],
            "lost_ack_kept_pending": len(lost_ack["pending_resend"]) == 1,
            "anti_entropy_reports_ack_recovery": len(hinted["ack_recovery_needed"]) == 1,
            "inventory_alone_not_ack": inventory_had_no_ack,
            "repeat_is_idempotent": retry["ack"] == deliver["ack"],
            "recorded_ack": acknowledged,
            "outbox_cleared_by_signed_ack": len(reconcile(outbox, roster)["pending_resend"]) == 0,
            "recipient_inbox_preserved": len(read_inbox(inbox)) == 1,
            "010_observation_journals_unchanged": len(read_local(west_observations, "west")) == 1
                and len(read_local(east_observations, "east")) == 1,
            "native_external_execution": False,
        }
    finally:
        tmp.cleanup()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "verify"))
    names = ("parent", "roster", "challenge", "statements", "primary_anchor",
             "primary_precommit", "primary_measurement", "pinset",
             "primary_custody", "secondary_custody", "secondary_measurement",
             "manifest", "attestations", "audit_policy", "audit_commits",
             "audit_reports", "trusted_root")
    for name in names + ("log_policy", "log_root", "gossip_roster", "gossip_root",
                         "envelope", "ack"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path)
    parser.add_argument("--now", type=int)
    args = parser.parse_args()
    if args.command == "demo":
        output = demo()
    else:
        mandatory = names + ("log_policy", "log_root", "gossip_roster",
                             "gossip_root", "envelope", "ack")
        if args.now is None or any(getattr(args, x) is None for x in mandatory):
            parser.error("verify requires all 008 source artifacts and signed 011 evidence plus --now")
        try:
            common = [load(getattr(args, n)) for n in names]
            evidence = [load(getattr(args, n)) for n in mandatory[len(names):]]
            decision = verify_ack(common, evidence[0], evidence[1], evidence[2],
                                  evidence[3], evidence[4], evidence[5], now=args.now)
            output = {"verified": True, "decision": decision["decision"]}
        except (InvalidWorld, ValueError, KeyError, TypeError, OSError, IdentityProfileError) as exc:
            parser.error(str(exc))
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
