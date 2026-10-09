#!/usr/bin/env python3
"""UNHEARD CHOIR 017 — The Negative That Outlived the Positive.

Two independently signed local observation histories carry the *same* historical
015 approval but differ in knowledge of a genuine 016 source-signed revocation.
An observer's silence about a notice is UNKNOWN, not proof of no revocation.
A signed gossip transfer can add a new locally signed review receipt, but cannot
retroactively edit the initial observation, admit, revoke arbitrary permissions,
or prove real-world delivery. Simulated clocks and local SQLite only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_witness_custody import (
    build_fixture as fixture016, make_notice,
    assess as assess016, verify_policy as verify016_policy,
    verify_notice as verify016_notice,
    CUSTODY_ONLY, REVOKED, prior_key_set,
)
from unheard_choir_successors import exact, public, distinct, sign, authenticate
from unheard_choir_third_party import check_clock
from relatte_identity import IdentityKey, IdentityProfileError

ROSTER = "ghot.unheard-choir-017-observer-roster/v0"
OBS = "ghot.unheard-choir-017-site-snapshot/v0"
REVIEW = "ghot.unheard-choir-017-local-gossip-review/v0"
COMPARE = "ghot.unheard-choir-017-comparison/v0"
ROOT_DOMAIN = b"GHOT-CHOIR-017-ROSTER-v0|"
OBS_DOMAIN = b"GHOT-CHOIR-017-SNAPSHOT-v0|"
REVIEW_DOMAIN = b"GHOT-CHOIR-017-GOSSIP-REVIEW-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-017-local-genesis/v0"})
SITES = ("west", "east")
UNKNOWN = "HOLD_REVOCATION_STATE_UNKNOWN"
KNOWN = "HOLD_SIGNED_REVOCATION_WITNESSED_IN_GOSSIP"
FUTURE = "HOLD_SIGNED_FUTURE_REVOCATION_NOT_ACTIVE"
EXPIRED = "HOLD_SIGNED_EXPIRED_NOTICE_NO_NEW_CURRENT_GRANT"
OTHER = "HOLD_SOURCE_NOTICE_DOES_NOT_ASSERT_REVOCATION"
CONFLICT = "HOLD_DISTINCT_SIGNED_SOURCE_NOTICES_UNRESOLVED"


def case_inputs(prior: list, policy016: dict, root016: dict,
                holder_manifest: dict) -> dict:
    return {
        "prior015_digest": digest(prior),
        "016_policy_digest": digest(policy016),
        "016_root_digest": digest(root016),
        "016_holder_manifest_digest": digest(holder_manifest),
        "original_source_review_digest": digest(prior[11]),
    }


def make_roster(prior: list, policy016: dict, root016: dict,
                holder_manifest: dict, root: IdentityKey,
                sites: dict[str, IdentityKey]):
    verify016_policy(prior, policy016, root016)
    if type(prior) is not list or len(prior) != 13 or prior[11] is None:
        raise InvalidWorld("both observers must share an authentic historical 015 source approval")
    if set(sites) != set(SITES):
        raise InvalidWorld("exactly west and east observer signers required")
    if not distinct(prior_key_set(prior) + [
        root016, policy016["neutral_recorder_public_key"],
        root.public_jwk(), sites["west"].public_jwk(), sites["east"].public_jwk(),
    ]):
        raise InvalidWorld("017 observer and roster keys must be independent of every inherited identity")
    body = {
        "schema": ROSTER,
        "scope": "PINNED_LOCAL_OBSERVER_IDS_NOT_SOURCE_AUTHORITY",
        "case": case_inputs(prior, policy016, root016, holder_manifest),
        "sites": {name: sites[name].public_jwk() for name in SITES},
    }
    return {**body, "signature": sign(root, body, ROOT_DOMAIN)}


def verify_roster(prior: list, policy016: dict, root016: dict,
                  holder_manifest: dict, roster: Any, pinned_root: Any):
    verify016_policy(prior, policy016, root016)
    exact(roster, ("schema", "scope", "case", "sites", "signature"), "017 signed roster")
    exact(roster["sites"], SITES, "017 signed observer identities")
    if (roster["schema"] != ROSTER
        or roster["scope"] != "PINNED_LOCAL_OBSERVER_IDS_NOT_SOURCE_AUTHORITY"
        or roster["case"] != case_inputs(prior, policy016, root016, holder_manifest)):
        raise InvalidWorld("site roster must bind exact 015 approval and 016 context")
    keys = prior_key_set(prior) + [
        root016, policy016["neutral_recorder_public_key"],
        pinned_root, roster["sites"]["west"], roster["sites"]["east"],
    ]
    if not distinct(keys):
        raise InvalidWorld("017 observation trust key collision")
    body = {k: v for k, v in roster.items() if k != "signature"}
    authenticate(body, roster["signature"], pinned_root, ROOT_DOMAIN,
                 "independently pinned gossip roster")


def local_status(notice: dict | None, *, now: int):
    if notice is None:
        return UNKNOWN
    if notice["kind"] != "REVOKE_EXACT_SOURCE_REVIEW":
        return OTHER
    if now < notice["simulated_effective_at"]:
        return FUTURE
    if now > notice["simulated_not_after"]:
        return EXPIRED
    return KNOWN


def make_snapshot(prior: list, policy016: dict, root016: dict,
                  holder_manifest: dict, roster: dict, pinned_root: dict,
                  site: str, signer: IdentityKey, notice: dict | None,
                  *, now: int):
    check_clock(now, "site observer clock")
    verify_roster(prior, policy016, root016, holder_manifest, roster, pinned_root)
    if site not in SITES or public(signer.public_jwk()) != public(roster["sites"][site]):
        raise InvalidWorld("only exact pinned local site may create its observation")
    a = assess016(prior, policy016, root016, holder_manifest, notice, now=now)
    if a["decision"] not in (CUSTODY_ONLY, REVOKED):
        raise InvalidWorld("unexpected 016 predecessor; cannot claim a verified positive snapshot")
    body = {
        "schema": OBS, "scope": "OBSERVER_KNOWLEDGE_NOT_WORLD_COMPLETENESS",
        "site": site, "roster_digest": digest(roster),
        "local_index": 0, "previous_digest": GENESIS,
        "observation_clock": now,
        "source_notice": notice,
        "016_assessment_digest": a["assessment_digest"],
        "016_decision": a["decision"],
        "revocation_knowledge": local_status(notice, now=now),
        "lack_of_revocation_proves_never_revoked": False,
        "original_015_source_approval_preserved": digest(prior[11]),
        "forwarding_permitted": False, "native_relatte_receive": False,
        "external_execution": False,
    }
    return {**body, "signature": sign(signer, body, OBS_DOMAIN)}


def verify_snapshot(prior: list, policy016: dict, root016: dict,
                    holder_manifest: dict, roster: dict, pinned_root: dict,
                    snapshot: Any, *, expected_site: str | None = None):
    verify_roster(prior, policy016, root016, holder_manifest, roster, pinned_root)
    exact(snapshot, ("schema", "scope", "site", "roster_digest",
                     "local_index", "previous_digest", "observation_clock",
                     "source_notice", "016_assessment_digest", "016_decision",
                     "revocation_knowledge", "lack_of_revocation_proves_never_revoked",
                     "original_015_source_approval_preserved", "forwarding_permitted",
                     "native_relatte_receive", "external_execution",
                     "signature"), "017 signed observation")
    site = snapshot["site"]
    if (snapshot["schema"] != OBS
        or snapshot["scope"] != "OBSERVER_KNOWLEDGE_NOT_WORLD_COMPLETENESS"
        or site not in SITES or (expected_site is not None and site != expected_site)
        or snapshot["roster_digest"] != digest(roster)
        or type(snapshot["local_index"]) is not int or snapshot["local_index"] != 0
        or snapshot["previous_digest"] != GENESIS
        or snapshot["lack_of_revocation_proves_never_revoked"] is not False
        or snapshot["forwarding_permitted"] is not False
        or snapshot["native_relatte_receive"] is not False
        or snapshot["external_execution"] is not False
        or snapshot["original_015_source_approval_preserved"] != digest(prior[11])):
        raise InvalidWorld("observation attempted scope, role or history elevation")
    now = snapshot["observation_clock"]
    check_clock(now, "observation clock")
    a = assess016(prior, policy016, root016, holder_manifest,
                  snapshot["source_notice"], now=now)
    if (a["decision"] not in (CUSTODY_ONLY, REVOKED)
        or snapshot["016_assessment_digest"] != a["assessment_digest"]
        or snapshot["016_decision"] != a["decision"]
        or snapshot["revocation_knowledge"] != local_status(
            snapshot["source_notice"], now=now)):
        raise InvalidWorld("017 snapshot does not replay under its own 016 provenance")
    body = {k: v for k, v in snapshot.items() if k != "signature"}
    authenticate(body, snapshot["signature"], roster["sites"][site],
                 OBS_DOMAIN, "017 site observation")
    return a


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS original_observations(
        site TEXT PRIMARY KEY,
        snapshot_json TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS imported_gossip(
        peer_snapshot_digest TEXT PRIMARY KEY,
        review_json TEXT NOT NULL
    )""")


def read_local(path: Path, site: str):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        r = db.execute("SELECT snapshot_json FROM original_observations WHERE site=?", (site,)).fetchone()
    return json.loads(r[0]) if r is not None else None


def read_imports(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        rs = db.execute("SELECT review_json FROM imported_gossip ORDER BY peer_snapshot_digest").fetchall()
    return [json.loads(row[0]) for row in rs]


def observe_once(db_path: Path, prior: list, policy016: dict, root016: dict,
                 manifest: dict, roster: dict, pinned_root: dict, site: str,
                 signer: IdentityKey, notice: dict | None, *, now: int):
    snapshot = make_snapshot(prior, policy016, root016, manifest,
                             roster, pinned_root, site, signer, notice, now=now)
    with sqlite3.connect(str(db_path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            existing = db.execute("SELECT snapshot_json FROM original_observations WHERE site=?",
                                  (site,)).fetchone()
            if existing:
                if json.loads(existing[0]) != snapshot:
                    # ECDSA may be nondeterministic: a second freshly signed
                    # snapshot must not rewrite an existing local history.
                    original = json.loads(existing[0])
                    verify_snapshot(prior, policy016, root016, manifest, roster,
                                    pinned_root, original, expected_site=site)
                    if {k: v for k, v in original.items() if k != "signature"} != {
                        k: v for k, v in snapshot.items() if k != "signature"
                    }:
                        raise InvalidWorld("original observer state may never be rewritten")
                result = original
            else:
                if db.execute("SELECT COUNT(*) FROM original_observations").fetchone()[0]:
                    raise InvalidWorld("one signer/site per observer-local database")
                db.execute("INSERT INTO original_observations VALUES(?,?)", (
                    site, json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
                ))
                result = snapshot
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return result


def compare(prior: list, policy016: dict, root016: dict,
            manifest: dict, roster: dict, pinned_root: dict,
            local: dict, remote: dict, *, now: int):
    check_clock(now, "017 recipient-local simulated clock")
    verify_snapshot(prior, policy016, root016, manifest, roster,
                    pinned_root, local)
    verify_snapshot(prior, policy016, root016, manifest, roster,
                    pinned_root, remote)
    if local["site"] == remote["site"]:
        raise InvalidWorld("two self-issued snapshots do not constitute cross-site gossip")
    notes = [x["source_notice"] for x in (local, remote) if x["source_notice"] is not None]
    for note in notes:
        verify016_notice(prior, policy016, note, now=now)
    unique = {digest(x): x for x in notes}
    if len(unique) > 1:
        decision = CONFLICT
    elif not unique:
        decision = UNKNOWN
    else:
        decision = local_status(next(iter(unique.values())), now=now)
    result = {
        "schema": COMPARE, "scope": "SOURCE_NOTICE_GOSSIP_NOT_RECEIVER_PERMISSION",
        "local_site": local["site"], "remote_site": remote["site"],
        "local_original_snapshot_digest": digest(local),
        "remote_original_snapshot_digest": digest(remote),
        "source_notice_digests": sorted(unique),
        "retained_historical_015_approval_digest": digest(prior[11]),
        "decision": decision,
        "lack_of_revocation_proves_never_revoked": False,
        "source_reviewer_signed_notice_required": True,
        "past_observation_mutated": False,
        "native_relatte_receive": False, "forwarding_permitted": False,
        "external_execution": False, "simulated_receiver_clock": now,
    }
    result["assessment_digest"] = digest(result)
    return result


def make_review(assessment: dict, signer: IdentityKey,
                *, prior_review_digest: str = GENESIS):
    if prior_review_digest != GENESIS:
        raise InvalidWorld("one inbound event per local experiment fixture")
    body = {
        "schema": REVIEW, "scope": "OWNER_LOCAL_GOSSIP_REVIEW_NOT_ADMISSION",
        "local_index": 0, "previous_review_digest": GENESIS,
        "assessment": assessment,
    }
    return {**body, "signature": sign(signer, body, REVIEW_DOMAIN)}


def verify_review(prior: list, policy016: dict, root016: dict,
                  manifest: dict, roster: dict, pinned_root: dict,
                  local: dict, remote: dict, review: Any):
    exact(review, ("schema", "scope", "local_index", "previous_review_digest",
                   "assessment", "signature"), "017 signed local review")
    if (review["schema"] != REVIEW
        or review["scope"] != "OWNER_LOCAL_GOSSIP_REVIEW_NOT_ADMISSION"
        or type(review["local_index"]) is not int or review["local_index"] != 0
        or review["previous_review_digest"] != GENESIS
        or type(review["assessment"]) is not dict):
        raise InvalidWorld("unexpected 017 local review scope")
    now = review["assessment"].get("simulated_receiver_clock")
    replay = compare(prior, policy016, root016, manifest,
                     roster, pinned_root, local, remote, now=now)
    if replay != review["assessment"]:
        raise InvalidWorld("review decision cannot be detached from exact signed snapshots")
    body = {k: v for k, v in review.items() if k != "signature"}
    authenticate(body, review["signature"],
                 roster["sites"][local["site"]], REVIEW_DOMAIN,
                 "observer-local gossip receipt")
    return replay


def ingest_once(db_path: Path, prior: list, policy016: dict, root016: dict,
                manifest: dict, roster: dict, pinned_root: dict,
                local_site: str, peer_snapshot: dict, signer: IdentityKey,
                *, now: int):
    if local_site not in SITES or public(signer.public_jwk()) != public(roster["sites"][local_site]):
        raise InvalidWorld("recipient observer alone may issue its local review")
    # A signed remote message never changes the original local snapshot.
    with sqlite3.connect(str(db_path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT snapshot_json FROM original_observations WHERE site=?",
                             (local_site,)).fetchone()
            if row is None:
                raise InvalidWorld("recipient has no signed original local observation")
            local = json.loads(row[0])
            outcome = compare(prior, policy016, root016, manifest,
                              roster, pinned_root, local, peer_snapshot, now=now)
            existing = db.execute("SELECT review_json FROM imported_gossip").fetchall()
            if len(existing) > 1:
                raise InvalidWorld("bounded one-message inbox exceeded")
            if existing:
                review = json.loads(existing[0][0])
                verify_review(prior, policy016, root016, manifest, roster,
                              pinned_root, local, peer_snapshot, review)
                if review["assessment"] != outcome:
                    raise InvalidWorld("new gossip cannot retroactively reclassify already signed local receipt")
                status = "DUPLICATE_SIGNED_REVIEW_UNCHANGED"
            else:
                review = make_review(outcome, signer)
                db.execute("INSERT INTO imported_gossip VALUES(?,?)", (
                    digest(peer_snapshot),
                    json.dumps(review, sort_keys=True, separators=(",", ":")),
                ))
                status = "SIGNED_GOSSIP_REVIEW_DURABLY_WRITTEN"
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return {"status": status, "review": review}


def build_fixture():
    tmp, prior, p016, root016, manifest, keys = fixture016()
    from pathlib import Path as P
    root = IdentityKey.load_or_create(P(tmp.name) / "017-root.pem")
    west = IdentityKey.load_or_create(P(tmp.name) / "017-west.pem")
    east = IdentityKey.load_or_create(P(tmp.name) / "017-east.pem")
    keys.update({"017-root": root, "017-west": west, "017-east": east})
    roster = make_roster(prior, p016, root016, manifest,
                         root, {"west": west, "east": east})
    notice = make_notice(prior, p016, keys["015-source-reviewer"],
                         "REVOKE_EXACT_SOURCE_REVIEW",
                         claimed_at=1100, effective_at=1200, not_after=5000)
    return tmp, prior, p016, root016, manifest, roster, root.public_jwk(), notice, keys


def demo():
    tmp, prior, p016, root016, manifest, roster, root, notice, keys = build_fixture()
    try:
        west_db = Path(tmp.name) / "west-observer.sqlite"
        east_db = Path(tmp.name) / "east-observer.sqlite"
        west = observe_once(west_db, prior, p016, root016, manifest, roster, root,
                            "west", keys["017-west"], None, now=1250)
        east = observe_once(east_db, prior, p016, root016, manifest, roster, root,
                            "east", keys["017-east"], notice, now=1250)
        pre = west["revocation_knowledge"]
        # Transport drop: only WEST's original signed snapshot exists locally.
        before = len(read_imports(west_db))
        transferred = ingest_once(west_db, prior, p016, root016, manifest,
                                  roster, root, "west", east, keys["017-west"],
                                  now=1250)
        duplicate = ingest_once(west_db, prior, p016, root016, manifest,
                                roster, root, "west", east, keys["017-west"],
                                now=1250)
        cold = verify_review(prior, p016, root016, manifest, roster, root,
                             west, east, transferred["review"])
        return {
            "west_initial": pre,
            "east_initial": east["revocation_knowledge"],
            "transport_drop_kept_sender_unknown": before == 0,
            "signed_exchange_decision": cold["decision"],
            "old_positive_approval_retained": cold["retained_historical_015_approval_digest"] == digest(prior[11]),
            "west_original_snapshot_preserved": read_local(west_db, "west") == west,
            "east_original_snapshot_preserved": read_local(east_db, "east") == east,
            "gossip_receipt_durable": len(read_imports(west_db)) == 1,
            "idempotent_duplicate": duplicate["review"] == transferred["review"],
            "public_cold_replay": True,
            "native_relatte_receive": cold["native_relatte_receive"],
            "external_execution": cold["external_execution"],
        }
    finally:
        tmp.cleanup()


PRIOR_NAMES = (
    "parcel", "historical-local-package", "historical-pins",
    "succession-policy", "succession-root", "reviewer-selections",
    "candidate-archive-grants", "legacy-delegation", "third-party-policy",
    "third-party-root", "third-party-presentation", "fresh-source-review",
    "new-owner-consent",
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "verify"))
    for n in PRIOR_NAMES + (
        "custody-policy", "custody-root", "holder-manifest", "roster",
        "roster-root", "local-snapshot", "remote-snapshot", "gossip-review",
    ):
        parser.add_argument("--" + n, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "demo":
            result = demo()
        else:
            names = PRIOR_NAMES + (
                "custody-policy", "custody-root", "holder-manifest", "roster",
                "roster-root", "local-snapshot", "remote-snapshot", "gossip-review",
            )
            if any(getattr(args, n.replace("-", "_")) is None for n in names):
                parser.error("verify requires all public 015–017 evidence and signed snapshots")
            prior = [load(getattr(args, n.replace("-", "_"))) for n in PRIOR_NAMES]
            x = [load(getattr(args, n.replace("-", "_"))) for n in names[len(PRIOR_NAMES):]]
            outcome = verify_review(prior, *x)
            result = {"verified": True, "decision": outcome["decision"]}
    except (InvalidWorld, TypeError, ValueError, KeyError,
            OSError, sqlite3.Error, IdentityProfileError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
