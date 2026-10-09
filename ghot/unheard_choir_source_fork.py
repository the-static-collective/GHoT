#!/usr/bin/env python3
"""UNHEARD CHOIR 018 — The Negative That Forked.

Two authentic source-key statements can conflict without creating a current
grant or destroying past history. Separate site owners sign exactly which
source evidence they have seen. A neutral comparison retains every authenticated
claim in a sorted evidence set; it cannot rank by timestamp, arrival, or key.
All clocks, sites, transports and receipt stores are synthetic GHoT fixtures.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_delayed_revocation import (
    build_fixture as fixture017,
    make_snapshot as make_017_snapshot,
    verify_snapshot as verify_017_snapshot,
    verify_roster as verify_017_roster,
    GENESIS as GENESIS_017,
)
from unheard_choir_witness_custody import (
    make_notice as make_016_notice,
    verify_notice as verify_016_notice,
)
from unheard_choir_successors import exact, public, sign, authenticate
from unheard_choir_third_party import check_clock, check_window
from relatte_identity import IdentityKey, IdentityProfileError

REINSTATEMENT = "ghot.unheard-choir-018-source-reinstatement-claim/v0"
VIEW = "ghot.unheard-choir-018-site-view/v0"
ASSESSMENT = "ghot.unheard-choir-018-source-conflict-assessment/v0"
RECEIPT = "ghot.unheard-choir-018-local-conflict-receipt/v0"
S_DOMAIN = b"GHOT-CHOIR-018-SOURCE-REINSTATEMENT-v0|"
V_DOMAIN = b"GHOT-CHOIR-018-SITE-VIEW-v0|"
R_DOMAIN = b"GHOT-CHOIR-018-CONFLICT-RECEIPT-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-018-genesis/v0"})
UNKNOWN = "HOLD_SOURCE_STATE_UNKNOWN_NO_NEGATIVE_EVIDENCE"
SINGLE = "HOLD_SINGLE_SIGNED_REVOCATION_NO_NATIVE_GRANT"
FORKED_NEGATIVE = "HOLD_MULTIPLE_SOURCE_REVOCATIONS_UNORDERED"
FORKED_POLARITY = "HOLD_SOURCE_REVOCATION_REINSTATEMENT_UNRESOLVED"


def context(prior, p016, root016, manifest, roster, root):
    return prior, p016, root016, manifest, roster, root


def make_reinstatement(prior: list, policy016: dict, roster: dict,
                       original_revocation: dict, signer: IdentityKey,
                       *, claimed_at: int = 1201,
                       effective_at: int = 1300, not_after: int = 5000):
    if public(signer.public_jwk()) != public(policy016["source_public_key"]):
        raise InvalidWorld("only the pinned original source may sign reinstatement claim")
    check_window(claimed_at, not_after, "reinstatement claim")
    check_clock(effective_at, "reinstatement effect claim")
    if not claimed_at <= effective_at <= not_after:
        raise InvalidWorld("reinstatement claimed effect outside synthetic interval")
    verify_016_notice(prior, policy016, original_revocation, now=claimed_at)
    if original_revocation["kind"] != "REVOKE_EXACT_SOURCE_REVIEW":
        raise InvalidWorld("reinstatement claim must name one authentic exact revocation")
    if claimed_at < original_revocation["simulated_claimed_at"]:
        raise InvalidWorld("reinstatement cannot claim issue before original revocation")
    body = {
        "schema": REINSTATEMENT,
        "scope": "SOURCE_CLAIM_NOT_VALID_GRANT_OR_REACTIVATION",
        "roster_digest": digest(roster),
        "016_policy_digest": digest(policy016),
        "original_015_approval_digest": digest(prior[11]),
        "revocation_notice": original_revocation,
        "revocation_notice_digest": digest(original_revocation),
        "claimed_action": "REINSTATE_HISTORICAL_SOURCE_REVIEW_CLAIM_ONLY",
        "simulated_claimed_at": claimed_at,
        "simulated_effective_at": effective_at,
        "simulated_not_after": not_after,
        "restores_native_source_authority": False,
        "effect_permission": "NONE",
    }
    return {**body, "signature": sign(signer, body, S_DOMAIN)}


def verify_reinstatement(prior: list, policy016: dict, roster: dict,
                         claim: Any):
    exact(claim, ("schema", "scope", "roster_digest", "016_policy_digest",
                  "original_015_approval_digest", "revocation_notice",
                  "revocation_notice_digest", "claimed_action",
                  "simulated_claimed_at", "simulated_effective_at",
                  "simulated_not_after", "restores_native_source_authority",
                  "effect_permission", "signature"), "018 signed reinstatement")
    if (claim["schema"] != REINSTATEMENT
        or claim["scope"] != "SOURCE_CLAIM_NOT_VALID_GRANT_OR_REACTIVATION"
        or claim["roster_digest"] != digest(roster)
        or claim["016_policy_digest"] != digest(policy016)
        or claim["original_015_approval_digest"] != digest(prior[11])
        or claim["revocation_notice_digest"] != digest(claim["revocation_notice"])
        or claim["claimed_action"] != "REINSTATE_HISTORICAL_SOURCE_REVIEW_CLAIM_ONLY"
        or claim["restores_native_source_authority"] is not False
        or claim["effect_permission"] != "NONE"):
        raise InvalidWorld("018 signed claim attempted native permission or changed source identity")
    check_window(claim["simulated_claimed_at"],
                 claim["simulated_not_after"], "signed reinstatement")
    check_clock(claim["simulated_effective_at"], "reinstatement claimed effect")
    if not (claim["simulated_claimed_at"] <= claim["simulated_effective_at"]
            <= claim["simulated_not_after"]):
        raise InvalidWorld("reinstatement claimed effect outside signed interval")
    revocation = claim["revocation_notice"]
    verify_016_notice(prior, policy016, revocation, now=claim["simulated_claimed_at"])
    if (revocation["kind"] != "REVOKE_EXACT_SOURCE_REVIEW"
        or claim["simulated_claimed_at"] < revocation["simulated_claimed_at"]):
        raise InvalidWorld("restoration claim must bind an actual earlier source revocation")
    body = {k: v for k, v in claim.items() if k != "signature"}
    authenticate(body, claim["signature"], policy016["source_public_key"],
                 S_DOMAIN, "same source signing a later claim")


def verify_event(prior: list, policy016: dict, roster: dict, item: Any):
    if type(item) is not dict or type(item.get("schema")) is not str:
        raise InvalidWorld("missing signed source event schema")
    if item["schema"] == REINSTATEMENT:
        verify_reinstatement(prior, policy016, roster, item)
        return "REINSTATEMENT"
    if item["schema"] == "ghot.unheard-choir-016-source-local-notice/v0":
        verify_016_notice(prior, policy016, item, now=item.get("simulated_claimed_at"))
        if item["kind"] != "REVOKE_EXACT_SOURCE_REVIEW":
            raise InvalidWorld("018 revocation register accepts exact revocations only")
        return "REVOCATION"
    raise InvalidWorld("unknown source event; fail closed")


def event_set(prior: list, policy016: dict, roster: dict,
              view_events: list, original_017_notice: dict | None):
    if type(view_events) is not list or len(view_events) > 3:
        raise InvalidWorld("bounded source event view requires zero to three items")
    result = {}
    for item in view_events + ([original_017_notice] if original_017_notice is not None else []):
        category = verify_event(prior, policy016, roster, item)
        result[digest(item)] = {"category": category, "document": item}
        if category == "REINSTATEMENT":
            underlying = item["revocation_notice"]
            verify_event(prior, policy016, roster, underlying)
            result[digest(underlying)] = {
                "category": "REVOCATION", "document": underlying,
            }
    return result


def make_view(prior: list, p016: dict, root016: dict, manifest: dict,
              roster: dict, pinned_root: dict,
              snapshot: dict, new_events: list, signer: IdentityKey):
    verify_017_snapshot(prior, p016, root016, manifest,
                        roster, pinned_root, snapshot)
    site = snapshot["site"]
    if public(signer.public_jwk()) != public(roster["sites"][site]):
        raise InvalidWorld("017 site key owns its own 018 evidence view")
    values = event_set(prior, p016, roster, new_events, snapshot["source_notice"])
    # Canonical sorted digests avoid an arrival-order winner.
    if len(new_events) != len({digest(x) for x in new_events}):
        raise InvalidWorld("duplicate event in one signed local view")
    body = {
        "schema": VIEW, "scope": "SITE_EVIDENCE_SET_NOT_AUTHORITY",
        "site": site, "roster_digest": digest(roster),
        "original_017_snapshot": snapshot,
        "original_017_snapshot_digest": digest(snapshot),
        "additional_source_events": sorted(new_events, key=digest),
        "observed_source_digest_set": sorted(values),
        "original_015_approval_digest": digest(prior[11]),
        "lack_of_seen_revocation_proves_no_revocation": False,
        "external_execution": False, "native_relatte_receive": False,
    }
    return {**body, "signature": sign(signer, body, V_DOMAIN)}


def verify_view(prior: list, p016: dict, root016: dict, manifest: dict,
                roster: dict, pinned_root: dict, view: Any):
    exact(view, ("schema", "scope", "site", "roster_digest",
                 "original_017_snapshot", "original_017_snapshot_digest",
                 "additional_source_events", "observed_source_digest_set",
                 "original_015_approval_digest",
                 "lack_of_seen_revocation_proves_no_revocation",
                 "external_execution", "native_relatte_receive", "signature"),
          "018 signed observer view")
    snapshot = view["original_017_snapshot"]
    verify_017_snapshot(prior, p016, root016, manifest, roster,
                        pinned_root, snapshot)
    if (view["schema"] != VIEW
        or view["scope"] != "SITE_EVIDENCE_SET_NOT_AUTHORITY"
        or view["site"] != snapshot["site"]
        or view["roster_digest"] != digest(roster)
        or view["original_017_snapshot_digest"] != digest(snapshot)
        or view["original_015_approval_digest"] != digest(prior[11])
        or view["lack_of_seen_revocation_proves_no_revocation"] is not False
        or view["external_execution"] is not False
        or view["native_relatte_receive"] is not False):
        raise InvalidWorld("018 view cannot redefine predecessor or admit native effects")
    events = view["additional_source_events"]
    values = event_set(prior, p016, roster, events, snapshot["source_notice"])
    if (len(events) != len({digest(x) for x in events})
        or events != sorted(events, key=digest)
        or view["observed_source_digest_set"] != sorted(values)):
        raise InvalidWorld("view's complete evidence set or canonical ordering changed")
    body = {k: v for k, v in view.items() if k != "signature"}
    authenticate(body, view["signature"], roster["sites"][view["site"]],
                 V_DOMAIN, "018 site-local evidence set")
    return values


def compare(prior: list, p016: dict, root016: dict, manifest: dict,
            roster: dict, pinned_root: dict,
            local: dict, remote: dict, *, now: int):
    check_clock(now, "018 comparison clock")
    local_set = verify_view(prior, p016, root016, manifest, roster, pinned_root, local)
    remote_set = verify_view(prior, p016, root016, manifest, roster, pinned_root, remote)
    if local["site"] == remote["site"]:
        raise InvalidWorld("source gossip requires two distinct pinned sites")
    union = {**local_set, **remote_set}
    revocations = sorted(k for k, v in union.items() if v["category"] == "REVOCATION")
    reactivations = sorted(k for k, v in union.items() if v["category"] == "REINSTATEMENT")
    if reactivations and revocations:
        decision = FORKED_POLARITY
    elif len(revocations) > 1:
        decision = FORKED_NEGATIVE
    elif revocations:
        decision = SINGLE
    else:
        decision = UNKNOWN
    result = {
        "schema": ASSESSMENT, "scope": "PRESERVE_ALL_SIGNED_SOURCE_CLAIMS_AS_HOLD",
        "local_site": local["site"], "peer_site": remote["site"],
        "local_original_view_digest": digest(local),
        "remote_original_view_digest": digest(remote),
        "source_event_digests": sorted(union),
        "revocation_digests": revocations,
        "reinstatement_claim_digests": reactivations,
        "historical_015_approval_digest": digest(prior[11]),
        "decision": decision,
        "claimed_timestamp_is_precedence": False,
        "arrival_order_is_precedence": False,
        "source_key_signature_proves_global_jurisdiction": False,
        "has_valid_native_reinstatement": False,
        "original_017_snapshots_mutated": False,
        "forwarding_permitted": False,
        "native_relatte_receive": False, "native_relatte_admission": False,
        "external_execution": False, "effects": [], "authority": "NONE",
        "receiver_local_simulated_clock": now,
    }
    result["assessment_digest"] = digest(result)
    return result


def make_receipt(outcome: dict, signer: IdentityKey):
    body = {
        "schema": RECEIPT, "scope": "LOCAL_UNRESOLVED_SOURCE_FORK_NOT_ADMISSION",
        "local_index": 0, "previous_receipt_digest": GENESIS,
        "assessment": outcome,
    }
    return {**body, "signature": sign(signer, body, R_DOMAIN)}


def verify_receipt(prior: list, p016: dict, root016: dict, manifest: dict,
                   roster: dict, pinned_root: dict,
                   local: dict, remote: dict, receipt: Any):
    exact(receipt, ("schema", "scope", "local_index",
                    "previous_receipt_digest", "assessment", "signature"),
          "018 source fork receipt")
    if (receipt["schema"] != RECEIPT
        or receipt["scope"] != "LOCAL_UNRESOLVED_SOURCE_FORK_NOT_ADMISSION"
        or type(receipt["local_index"]) is not int or receipt["local_index"] != 0
        or receipt["previous_receipt_digest"] != GENESIS
        or type(receipt["assessment"]) is not dict):
        raise InvalidWorld("18th generation cannot turn source claims into permissions")
    now = receipt["assessment"].get("receiver_local_simulated_clock")
    replay = compare(prior, p016, root016, manifest, roster, pinned_root,
                     local, remote, now=now)
    if replay != receipt["assessment"]:
        raise InvalidWorld("018 cold proof no longer matches exact signed evidence")
    body = {k: v for k, v in receipt.items() if k != "signature"}
    authenticate(body, receipt["signature"], roster["sites"][local["site"]],
                 R_DOMAIN, "owner-local non-admitting source-fork receipt")
    return replay


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS original_view(
        site TEXT PRIMARY KEY, view_json TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS local_reviews(
        local_index INTEGER PRIMARY KEY,
        remote_view_digest TEXT NOT NULL UNIQUE,
        review_json TEXT NOT NULL
    )""")


def read_view(path: Path, site: str):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        x = db.execute("SELECT view_json FROM original_view WHERE site=?", (site,)).fetchone()
        return json.loads(x[0]) if x else None


def read_receipts(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        return [json.loads(x[0]) for x in db.execute(
            "SELECT review_json FROM local_reviews ORDER BY local_index").fetchall()]


def stage_once(path: Path, prior: list, p016: dict, root016: dict, manifest: dict,
               roster: dict, pinned_root: dict, view: dict):
    verify_view(prior, p016, root016, manifest, roster, pinned_root, view)
    with sqlite3.connect(str(path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT site,view_json FROM original_view").fetchone()
            if row:
                saved = json.loads(row[1])
                verify_view(prior, p016, root016, manifest, roster, pinned_root, saved)
                if saved["site"] != view["site"] or {
                    k: v for k, v in saved.items() if k != "signature"
                } != {k: v for k, v in view.items() if k != "signature"}:
                    raise InvalidWorld("site's original signed evidence view may not be rewritten")
                out = saved
            else:
                db.execute("INSERT INTO original_view VALUES(?,?)", (
                    view["site"], json.dumps(view, sort_keys=True, separators=(",", ":"))
                ))
                out = view
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return out


def ingest_once(path: Path, prior: list, p016: dict, root016: dict, manifest: dict,
                roster: dict, pinned_root: dict, local_site: str, remote_view: dict,
                signer: IdentityKey, *, now: int):
    if (local_site not in roster["sites"]
        or public(signer.public_jwk()) != public(roster["sites"][local_site])):
        raise InvalidWorld("only pinned owner of exact recipient view can sign local conflict")
    with sqlite3.connect(str(path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT site,view_json FROM original_view").fetchone()
            if row is None or row[0] != local_site:
                raise InvalidWorld("no original locally signed evidence view to reconcile")
            local = json.loads(row[1])
            outcome = compare(prior, p016, root016, manifest, roster,
                              pinned_root, local, remote_view, now=now)
            saved = db.execute("SELECT remote_view_digest,review_json FROM local_reviews").fetchall()
            if len(saved) > 1:
                raise InvalidWorld("bounded one-message comparison journal exceeded")
            if saved:
                if saved[0][0] != digest(remote_view):
                    raise InvalidWorld("peer change is new history, not a replacement for signed receipt")
                receipt = json.loads(saved[0][1])
                verify_receipt(prior, p016, root016, manifest, roster,
                               pinned_root, local, remote_view, receipt)
                if receipt["assessment"] != outcome:
                    raise InvalidWorld("replay clock cannot retroactively alter original signed disposition")
                status = "DUPLICATE_IDENTICAL_RECEIPT"
            else:
                receipt = make_receipt(outcome, signer)
                db.execute("INSERT INTO local_reviews VALUES (?,?,?)", (
                    0, digest(remote_view),
                    json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                ))
                status = "SIGNED_SOURCE_FORK_RECEIPT_STORED"
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return {"status": status, "receipt": receipt}


def build_fixture():
    tmp, prior, p016, root016, manifest, roster, root, original, keys = fixture017()
    later = make_016_notice(prior, p016, keys["015-source-reviewer"],
                            "REVOKE_EXACT_SOURCE_REVIEW",
                            claimed_at=1120, effective_at=1230, not_after=5000)
    reinstatement = make_reinstatement(
        prior, p016, roster, original, keys["015-source-reviewer"],
        claimed_at=1220, effective_at=1240, not_after=5000)
    return tmp, prior, p016, root016, manifest, roster, root, original, later, reinstatement, keys


def demo():
    tmp, prior, p016, root016, manifest, roster, root, original, later, restore, keys = build_fixture()
    try:
        common = prior, p016, root016, manifest, roster, root
        west_old = make_017_snapshot(*common, "west", keys["017-west"], None, now=1250)
        east_old = make_017_snapshot(*common, "east", keys["017-east"], original, now=1250)
        west = make_view(*common, west_old, [later], keys["017-west"])
        east = make_view(*common, east_old, [restore], keys["017-east"])
        west_db = Path(tmp.name) / "018-west.sqlite"
        east_db = Path(tmp.name) / "018-east.sqlite"
        west = stage_once(west_db, *common, west)
        east = stage_once(east_db, *common, east)
        negative_only = make_view(*common, east_old, [], keys["017-east"])
        forked_negative = compare(*common, west, negative_only, now=1250)
        forked_polarity = compare(*common, west, east, now=1250)
        receipt = ingest_once(west_db, *common, "west", east, keys["017-west"], now=1250)
        duplicate = ingest_once(west_db, *common, "west", east, keys["017-west"], now=1250)
        cold = verify_receipt(*common, west, east, receipt["receipt"])
        return {
            "two_valid_source_revocations": forked_negative["decision"],
            "signed_reinstatement_and_revocations": forked_polarity["decision"],
            "both_original_017_snapshots_retained": (
                read_view(west_db, "west")["original_017_snapshot"] == west_old
                and read_view(east_db, "east")["original_017_snapshot"] == east_old
            ),
            "historical_015_approval_retained": (
                cold["historical_015_approval_digest"] == digest(prior[11])
            ),
            "local_receipt_written": receipt["status"] == "SIGNED_SOURCE_FORK_RECEIPT_STORED",
            "idempotent_replay": duplicate["status"] == "DUPLICATE_IDENTICAL_RECEIPT"
                                and duplicate["receipt"] == receipt["receipt"],
            "cold_public_verification": cold["decision"] == FORKED_POLARITY,
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
        "roster-root", "local-view", "remote-view", "fork-receipt",
    ):
        parser.add_argument("--" + n, type=Path)
    options = parser.parse_args()
    try:
        if options.command == "demo":
            result = demo()
        else:
            names = PRIOR_NAMES + (
                "custody-policy", "custody-root", "holder-manifest", "roster",
                "roster-root", "local-view", "remote-view", "fork-receipt",
            )
            if any(getattr(options, n.replace("-", "_")) is None for n in names):
                parser.error("verify needs all public 015–018 ancestry, observations and local receipt")
            prior = [load(getattr(options, n.replace("-", "_"))) for n in PRIOR_NAMES]
            rest = [load(getattr(options, n.replace("-", "_")))
                    for n in names[len(PRIOR_NAMES):]]
            result = {"verified": True,
                      "decision": verify_receipt(prior, *rest)["decision"]}
    except (InvalidWorld, IdentityProfileError, KeyError,
            ValueError, TypeError, sqlite3.Error, OSError) as err:
        parser.error(str(err))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
