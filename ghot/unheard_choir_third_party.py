#!/usr/bin/env python3
"""UNHEARD CHOIR 015 — The Rightful Third Party.

A genuine but expired, old-owner-signed delegation survives as historical
evidence. A third party must authenticate its own presentation. Fresh source
review and independently signed successor-local consent must BOTH exist after
the 014 bounded archival-review selection. Even then the result is a strictly
non-admitted local archival HOLD. No inherited delegation becomes authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_successors import (
    ARCHIVED as REVIEW_ARCHIVED, CHOICES,
    assess as assess_014, build_fixture as fixture014,
    verify_policy as verify_014_policy, make_selection,
    prior_keys, exact, public, distinct, sign, authenticate,
)
from relatte_identity import IdentityKey, IdentityProfileError

POLICY = "ghot.unheard-choir-015-third-party-policy/v0"
DELEGATION = "ghot.unheard-choir-015-legacy-delegation/v0"
PRESENTATION = "ghot.unheard-choir-015-third-party-presentation/v0"
SOURCE = "ghot.unheard-choir-015-fresh-source-review/v0"
CONSENT = "ghot.unheard-choir-015-selected-owner-consent/v0"
ASSESSMENT = "ghot.unheard-choir-015-three-door-assessment/v0"
RECEIPT = "ghot.unheard-choir-015-neutral-custody/v0"
PD = b"GHOT-CHOIR-015-LOCAL-POLICY-v0|"
DD = b"GHOT-CHOIR-015-LEGACY-DELEGATION-v0|"
TD = b"GHOT-CHOIR-015-THIRD-PARTY-PRESENTATION-v0|"
SD = b"GHOT-CHOIR-015-FRESH-SOURCE-v0|"
OD = b"GHOT-CHOIR-015-OWNER-CONSENT-v0|"
RD = b"GHOT-CHOIR-015-NEUTRAL-CUSTODY-v0|"
ACTION = "ARCHIVE_HISTORICAL_FORK_EVIDENCE_ONLY"
GENESIS = digest({"domain": "ghot.unheard-choir-015-neutral-genesis/v0"})
CONTEST = "HOLD_014_SUCCESSION_NOT_RESOLVED_FOR_ARCHIVAL_REVIEW"
UNPRESENTED = "HOLD_THIRD_PARTY_HAS_NOT_PRESENTED_HISTORIC_DELEGATION"
SOURCE_MISSING = "HOLD_LEGACY_DELEGATION_NO_FRESH_SOURCE_REVIEW"
OWNER_MISSING = "HOLD_FRESH_SOURCE_BUT_SELECTED_OWNER_CONSENT_MISSING"
BOUNDED = "HOLD_THREE_PARTY_ARCHIVAL_EVIDENCE_ONLY_NOT_ADMITTED"


def check_clock(value: Any, name: str):
    if type(value) is not int or not 0 <= value <= 9999999:
        raise InvalidWorld(name + ": invalid simulated clock")


def check_window(issued: Any, until: Any, name: str):
    check_clock(issued, name + " issued")
    check_clock(until, name + " expires")
    if issued > until:
        raise InvalidWorld(name + ": reversed simulated interval")


def make_legacy(parcel: dict, historical_pins: dict, holder: IdentityKey,
                former_owner: IdentityKey,
                *, claimed_issued_at: int = 1000, not_after: int = 1050):
    check_window(claimed_issued_at, not_after, "legacy delegation")
    if public(former_owner.public_jwk()) != public(historical_pins["recipient_public_key"]):
        raise InvalidWorld("legacy issuer is not the pinned historical receiver")
    if public(holder.public_jwk()) == public(former_owner.public_jwk()):
        raise InvalidWorld("delegation holder must be distinct from old owner")
    if (not_after > parcel["simulated_not_after"]
        or claimed_issued_at < parcel["cargo"]["common_evidence"]["challenge"]["issued_at"]):
        raise InvalidWorld("old delegate claim exceeds original simulated 012 window")
    body = {
        "schema": DELEGATION, "scope": "HISTORICAL_DELEGATION_NEVER_CURRENT",
        "original_parcel_digest": digest(parcel),
        "original_owner_public_key": historical_pins["recipient_public_key"],
        "holder_public_key": holder.public_jwk(),
        "logical_address": historical_pins["recipient_site"],
        "action": ACTION,
        "simulated_claimed_issued_at": claimed_issued_at,
        "simulated_not_after": not_after,
    }
    return {**body, "signature": sign(former_owner, body, DD)}


def verify_legacy(parcel: dict, historical_pins: dict, instrument: Any):
    exact(instrument, ("schema", "scope", "original_parcel_digest",
                       "original_owner_public_key", "holder_public_key",
                       "logical_address", "action", "simulated_claimed_issued_at",
                       "simulated_not_after", "signature"), "historic delegation")
    if (instrument["schema"] != DELEGATION
        or instrument["scope"] != "HISTORICAL_DELEGATION_NEVER_CURRENT"
        or instrument["action"] != ACTION
        or instrument["original_parcel_digest"] != digest(parcel)
        or public(instrument["original_owner_public_key"]) != public(historical_pins["recipient_public_key"])
        or instrument["logical_address"] != historical_pins["recipient_site"]):
        raise InvalidWorld("old instrument is not bound to actual 012 addressed parcel")
    check_window(instrument["simulated_claimed_issued_at"],
                 instrument["simulated_not_after"], "historic instrument")
    if (instrument["simulated_claimed_issued_at"] <
        parcel["cargo"]["common_evidence"]["challenge"]["issued_at"]
        or instrument["simulated_not_after"] > parcel["simulated_not_after"]):
        raise InvalidWorld("claimed historical authority outside signed source window")
    if public(instrument["holder_public_key"]) == public(instrument["original_owner_public_key"]):
        raise InvalidWorld("former owner cannot impersonate third party")
    body = {k: v for k, v in instrument.items() if k != "signature"}
    authenticate(body, instrument["signature"],
                 historical_pins["recipient_public_key"], DD, "old owner")
    return True


def make_policy(parcel: dict, historical_pins: dict, policy014: dict,
                review_root014: dict, instrument: dict,
                root: IdentityKey, source: IdentityKey,
                recorder: IdentityKey, *, epoch: int = 1):
    verify_014_policy(parcel, historical_pins, policy014, review_root014)
    verify_legacy(parcel, historical_pins, instrument)
    if type(epoch) is not int or epoch < 1 or epoch > 1000000:
        raise InvalidWorld("invalid third-party review epoch")
    keys = prior_keys(parcel) + [
        review_root014, policy014["reviewer_public_key"],
        policy014["neutral_recorder_public_key"],
        policy014["candidates"]["north"]["owner_public_key"],
        policy014["candidates"]["south"]["owner_public_key"],
        instrument["holder_public_key"],
        root.public_jwk(), source.public_jwk(), recorder.public_jwk(),
    ]
    if not distinct(keys):
        raise InvalidWorld("new review authority keys cannot overlap historical or successor actors")
    body = {
        "schema": POLICY, "scope": "EXTERNAL_SOURCE_PLUS_OWNER_LOCAL_ARCHIVE_ONLY",
        "policy014_digest": digest(policy014),
        "historic_parcel_digest": digest(parcel),
        "historic_pins_digest": digest(historical_pins),
        "old_instrument_digest": digest(instrument),
        "third_party_public_key": instrument["holder_public_key"],
        "source_reviewer_public_key": source.public_jwk(),
        "neutral_recorder_public_key": recorder.public_jwk(),
        "review_epoch": epoch,
        "allowed_action": ACTION,
    }
    return {**body, "signature": sign(root, body, PD)}


def verify_policy(parcel: dict, historical_pins: dict, policy014: dict,
                  root014: dict, legacy: dict, policy: Any, pinned_root: dict):
    verify_014_policy(parcel, historical_pins, policy014, root014)
    verify_legacy(parcel, historical_pins, legacy)
    exact(policy, ("schema", "scope", "policy014_digest",
                   "historic_parcel_digest", "historic_pins_digest",
                   "old_instrument_digest", "third_party_public_key",
                   "source_reviewer_public_key", "neutral_recorder_public_key",
                   "review_epoch", "allowed_action", "signature"),
          "015 independent policy")
    if (policy["schema"] != POLICY
        or policy["scope"] != "EXTERNAL_SOURCE_PLUS_OWNER_LOCAL_ARCHIVE_ONLY"
        or policy["policy014_digest"] != digest(policy014)
        or policy["historic_parcel_digest"] != digest(parcel)
        or policy["historic_pins_digest"] != digest(historical_pins)
        or policy["old_instrument_digest"] != digest(legacy)
        or public(policy["third_party_public_key"]) != public(legacy["holder_public_key"])
        or type(policy["review_epoch"]) is not int
        or not 1 <= policy["review_epoch"] <= 1000000
        or policy["allowed_action"] != ACTION):
        raise InvalidWorld("new root policy not bound to complete predecessor evidence")
    keys = prior_keys(parcel) + [
        root014, policy014["reviewer_public_key"],
        policy014["neutral_recorder_public_key"],
        policy014["candidates"]["north"]["owner_public_key"],
        policy014["candidates"]["south"]["owner_public_key"],
        policy["third_party_public_key"], pinned_root,
        policy["source_reviewer_public_key"],
        policy["neutral_recorder_public_key"],
    ]
    if not distinct(keys):
        raise InvalidWorld("independently pinned root or roles reuse prior keys")
    body = {k: v for k, v in policy.items() if k != "signature"}
    authenticate(body, policy["signature"], pinned_root, PD,
                 "separate source-review trust root")


def make_presentation(policy: dict, legacy: dict, holder: IdentityKey,
                      *, claimed_at: int = 1100, not_after: int = 5000):
    check_window(claimed_at, not_after, "third-party presentation")
    if public(holder.public_jwk()) != public(policy["third_party_public_key"]):
        raise InvalidWorld("only historical holder may present instrument")
    body = {
        "schema": PRESENTATION, "scope": "THIRD_PARTY_SIGNED_REQUEST_NOT_AUTHORITY",
        "policy_digest": digest(policy),
        "historical_delegation_digest": digest(legacy),
        "holder_public_key": holder.public_jwk(),
        "requested_action": ACTION,
        "simulated_claimed_at": claimed_at,
        "simulated_not_after": not_after,
    }
    return {**body, "signature": sign(holder, body, TD)}


def verify_presentation(policy: dict, legacy: dict, claim: Any, *, now: int):
    exact(claim, ("schema", "scope", "policy_digest",
                  "historical_delegation_digest", "holder_public_key",
                  "requested_action", "simulated_claimed_at",
                  "simulated_not_after", "signature"), "third party presentation")
    if (claim["schema"] != PRESENTATION
        or claim["scope"] != "THIRD_PARTY_SIGNED_REQUEST_NOT_AUTHORITY"
        or claim["policy_digest"] != digest(policy)
        or claim["historical_delegation_digest"] != digest(legacy)
        or public(claim["holder_public_key"]) != public(policy["third_party_public_key"])
        or claim["requested_action"] != ACTION):
        raise InvalidWorld("third party request isn't a signed request for this parcel")
    check_window(claim["simulated_claimed_at"], claim["simulated_not_after"],
                 "third party claim")
    body = {k: v for k, v in claim.items() if k != "signature"}
    authenticate(body, claim["signature"], policy["third_party_public_key"], TD,
                 "third-party presenter")
    return now > claim["simulated_not_after"]


def make_source(policy: dict, claim: dict, succession_policy: dict,
                candidate: str, signer: IdentityKey, *,
                claimed_at: int = 1100, not_after: int = 5000):
    if candidate not in CHOICES or public(signer.public_jwk()) != public(
        policy["source_reviewer_public_key"]
    ):
        raise InvalidWorld("source reviewer not pinned or successor unknown")
    check_window(claimed_at, not_after, "new source review")
    body = {
        "schema": SOURCE, "scope": "NEW_SOURCE_ARCHIVE_REVIEW_ONLY",
        "policy_digest": digest(policy),
        "presentation_digest": digest(claim),
        "selected_candidate": candidate,
        "incarnation_digest": digest(succession_policy["candidates"][candidate]["incarnation"]),
        "allowed_action": ACTION,
        "simulated_claimed_at": claimed_at,
        "simulated_not_after": not_after,
        "effect_permission": "NONE",
    }
    return {**body, "signature": sign(signer, body, SD)}


def verify_source(policy: dict, claim: dict, succession_policy: dict,
                  approval: Any, *, now: int):
    exact(approval, ("schema", "scope", "policy_digest",
                     "presentation_digest", "selected_candidate",
                     "incarnation_digest", "allowed_action",
                     "simulated_claimed_at", "simulated_not_after",
                     "effect_permission", "signature"), "fresh source approval")
    chosen = approval["selected_candidate"]
    if (chosen not in CHOICES or approval["schema"] != SOURCE
        or approval["scope"] != "NEW_SOURCE_ARCHIVE_REVIEW_ONLY"
        or approval["policy_digest"] != digest(policy)
        or approval["presentation_digest"] != digest(claim)
        or approval["incarnation_digest"] != digest(succession_policy["candidates"][chosen]["incarnation"])
        or approval["allowed_action"] != ACTION
        or approval["effect_permission"] != "NONE"):
        raise InvalidWorld("source review not a bounded exact-cut authorization")
    check_window(approval["simulated_claimed_at"], approval["simulated_not_after"],
                 "fresh source grant")
    body = {k: v for k, v in approval.items() if k != "signature"}
    authenticate(body, approval["signature"],
                 policy["source_reviewer_public_key"], SD, "fresh source")
    return now > approval["simulated_not_after"]


def make_owner_consent(policy: dict, claim: dict, source: dict,
                       succession_policy: dict, owner: IdentityKey,
                       *, claimed_at: int = 1100, not_after: int = 5000):
    chosen = source["selected_candidate"]
    if (chosen not in CHOICES
        or public(owner.public_jwk()) != public(
            succession_policy["candidates"][chosen]["owner_public_key"])):
        raise InvalidWorld("owner consent must be separately signed by selected successor")
    check_window(claimed_at, not_after, "owner consent")
    body = {
        "schema": CONSENT, "scope": "OWNER_LOCAL_ARCHIVE_CONSENT_NOT_DELEGATION_TRANSFER",
        "policy_digest": digest(policy),
        "third_party_claim_digest": digest(claim),
        "source_approval_digest": digest(source),
        "selected_candidate": chosen,
        "selected_incarnation_digest": digest(
            succession_policy["candidates"][chosen]["incarnation"]),
        "allowed_action": ACTION,
        "simulated_claimed_at": claimed_at,
        "simulated_not_after": not_after,
        "effect_permission": "NONE",
    }
    return {**body, "signature": sign(owner, body, OD)}


def verify_owner_consent(policy: dict, claim: dict, source: dict,
                         succession_policy: dict, consent: Any, *, now: int):
    exact(consent, ("schema", "scope", "policy_digest",
                    "third_party_claim_digest", "source_approval_digest",
                    "selected_candidate", "selected_incarnation_digest",
                    "allowed_action", "simulated_claimed_at",
                    "simulated_not_after", "effect_permission", "signature"),
          "successor-local consent")
    chosen = source["selected_candidate"]
    if (consent["schema"] != CONSENT
        or consent["scope"] != "OWNER_LOCAL_ARCHIVE_CONSENT_NOT_DELEGATION_TRANSFER"
        or consent["policy_digest"] != digest(policy)
        or consent["third_party_claim_digest"] != digest(claim)
        or consent["source_approval_digest"] != digest(source)
        or consent["selected_candidate"] != chosen
        or consent["selected_incarnation_digest"] != digest(
            succession_policy["candidates"][chosen]["incarnation"])
        or consent["allowed_action"] != ACTION
        or consent["effect_permission"] != "NONE"):
        raise InvalidWorld("owner consent cannot migrate to another actor, epoch or source grant")
    check_window(consent["simulated_claimed_at"], consent["simulated_not_after"],
                 "owner-local consent")
    body = {k: v for k, v in consent.items() if k != "signature"}
    authenticate(body, consent["signature"],
                 succession_policy["candidates"][chosen]["owner_public_key"],
                 OD, "selected owner")
    return now > consent["simulated_not_after"]


def assess(parcel: dict, independent_old_local: dict, historical_pins: dict,
           succession_policy: dict, succession_root: dict,
           reviewer_selections: list, candidate_archive_grants: dict,
           legacy_delegation: dict, policy: dict, locally_pinned_root: dict,
           third_party_presentation: dict | None,
           fresh_source_review: dict | None,
           new_owner_consent: dict | None, *, now: int):
    check_clock(now, "receiver clock")
    verify_policy(parcel, historical_pins, succession_policy, succession_root,
                  legacy_delegation, policy, locally_pinned_root)
    inherited = assess_014(
        parcel, independent_old_local, historical_pins,
        succession_policy, succession_root,
        reviewer_selections, candidate_archive_grants, now=now)
    presentation_stale, source_stale, consent_stale = False, False, False
    if third_party_presentation is not None:
        presentation_stale = verify_presentation(
            policy, legacy_delegation, third_party_presentation, now=now)
    if fresh_source_review is not None:
        if third_party_presentation is None:
            raise InvalidWorld("signed source review without witnessed third-party claim")
        source_stale = verify_source(
            policy, third_party_presentation, succession_policy,
            fresh_source_review, now=now)
    if new_owner_consent is not None:
        if fresh_source_review is None:
            raise InvalidWorld("successor consent without independently signed source review")
        consent_stale = verify_owner_consent(
            policy, third_party_presentation, fresh_source_review,
            succession_policy, new_owner_consent, now=now)
    candidate = inherited["selected_for_bounded_local_archival_review"]
    if inherited["decision"] != REVIEW_ARCHIVED:
        decision = CONTEST
    elif third_party_presentation is None or presentation_stale:
        decision = UNPRESENTED
    elif fresh_source_review is None or source_stale:
        decision = SOURCE_MISSING
    elif (fresh_source_review["selected_candidate"] != candidate):
        # Signed source and selection disagree; current custody remains HOLD.
        decision = CONTEST
    elif new_owner_consent is None or consent_stale:
        decision = OWNER_MISSING
    else:
        decision = BOUNDED
    result = {
        "schema": ASSESSMENT, "014_assessment_digest": inherited["assessment_digest"],
        "014_decision": inherited["decision"],
        "historical_parcel_digest": digest(parcel),
        "historical_delegation_digest": digest(legacy_delegation),
        "015_policy_digest": digest(policy),
        "third_party_presentation_digest":
            digest(third_party_presentation) if third_party_presentation else None,
        "fresh_source_review_digest":
            digest(fresh_source_review) if fresh_source_review else None,
        "new_owner_consent_digest": digest(new_owner_consent) if new_owner_consent else None,
        "owner_relative_archive_review_choice": candidate,
        "decision": decision,
        "old_delegation_simulated_not_after": legacy_delegation["simulated_not_after"],
        "old_delegation_remains_historical": True,
        "historical_signer_authorizes_current_effects": False,
        "third_party_self_admitted": False,
        "separate_source_signer_verified": fresh_source_review is not None,
        "selected_owner_local_consent_verified": new_owner_consent is not None,
        "global_rightful_owner_proven": False,
        "native_relatte_receive": False,
        "native_relatte_admission": False,
        "forwarding_authorized": False,
        "external_execution": False,
        "simulated_receiver_clock": now, "authority": "NONE", "effects": [],
    }
    result["assessment_digest"] = digest(result)
    return result


def make_receipt(outcome: dict, signer: IdentityKey,
                 *, index: int = 0, previous: str = GENESIS):
    if type(index) is not int or index != 0 or previous != GENESIS:
        raise InvalidWorld("one-case journal must begin at known genesis receipt")
    body = {
        "schema": RECEIPT,
        "scope": "NEUTRAL_ARCHIVAL_EVIDENCE_RECORD_NOT_ADMISSION",
        "local_index": index, "previous_receipt_digest": previous,
        "assessment": outcome,
    }
    return {**body, "signature": sign(signer, body, RD)}


def verify_receipt(*sources, receipt: Any = None):
    if len(sources) != 13 or type(receipt) is not dict:
        raise InvalidWorld("015 keyless verifier needs thirteen public sources and signed receipt")
    exact(receipt, ("schema", "scope", "local_index",
                    "previous_receipt_digest", "assessment", "signature"),
          "015 neutral custody receipt")
    if (receipt["schema"] != RECEIPT
        or receipt["scope"] != "NEUTRAL_ARCHIVAL_EVIDENCE_RECORD_NOT_ADMISSION"
        or type(receipt["local_index"]) is not int or receipt["local_index"] != 0
        or receipt["previous_receipt_digest"] != GENESIS
        or type(receipt["assessment"]) is not dict):
        raise InvalidWorld("receipt tries to act beyond neutral one-case custody")
    clock = receipt["assessment"].get("simulated_receiver_clock")
    recomputed = assess(*sources, now=clock)
    if recomputed != receipt["assessment"]:
        raise InvalidWorld("receipt content not equal to fully revalidated historical and local evidence")
    body = {k: v for k, v in receipt.items() if k != "signature"}
    authenticate(body, receipt["signature"],
                 sources[8]["neutral_recorder_public_key"], RD, "015 neutral recorder")
    return recomputed


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS source_owner_history (
        local_index INTEGER PRIMARY KEY,
        policy_digest TEXT NOT NULL UNIQUE,
        signed_receipt_json TEXT NOT NULL
    )""")


def read_receipts(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        return [json.loads(x[0]) for x in db.execute(
            "SELECT signed_receipt_json FROM source_owner_history ORDER BY local_index").fetchall()]


def record_once(db_path: Path, *sources, recorder: IdentityKey, now: int):
    if len(sources) != 13:
        raise InvalidWorld("missing expected 015 public evidence")
    if public(recorder.public_jwk()) != public(sources[8]["neutral_recorder_public_key"]):
        raise InvalidWorld("former signer or third party cannot sign neutral record")
    outcome = assess(*sources, now=now)
    with sqlite3.connect(str(db_path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [json.loads(x[0]) for x in db.execute(
                "SELECT signed_receipt_json FROM source_owner_history ORDER BY local_index").fetchall()]
            if len(rows) > 1:
                raise InvalidWorld("one-case owner-local journal exceeded")
            if rows:
                old = rows[0]
                verify_receipt(*sources, receipt=old)
                if old["assessment"] != outcome:
                    raise InvalidWorld("signed case cannot be reclassified by retroactive consent")
                result = {"status": "DUPLICATE_UNCHANGED", "receipt": old}
            else:
                signed = make_receipt(outcome, recorder)
                db.execute("INSERT INTO source_owner_history VALUES(?,?,?)", (
                    0, digest(sources[8]),
                    json.dumps(signed, separators=(",", ":"), sort_keys=True),
                ))
                result = {"status": "SIGNED_LOCAL_EVIDENCE_RECORDED", "receipt": signed}
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return result


def build_fixture():
    tmp, parcel, old_local, pins, policy014, root014, grants, keys = fixture014()
    folder = Path(tmp.name)
    extra = {
        name: IdentityKey.load_or_create(folder / (name + ".pem"))
        for name in ("delegation-holder", "015-trust-root", "015-source-reviewer",
                     "015-neutral-recorder")
    }
    keys.update(extra)
    legacy = make_legacy(parcel, pins, extra["delegation-holder"],
                         keys["gossip-east"])
    policy = make_policy(parcel, pins, policy014, root014, legacy,
                         extra["015-trust-root"], extra["015-source-reviewer"],
                         extra["015-neutral-recorder"])
    selections = [make_selection(policy014, keys["succession-reviewer"], "north")]
    presentation = make_presentation(policy, legacy, extra["delegation-holder"])
    fresh_source = make_source(policy, presentation, policy014, "north",
                               extra["015-source-reviewer"])
    owner = make_owner_consent(policy, presentation, fresh_source, policy014,
                               keys["east-reconstituted"])
    evidence = [
        parcel, old_local, pins, policy014, root014, selections, grants,
        legacy, policy, extra["015-trust-root"].public_jwk(),
        presentation, fresh_source, owner,
    ]
    return tmp, evidence, keys


def demo():
    tmp, sources, keys = build_fixture()
    try:
        stages = {
            "historic_delegation_alone": assess(*sources[:5], [], sources[6],
                *sources[7:10], None, None, None, now=1100)["decision"],
            "third_party_presents": assess(*sources[:10], sources[10],
                None, None, now=1100)["decision"],
            "source_reviews": assess(*sources[:11], sources[11],
                None, now=1100)["decision"],
            "fresh_three_party": assess(*sources, now=1100)["decision"],
        }
        output = Path(tmp.name) / "015-neutral-signed.sqlite"
        rec = record_once(output, *sources,
                          recorder=keys["015-neutral-recorder"], now=1100)
        return {
            **stages,
            "legacy_instrument_expired_at": sources[7]["simulated_not_after"],
            "receiver_simulated_now": 1100,
            "one_signed_receipt": len(read_receipts(output)) == 1,
            "cold_receipt_verified": verify_receipt(
                *sources, receipt=rec["receipt"])["decision"] == BOUNDED,
            "no_native_admission": not rec["receipt"]["assessment"]["native_relatte_admission"],
            "no_forwarding": not rec["receipt"]["assessment"]["forwarding_authorized"],
            "no_external_execution": not rec["receipt"]["assessment"]["external_execution"],
        }
    finally:
        tmp.cleanup()


SOURCE_NAMES = (
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
    parser.add_argument("command", choices=("demo", "assess", "record", "verify"))
    for name in SOURCE_NAMES + ("neutral-private-key", "neutral-db", "receipt"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--now", type=int)
    opts = parser.parse_args()
    try:
        if opts.command == "demo":
            result = demo()
        else:
            required = SOURCE_NAMES[:10]
            if any(getattr(opts, x.replace("-", "_")) is None for x in required):
                parser.error("public 012–015 ancestry and independently pinned local review root required")
            sources = [
                load(getattr(opts, n.replace("-", "_")))
                if getattr(opts, n.replace("-", "_")) is not None else None
                for n in SOURCE_NAMES
            ]
            if opts.command == "assess":
                if opts.now is None:
                    parser.error("assess requires --now")
                result = assess(*sources, now=opts.now)
            elif opts.command == "record":
                if not opts.neutral_private_key or not opts.neutral_db or opts.now is None:
                    parser.error("record requires existing neutral signer, local DB and --now")
                if not opts.neutral_private_key.is_file():
                    parser.error("neutral private key cannot be generated by incoming evidence")
                signer = IdentityKey.load_or_create(opts.neutral_private_key)
                result = record_once(opts.neutral_db, *sources, recorder=signer, now=opts.now)
            else:
                if not opts.receipt:
                    parser.error("verify needs public signed receipt")
                outcome = verify_receipt(*sources, receipt=load(opts.receipt))
                result = {"verified": True, "decision": outcome["decision"]}
    except (InvalidWorld, IdentityProfileError, KeyError, TypeError,
            ValueError, OSError, sqlite3.Error) as err:
        parser.error(str(err))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
