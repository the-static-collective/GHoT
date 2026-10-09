#!/usr/bin/env python3
"""UNHEARD CHOIR 016 — The Witness Who Owns Nothing.

Historical custody never becomes source power. Holder-signed local inventory
distinguishes supplied signed documents from documents absent in this packet.
No signed source answer is UNKNOWN, not denial. A separately authenticated
source-local statement may assert unavailability, a record gap, explicit
decline or the revocation of an exact earlier source review. All dispositions
remain owner-local simulation-only HOLD and have no native reLATTE effect.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_third_party import (
    ACTION, BOUNDED as PRIOR_BOUNDED, CONTEST as PRIOR_CONTEST,
    SOURCE_MISSING as PRIOR_SOURCE_MISSING,
    OWNER_MISSING as PRIOR_OWNER_MISSING, UNPRESENTED as PRIOR_UNPRESENTED,
    assess as assess_015, build_fixture as fixture015,
    verify_policy as verify_015_policy,
    check_clock, check_window,
)
from unheard_choir_successors import prior_keys, exact, public, distinct, sign, authenticate
from relatte_identity import IdentityKey, IdentityProfileError

POLICY = "ghot.unheard-choir-016-custody-policy/v0"
MANIFEST = "ghot.unheard-choir-016-holder-inventory/v0"
NOTICE = "ghot.unheard-choir-016-source-local-notice/v0"
ASSESSMENT = "ghot.unheard-choir-016-evidence-gap-assessment/v0"
RECEIPT = "ghot.unheard-choir-016-neutral-local-receipt/v0"
PD = b"GHOT-CHOIR-016-CUSTODY-POLICY-v0|"
MD = b"GHOT-CHOIR-016-HOLDER-INVENTORY-v0|"
ND = b"GHOT-CHOIR-016-SOURCE-STATUS-v0|"
RD = b"GHOT-CHOIR-016-NEUTRAL-HOLD-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-016-neutral-genesis/v0"})
SLOTS = ("third_party_presentation", "fresh_source_review", "new_owner_consent")
STATUSES = ("PRESENT", "ABSENT_FROM_HOLDER_PACKET")
KINDS = ("SOURCE_UNAVAILABLE_LOCAL", "SOURCE_RECORD_NOT_FOUND_LOCAL",
         "SOURCE_DECLINED_NEW_REVIEW", "REVOKE_EXACT_SOURCE_REVIEW")
UNKNOWN = "HOLD_SOURCE_RESPONSE_UNKNOWN_NOT_DENIAL"
UNAVAILABLE = "HOLD_SOURCE_SIGNED_UNAVAILABLE_NOT_DENIAL"
RECORD_GAP = "HOLD_SOURCE_REPORTED_LOCAL_GAP_NOT_ERASURE"
DECLINED = "HOLD_SOURCE_EXPLICIT_DECLINE_NOT_HISTORICAL_ERASURE"
REVOKED = "HOLD_SOURCE_REVOKED_CURRENT_ARCHIVE_REVIEW"
OWNER_UNKNOWN = "HOLD_OWNER_CONSENT_NOT_IN_PACKET"
PREDECESSOR_HOLD = "HOLD_PREDECESSOR_AUTHORITY_UNRESOLVED"
CUSTODY_ONLY = "HOLD_CUSTODY_EVIDENCE_ONLY_NOT_ADMITTED"


def evidence_slots(prior: list) -> dict:
    if type(prior) is not list or len(prior) != 13:
        raise InvalidWorld("016 requires exactly 13 ordered 015 public evidence slots")
    return dict(zip(SLOTS, prior[10:13]))


def prior_key_set(prior: list) -> list:
    old = prior[0]
    succession = prior[3]
    review015 = prior[8]
    return prior_keys(old) + [
        prior[4],
        succession["reviewer_public_key"],
        succession["neutral_recorder_public_key"],
        succession["candidates"]["north"]["owner_public_key"],
        succession["candidates"]["south"]["owner_public_key"],
        prior[9], review015["source_reviewer_public_key"],
        review015["neutral_recorder_public_key"],
        review015["third_party_public_key"],
    ]


def make_policy(prior: list, root: IdentityKey, recorder: IdentityKey):
    verify_015_policy(prior[0], prior[2], prior[3], prior[4],
                      prior[7], prior[8], prior[9])
    keys = prior_key_set(prior) + [root.public_jwk(), recorder.public_jwk()]
    if not distinct(keys):
        raise InvalidWorld("016 root and neutral recorder keys must be independent of all prior roles")
    body = {
        "schema": POLICY, "scope": "LOCAL_SIGNED_CUSTODY_WITHOUT_SOURCE_ADMISSION",
        "prior015_policy_digest": digest(prior[8]),
        "prior014_policy_digest": digest(prior[3]),
        "historical_parcel_digest": digest(prior[0]),
        "legacy_instrument_digest": digest(prior[7]),
        "holder_public_key": prior[8]["third_party_public_key"],
        "source_public_key": prior[8]["source_reviewer_public_key"],
        "neutral_recorder_public_key": recorder.public_jwk(),
        "authorized_local_action": "PRESERVE_SIGNED_EVIDENCE_ONLY",
    }
    return {**body, "signature": sign(root, body, PD)}


def verify_policy(prior: list, policy: Any, pinned_root: Any):
    verify_015_policy(prior[0], prior[2], prior[3], prior[4],
                      prior[7], prior[8], prior[9])
    exact(policy, ("schema", "scope", "prior015_policy_digest",
                   "prior014_policy_digest", "historical_parcel_digest",
                   "legacy_instrument_digest", "holder_public_key",
                   "source_public_key", "neutral_recorder_public_key",
                   "authorized_local_action", "signature"), "016 custody policy")
    if (policy["schema"] != POLICY
        or policy["scope"] != "LOCAL_SIGNED_CUSTODY_WITHOUT_SOURCE_ADMISSION"
        or policy["prior015_policy_digest"] != digest(prior[8])
        or policy["prior014_policy_digest"] != digest(prior[3])
        or policy["historical_parcel_digest"] != digest(prior[0])
        or policy["legacy_instrument_digest"] != digest(prior[7])
        or public(policy["holder_public_key"]) != public(prior[8]["third_party_public_key"])
        or public(policy["source_public_key"]) != public(prior[8]["source_reviewer_public_key"])
        or policy["authorized_local_action"] != "PRESERVE_SIGNED_EVIDENCE_ONLY"):
        raise InvalidWorld("016 local policy does not match independently verified predecessor")
    if not distinct(prior_key_set(prior) + [
        pinned_root, policy["neutral_recorder_public_key"]
    ]):
        raise InvalidWorld("new owner-local trust root reused an inherited signer key")
    body = {k: v for k, v in policy.items() if k != "signature"}
    authenticate(body, policy["signature"], pinned_root, PD, "locally pinned custody policy")


def make_manifest(prior: list, policy: dict, holder: IdentityKey):
    if public(holder.public_jwk()) != public(policy["holder_public_key"]):
        raise InvalidWorld("holder cannot sign another person's observed inventory")
    inventory = [
        {"slot": name,
         "status": "PRESENT" if evidence_slots(prior)[name] is not None else
                   "ABSENT_FROM_HOLDER_PACKET",
         "document_digest": digest(evidence_slots(prior)[name])
         if evidence_slots(prior)[name] is not None else None}
        for name in SLOTS
    ]
    body = {
        "schema": MANIFEST, "scope": "HOLDER_LOCAL_PACKET_ONLY_NOT_WORLD_ABSENCE",
        "policy_digest": digest(policy),
        "historic_instrument_digest": digest(prior[7]),
        "holder_public_key": policy["holder_public_key"],
        "slots": inventory,
        "negative_evidence_is_global_absence": False,
    }
    return {**body, "signature": sign(holder, body, MD)}


def verify_manifest(prior: list, policy: dict, manifest: Any):
    exact(manifest, ("schema", "scope", "policy_digest",
                     "historic_instrument_digest", "holder_public_key",
                     "slots", "negative_evidence_is_global_absence",
                     "signature"), "holder custody manifest")
    if (manifest["schema"] != MANIFEST
        or manifest["scope"] != "HOLDER_LOCAL_PACKET_ONLY_NOT_WORLD_ABSENCE"
        or manifest["policy_digest"] != digest(policy)
        or manifest["historic_instrument_digest"] != digest(prior[7])
        or public(manifest["holder_public_key"]) != public(policy["holder_public_key"])
        or manifest["negative_evidence_is_global_absence"] is not False
        or type(manifest["slots"]) is not list
        or len(manifest["slots"]) != len(SLOTS)):
        raise InvalidWorld("holder manifest claimed more than its own packet")
    for name, row in zip(SLOTS, manifest["slots"]):
        exact(row, ("slot", "status", "document_digest"), "manifest record")
        val = evidence_slots(prior)[name]
        status = "PRESENT" if val is not None else "ABSENT_FROM_HOLDER_PACKET"
        actual = digest(val) if val is not None else None
        if row != {"slot": name, "status": status, "document_digest": actual}:
            raise InvalidWorld("signed omission must describe exactly the supplied local packet")
    body = {k: v for k, v in manifest.items() if k != "signature"}
    authenticate(body, manifest["signature"], policy["holder_public_key"],
                 MD, "historical holder inventory")


def make_notice(prior: list, policy: dict, signer: IdentityKey,
                kind: str, *, claimed_at: int = 1100,
                effective_at: int = 1100, not_after: int = 5000):
    if kind not in KINDS or public(signer.public_jwk()) != public(
        policy["source_public_key"]
    ):
        raise InvalidWorld("only locally pinned source reviewer may issue source-status notice")
    check_window(claimed_at, not_after, "source-local notice")
    check_clock(effective_at, "source notice effective instant")
    if not claimed_at <= effective_at <= not_after:
        raise InvalidWorld("notice effect cannot precede its declared origin or exceed interval")
    prior_grant = prior[11]
    if kind == "REVOKE_EXACT_SOURCE_REVIEW" and prior_grant is None:
        raise InvalidWorld("cannot revoke a missing specific signed source review")
    body = {
        "schema": NOTICE, "scope": "SOURCE_LOCAL_REPORT_NOT_GLOBAL_EVIDENCE_ABSENCE",
        "policy_digest": digest(policy),
        "historic_instrument_digest": digest(prior[7]),
        "holder_public_key": policy["holder_public_key"],
        "kind": kind,
        "review_target_digest": digest(prior_grant) if
            kind == "REVOKE_EXACT_SOURCE_REVIEW" else None,
        "simulated_claimed_at": claimed_at,
        "simulated_effective_at": effective_at,
        "simulated_not_after": not_after,
        "proves_nonresponse_elsewhere": False,
        "effect_permission": "NONE",
    }
    return {**body, "signature": sign(signer, body, ND)}


def verify_notice(prior: list, policy: dict, notice: Any, *, now: int):
    exact(notice, ("schema", "scope", "policy_digest",
                   "historic_instrument_digest", "holder_public_key",
                   "kind", "review_target_digest", "simulated_claimed_at",
                   "simulated_effective_at", "simulated_not_after",
                   "proves_nonresponse_elsewhere", "effect_permission",
                   "signature"), "source-local notice")
    if (notice["schema"] != NOTICE
        or notice["scope"] != "SOURCE_LOCAL_REPORT_NOT_GLOBAL_EVIDENCE_ABSENCE"
        or notice["policy_digest"] != digest(policy)
        or notice["historic_instrument_digest"] != digest(prior[7])
        or public(notice["holder_public_key"]) != public(policy["holder_public_key"])
        or notice["kind"] not in KINDS
        or notice["effect_permission"] != "NONE"
        or notice["proves_nonresponse_elsewhere"] is not False):
        raise InvalidWorld("source notice attempted unbounded source authority")
    check_window(notice["simulated_claimed_at"],
                 notice["simulated_not_after"], "source notice")
    check_clock(notice["simulated_effective_at"], "source effect time")
    if not (notice["simulated_claimed_at"] <=
            notice["simulated_effective_at"] <=
            notice["simulated_not_after"]):
        raise InvalidWorld("source notice time-window contradiction")
    target = digest(prior[11]) if notice["kind"] == "REVOKE_EXACT_SOURCE_REVIEW" and prior[11] is not None else None
    if (notice["review_target_digest"] != target
        or (notice["kind"] == "REVOKE_EXACT_SOURCE_REVIEW" and target is None)):
        raise InvalidWorld("source revocation must identify the exact existing source review")
    body = {k: v for k, v in notice.items() if k != "signature"}
    authenticate(body, notice["signature"], policy["source_public_key"],
                 ND, "independent source reviewer")
    return {
        "historically_signed": True,
        "active_at_simulated_clock": notice["simulated_effective_at"] <= now <= notice["simulated_not_after"],
        "kind": notice["kind"],
        "target_digest": target,
    }


def assess(prior: list, policy: dict, pinned_root: dict,
           holder_manifest: dict, source_notice: dict | None, *,
           now: int):
    check_clock(now, "016 local simulated clock")
    verify_policy(prior, policy, pinned_root)
    verify_manifest(prior, policy, holder_manifest)
    prior_decision = assess_015(*prior, now=now)
    signed_notice = verify_notice(prior, policy, source_notice, now=now) if source_notice is not None else None
    if prior_decision["014_decision"] != "HOLD_SELECTED_SUCCESSOR_ARCHIVAL_ONLY_NOT_ADMITTED":
        decision = PREDECESSOR_HOLD
    elif source_notice is not None and signed_notice["active_at_simulated_clock"]:
        if signed_notice["kind"] == "SOURCE_UNAVAILABLE_LOCAL":
            decision = UNAVAILABLE
        elif signed_notice["kind"] == "SOURCE_RECORD_NOT_FOUND_LOCAL":
            decision = RECORD_GAP
        elif signed_notice["kind"] == "SOURCE_DECLINED_NEW_REVIEW":
            decision = DECLINED
        else:
            decision = REVOKED
    elif prior[11] is None or prior_decision["decision"] == PRIOR_SOURCE_MISSING:
        decision = UNKNOWN
    elif prior[12] is None or prior_decision["decision"] == PRIOR_OWNER_MISSING:
        decision = OWNER_UNKNOWN
    elif prior_decision["decision"] == PRIOR_BOUNDED:
        decision = CUSTODY_ONLY
    else:
        decision = PREDECESSOR_HOLD
    slots = {row["slot"]: row for row in holder_manifest["slots"]}
    out = {
        "schema": ASSESSMENT,
        "015_assessment_digest": prior_decision["assessment_digest"],
        "015_decision": prior_decision["decision"],
        "policy_digest": digest(policy),
        "holder_signed_inventory_digest": digest(holder_manifest),
        "source_notice_digest": digest(source_notice) if source_notice is not None else None,
        "source_notice_status": signed_notice,
        "holder_custody_slots": slots,
        "source_response_observed": source_notice is not None,
        "missing_source_response_is_refusal": False,
        "missing_document_proves_world_nonexistence": False,
        "holder_has_current_source_power": False,
        "historical_document_erased_by_revocation": False,
        "retained_legacy_delegation_digest": digest(prior[7]),
        "retained_third_party_holder_public_key": policy["holder_public_key"],
        "decision": decision,
        "native_relatte_receive": False,
        "native_relatte_admission": False,
        "forwarding_authorized": False,
        "external_execution": False,
        "authority": "NONE", "effects": [],
        "simulated_receiver_clock": now,
    }
    out["assessment_digest"] = digest(out)
    return out


def make_receipt(outcome: dict, signer: IdentityKey):
    body = {
        "schema": RECEIPT, "scope": "NEUTRAL_SIGNED_UNKNOWN_OR_LOCAL_HOLD_NOT_ADMISSION",
        "local_index": 0, "previous_receipt_digest": GENESIS,
        "assessment": outcome,
    }
    return {**body, "signature": sign(signer, body, RD)}


def verify_receipt(prior: list, policy: dict, pinned_root: dict,
                   manifest: dict, notice: dict | None, receipt: Any):
    exact(receipt, ("schema", "scope", "local_index",
                    "previous_receipt_digest", "assessment", "signature"),
          "016 neutral custody receipt")
    if (receipt["schema"] != RECEIPT
        or receipt["scope"] != "NEUTRAL_SIGNED_UNKNOWN_OR_LOCAL_HOLD_NOT_ADMISSION"
        or type(receipt["local_index"]) is not int or receipt["local_index"] != 0
        or receipt["previous_receipt_digest"] != GENESIS
        or type(receipt["assessment"]) is not dict):
        raise InvalidWorld("custody receipt not an owner-local HOLD")
    calculated = assess(prior, policy, pinned_root, manifest, notice,
                        now=receipt["assessment"].get("simulated_receiver_clock"))
    if calculated != receipt["assessment"]:
        raise InvalidWorld("recipient's signed receipt differs from cold re-evaluation")
    body = {k: v for k, v in receipt.items() if k != "signature"}
    authenticate(body, receipt["signature"],
                 policy["neutral_recorder_public_key"], RD, "016 neutral local signer")
    return calculated


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS custody (
        local_index INTEGER PRIMARY KEY,
        policy_digest TEXT NOT NULL UNIQUE,
        receipt_json TEXT NOT NULL
    )""")


def read_receipts(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        return [json.loads(row[0]) for row in db.execute(
            "SELECT receipt_json FROM custody ORDER BY local_index").fetchall()]


def record_once(path: Path, prior: list, policy: dict, pinned_root: dict,
                manifest: dict, notice: dict | None, recorder: IdentityKey,
                *, now: int):
    if public(recorder.public_jwk()) != public(policy["neutral_recorder_public_key"]):
        raise InvalidWorld("holder/source/former owner cannot sign neutral receipt")
    outcome = assess(prior, policy, pinned_root, manifest, notice, now=now)
    with sqlite3.connect(str(path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [json.loads(r[0]) for r in db.execute(
                "SELECT receipt_json FROM custody ORDER BY local_index").fetchall()]
            if len(rows) > 1:
                raise InvalidWorld("one-case local journal exceeded")
            if rows:
                old = rows[0]
                verify_receipt(prior, policy, pinned_root, manifest, notice, old)
                if old["assessment"] != outcome:
                    raise InvalidWorld("new source notice cannot retrospectively rewrite signed local state")
                result = {"status": "DUPLICATE_UNCHANGED", "receipt": old}
            else:
                signed = make_receipt(outcome, recorder)
                db.execute("INSERT INTO custody VALUES(?,?,?)", (
                    0, digest(policy), json.dumps(signed, sort_keys=True, separators=(",", ":")),
                ))
                result = {"status": "SIGNED_NEUTRAL_EVIDENCE_RECORDED", "receipt": signed}
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return result


def build_fixture():
    tmp, prior, keys = fixture015()
    root = IdentityKey.load_or_create(Path(tmp.name) / "016-custody-root.pem")
    neutral = IdentityKey.load_or_create(Path(tmp.name) / "016-neutral-recorder.pem")
    keys["016-custody-root"] = root
    keys["016-neutral-recorder"] = neutral
    policy = make_policy(prior, root, neutral)
    holder_manifest = make_manifest(prior, policy, keys["delegation-holder"])
    return tmp, prior, policy, root.public_jwk(), holder_manifest, keys


def demo():
    tmp, prior, policy, root, manifest, keys = build_fixture()
    try:
        base = assess(prior, policy, root, manifest, None, now=1250)
        no_source = list(prior)
        no_source[11], no_source[12] = None, None
        absent = make_manifest(no_source, policy, keys["delegation-holder"])
        unknown = assess(no_source, policy, root, absent, None, now=1250)
        unavailable_notice = make_notice(no_source, policy,
            keys["015-source-reviewer"], "SOURCE_UNAVAILABLE_LOCAL",
            claimed_at=1100, effective_at=1200, not_after=5000)
        unavailable = assess(no_source, policy, root, absent, unavailable_notice, now=1250)
        revoke = make_notice(prior, policy, keys["015-source-reviewer"],
                             "REVOKE_EXACT_SOURCE_REVIEW",
                             claimed_at=1100, effective_at=1200, not_after=5000)
        revoked = assess(prior, policy, root, manifest, revoke, now=1250)
        db = Path(tmp.name) / "016-custody.sqlite"
        rec = record_once(db, no_source, policy, root, absent,
                          unavailable_notice, keys["016-neutral-recorder"], now=1250)
        return {
            "full_prior_evidence_archive_only": base["decision"],
            "source_never_responded": unknown["decision"],
            "signed_source_unavailable": unavailable["decision"],
            "signed_exact_source_review_revocation": revoked["decision"],
            "revoked_source_history_retained": not revoked["historical_document_erased_by_revocation"],
            "no_reply_does_not_mean_refusal": not unknown["missing_source_response_is_refusal"],
            "signed_omission_does_not_prove_absence": not unavailable["missing_document_proves_world_nonexistence"],
            "neutral_signed_local_receipt": len(read_receipts(db)) == 1,
            "cold_public_receipt_verified": verify_receipt(
                no_source, policy, root, absent, unavailable_notice,
                rec["receipt"])["decision"] == UNAVAILABLE,
            "native_relatte_admission": revoked["native_relatte_admission"],
            "external_execution": revoked["external_execution"],
        }
    finally:
        tmp.cleanup()


SOURCE_NAMES = (
    "parcel", "historical-local-package", "historical-pins",
    "succession-policy", "succession-root", "reviewer-selections",
    "candidate-archive-grants", "legacy-delegation",
    "third-party-policy", "third-party-root",
    "third-party-presentation", "fresh-source-review", "new-owner-consent",
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "record", "verify"))
    for name in SOURCE_NAMES + (
        "custody-policy", "custody-root", "holder-inventory",
        "source-notice", "neutral-private-key", "neutral-db", "receipt",
    ):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--now", type=int)
    options = parser.parse_args()
    try:
        if options.command == "demo":
            result = demo()
        else:
            required = SOURCE_NAMES[:10] + (
                "custody-policy", "custody-root", "holder-inventory"
            )
            if any(getattr(options, n.replace("-", "_")) is None for n in required):
                parser.error("all historical trust material and owner-local holder manifest required")
            prior = [
                load(getattr(options, n.replace("-", "_")))
                if getattr(options, n.replace("-", "_")) is not None else None
                for n in SOURCE_NAMES
            ]
            policy = load(options.custody_policy)
            root = load(options.custody_root)
            manifest = load(options.holder_inventory)
            notice = load(options.source_notice) if options.source_notice else None
            if options.command == "assess":
                if options.now is None:
                    parser.error("assess requires a simulated receiver --now")
                result = assess(prior, policy, root, manifest, notice, now=options.now)
            elif options.command == "record":
                if (not options.neutral_private_key or not options.neutral_db
                    or options.now is None):
                    parser.error("record requires a preexisting neutral key, database and --now")
                if not options.neutral_private_key.is_file():
                    parser.error("recipient cannot silently provision a new neutral identity")
                signer = IdentityKey.load_or_create(options.neutral_private_key)
                result = record_once(options.neutral_db, prior, policy, root,
                                     manifest, notice, signer, now=options.now)
            else:
                if options.receipt is None:
                    parser.error("verify requires a signed public receipt")
                replay = verify_receipt(prior, policy, root, manifest, notice,
                                        load(options.receipt))
                result = {"verified": True, "decision": replay["decision"]}
    except (InvalidWorld, IdentityProfileError, KeyError, ValueError,
            TypeError, OSError, sqlite3.Error) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
