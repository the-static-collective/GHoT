#!/usr/bin/env python3
"""UNHEARD CHOIR 019 — The Referee Who Refused to Rule.

A separately pinned, synthetic source-epoch witness signs exact source-event
assignments. A different referee may refuse or select an unambiguously maximal
attested epoch for one exact local archival review. The owner-local selector
must separately consent before the assessment can narrow to archival HOLD.
No claimed timestamp, local arrival order, historical signature or referee
creates actual source authority. Earlier signed forks remain immutable.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_source_fork import (
    build_fixture as fixture018, make_view, make_017_snapshot,
    compare as compare018, verify_event, event_set,
)
from unheard_choir_successors import (
    prior_keys, distinct, public, exact, sign, authenticate,
)
from unheard_choir_third_party import check_clock, check_window
from relatte_identity import IdentityKey, IdentityProfileError

POLICY = "ghot.unheard-choir-019-local-precedence-policy/v0"
EPOCH = "ghot.unheard-choir-019-independent-source-epoch/v0"
REFEREE = "ghot.unheard-choir-019-referee-choice/v0"
OWNER = "ghot.unheard-choir-019-owner-local-selection/v0"
ASSESSMENT = "ghot.unheard-choir-019-scoped-referee-assessment/v0"
RECEIPT = "ghot.unheard-choir-019-neutral-history-receipt/v0"
P_DOMAIN = b"GHOT-CHOIR-019-INDEPENDENT-POLICY-v0|"
E_DOMAIN = b"GHOT-CHOIR-019-EPOCH-v0|"
F_DOMAIN = b"GHOT-CHOIR-019-REFEREE-v0|"
O_DOMAIN = b"GHOT-CHOIR-019-OWNER-v0|"
R_DOMAIN = b"GHOT-CHOIR-019-NEUTRAL-RECEIPT-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-019-local-genesis/v0"})
SCOPE = "ONE_CASE_HISTORICAL_ARCHIVE_REVIEW_ONLY"
NO_EPOCH = "HOLD_MISSING_INDEPENDENT_EPOCH_PROOF"
EPOCH_COLLISION = "HOLD_CONFLICTING_EPOCH_ASSIGNMENTS"
NO_REFEREE = "HOLD_REFEREE_HAS_NOT_RULED"
REFUSED = "HOLD_REFEREE_EXPLICITLY_DECLINED"
BAD_SELECTION = "HOLD_REFEREE_CHOICE_CONTRADICTS_CERTIFIED_PRECEDENCE"
NO_OWNER = "HOLD_OWNER_LOCAL_SELECTION_ABSENT"
OWNER_REFUSED = "HOLD_OWNER_LOCAL_REFUSED_OR_DIFFERENT"
BOUNDED = "HOLD_SCOPED_ARCHIVAL_REVIEW_SELECTED_NOT_ADMITTED"


def witness_keys(prior: list, p016: dict, root016: dict,
                 roster017: dict, root017: dict) -> list:
    keys = prior_keys(prior[0]) + [
        prior[4], prior[9],
        prior[3]["reviewer_public_key"],
        prior[3]["neutral_recorder_public_key"],
        prior[3]["candidates"]["north"]["owner_public_key"],
        prior[3]["candidates"]["south"]["owner_public_key"],
        prior[8]["third_party_public_key"],
        prior[8]["source_reviewer_public_key"],
        prior[8]["neutral_recorder_public_key"],
        root016, p016["neutral_recorder_public_key"], root017,
        roster017["sites"]["west"], roster017["sites"]["east"],
    ]
    return keys


def signed_events(prior: list, p016: dict, roster017: dict,
                  local: dict, remote: dict) -> dict:
    all_events = {}
    for view in (local, remote):
        snap = view["original_017_snapshot"]
        this = event_set(prior, p016, roster017,
                         view["additional_source_events"], snap["source_notice"])
        all_events.update(this)
    return all_events


def make_policy(prior: list, p016: dict, root016: dict, manifest: dict,
                roster017: dict, root017: dict,
                local: dict, remote: dict,
                root: IdentityKey, epoch_witness: IdentityKey,
                referee: IdentityKey, owner_selector: IdentityKey,
                recorder: IdentityKey):
    base = compare018(prior, p016, root016, manifest,
                      roster017, root017, local, remote, now=1250)
    if base["decision"] not in (
        "HOLD_SOURCE_REVOCATION_REINSTATEMENT_UNRESOLVED",
        "HOLD_MULTIPLE_SOURCE_REVOCATIONS_UNORDERED",
    ):
        raise InvalidWorld("019 precedence experiment needs independently signed source fork")
    if local["site"] != "west" or remote["site"] != "east":
        raise InvalidWorld("bounded 019 owner-local review is WEST receiving EAST")
    keys = witness_keys(prior, p016, root016, roster017, root017) + [
        root.public_jwk(), epoch_witness.public_jwk(),
        referee.public_jwk(), owner_selector.public_jwk(), recorder.public_jwk(),
    ]
    if not distinct(keys):
        raise InvalidWorld("019 separate trust root, epoch witness, referee, owner and recorder required")
    body = {
        "schema": POLICY,
        "scope": SCOPE,
        "original_018_local_view_digest": digest(local),
        "original_018_remote_view_digest": digest(remote),
        "original_018_evidence_digest": base["assessment_digest"],
        "historic_015_source_approval_digest": digest(prior[11]),
        "event_digest_set": base["source_event_digests"],
        "pinned_epoch_witness": epoch_witness.public_jwk(),
        "pinned_referee": referee.public_jwk(),
        "pinned_owner_selector": owner_selector.public_jwk(),
        "pinned_neutral_recorder": recorder.public_jwk(),
        "winner_rule": "UNIQUE_GREATEST_INDEPENDENTLY_CERTIFIED_EPOCH",
        "owner_may_refuse": True,
        "creates_native_grant": False,
    }
    return {**body, "signature": sign(root, body, P_DOMAIN)}


def verify_policy(prior: list, p016: dict, root016: dict, manifest: dict,
                  roster017: dict, root017: dict,
                  local: dict, remote: dict, policy: Any, pinned_root: Any):
    base = compare018(prior, p016, root016, manifest,
                      roster017, root017, local, remote, now=1250)
    exact(policy, (
        "schema", "scope", "original_018_local_view_digest",
        "original_018_remote_view_digest", "original_018_evidence_digest",
        "historic_015_source_approval_digest", "event_digest_set",
        "pinned_epoch_witness", "pinned_referee",
        "pinned_owner_selector", "pinned_neutral_recorder",
        "winner_rule", "owner_may_refuse", "creates_native_grant", "signature",
    ), "independently pinned 019 local policy")
    if (policy["schema"] != POLICY
        or policy["scope"] != SCOPE
        or local["site"] != "west" or remote["site"] != "east"
        or base["decision"] not in (
            "HOLD_SOURCE_REVOCATION_REINSTATEMENT_UNRESOLVED",
            "HOLD_MULTIPLE_SOURCE_REVOCATIONS_UNORDERED")
        or policy["original_018_local_view_digest"] != digest(local)
        or policy["original_018_remote_view_digest"] != digest(remote)
        or policy["original_018_evidence_digest"] != base["assessment_digest"]
        or policy["historic_015_source_approval_digest"] != digest(prior[11])
        or policy["event_digest_set"] != base["source_event_digests"]
        or policy["winner_rule"] != "UNIQUE_GREATEST_INDEPENDENTLY_CERTIFIED_EPOCH"
        or policy["owner_may_refuse"] is not True
        or policy["creates_native_grant"] is not False):
        raise InvalidWorld("019 policy misbinds the original fork or expands scope")
    keys = witness_keys(prior, p016, root016, roster017, root017) + [
        pinned_root, policy["pinned_epoch_witness"],
        policy["pinned_referee"], policy["pinned_owner_selector"],
        policy["pinned_neutral_recorder"],
    ]
    if not distinct(keys):
        raise InvalidWorld("019 pinned root or role key overlaps earlier signers")
    body = {k: v for k, v in policy.items() if k != "signature"}
    authenticate(body, policy["signature"], pinned_root, P_DOMAIN,
                 "external pinned 019 local review policy")


def make_epoch(policy: dict, event: dict, witness: IdentityKey,
               epoch: int):
    if public(witness.public_jwk()) != public(policy["pinned_epoch_witness"]):
        raise InvalidWorld("source epochs require separately pinned attestor")
    if type(epoch) is not int or not 1 <= epoch <= 1000000:
        raise InvalidWorld("source epoch needs bounded positive integer")
    if digest(event) not in policy["event_digest_set"]:
        raise InvalidWorld("source epoch certificate cannot point to unseen source claim")
    body = {
        "schema": EPOCH, "scope": SCOPE,
        "policy_digest": digest(policy),
        "source_event_digest": digest(event),
        "source_epoch": epoch,
        "is_external_certificate_of_source_time": False,
        "grants_execution": False,
    }
    return {**body, "signature": sign(witness, body, E_DOMAIN)}


def verify_epochs(policy: dict, source_events: dict,
                  certificates: Any):
    if type(certificates) is not list or len(certificates) > 5:
        raise InvalidWorld("at most five separately signed epoch statements in bounded fixture")
    by_document = {}
    by_epoch = {}
    for cert in certificates:
        exact(cert, ("schema", "scope", "policy_digest", "source_event_digest",
                     "source_epoch", "is_external_certificate_of_source_time",
                     "grants_execution", "signature"), "019 source epoch attestation")
        name, epoch = cert["source_event_digest"], cert["source_epoch"]
        if (cert["schema"] != EPOCH or cert["scope"] != SCOPE
            or cert["policy_digest"] != digest(policy)
            or type(epoch) is not int or not 1 <= epoch <= 1000000
            or name not in policy["event_digest_set"]
            or name not in source_events
            or cert["is_external_certificate_of_source_time"] is not False
            or cert["grants_execution"] is not False):
            raise InvalidWorld("epoch certificate attempted unpinned scope or forged event")
        body = {k: v for k, v in cert.items() if k != "signature"}
        authenticate(body, cert["signature"], policy["pinned_epoch_witness"],
                     E_DOMAIN, "independent epoch assignment")
        # Repeated authentication of the same (event, epoch) is not a
        # contradictory assignment, even when ECDSA signatures differ.
        by_document.setdefault(name, set()).add(epoch)
        by_epoch.setdefault(epoch, set()).add(name)
    complete = set(by_document) == set(policy["event_digest_set"])
    unique = (complete and all(len(x) == 1 for x in by_document.values())
              and all(len(x) == 1 for x in by_epoch.values()))
    winner = None
    if unique:
        winner = max(
            ((next(iter(epochs)), name)
             for name, epochs in by_document.items())
        )[1]
    return {
        "complete": complete, "unique": unique, "winner": winner,
        "signed_certificate_digests": sorted(digest(c) for c in certificates),
        "certificate_count": len(certificates),
    }


def make_referee(policy: dict, certificates: list, referee: IdentityKey,
                 *, action: str, selected: str | None = None,
                 claimed_at: int = 1300, not_after: int = 5000):
    if public(referee.public_jwk()) != public(policy["pinned_referee"]):
        raise InvalidWorld("only pinned reviewer may make a scoped precedence choice")
    if action not in ("DECLINE", "SELECT"):
        raise InvalidWorld("referee action is explicit refusal or selection only")
    if (action == "DECLINE" and selected is not None) or (
        action == "SELECT" and selected not in policy["event_digest_set"]
    ):
        raise InvalidWorld("referee cannot select unknown claim or hide choice in refusal")
    check_window(claimed_at, not_after, "019 referee review")
    body = {
        "schema": REFEREE, "scope": SCOPE,
        "policy_digest": digest(policy),
        "certificates_digest": digest(sorted(certificates, key=digest)),
        "action": action, "selected_event_digest": selected,
        "simulated_claimed_at": claimed_at, "simulated_not_after": not_after,
        "declares_global_authority": False,
        "effect_permission": "NONE",
    }
    return {**body, "signature": sign(referee, body, F_DOMAIN)}


def verify_referee(policy: dict, certificates: list,
                   choice: Any, *, now: int):
    exact(choice, ("schema", "scope", "policy_digest",
                   "certificates_digest", "action", "selected_event_digest",
                   "simulated_claimed_at", "simulated_not_after",
                   "declares_global_authority", "effect_permission",
                   "signature"), "019 signed referee response")
    action, name = choice["action"], choice["selected_event_digest"]
    if (choice["schema"] != REFEREE or choice["scope"] != SCOPE
        or choice["policy_digest"] != digest(policy)
        or choice["certificates_digest"] != digest(sorted(certificates, key=digest))
        or action not in ("DECLINE", "SELECT")
        or (action == "DECLINE" and name is not None)
        or (action == "SELECT" and name not in policy["event_digest_set"])
        or choice["declares_global_authority"] is not False
        or choice["effect_permission"] != "NONE"):
        raise InvalidWorld("referee attempted universal authority or incompatible scope")
    check_window(choice["simulated_claimed_at"],
                 choice["simulated_not_after"], "referee response")
    body = {k: v for k, v in choice.items() if k != "signature"}
    authenticate(body, choice["signature"], policy["pinned_referee"],
                 F_DOMAIN, "independently pinned referee")
    return now > choice["simulated_not_after"]


def make_owner(policy: dict, referee: dict,
               owner: IdentityKey, *, action: str,
               selected: str | None = None, claimed_at: int = 1300,
               not_after: int = 5000):
    if public(owner.public_jwk()) != public(policy["pinned_owner_selector"]):
        raise InvalidWorld("owner-local selector is distinct from referee")
    if action not in ("REFUSE", "SELECT") or (
        action == "REFUSE" and selected is not None
    ) or (action == "SELECT" and selected not in policy["event_digest_set"]):
        raise InvalidWorld("owner selector must explicitly refuse or choose known claim")
    check_window(claimed_at, not_after, "owner-local selection")
    body = {
        "schema": OWNER, "scope": SCOPE,
        "policy_digest": digest(policy),
        "referee_digest": digest(referee),
        "action": action, "selected_event_digest": selected,
        "simulated_claimed_at": claimed_at, "simulated_not_after": not_after,
        "creates_source_grant": False,
        "effect_permission": "NONE",
    }
    return {**body, "signature": sign(owner, body, O_DOMAIN)}


def verify_owner(policy: dict, referee: dict,
                 owner: Any, *, now: int):
    exact(owner, ("schema", "scope", "policy_digest",
                  "referee_digest", "action", "selected_event_digest",
                  "simulated_claimed_at", "simulated_not_after",
                  "creates_source_grant", "effect_permission", "signature"),
          "019 owner-local choice")
    action, name = owner["action"], owner["selected_event_digest"]
    if (owner["schema"] != OWNER or owner["scope"] != SCOPE
        or owner["policy_digest"] != digest(policy)
        or owner["referee_digest"] != digest(referee)
        or action not in ("REFUSE", "SELECT")
        or (action == "REFUSE" and name is not None)
        or (action == "SELECT" and name not in policy["event_digest_set"])
        or owner["creates_source_grant"] is not False
        or owner["effect_permission"] != "NONE"):
        raise InvalidWorld("owner-local choice cannot create production source authority")
    check_window(owner["simulated_claimed_at"], owner["simulated_not_after"],
                 "owner-local selection")
    body = {k: v for k, v in owner.items() if k != "signature"}
    authenticate(body, owner["signature"], policy["pinned_owner_selector"],
                 O_DOMAIN, "distinct owner-local selector")
    return now > owner["simulated_not_after"]


def assess(prior: list, p016: dict, root016: dict, manifest: dict,
           roster: dict, root017: dict, local: dict, remote: dict,
           policy: dict, pinned_root: dict, certificates: list,
           referee: dict | None, owner: dict | None,
           *, now: int):
    check_clock(now, "local 019 synthetic review clock")
    verify_policy(prior, p016, root016, manifest,
                  roster, root017, local, remote, policy, pinned_root)
    historical = compare018(prior, p016, root016, manifest,
                            roster, root017, local, remote, now=now)
    sources = signed_events(prior, p016, roster, local, remote)
    coverage = verify_epochs(policy, sources, certificates)
    expired_referee = False
    expired_owner = False
    if referee is not None:
        expired_referee = verify_referee(policy, certificates,
                                         referee, now=now)
    if owner is not None:
        if referee is None:
            raise InvalidWorld("owner-local selector cannot act without signed referee statement")
        expired_owner = verify_owner(policy, referee, owner, now=now)
    if not coverage["complete"]:
        decision = NO_EPOCH
    elif not coverage["unique"]:
        decision = EPOCH_COLLISION
    elif referee is None:
        decision = NO_REFEREE
    elif referee["action"] == "DECLINE" or expired_referee:
        decision = REFUSED
    elif referee["selected_event_digest"] != coverage["winner"]:
        decision = BAD_SELECTION
    elif owner is None:
        decision = NO_OWNER
    elif expired_owner or owner["action"] == "REFUSE" or (
        owner["selected_event_digest"] != coverage["winner"]
    ):
        decision = OWNER_REFUSED
    else:
        decision = BOUNDED
    out = {
        "schema": ASSESSMENT, "scope": SCOPE,
        "prior018_assessment_digest": historical["assessment_digest"],
        "prior018_source_conflict": historical["decision"],
        "source_history_digest_set": historical["source_event_digests"],
        "original_015_approval_digest": digest(prior[11]),
        "policy_digest": digest(policy),
        "epoch_evidence": coverage,
        "referee_statement_digest": digest(referee) if referee is not None else None,
        "owner_local_statement_digest": digest(owner) if owner is not None else None,
        "chosen_for_local_archive_review_only": coverage["winner"] if decision == BOUNDED else None,
        "decision": decision,
        "prior_source_statements_unchanged": True,
        "global_jurisdiction_established": False,
        "referee_signature_is_native_authority": False,
        "simulated_clock_is_trusted_time": False,
        "native_relatte_receive": False,
        "native_relatte_admission": False,
        "external_execution": False,
        "forwarding_permitted": False,
        "authority": "NONE", "effects": [],
        "simulated_local_clock": now,
    }
    out["assessment_digest"] = digest(out)
    return out


def make_receipt(result: dict, recorder: IdentityKey):
    body = {
        "schema": RECEIPT, "scope": "LOCAL_SIGNED_EPOCH_REVIEW_HOLD_NOT_ADMISSION",
        "local_index": 0, "previous_receipt_digest": GENESIS,
        "assessment": result,
    }
    return {**body, "signature": sign(recorder, body, R_DOMAIN)}


def verify_receipt(prior: list, p016: dict, root016: dict, manifest: dict,
                   roster: dict, root017: dict, local: dict, remote: dict,
                   policy: dict, pinned_root: dict, certificates: list,
                   referee: dict | None, owner: dict | None, receipt: Any):
    exact(receipt, ("schema", "scope", "local_index",
                    "previous_receipt_digest", "assessment", "signature"),
          "019 cold local receipt")
    if (receipt["schema"] != RECEIPT
        or receipt["scope"] != "LOCAL_SIGNED_EPOCH_REVIEW_HOLD_NOT_ADMISSION"
        or type(receipt["local_index"]) is not int or receipt["local_index"] != 0
        or receipt["previous_receipt_digest"] != GENESIS
        or type(receipt["assessment"]) is not dict):
        raise InvalidWorld("019 neutral receipt is bounded to original genesis and no-effects scope")
    replay = assess(prior, p016, root016, manifest, roster, root017, local, remote,
                    policy, pinned_root, certificates, referee, owner,
                    now=receipt["assessment"].get("simulated_local_clock"))
    if replay != receipt["assessment"]:
        raise InvalidWorld("signed receipt differs from cold source/epoch/referee/owner replay")
    body = {k: v for k, v in receipt.items() if k != "signature"}
    authenticate(body, receipt["signature"], policy["pinned_neutral_recorder"],
                 R_DOMAIN, "locally pinned neutral 019 recorder")
    return replay


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS local_precedence_receipt(
        local_index INTEGER PRIMARY KEY,
        policy_digest TEXT NOT NULL UNIQUE,
        receipt_json TEXT NOT NULL
    )""")


def read_receipts(path: Path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        return [json.loads(r[0]) for r in db.execute(
            "SELECT receipt_json FROM local_precedence_receipt ORDER BY local_index").fetchall()]


def record_once(path: Path, prior: list, p016: dict, root016: dict,
                manifest: dict, roster: dict, root017: dict,
                local: dict, remote: dict, policy: dict,
                pinned_root: dict, certificates: list,
                referee: dict | None, owner: dict | None,
                recorder: IdentityKey, *, now: int):
    if public(recorder.public_jwk()) != public(policy["pinned_neutral_recorder"]):
        raise InvalidWorld("only separately pinned neutral recorder can sign")
    inputs = (
        prior, p016, root016, manifest, roster, root017, local, remote,
        policy, pinned_root, certificates, referee, owner,
    )
    outcome = assess(*inputs, now=now)
    with sqlite3.connect(str(path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [json.loads(r[0]) for r in db.execute(
                "SELECT receipt_json FROM local_precedence_receipt ORDER BY local_index").fetchall()]
            if len(rows) > 1:
                raise InvalidWorld("one-case journal cannot contain multiple opinions")
            if rows:
                old = rows[0]
                verify_receipt(*inputs, old)
                if old["assessment"] != outcome:
                    raise InvalidWorld("later ruling cannot rewrite already-signed disposition")
                result = {"status": "DUPLICATE_UNCHANGED", "receipt": old}
            else:
                signed = make_receipt(outcome, recorder)
                db.execute("INSERT INTO local_precedence_receipt VALUES(?,?,?)", (
                    0, digest(policy),
                    json.dumps(signed, sort_keys=True, separators=(",", ":")),
                ))
                result = {"status": "SIGNED_PRECEDENCE_REVIEW_HOLD", "receipt": signed}
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return result


def build_fixture():
    tmp, prior, p016, root016, manifest, roster017, root017, old, later, restore, keys = fixture018()
    common = (prior, p016, root016, manifest, roster017, root017)
    west_old = make_017_snapshot(*common, "west", keys["017-west"], None, now=1250)
    east_old = make_017_snapshot(*common, "east", keys["017-east"], old, now=1250)
    west = make_view(*common, west_old, [later], keys["017-west"])
    east = make_view(*common, east_old, [restore], keys["017-east"])
    roles = {}
    for name in ("019-local-trust-root", "019-epoch-witness",
                 "019-referee", "019-owner-selector", "019-neutral-recorder"):
        roles[name] = IdentityKey.load_or_create(Path(tmp.name) / (name + ".pem"))
    keys.update(roles)
    policy = make_policy(*common, west, east,
                         roles["019-local-trust-root"], roles["019-epoch-witness"],
                         roles["019-referee"], roles["019-owner-selector"],
                         roles["019-neutral-recorder"])
    source_documents = signed_events(prior, p016, roster017, west, east)
    documents = [source_documents[name]["document"] for name in sorted(source_documents)]
    certificates = [make_epoch(policy, doc, roles["019-epoch-witness"], epoch=i+1)
                    for i, doc in enumerate(documents)]
    summary = verify_epochs(policy, source_documents, certificates)
    choice = make_referee(policy, certificates, roles["019-referee"],
                          action="SELECT", selected=summary["winner"])
    consent = make_owner(policy, choice, roles["019-owner-selector"],
                         action="SELECT", selected=summary["winner"])
    return tmp, (*common, west, east, policy, roles["019-local-trust-root"].public_jwk(),
                 certificates, choice, consent), keys


def demo():
    tmp, sources, keys = build_fixture()
    try:
        unruled = assess(*sources[:-2], None, None, now=1350)
        refused = make_referee(sources[8], sources[10], keys["019-referee"],
                               action="DECLINE")
        declined = assess(*sources[:-2], refused, None, now=1350)
        certificates = list(sources[10])
        # Authenticate a genuine but incompatible second epoch assignment:
        second_doc_name = certificates[1]["source_event_digest"]
        documents = signed_events(sources[0], sources[1], sources[4],
                                  sources[6], sources[7])
        collision = make_epoch(sources[8], documents[second_doc_name]["document"],
                               keys["019-epoch-witness"],
                               epoch=certificates[0]["source_epoch"])
        conflict = assess(*sources[:10], certificates + [collision],
                          sources[11], sources[12], now=1350)
        selected = assess(*sources, now=1350)
        path = Path(tmp.name) / "019-local-receipt.sqlite"
        written = record_once(path, *sources, keys["019-neutral-recorder"], now=1350)
        cold = verify_receipt(*sources, written["receipt"])
        return {
            "no_referee": unruled["decision"],
            "signed_referee_declined": declined["decision"],
            "independently_signed_epoch_collision": conflict["decision"],
            "referee_and_separate_owner_consented": selected["decision"],
            "old_source_fork_retained": (
                cold["source_history_digest_set"] == selected["source_history_digest_set"]
            ),
            "owner_local_receipt_durable": len(read_receipts(path)) == 1,
            "cold_public_receipt_valid": cold["decision"] == BOUNDED,
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
OTHER_NAMES = (
    "custody-policy", "custody-root", "holder-manifest",
    "roster", "roster-root", "local-view", "remote-view",
    "precedence-policy", "precedence-root", "epoch-certificates",
    "referee-statement", "owner-selection", "receipt",
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "record", "verify"))
    for key in PRIOR_NAMES + OTHER_NAMES + ("neutral-private-key", "neutral-db"):
        parser.add_argument("--" + key, type=Path)
    parser.add_argument("--now", type=int)
    options = parser.parse_args()
    try:
        if options.command == "demo":
            output = demo()
        else:
            required = PRIOR_NAMES + OTHER_NAMES[:10]
            if any(getattr(options, n.replace("-", "_")) is None for n in required):
                parser.error("full 001–018 independent public evidence and 019 source epoch certificates required")
            sources = [load(getattr(options, k.replace("-", "_")))
                       for k in PRIOR_NAMES + OTHER_NAMES[:10]]
            choice = load(options.referee_statement) if options.referee_statement else None
            owner = load(options.owner_selection) if options.owner_selection else None
            if options.command == "assess":
                if options.now is None:
                    parser.error("assess requires --now")
                output = assess(*sources, choice, owner, now=options.now)
            elif options.command == "record":
                if not options.neutral_private_key or not options.neutral_db or options.now is None:
                    parser.error("record requires already provisioned local signer, journal and --now")
                if not options.neutral_private_key.is_file():
                    parser.error("incoming source may not silently provision a neutral signing identity")
                signer = IdentityKey.load_or_create(options.neutral_private_key)
                output = record_once(options.neutral_db, *sources, choice, owner,
                                     signer, now=options.now)
            else:
                if not options.receipt:
                    parser.error("verify requires public signed --receipt")
                result = verify_receipt(*sources, choice, owner, load(options.receipt))
                output = {"verified": True, "decision": result["decision"]}
    except (InvalidWorld, IdentityProfileError, KeyError, TypeError,
            ValueError, OSError, sqlite3.Error) as e:
        parser.error(str(e))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
