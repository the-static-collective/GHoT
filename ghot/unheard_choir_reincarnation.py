#!/usr/bin/env python3
"""UNHEARD CHOIR 013 — The Letter That Outlived Its Address.

A signed 012 parcel can remain historically verifiable after its named receiver
has been reconstituted with a fresh, separately pinned signing identity.
Old destination authority never crosses incarnation boundaries. A fresh owner
may sign a parcel-specific permission to archive it as history only. No device
authority, native reLATTE crossing, real identity or wall-clock assertion.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_dead_letter import build_fixture as fixture012, unpack
from unheard_choir_gossip import compare_views, verify_package
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes,
    normalize_public_jwk, verify_p256,
)

INCARNATION = "ghot.unheard-choir-013-owner-incarnation/v0"
GRANT = "ghot.unheard-choir-013-archive-grant/v0"
RECEIPT = "ghot.unheard-choir-013-custody-receipt/v0"
IDOM = b"GHOT-CHOIR-013-INCARNATION-v0|"
GDOM = b"GHOT-CHOIR-013-ARCHIVE-GRANT-v0|"
RDOM = b"GHOT-CHOIR-013-OWNER-CUSTODY-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-013-genesis/v0"})
HOLD = "HOLD_STALE_INCARNATION_NO_ARCHIVE_GRANT"
ARCHIVED = "HOLD_ARCHIVED_AS_HISTORY_BY_NEW_OWNER_NOT_ADMITTED"
ACTION = "ARCHIVE_HISTORICAL_EVIDENCE_ONLY"


def exact(x: Any, fields: tuple | set, label: str):
    if type(x) is not dict or set(x) != set(fields):
        raise InvalidWorld(label + ": missing or unexpected fields")


def jwk(x: Any):
    try:
        return normalize_public_jwk(x)
    except (IdentityProfileError, TypeError, ValueError) as error:
        raise InvalidWorld("invalid owner signing identity") from error


def sign(key: IdentityKey, body: dict, domain: bytes):
    return key.sign(domain + jcs_bytes(body))


def verify(body: dict, signature: Any, public: dict, domain: bytes, label: str):
    if type(signature) is not str or not verify_p256(jwk(public), domain + jcs_bytes(body), signature):
        raise InvalidWorld(label + ": invalid signature")


def make_incarnation(parcel: dict, historical_pins: dict,
                     new_owner: IdentityKey, *, epoch: int = 2):
    if type(epoch) is not int or epoch < 2 or epoch > 1000000:
        raise InvalidWorld("reconstituted epoch must be at least two")
    if jwk(new_owner.public_jwk()) == jwk(historical_pins["recipient_public_key"]):
        raise InvalidWorld("cannot reconstitute with the old signing identity")
    body = {
        "schema": INCARNATION, "scope": "LOCAL_NEW_OWNER_NOT_LEGACY_ADMISSION",
        "logical_address": historical_pins["recipient_site"],
        "old_pins_digest": digest(historical_pins),
        "old_owner_public_key": historical_pins["recipient_public_key"],
        "new_owner_public_key": new_owner.public_jwk(),
        "incarnation_epoch": epoch,
        "historical_parcel_digest": digest(parcel),
    }
    return {**body, "signature": sign(new_owner, body, IDOM)}


def verify_incarnation(parcel: dict, historical_pins: dict,
                       incarnation: Any, locally_pinned_new_owner: Any):
    exact(incarnation, (
        "schema", "scope", "logical_address", "old_pins_digest",
        "old_owner_public_key", "new_owner_public_key",
        "incarnation_epoch", "historical_parcel_digest", "signature",
    ), "reconstituted owner")
    if (incarnation["schema"] != INCARNATION
        or incarnation["scope"] != "LOCAL_NEW_OWNER_NOT_LEGACY_ADMISSION"
        or incarnation["logical_address"] != historical_pins["recipient_site"]
        or incarnation["old_pins_digest"] != digest(historical_pins)
        or jwk(incarnation["old_owner_public_key"]) != jwk(historical_pins["recipient_public_key"])
        or jwk(incarnation["new_owner_public_key"]) != jwk(locally_pinned_new_owner)
        or jwk(locally_pinned_new_owner) == jwk(historical_pins["recipient_public_key"])
        or type(incarnation["incarnation_epoch"]) is not int
        or not 2 <= incarnation["incarnation_epoch"] <= 1000000
        or incarnation["historical_parcel_digest"] != digest(parcel)):
        raise InvalidWorld("old owner or old parcel cannot become current owner authority")
    body = {k: v for k, v in incarnation.items() if k != "signature"}
    verify(body, incarnation["signature"], locally_pinned_new_owner, IDOM,
           "new-owner incarnation")
    # Historical parcel and parent signatures are independently verified, but
    # do NOT gain authority in the current incarnation.
    common, policy, root, roster, gossip_root, env = unpack(parcel, historical_pins)
    if env["recipient"] != incarnation["logical_address"]:
        raise InvalidWorld("predecessor parcel never named this logical address")
    return common, policy, root, roster, gossip_root, env


def make_archive_grant(parcel: dict, incarnation: dict,
                       new_owner: IdentityKey, *, not_after: int):
    if jwk(new_owner.public_jwk()) != jwk(incarnation["new_owner_public_key"]):
        raise InvalidWorld("old signer cannot authorize new archival disposition")
    if type(not_after) is not int or not 0 <= not_after <= 9999999:
        raise InvalidWorld("invalid archival grant clock bound")
    body = {
        "schema": GRANT, "scope": "NEW_OWNER_LOCAL_HISTORY_ONLY",
        "action": ACTION,
        "incarnation_digest": digest(incarnation),
        "historical_parcel_digest": digest(parcel),
        "recipient": incarnation["logical_address"],
        "epoch": incarnation["incarnation_epoch"],
        "simulated_not_after": not_after,
    }
    return {**body, "signature": sign(new_owner, body, GDOM)}


def verify_grant(parcel: dict, incarnation: dict,
                 locally_pinned_new_owner: dict, grant: Any, *, now: int):
    exact(grant, ("schema", "scope", "action", "incarnation_digest",
                  "historical_parcel_digest", "recipient", "epoch",
                  "simulated_not_after", "signature"), "archive grant")
    if (grant["schema"] != GRANT
        or grant["scope"] != "NEW_OWNER_LOCAL_HISTORY_ONLY"
        or grant["action"] != ACTION
        or grant["incarnation_digest"] != digest(incarnation)
        or grant["historical_parcel_digest"] != digest(parcel)
        or grant["recipient"] != incarnation["logical_address"]
        or grant["epoch"] != incarnation["incarnation_epoch"]
        or type(grant["simulated_not_after"]) is not int
        or not 0 <= grant["simulated_not_after"] <= 9999999):
        raise InvalidWorld("archive grant not bound to exact new owner and historic parcel")
    body = {k: v for k, v in grant.items() if k != "signature"}
    verify(body, grant["signature"], locally_pinned_new_owner, GDOM, "archive grant")
    if now > grant["simulated_not_after"]:
        raise InvalidWorld("new owner's archive grant expired")


def assess(parcel: dict, historic_local_package: dict, historic_pins: dict,
           incarnation: dict, current_owner_pin: dict,
           archive_grant: dict | None, *, now: int):
    if type(now) is not int or now < 0:
        raise InvalidWorld("invalid owner-local simulated clock")
    common, policy, root, roster, gossip_root, env = verify_incarnation(
        parcel, historic_pins, incarnation, current_owner_pin)
    if (type(historic_local_package) is not dict
        or historic_local_package.get("site") != historic_pins["recipient_site"]):
        raise InvalidWorld("old receiver's independent observation is required")
    # Historical signatures remain verifiable after the 012 expiry; historical
    # evidence is checked at the original signed challenge instant, not promoted
    # to any current action/grant.
    historical_instant = common[2]["issued_at"]
    verify_package(common, policy, root, roster, gossip_root,
                   historic_pins["recipient_site"], historic_local_package,
                   now=historical_instant)
    comparison = compare_views(common, policy, root, roster, gossip_root,
                               historic_local_package, env["origin_package"],
                               now=historical_instant)
    if comparison["decision"] != "HOLD_GOSSIP_REVEALS_UNSEEN_FORK":
        raise InvalidWorld("expected historically verified signed fork is absent")
    if archive_grant is not None:
        verify_grant(parcel, incarnation, current_owner_pin, archive_grant, now=now)
        decision = ARCHIVED
    else:
        decision = HOLD
    result = {
        "schema": "ghot.unheard-choir-013-owner-local-assessment/v0",
        "parcel_digest": digest(parcel),
        "historic_pins_digest": digest(historic_pins),
        "historic_local_package_digest": digest(historic_local_package),
        "historic_fork_assessment_digest": comparison["assessment_digest"],
        "new_incarnation_digest": digest(incarnation),
        "locally_pinned_new_owner_digest": digest(current_owner_pin),
        "grant_digest": digest(archive_grant) if archive_grant is not None else None,
        "simulated_receiver_clock": now,
        "original_parcel_not_after": parcel["simulated_not_after"],
        "historical_parcel_signatures_verified": True,
        "decision": decision,
        "old_receiver_identity_has_current_grants": False,
        "historical_expiry_extends_current_authority": False,
        "archived_evidence_is_native_admission": False,
        "forward_or_redirect_permitted": False,
        "native_relatte_receive": False,
        "external_execution": False,
        "authority": "NONE",
        "effects": [],
    }
    result["assessment_digest"] = digest(result)
    return result


def make_receipt(assessment: dict, new_owner: IdentityKey,
                 *, index: int, predecessor: str):
    if type(index) is not int or index < 0 or type(predecessor) is not str:
        raise InvalidWorld("invalid owner-local receipt position")
    body = {
        "schema": RECEIPT,
        "scope": "RECONSTITUTED_RECEIVER_LOCAL_HISTORY_ONLY",
        "local_index": index,
        "previous_receipt_digest": predecessor,
        "assessment": assessment,
    }
    return {**body, "signature": sign(new_owner, body, RDOM)}


def verify_receipt(parcel: dict, historic_local_package: dict,
                   historic_pins: dict, incarnation: dict, current_owner_pin: dict,
                   archive_grant: dict | None, receipt: Any):
    exact(receipt, ("schema", "scope", "local_index", "previous_receipt_digest",
                    "assessment", "signature"), "013 custody receipt")
    if (receipt["schema"] != RECEIPT
        or receipt["scope"] != "RECONSTITUTED_RECEIVER_LOCAL_HISTORY_ONLY"
        or type(receipt["local_index"]) is not int or receipt["local_index"] < 0
        or receipt["local_index"] != 0
        or receipt["previous_receipt_digest"] != GENESIS
        or type(receipt["assessment"]) is not dict):
        raise InvalidWorld("not a bounded 013 custody receipt")
    claimed_now = receipt["assessment"].get("simulated_receiver_clock")
    original = assess(parcel, historic_local_package, historic_pins,
                      incarnation, current_owner_pin, archive_grant,
                      now=claimed_now)
    if original != receipt["assessment"]:
        raise InvalidWorld("custody receipt disagrees with replayed locally pinned assessment")
    body = {k: v for k, v in receipt.items() if k != "signature"}
    verify(body, receipt["signature"], current_owner_pin, RDOM, "new-owner custody")
    return original


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS owner_history (
        local_index INTEGER PRIMARY KEY,
        parcel_digest TEXT NOT NULL UNIQUE,
        receipt_json TEXT NOT NULL
    )""")


def read_receipts(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        return [json.loads(row[0]) for row in db.execute(
            "SELECT receipt_json FROM owner_history ORDER BY local_index").fetchall()]


def import_once(parcel: dict, historic_local_package: dict,
                historic_pins: dict, incarnation: dict, current_owner_pin: dict,
                archive_grant: dict | None, new_owner: IdentityKey,
                db_path: Path, *, now: int):
    if jwk(new_owner.public_jwk()) != jwk(current_owner_pin):
        raise InvalidWorld("owner-local receipt may only be signed by currently pinned incarnation")
    assessment = assess(parcel, historic_local_package, historic_pins,
                        incarnation, current_owner_pin, archive_grant, now=now)
    with sqlite3.connect(str(db_path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [json.loads(row[0]) for row in db.execute(
                "SELECT receipt_json FROM owner_history ORDER BY local_index").fetchall()]
            # Bounded one-parcel fixture. A future multiparcel design must keep
            # per-row source evidence in an independently trusted local catalog.
            previous = GENESIS
            for i, row in enumerate(rows):
                exact(row, ("schema", "scope", "local_index",
                            "previous_receipt_digest", "assessment", "signature"),
                      "historical custody journal")
                if row["local_index"] != i or row["previous_receipt_digest"] != previous:
                    raise InvalidWorld("local signed chain damaged")
                verify_receipt(parcel, historic_local_package, historic_pins,
                               incarnation, current_owner_pin, archive_grant, row)
                previous = digest(row)
            duplicate = next((row for row in rows
                              if row["assessment"]["parcel_digest"] == digest(parcel)), None)
            if duplicate:
                if duplicate["assessment"] != assessment:
                    raise InvalidWorld("owner-local replay cannot retroactively change signed disposition")
                result = {"status": "DUPLICATE_UNCHANGED", "receipt": duplicate}
            else:
                if rows:
                    raise InvalidWorld("one-parcel fixture does not authorize a multiparcel journal")
                receipt = make_receipt(assessment, new_owner,
                                       index=0, predecessor=GENESIS)
                db.execute("INSERT INTO owner_history VALUES (?,?,?)",
                           (0, digest(parcel),
                            json.dumps(receipt, separators=(",", ":"), sort_keys=True)))
                result = {"status": "SIGNED_HISTORY_RECEIPT_WRITTEN", "receipt": receipt}
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return result


def build_fixture():
    tmp, parcel, east_package, pins, keys = fixture012()
    current = IdentityKey.load_or_create(Path(tmp.name) / "east-reconstituted.pem")
    keys["east-reconstituted"] = current
    incarnation = make_incarnation(parcel, pins, current, epoch=2)
    grant = make_archive_grant(parcel, incarnation, current, not_after=5000)
    return tmp, parcel, east_package, pins, incarnation, current.public_jwk(), grant, keys


def demo():
    tmp, parcel, local, pins, incarnation, current_pin, grant, keys = build_fixture()
    try:
        cwd = Path(tmp.name)
        db_without = cwd / "new-east-no-grant.sqlite"
        db_with = cwd / "new-east-owner-granted.sqlite"
        held = import_once(parcel, local, pins, incarnation, current_pin, None,
                           keys["east-reconstituted"], db_without, now=1100)
        authorized = import_once(parcel, local, pins, incarnation, current_pin, grant,
                                 keys["east-reconstituted"], db_with, now=1100)
        return {
            "historic_parcel_expired_at": parcel["simulated_not_after"],
            "new_incarnation_epoch": incarnation["incarnation_epoch"],
            "new_receiver_key_distinct": jwk(current_pin) != jwk(pins["recipient_public_key"]),
            "historical_fork_signatures_survive": held["receipt"]["assessment"]["historical_parcel_signatures_verified"],
            "no_grant_decision": held["receipt"]["assessment"]["decision"],
            "owner_archival_decision": authorized["receipt"]["assessment"]["decision"],
            "signed_receipts_persisted": len(read_receipts(db_without)) == 1 and len(read_receipts(db_with)) == 1,
            "cold_public_receipt_verifies": (
                verify_receipt(parcel, local, pins, incarnation, current_pin, grant,
                               authorized["receipt"])["decision"] == ARCHIVED
            ),
            "no_native_relatte_receipt": not authorized["receipt"]["assessment"]["native_relatte_receive"],
            "no_forwarding": not authorized["receipt"]["assessment"]["forward_or_redirect_permitted"],
            "no_execution": not authorized["receipt"]["assessment"]["external_execution"],
        }
    finally:
        tmp.cleanup()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "import", "verify"))
    for name in ("parcel", "historic-local-package", "historic-pins",
                 "incarnation", "current-owner-pin", "archive-grant",
                 "new-owner-key", "receiver-db", "receipt"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--now", type=int)
    opts = parser.parse_args()
    try:
        if opts.command == "demo":
            output = demo()
        else:
            required = ("parcel", "historic_local_package", "historic_pins",
                        "incarnation", "current_owner_pin")
            if any(getattr(opts, name) is None for name in required):
                parser.error("import/verify require all historical evidence and locally pinned new owner")
            parcel, old, pins, incarnation, public = (load(getattr(opts, n)) for n in required)
            grant = load(opts.archive_grant) if opts.archive_grant else None
            if opts.command == "import":
                if not opts.new_owner_key or not opts.receiver_db or opts.now is None:
                    parser.error("import requires existing new-owner key, --receiver-db and --now")
                if not opts.new_owner_key.is_file():
                    parser.error("new-owner key must be preexisting; importer cannot create a new identity")
                signer = IdentityKey.load_or_create(opts.new_owner_key)
                output = import_once(parcel, old, pins, incarnation, public,
                                     grant, signer, opts.receiver_db, now=opts.now)
            else:
                if not opts.receipt:
                    parser.error("verify requires public --receipt")
                verified = verify_receipt(parcel, old, pins, incarnation, public,
                                          grant, load(opts.receipt))
                output = {"verified": True, "decision": verified["decision"]}
    except (InvalidWorld, ValueError, TypeError, KeyError, OSError,
            IdentityProfileError, sqlite3.Error) as err:
        parser.error(str(err))
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
