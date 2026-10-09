#!/usr/bin/env python3
"""UNHEARD CHOIR 014 — The Two Equal Successors.

Two separately keyed, validly signed 013 incarnation claims can name one
historical address. A separately pinned, simulation-local review root authorizes
a scoped reviewer and a neutral local recorder. With no reviewer selection,
or with contradictory signed selections, a neutral receipt records HOLD.
A single selection plus a separate successor-signed 013 archival grant yields
only an archival HOLD, never successor legitimacy or native admission.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_reincarnation import (
    make_incarnation, make_archive_grant,
    verify_incarnation, verify_grant, assess as assess_013,
    build_fixture as build_013,
)
from unheard_choir_gossip import all_prior_keys
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes,
    normalize_public_jwk, particular_for_public_key, verify_p256,
)

POLICY = "ghot.unheard-choir-014-local-succession-policy/v0"
DECISION = "ghot.unheard-choir-014-review-selection/v0"
ASSESSMENT = "ghot.unheard-choir-014-two-successor-assessment/v0"
RECEIPT = "ghot.unheard-choir-014-neutral-custody-receipt/v0"
PDOM = b"GHOT-CHOIR-014-LOCAL-SUCCESSION-POLICY-v0|"
DDOM = b"GHOT-CHOIR-014-REVIEW-SELECTION-v0|"
RDOM = b"GHOT-CHOIR-014-NEUTRAL-CUSTODY-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-014-neutral-genesis/v0"})
CONTESTED = "HOLD_TWO_EQUAL_SUCCESSORS_UNRESOLVED"
EQUIVOCATED = "HOLD_CONTRADICTORY_SIGNED_SUCCESSION_SELECTIONS"
NO_GRANT = "HOLD_SELECTED_SUCCESSOR_NO_OWNER_ARCHIVAL_GRANT"
ARCHIVED = "HOLD_SELECTED_SUCCESSOR_ARCHIVAL_ONLY_NOT_ADMITTED"
CHOICES = ("north", "south")
SCOPE = "LOCAL_SIMULATED_HISTORY_ARCHIVE_REVIEW_ONLY"


def exact(value: Any, keys: tuple | set, name: str):
    if type(value) is not dict or set(value) != set(keys):
        raise InvalidWorld(f"{name}: missing or unexpected fields")


def public(raw: Any) -> dict:
    try:
        return normalize_public_jwk(raw)
    except (IdentityProfileError, ValueError, TypeError) as exc:
        raise InvalidWorld("invalid P-256 public key") from exc


def distinct(keys: list) -> bool:
    return len({particular_for_public_key(public(x)) for x in keys}) == len(keys)


def sign(signer: IdentityKey, body: dict, domain: bytes):
    return signer.sign(domain + jcs_bytes(body))


def authenticate(body: dict, signature: Any, signer: dict,
                 domain: bytes, name: str):
    if type(signature) is not str or not verify_p256(
        public(signer), domain + jcs_bytes(body), signature
    ):
        raise InvalidWorld(f"{name}: invalid P-256 signature")


def prior_keys(parcel: dict) -> list:
    cargo = parcel["cargo"]
    inputs = [cargo["common_evidence"][n] for n in (
        "parent", "roster", "challenge", "statements",
        "primary_anchor", "primary_precommit", "primary_measurement",
        "pinset", "primary_custody", "secondary_custody",
        "secondary_measurement", "manifest", "attestations",
        "audit_policy", "audit_commits", "audit_reports", "trusted_root",
    )]
    inputs += [cargo["log_policy"], cargo["log_root"], [], []]
    keys = all_prior_keys(inputs)
    keys += list(cargo["gossip_roster"]["sites"].values())
    keys.append(cargo["gossip_root"])
    return keys


def make_policy(parcel: dict, historical_pins: dict,
                candidates: dict[str, dict], root: IdentityKey,
                reviewer: IdentityKey, recorder: IdentityKey,
                *, epoch: int = 2) -> dict:
    if set(candidates) != set(CHOICES) or type(epoch) is not int or epoch < 2:
        raise InvalidWorld("exactly two epoch-2-or-later successor candidates required")
    for name in CHOICES:
        exact(candidates[name], ("incarnation", "owner_public_key"),
              "successor proposal")
        if candidates[name]["incarnation"]["incarnation_epoch"] != epoch:
            raise InvalidWorld("successor claim not in comparison epoch")
        verify_incarnation(parcel, historical_pins,
                           candidates[name]["incarnation"],
                           candidates[name]["owner_public_key"])
    keys = prior_keys(parcel)
    keys += [root.public_jwk(), reviewer.public_jwk(), recorder.public_jwk()]
    keys += [candidates[name]["owner_public_key"] for name in CHOICES]
    if not distinct(keys):
        raise InvalidWorld("all successors, root, reviewer and recorder must have separate P-256 keys")
    body = {
        "schema": POLICY, "scope": SCOPE,
        "old_parcel_digest": digest(parcel),
        "old_pins_digest": digest(historical_pins),
        "logical_address": historical_pins["recipient_site"],
        "competing_epoch": epoch,
        "candidates": {name: candidates[name] for name in CHOICES},
        "reviewer_public_key": reviewer.public_jwk(),
        "neutral_recorder_public_key": recorder.public_jwk(),
    }
    return {**body, "signature": sign(root, body, PDOM)}


def verify_policy(parcel: dict, historical_pins: dict,
                  policy: Any, locally_pinned_root: Any):
    exact(policy, ("schema", "scope", "old_parcel_digest",
                   "old_pins_digest", "logical_address",
                   "competing_epoch", "candidates",
                   "reviewer_public_key", "neutral_recorder_public_key",
                   "signature"), "succession policy")
    exact(policy["candidates"], CHOICES, "contenders")
    if (policy["schema"] != POLICY or policy["scope"] != SCOPE
        or policy["old_parcel_digest"] != digest(parcel)
        or policy["old_pins_digest"] != digest(historical_pins)
        or policy["logical_address"] != historical_pins["recipient_site"]
        or type(policy["competing_epoch"]) is not int
        or not 2 <= policy["competing_epoch"] <= 1000000):
        raise InvalidWorld("stale or foreign succession policy")
    for name in CHOICES:
        c = policy["candidates"][name]
        exact(c, ("incarnation", "owner_public_key"), "successor entry")
        if c["incarnation"]["incarnation_epoch"] != policy["competing_epoch"]:
            raise InvalidWorld("successor incarnations do not compete in same epoch")
        verify_incarnation(parcel, historical_pins,
                           c["incarnation"], c["owner_public_key"])
    keys = prior_keys(parcel)
    keys += [locally_pinned_root, policy["reviewer_public_key"],
             policy["neutral_recorder_public_key"]]
    keys += [policy["candidates"][name]["owner_public_key"] for name in CHOICES]
    if not distinct(keys):
        raise InvalidWorld("old signer, contender, reviewer, root or neutral recorder key collision")
    body = {k: v for k, v in policy.items() if k != "signature"}
    authenticate(body, policy["signature"], locally_pinned_root, PDOM,
                 "independently pinned local policy root")


def make_selection(policy: dict, reviewer: IdentityKey, chosen: str,
                   *, claimed_at: int = 1100, not_after: int = 5000) -> dict:
    if (chosen not in CHOICES or
        public(reviewer.public_jwk()) != public(policy["reviewer_public_key"])
        or type(claimed_at) is not int or type(not_after) is not int
        or not 0 <= claimed_at <= not_after <= 9999999):
        raise InvalidWorld("review decision requires pinned reviewer and bounded clock")
    body = {
        "schema": DECISION, "scope": SCOPE, "policy_digest": digest(policy),
        "chosen_candidate": chosen,
        "chosen_incarnation_digest": digest(policy["candidates"][chosen]["incarnation"]),
        "old_parcel_digest": policy["old_parcel_digest"],
        "simulated_claimed_at": claimed_at,
        "simulated_not_after": not_after,
        "effect_permission": "NONE",
    }
    return {**body, "signature": sign(reviewer, body, DDOM)}


def verify_selection(policy: dict, selection: Any, *, now: int):
    exact(selection, ("schema", "scope", "policy_digest",
                      "chosen_candidate", "chosen_incarnation_digest",
                      "old_parcel_digest", "simulated_claimed_at",
                      "simulated_not_after", "effect_permission", "signature"),
          "review selection")
    name = selection["chosen_candidate"]
    if (selection["schema"] != DECISION or selection["scope"] != SCOPE
        or name not in CHOICES or selection["policy_digest"] != digest(policy)
        or selection["chosen_incarnation_digest"] != digest(policy["candidates"][name]["incarnation"])
        or selection["old_parcel_digest"] != policy["old_parcel_digest"]
        or selection["effect_permission"] != "NONE"
        or type(selection["simulated_claimed_at"]) is not int
        or type(selection["simulated_not_after"]) is not int
        or not 0 <= selection["simulated_claimed_at"] <= selection["simulated_not_after"] <= 9999999):
        raise InvalidWorld("reviewer attempted unauthorized selection scope or epoch")
    body = {k: v for k, v in selection.items() if k != "signature"}
    authenticate(body, selection["signature"], policy["reviewer_public_key"],
                 DDOM, "reviewer selection")
    # An expired *validly signed* selection remains historical evidence but
    # cannot decide current archival custody. Represent this as a HOLD.
    return now > selection["simulated_not_after"]


def assess(parcel: dict, independent_old_local: dict, historical_pins: dict,
           policy: dict, locally_pinned_root: dict,
           selections: list, archive_grants: dict, *, now: int):
    if type(now) is not int or now < 0:
        raise InvalidWorld("invalid simulation-local clock")
    verify_policy(parcel, historical_pins, policy, locally_pinned_root)
    if type(selections) is not list or len(selections) > 2:
        raise InvalidWorld("at most two independently signed selection records")
    if type(archive_grants) is not dict or set(archive_grants) != set(CHOICES):
        raise InvalidWorld("archive-grant slots must be explicitly present for both candidates")
    seen = set()
    signed_selections, expired = [], []
    for item in selections:
        claim = item.get("chosen_candidate") if type(item) is dict else None
        if claim in seen:
            raise InvalidWorld("duplicate selection for same contender denied")
        expired_one = verify_selection(policy, item, now=now)
        seen.add(claim)
        signed_selections.append({"candidate": claim, "selection_digest": digest(item)})
        if expired_one:
            expired.append(claim)
    # These two histories remain owner-relative: the fact that two P-256 keys
    # verify does not appoint either key as the correct physical successor.
    claims = {}
    for name in CHOICES:
        c = policy["candidates"][name]
        r = assess_013(parcel, independent_old_local, historical_pins,
                       c["incarnation"], c["owner_public_key"], None, now=now)
        if r["decision"] != "HOLD_STALE_INCARNATION_NO_ARCHIVE_GRANT":
            raise InvalidWorld("inherited 013 predecessor restriction was cleared")
        claims[name] = {
            "public_key": c["owner_public_key"],
            "incarnation_digest": digest(c["incarnation"]),
            "inherited_013_digest": r["assessment_digest"],
            "history_alone_is_owner_authority": False,
        }
        grant = archive_grants[name]
        if grant is not None:
            # Verify the grant signature and narrow scope even if the recipient
            # is unselected. Expiry is a HOLD, not an admission.
            verify_grant(parcel, c["incarnation"], c["owner_public_key"],
                         grant, now=min(now, grant["simulated_not_after"]))
    valid = [x["candidate"] for x in signed_selections
             if x["candidate"] not in expired]
    if len(signed_selections) == 2 and len({
        x["candidate"] for x in signed_selections
    }) == 2:
        decision, chosen = EQUIVOCATED, None
    elif len(valid) == 0:
        decision, chosen = CONTESTED, None
    elif len(valid) == 1:
        chosen = valid[0]
        if archive_grants[chosen] is None or now > archive_grants[chosen]["simulated_not_after"]:
            decision = NO_GRANT
        else:
            # This permission is created by the selected contender, not by
            # the external reviewer or the historical 012 destination.
            granted = assess_013(parcel, independent_old_local, historical_pins,
                                 policy["candidates"][chosen]["incarnation"],
                                 policy["candidates"][chosen]["owner_public_key"],
                                 archive_grants[chosen], now=now)
            if granted["decision"] != "HOLD_ARCHIVED_AS_HISTORY_BY_NEW_OWNER_NOT_ADMITTED":
                raise InvalidWorld("013 archival grant never became archive-only HOLD")
            decision = ARCHIVED
    else:
        decision, chosen = EQUIVOCATED, None
    outcome = {
        "schema": ASSESSMENT,
        "policy_digest": digest(policy),
        "historical_parcel_digest": digest(parcel),
        "independent_historical_receiver_package_digest": digest(independent_old_local),
        "claims": claims,
        "signed_selection_claims": signed_selections,
        "expired_selection_candidates": sorted(expired),
        "archive_grant_digests": {
            n: digest(archive_grants[n]) if archive_grants[n] is not None else None
            for n in CHOICES
        },
        "selected_for_bounded_local_archival_review": chosen,
        "decision": decision,
        "competing_successors_have_separate_signatures": True,
        "global_rightful_successor_proven": False,
        "review_root_is_universal_authority": False,
        "local_review_authorizes_forwarding": False,
        "signed_history_creates_current_grant": False,
        "native_relatte_receive": False,
        "native_relatte_admission": False,
        "external_execution": False,
        "authority": "NONE", "effects": [],
        "simulated_receiver_clock": now,
    }
    outcome["assessment_digest"] = digest(outcome)
    return outcome


def make_receipt(outcome: dict, recorder: IdentityKey,
                 *, local_index: int = 0, previous: str = GENESIS):
    if type(local_index) is not int or local_index != 0 or previous != GENESIS:
        raise InvalidWorld("bounded neutral fixture requires genesis receipt")
    body = {
        "schema": RECEIPT, "scope": "NEUTRAL_LOCAL_CUSTODY_NOT_SUCCESSOR",
        "local_index": local_index, "previous_receipt_digest": previous,
        "assessment": outcome,
    }
    return {**body, "signature": sign(recorder, body, RDOM)}


def verify_receipt(parcel: dict, independent_old_local: dict, historical_pins: dict,
                   policy: dict, locally_pinned_root: dict,
                   selections: list, archive_grants: dict, receipt: Any):
    exact(receipt, ("schema", "scope", "local_index",
                    "previous_receipt_digest", "assessment", "signature"),
          "neutral succession custody receipt")
    if (receipt["schema"] != RECEIPT or
        receipt["scope"] != "NEUTRAL_LOCAL_CUSTODY_NOT_SUCCESSOR"
        or type(receipt["local_index"]) is not int or receipt["local_index"] != 0
        or receipt["previous_receipt_digest"] != GENESIS
        or type(receipt["assessment"]) is not dict):
        raise InvalidWorld("invalid neutral local receipt")
    replay = assess(parcel, independent_old_local, historical_pins,
                    policy, locally_pinned_root, selections, archive_grants,
                    now=receipt["assessment"].get("simulated_receiver_clock"))
    if receipt["assessment"] != replay:
        raise InvalidWorld("signed receipt contradicts replayed predecessor/selection evidence")
    body = {k: v for k, v in receipt.items() if k != "signature"}
    authenticate(body, receipt["signature"],
                 policy["neutral_recorder_public_key"], RDOM, "neutral recorder")
    return replay


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS disputed_succession (
        local_index INTEGER PRIMARY KEY,
        policy_digest TEXT NOT NULL UNIQUE,
        signed_receipt_json TEXT NOT NULL
    )""")


def read_receipts(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        return [json.loads(r[0]) for r in db.execute(
            "SELECT signed_receipt_json FROM disputed_succession ORDER BY local_index").fetchall()]


def record_once(db_path: Path, parcel: dict, independent_old_local: dict,
                historical_pins: dict, policy: dict, locally_pinned_root: dict,
                selections: list, archive_grants: dict, recorder: IdentityKey,
                *, now: int):
    if public(recorder.public_jwk()) != public(policy["neutral_recorder_public_key"]):
        raise InvalidWorld("only locally pinned neutral recorder may sign historical controversy")
    result = assess(parcel, independent_old_local, historical_pins,
                    policy, locally_pinned_root, selections, archive_grants, now=now)
    with sqlite3.connect(str(db_path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [json.loads(r[0]) for r in db.execute(
                "SELECT signed_receipt_json FROM disputed_succession ORDER BY local_index").fetchall()]
            if len(rows) > 1:
                raise InvalidWorld("fixture supports one signed controversy per local journal")
            if rows:
                saved = rows[0]
                # The prior receipt's signature is always checked before a retry.
                verify_receipt(parcel, independent_old_local, historical_pins,
                               policy, locally_pinned_root, selections, archive_grants, saved)
                if saved["assessment"] != result:
                    raise InvalidWorld("later selection cannot rewrite already-signed local controversy")
                output = {"status": "DUPLICATE_UNCHANGED", "receipt": saved}
            else:
                receipt = make_receipt(result, recorder)
                db.execute("INSERT INTO disputed_succession VALUES(?,?,?)", (
                    0, digest(policy),
                    json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                ))
                output = {"status": "SIGNED_LOCAL_CONTROVERSY_RECORDED", "receipt": receipt}
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return output


def build_fixture():
    tmp, parcel, old_local, pins, north_inc, north_pub, north_grant, keys = build_013()
    south = IdentityKey.load_or_create(Path(tmp.name) / "south-successor.pem")
    root = IdentityKey.load_or_create(Path(tmp.name) / "succession-root.pem")
    reviewer = IdentityKey.load_or_create(Path(tmp.name) / "succession-reviewer.pem")
    neutral = IdentityKey.load_or_create(Path(tmp.name) / "neutral-013-history-recorder.pem")
    keys.update({"south-successor": south, "succession-root": root,
                 "succession-reviewer": reviewer, "neutral-recorder": neutral})
    south_inc = make_incarnation(parcel, pins, south, epoch=2)
    policy = make_policy(parcel, pins, {
        "north": {"incarnation": north_inc, "owner_public_key": north_pub},
        "south": {"incarnation": south_inc, "owner_public_key": south.public_jwk()},
    }, root, reviewer, neutral)
    grants = {
        "north": north_grant,
        "south": make_archive_grant(parcel, south_inc, south, not_after=5000),
    }
    return tmp, parcel, old_local, pins, policy, root.public_jwk(), grants, keys


def demo():
    tmp, parcel, old_local, pins, policy, root, grants, keys = build_fixture()
    try:
        clock = 1100
        empty = assess(parcel, old_local, pins, policy, root, [], grants, now=clock)
        north = make_selection(policy, keys["succession-reviewer"], "north")
        south = make_selection(policy, keys["succession-reviewer"], "south")
        split = assess(parcel, old_local, pins, policy, root,
                       [north, south], grants, now=clock)
        chosen = assess(parcel, old_local, pins, policy, root, [north], grants, now=clock)
        db = Path(tmp.name) / "neutral-custody.sqlite"
        written = record_once(db, parcel, old_local, pins, policy, root, [north, south],
                              grants, keys["neutral-recorder"], now=clock)
        return {
            "unselected": empty["decision"],
            "two_signed_valid_but_incompatible_selections": split["decision"],
            "single_bounded_archival_selection": chosen["decision"],
            "one_neutral_receipt": len(read_receipts(db)) == 1,
            "cold_receipt_verified": (
                verify_receipt(parcel, old_local, pins, policy, root,
                               [north, south], grants, written["receipt"])["decision"] == EQUIVOCATED
            ),
            "global_successor_proven": split["global_rightful_successor_proven"],
            "forwarding_permitted": split["local_review_authorizes_forwarding"],
            "external_execution": split["external_execution"],
        }
    finally:
        tmp.cleanup()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "record", "verify"))
    for name in ("parcel", "old-local-package", "historical-pins", "policy",
                 "local-review-root", "selections", "archive-grants",
                 "neutral-private-key", "neutral-db", "receipt"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--now", type=int)
    args = parser.parse_args()
    try:
        if args.command == "demo":
            result = demo()
        else:
            mandatory = ("parcel", "old_local_package", "historical_pins",
                         "policy", "local_review_root", "selections", "archive_grants")
            if any(getattr(args, n) is None for n in mandatory):
                parser.error("full independent old evidence and locally pinned policy required")
            sources = [load(getattr(args, n)) for n in mandatory]
            if args.command == "assess":
                if args.now is None:
                    parser.error("assess requires --now")
                result = assess(*sources, now=args.now)
            elif args.command == "record":
                if not args.neutral_private_key or not args.neutral_db or args.now is None:
                    parser.error("record requires local neutral signer, database and --now")
                if not args.neutral_private_key.is_file():
                    parser.error("neutral recorder private key must exist before record")
                signer = IdentityKey.load_or_create(args.neutral_private_key)
                result = record_once(args.neutral_db, *sources, signer, now=args.now)
            else:
                if not args.receipt:
                    parser.error("verify requires public --receipt")
                decision = verify_receipt(*sources, load(args.receipt))
                result = {"verified": True, "decision": decision["decision"]}
    except (InvalidWorld, IdentityProfileError, ValueError,
            TypeError, KeyError, OSError, sqlite3.Error) as err:
        parser.error(str(err))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
