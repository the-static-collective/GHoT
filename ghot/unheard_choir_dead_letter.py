#!/usr/bin/env python3
"""UNHEARD CHOIR 012 — The Dead Letter That Came Home.

Offline file parcel of 011 signed fork evidence, independently pinned receiving
owner, and independently signed owner-local HOLD/REJECT custody receipt.
Verifiable in a new process without source private keys, network or GHoT effects.
This is NOT a native reLATTE crossing/RECEIVE, trusted timestamp, physical
custody or remotely immutable journal.
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
    fork_fixture, make_package, observe_once, compare_views, check_roster,
)
from unheard_choir_vanishing import (
    make_envelope, verify_envelope,
)
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk, verify_p256,
)

PARCEL = "ghot.unheard-choir-012-offline-parcel/v0"
PINS = "ghot.unheard-choir-012-local-pins/v0"
RECEIPT = "ghot.unheard-choir-012-owner-local-custody/v0"
PARCEL_DOMAIN = b"GHOT-CHOIR-012-PARCEL-v0|"
RECEIPT_DOMAIN = b"GHOT-CHOIR-012-CUSTODY-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-012-local-custody-genesis/v0"})
HELD = "RECEIVED_HELD_FORK_EVIDENCE_NOT_ADMITTED"
EXPIRED = "REJECT_EXPIRED_SIMULATED_WINDOW"
WRONG = "REJECT_WRONG_DESTINATION"
NO_FORK = "HOLD_NO_CONFIRMED_FORK"
PUBLIC_ROLES = (
    "parent", "roster", "challenge", "statements", "primary_anchor",
    "primary_precommit", "primary_measurement", "pinset",
    "primary_custody", "secondary_custody", "secondary_measurement",
    "manifest", "attestations", "audit_policy", "audit_commits",
    "audit_reports", "trusted_root",
)


def exact(item: Any, keys: Any, label: str):
    if type(item) is not dict or set(item) != set(keys):
        raise InvalidWorld(label + ": missing or unexpected keys")


def jwk(item):
    try:
        return normalize_public_jwk(item)
    except (IdentityProfileError, ValueError, TypeError) as exc:
        raise InvalidWorld("invalid P-256 public key") from exc


def sign(key: IdentityKey, data: dict, domain: bytes):
    return key.sign(domain + jcs_bytes(data))


def verify_sig(data: dict, signature: Any, pub: dict, domain: bytes, label: str):
    if type(signature) is not str or not verify_p256(jwk(pub), domain + jcs_bytes(data), signature):
        raise InvalidWorld(label + ": invalid pinned P-256 signature")


def make_local_pins(common: list, log_root: dict, gossip_roster: dict,
                    gossip_root: dict, local_site: str):
    if local_site not in ("west", "east"):
        raise InvalidWorld("unknown receiving vessel")
    return {
        "schema": PINS, "scope": "RECEIVER_LOCAL_PREPROVISIONED_TRUST_NOT_AUTHORITY",
        "recipient_site": local_site,
        "recipient_public_key": gossip_roster["sites"][local_site],
        "008_external_root": common[16],
        "009_external_root": log_root,
        "010_external_root": gossip_root,
        "roster_digest": digest(gossip_roster),
    }


def check_pins(pins: Any):
    exact(pins, ("schema", "scope", "recipient_site", "recipient_public_key",
                 "008_external_root", "009_external_root",
                 "010_external_root", "roster_digest"), "local trust pins")
    if (pins["schema"] != PINS or
        pins["scope"] != "RECEIVER_LOCAL_PREPROVISIONED_TRUST_NOT_AUTHORITY" or
        pins["recipient_site"] not in ("west", "east")):
        raise InvalidWorld("wrong local trust configuration")
    for label in ("recipient_public_key", "008_external_root", "009_external_root", "010_external_root"):
        jwk(pins[label])
    if type(pins["roster_digest"]) is not str or len(pins["roster_digest"]) != 64:
        raise InvalidWorld("malformed locally pinned roster digest")


def make_parcel(common: list, log_policy: dict, log_root: dict,
                roster: dict, gossip_root: dict, sender_envelope: dict,
                signer: IdentityKey, *, not_after: int, nonce: str):
    if type(nonce) is not str or len(nonce) != 32 or not nonce.isascii() or not nonce.isalnum():
        raise InvalidWorld("nonce must be exactly 32 ASCII alphanumerics")
    source_expiry = common[2]["expires_at"]
    if type(not_after) is not int or not common[2]["issued_at"] <= not_after <= source_expiry:
        raise InvalidWorld("parcel window cannot exceed signed owner challenge")
    if len(common) != len(PUBLIC_ROLES):
        raise InvalidWorld("missing inherited 008 public evidence")
    sender = sender_envelope["sender"]
    if jwk(signer.public_jwk()) != jwk(roster["sites"][sender]):
        raise InvalidWorld("parcel sender must own the 011 envelope's pinned key")
    # Verify payload against authentic ancestry before signing a new container.
    verify_envelope(common, log_policy, log_root, roster, gossip_root,
                    sender_envelope, now=common[2]["issued_at"])
    cargo = {
        "schema": "ghot.unheard-choir-012-public-cargo/v0",
        "common_evidence": dict(zip(PUBLIC_ROLES, common)),
        "log_policy": log_policy,
        "log_root": log_root,
        "gossip_roster": roster,
        "gossip_root": gossip_root,
        "011_envelope": sender_envelope,
    }
    body = {
        "schema": PARCEL,
        "scope": "OFFLINE_EVIDENCE_TRANSPORT_ONLY",
        "sender": sender,
        "recipient": sender_envelope["recipient"],
        "simulated_not_after": not_after,
        "nonce": nonce,
        "cargo_digest": digest(cargo),
        "cargo": cargo,
    }
    return {**body, "signature": sign(signer, body, PARCEL_DOMAIN)}


def unpack(parcel: Any, pins: Any):
    check_pins(pins)
    exact(parcel, ("schema", "scope", "sender", "recipient",
                   "simulated_not_after", "nonce", "cargo_digest",
                   "cargo", "signature"), "offline parcel")
    if (parcel["schema"] != PARCEL or parcel["scope"] != "OFFLINE_EVIDENCE_TRANSPORT_ONLY"
        or parcel["sender"] not in ("west", "east")
        or parcel["recipient"] not in ("west", "east")
        or parcel["sender"] == parcel["recipient"]
        or type(parcel["nonce"]) is not str or len(parcel["nonce"]) != 32
        or not parcel["nonce"].isascii() or not parcel["nonce"].isalnum()
        or type(parcel["simulated_not_after"]) is not int):
        raise InvalidWorld("invalid or insufficiently scoped parcel")
    cargo = parcel["cargo"]
    exact(cargo, ("schema", "common_evidence", "log_policy", "log_root",
                  "gossip_roster", "gossip_root", "011_envelope"), "public cargo")
    if cargo["schema"] != "ghot.unheard-choir-012-public-cargo/v0":
        raise InvalidWorld("unsupported cargo schema")
    exact(cargo["common_evidence"], PUBLIC_ROLES, "inherited public sources")
    common = [cargo["common_evidence"][name] for name in PUBLIC_ROLES]
    log_policy, log_root = cargo["log_policy"], cargo["log_root"]
    roster, gossip_root = cargo["gossip_roster"], cargo["gossip_root"]
    env = cargo["011_envelope"]
    if (jwk(common[16]) != jwk(pins["008_external_root"])
        or jwk(log_root) != jwk(pins["009_external_root"])
        or jwk(gossip_root) != jwk(pins["010_external_root"])
        or digest(roster) != pins["roster_digest"]
        or jwk(roster["sites"][pins["recipient_site"]]) != jwk(pins["recipient_public_key"])):
        raise InvalidWorld("parcel trust roots don't match independent local pinset")
    if parcel["cargo_digest"] != digest(cargo):
        raise InvalidWorld("cargo integrity digest mismatch")
    if (parcel["sender"] != env["sender"]
        or parcel["recipient"] != env["recipient"]):
        raise InvalidWorld("parcel route not equal to signed 011 envelope route")
    challenge = common[2]
    if not challenge["issued_at"] <= parcel["simulated_not_after"] <= challenge["expires_at"]:
        raise InvalidWorld("parcel expiry violates original signed challenge")
    check_roster(common + [log_policy, log_root, [], []], roster, gossip_root)
    body = {k: v for k, v in parcel.items() if k != "signature"}
    verify_sig(body, parcel["signature"], roster["sites"][parcel["sender"]],
               PARCEL_DOMAIN, "offline sender parcel")
    # Verify historical signature integrity at the signed challenge instant.
    # It is NOT a decision that current source grants remain fresh.
    verify_envelope(common, log_policy, log_root, roster, gossip_root,
                    env, now=challenge["issued_at"])
    return common, log_policy, log_root, roster, gossip_root, env


def assess_parcel(parcel: dict, local_package: dict, pins: dict, *, now: int):
    if type(now) is not int or now < 0:
        raise InvalidWorld("invalid receiver-local simulation clock")
    common, policy, log_root, roster, gossip_root, env = unpack(parcel, pins)
    if local_package.get("site") != pins["recipient_site"]:
        raise InvalidWorld("receiver's separately held local package must match local site")
    recipient = pins["recipient_site"]
    # Independent local package is not in the mailed parcel. Check even on rejects.
    from unheard_choir_gossip import verify_package
    verify_package(common, policy, log_root, roster, recipient,
                   local_package, now=common[2]["issued_at"])
    if parcel["recipient"] != recipient:
        decision, comparison = WRONG, None
    elif now > parcel["simulated_not_after"] or now > common[2]["expires_at"]:
        decision, comparison = EXPIRED, None
    else:
        comparison = compare_views(common, policy, log_root, roster, gossip_root,
                                   local_package, env["origin_package"], now=now)
        decision = HELD if comparison["decision"] == "HOLD_GOSSIP_REVEALS_UNSEEN_FORK" else NO_FORK
    return {
        "decision": decision,
        "comparison_digest": comparison["assessment_digest"] if comparison else None,
        "recipient_site": recipient,
        "parcel_digest": digest(parcel),
        "local_package_digest": digest(local_package),
        "local_pins_digest": digest(pins),
        "checked_at_simulated_clock": now,
        "native_relatte_receive": False,
        "native_relatte_admission": False,
        "external_execution": False,
    }


def init_db(connection: sqlite3.Connection):
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("""CREATE TABLE IF NOT EXISTS custody (
        local_index INTEGER PRIMARY KEY,
        parcel_digest TEXT NOT NULL UNIQUE,
        receipt_json TEXT NOT NULL
    )""")


def read_receipts(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        rows = db.execute("SELECT receipt_json FROM custody ORDER BY local_index").fetchall()
    return [json.loads(row[0]) for row in rows]


def verify_receipt(parcel: dict, local_package: dict, pins: dict, receipt: Any):
    check_pins(pins)
    exact(receipt, ("schema", "scope", "local_index", "previous_receipt_digest",
                    "assessment", "signature"), "receiver custody receipt")
    if (receipt["schema"] != RECEIPT
        or receipt["scope"] != "SIGNED_RECEIVER_LOCAL_CUSTODY_NO_ADMISSION"
        or type(receipt["local_index"]) is not int or receipt["local_index"] < 0
        or type(receipt["previous_receipt_digest"]) is not str):
        raise InvalidWorld("local custody receipt has invalid authority or index")
    assessment = assess_parcel(parcel, local_package, pins,
                               now=receipt["assessment"]["checked_at_simulated_clock"])
    if assessment != receipt["assessment"]:
        raise InvalidWorld("signed local receipt does not reproduce receiver decision")
    body = {k: v for k, v in receipt.items() if k != "signature"}
    verify_sig(body, receipt["signature"], pins["recipient_public_key"],
               RECEIPT_DOMAIN, "owner-local custody receipt")
    return assessment


def verify_history(rows: list, parcel: dict, local_package: dict, pins: dict):
    # Strictly scoped to one-parcel demo; other rows can be checked against their
    # respective imported public evidence using a broader owner-local registry.
    if type(rows) is not list or len(rows) > 64:
        raise InvalidWorld("invalid local custody count")
    prior = GENESIS
    for i, row in enumerate(rows):
        exact(row, ("schema", "scope", "local_index", "previous_receipt_digest",
                    "assessment", "signature"), "stored custody receipt")
        if row["local_index"] != i or row["previous_receipt_digest"] != prior:
            raise InvalidWorld("custody chain index or predecessor mismatch")
        verify_receipt(parcel, local_package, pins, row)
        prior = digest(row)
    return prior


def import_once(parcel: dict, local_package: dict, pins: dict,
                signer: IdentityKey, db_path: Path, *, now: int):
    if jwk(signer.public_jwk()) != jwk(pins["recipient_public_key"]):
        raise InvalidWorld("import signer not provisioned for local receiving owner")
    assessment = assess_parcel(parcel, local_package, pins, now=now)
    with sqlite3.connect(str(db_path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [json.loads(row[0]) for row in db.execute(
                "SELECT receipt_json FROM custody ORDER BY local_index").fetchall()]
            prior = verify_history(rows, parcel, local_package, pins)
            present = next((row for row in rows if row["assessment"]["parcel_digest"] == digest(parcel)), None)
            if present is not None:
                if present["assessment"] != assessment:
                    raise InvalidWorld("replay under changed recipient clock or policy denied")
                output = {"status": "DUPLICATE_RECEIPT_REPLAY", "receipt": present}
            else:
                if len(rows) >= 64:
                    raise InvalidWorld("receiver local journal full")
                body = {
                    "schema": RECEIPT,
                    "scope": "SIGNED_RECEIVER_LOCAL_CUSTODY_NO_ADMISSION",
                    "local_index": len(rows),
                    "previous_receipt_digest": prior,
                    "assessment": assessment,
                }
                receipt = {**body, "signature": sign(signer, body, RECEIPT_DOMAIN)}
                db.execute("INSERT INTO custody VALUES(?,?,?)", (
                    len(rows), digest(parcel),
                    json.dumps(receipt, separators=(",", ":"), sort_keys=True),
                ))
                output = {"status": "RECEIPT_DURABLY_WRITTEN", "receipt": receipt}
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return output


def build_fixture():
    tmp, west, east, keys, roster = fork_fixture()
    folder = Path(tmp.name)
    west_db = folder / "west-010.sqlite"
    east_db = folder / "east-010.sqlite"
    root = keys["gossip-root"].public_jwk()
    observe_once(west_db, west, roster, root, "west", keys["gossip-west"], now=1001)
    observe_once(east_db, east, roster, root, "east", keys["gossip-east"], now=1001)
    west_package = make_package(west, roster, "west", west_db)
    east_package = make_package(east, roster, "east", east_db)
    env = make_envelope(west[:17], west[17], west[18], roster, root,
                        west_package, "east", keys["gossip-west"])
    parcel = make_parcel(west[:17], west[17], west[18], roster, root, env,
                         keys["gossip-west"], not_after=1050, nonce="a" * 32)
    pins = make_local_pins(west[:17], west[18], roster, root, "east")
    return tmp, parcel, east_package, pins, keys


def demo():
    tmp, parcel, local_package, pins, keys = build_fixture()
    try:
        recipient = Path(tmp.name) / "recipient-runtime"
        recipient.mkdir()
        parcel_path = recipient / "incoming.json"
        parcel_path.write_text(json.dumps(parcel, sort_keys=True), encoding="utf-8")
        local_path = recipient / "local-source.json"
        local_path.write_text(json.dumps(local_package, sort_keys=True), encoding="utf-8")
        pins_path = recipient / "trust-pins.json"
        pins_path.write_text(json.dumps(pins, sort_keys=True), encoding="utf-8")
        receipt_db = recipient / "custody.sqlite"
        imported = import_once(json.loads(parcel_path.read_text()),
                               json.loads(local_path.read_text()),
                               json.loads(pins_path.read_text()),
                               keys["gossip-east"], receipt_db, now=1001)
        again = import_once(parcel, local_package, pins, keys["gossip-east"],
                            receipt_db, now=1001)
        assessment = verify_receipt(parcel, local_package, pins, imported["receipt"])
        return {
            "portable_public_parcel": True,
            "sender_private_key_absent_from_parcel": "PRIVATE KEY" not in parcel_path.read_text(),
            "import_decision": assessment["decision"],
            "new_receipt": imported["status"],
            "duplicate_import": again["status"],
            "recipient_journal_entries": len(read_receipts(receipt_db)),
            "cold_public_verification": True,
            "source_and_receiver_authority_not_transferred": True,
            "native_relatte_receive": assessment["native_relatte_receive"],
            "external_execution": assessment["external_execution"],
        }
    finally:
        tmp.cleanup()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "import", "verify"))
    for name in ("parcel", "local-package", "pins", "receiver-key", "receiver-db", "receipt"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--now", type=int)
    args = parser.parse_args()
    try:
        if args.command == "demo":
            result = demo()
        else:
            if not args.parcel or not getattr(args, "local_package") or not args.pins:
                parser.error("import/verify need --parcel --local-package and --pins")
            parcel = load(args.parcel)
            local = load(args.local_package)
            pins = load(args.pins)
            if args.command == "import":
                if not args.receiver_key or not args.receiver_db or args.now is None:
                    parser.error("import requires local --receiver-key, --receiver-db and --now")
                if not args.receiver_key.is_file():
                    parser.error("local owner key missing; key is never created by import")
                signer = IdentityKey.load_or_create(args.receiver_key)
                result = import_once(parcel, local, pins, signer,
                                     args.receiver_db, now=args.now)
            else:
                if not args.receipt:
                    parser.error("verify requires public --receipt")
                decision = verify_receipt(parcel, local, pins, load(args.receipt))
                result = {"verified": True, "decision": decision["decision"]}
    except (InvalidWorld, ValueError, KeyError, TypeError, OSError, IdentityProfileError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
