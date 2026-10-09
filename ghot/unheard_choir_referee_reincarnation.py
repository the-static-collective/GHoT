#!/usr/bin/env python3
"""UNHEARD CHOIR 020 — The Referee Who Died.

An authentic 019 referee decision survives retirement as history, but may not
authorize a new case. An independently pinned new policy root admits a distinct
epoch-2 referee; a distinct owner signs fresh case-specific consent. All
dispositions remain simulated local HOLD without native reLATTE effects.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, digest
from unheard_choir_referee import (
    build_fixture as fixture019, make_receipt as make_019_receipt,
    assess as assess019, verify_receipt as verify_019_receipt, witness_keys
)
from unheard_choir_successors import exact, distinct, public, sign, authenticate
from unheard_choir_third_party import check_clock, check_window
from relatte_identity import IdentityKey, IdentityProfileError

POLICY = "ghot.unheard-choir-020-local-referee-reconstitution/v0"
RETIREMENT = "ghot.unheard-choir-020-referee-retirement/v0"
FRESH = "ghot.unheard-choir-020-new-referee-choice/v0"
OWNER = "ghot.unheard-choir-020-new-case-owner-consent/v0"
ASSESSMENT = "ghot.unheard-choir-020-fresh-case-disposition/v0"
RECEIPT = "ghot.unheard-choir-020-neutral-hold-receipt/v0"
PD = b"GHOT-CHOIR-020-POLICY-v0|"
DD = b"GHOT-CHOIR-020-RETIREMENT-v0|"
FD = b"GHOT-CHOIR-020-FRESH-REFEREE-v0|"
OD = b"GHOT-CHOIR-020-FRESH-OWNER-v0|"
RD = b"GHOT-CHOIR-020-HOLD-RECEIPT-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-020-genesis/v0"})
CASE = "CHOIR-020-NEW-ARCHIVE-REVIEW-001"
SCOPE = "NEW_CASE_HISTORICAL_ARCHIVE_REVIEW_ONLY"
NO_RETIRE = "HOLD_NEW_REFEREE_EPOCH_NOT_ADMITTED"
NO_REFEREE = "HOLD_NEW_CASE_REFEREE_MISSING"
REFUSED = "HOLD_NEW_REFEREE_DECLINED_OR_EXPIRED"
NO_OWNER = "HOLD_NEW_CASE_OWNER_CONSENT_MISSING"
OWNER_REFUSED = "HOLD_NEW_CASE_OWNER_REFUSED_OR_EXPIRED"
BOUNDED = "HOLD_NEW_CASE_ARCHIVAL_REVIEW_ONLY_NOT_ADMITTED"


def historical(sources, receipt):
    if type(sources) not in (tuple, list) or len(sources) != 13:
        raise InvalidWorld("020 requires exactly thirteen signed 019 ancestor slots")
    return verify_019_receipt(*sources, receipt)


def all_old_keys(sources):
    prior, p016, root016, manifest, roster, root017 = sources[:6]
    old = sources[8]
    return witness_keys(prior, p016, root016, roster, root017) + [
        sources[9], old["pinned_epoch_witness"], old["pinned_referee"],
        old["pinned_owner_selector"], old["pinned_neutral_recorder"],
    ]


def make_policy(sources, receipt, root, referee, owner, recorder):
    past = historical(sources, receipt)
    if past["decision"] != "HOLD_SCOPED_ARCHIVAL_REVIEW_SELECTED_NOT_ADMITTED":
        raise InvalidWorld("historical 019 signed bounded HOLD required")
    keys = all_old_keys(sources) + [x.public_jwk() for x in (root, referee, owner, recorder)]
    if not distinct(keys):
        raise InvalidWorld("new root, referee, owner and neutral signer must be independent of old keys")
    old = sources[8]
    body = {
        "schema": POLICY, "scope": SCOPE, "new_case_id": CASE,
        "new_case_question_digest": digest({"case": CASE, "question": "Review another occurrence of the signed 018 source fork"}),
        "historical_019_receipt_digest": digest(receipt),
        "historical_019_policy_digest": digest(old),
        "old_referee_public_key": old["pinned_referee"],
        "old_referee_epoch": 1, "new_referee_epoch": 2,
        "new_referee_public_key": referee.public_jwk(),
        "new_owner_public_key": owner.public_jwk(),
        "neutral_recorder_public_key": recorder.public_jwk(),
        "allowed_event_digests": list(old["event_digest_set"]),
        "native_source_grant": False,
    }
    return {**body, "signature": sign(root, body, PD)}


def verify_policy(sources, receipt, policy, pinned_root):
    past = historical(sources, receipt)
    exact(policy, ("schema", "scope", "new_case_id", "new_case_question_digest",
                   "historical_019_receipt_digest", "historical_019_policy_digest",
                   "old_referee_public_key", "old_referee_epoch",
                   "new_referee_epoch", "new_referee_public_key",
                   "new_owner_public_key", "neutral_recorder_public_key",
                   "allowed_event_digests", "native_source_grant", "signature"),
          "020 independently pinned replacement policy")
    old = sources[8]
    if (policy["schema"] != POLICY or policy["scope"] != SCOPE
        or policy["new_case_id"] != CASE
        or policy["new_case_question_digest"] != digest({"case": CASE, "question": "Review another occurrence of the signed 018 source fork"})
        or policy["historical_019_receipt_digest"] != digest(receipt)
        or policy["historical_019_policy_digest"] != digest(old)
        or public(policy["old_referee_public_key"]) != public(old["pinned_referee"])
        or type(policy["old_referee_epoch"]) is not int or policy["old_referee_epoch"] != 1
        or type(policy["new_referee_epoch"]) is not int or policy["new_referee_epoch"] != 2
        or policy["allowed_event_digests"] != old["event_digest_set"]
        or policy["native_source_grant"] is not False
        or past["decision"] != "HOLD_SCOPED_ARCHIVAL_REVIEW_SELECTED_NOT_ADMITTED"):
        raise InvalidWorld("fresh policy cannot launder old source authority")
    if not distinct(all_old_keys(sources) + [
        pinned_root, policy["new_referee_public_key"],
        policy["new_owner_public_key"], policy["neutral_recorder_public_key"],
    ]):
        raise InvalidWorld("new signer collided with inherited signature key")
    authenticate({k: v for k, v in policy.items() if k != "signature"},
                 policy["signature"], pinned_root, PD, "independently pinned 020 root")


def make_retirement(policy, root):
    body = {
        "schema": RETIREMENT, "scope": SCOPE, "policy_digest": digest(policy),
        "old_referee_key": policy["old_referee_public_key"],
        "old_epoch": 1, "new_referee_key": policy["new_referee_public_key"],
        "new_epoch": 2, "old_key_status": "RETIRED_FOR_FUTURE_020_CASES",
        "historical_signature_still_valid": True,
        "claims_actual_biological_death": False,
        "transfers_native_authority": False,
    }
    return {**body, "signature": sign(root, body, DD)}


def verify_retirement(policy, pinned_root, retirement):
    exact(retirement, ("schema", "scope", "policy_digest", "old_referee_key",
                       "old_epoch", "new_referee_key", "new_epoch",
                       "old_key_status", "historical_signature_still_valid",
                       "claims_actual_biological_death", "transfers_native_authority",
                       "signature"), "020 signed retirement declaration")
    if (retirement["schema"] != RETIREMENT or retirement["scope"] != SCOPE
        or retirement["policy_digest"] != digest(policy)
        or public(retirement["old_referee_key"]) != public(policy["old_referee_public_key"])
        or type(retirement["old_epoch"]) is not int or retirement["old_epoch"] != 1
        or public(retirement["new_referee_key"]) != public(policy["new_referee_public_key"])
        or type(retirement["new_epoch"]) is not int or retirement["new_epoch"] != 2
        or retirement["old_key_status"] != "RETIRED_FOR_FUTURE_020_CASES"
        or retirement["historical_signature_still_valid"] is not True
        or retirement["claims_actual_biological_death"] is not False
        or retirement["transfers_native_authority"] is not False):
        raise InvalidWorld("retirement statement invented live transfer or erased history")
    authenticate({k: v for k, v in retirement.items() if k != "signature"},
                 retirement["signature"], pinned_root, DD, "independent reconstitution root")


def make_referee(policy, retirement, signer, *, action, selected=None,
                 claimed_at=1400, not_after=5000):
    if public(signer.public_jwk()) != public(policy["new_referee_public_key"]):
        raise InvalidWorld("old referee cannot sign successor's case")
    if action not in ("DECLINE", "SELECT") or (
        action == "DECLINE" and selected is not None
    ) or (action == "SELECT" and selected not in policy["allowed_event_digests"]):
        raise InvalidWorld("fresh referee must select exact permitted source event or decline")
    check_window(claimed_at, not_after, "new case referee")
    body = {
        "schema": FRESH, "scope": SCOPE, "case_id": policy["new_case_id"],
        "policy_digest": digest(policy), "retirement_digest": digest(retirement),
        "referee_epoch": 2, "action": action, "selected_event_digest": selected,
        "simulated_claimed_at": claimed_at, "simulated_not_after": not_after,
        "native_authority": False, "effect_permission": "NONE",
    }
    return {**body, "signature": sign(signer, body, FD)}


def verify_referee(policy, retirement, statement, *, now):
    exact(statement, ("schema", "scope", "case_id", "policy_digest",
                      "retirement_digest", "referee_epoch", "action",
                      "selected_event_digest", "simulated_claimed_at",
                      "simulated_not_after", "native_authority",
                      "effect_permission", "signature"), "020 fresh referee")
    a, selected = statement["action"], statement["selected_event_digest"]
    if (statement["schema"] != FRESH or statement["scope"] != SCOPE
        or statement["case_id"] != policy["new_case_id"]
        or statement["policy_digest"] != digest(policy)
        or statement["retirement_digest"] != digest(retirement)
        or type(statement["referee_epoch"]) is not int or statement["referee_epoch"] != 2
        or a not in ("DECLINE", "SELECT")
        or (a == "DECLINE" and selected is not None)
        or (a == "SELECT" and selected not in policy["allowed_event_digests"])
        or statement["native_authority"] is not False
        or statement["effect_permission"] != "NONE"):
        raise InvalidWorld("020 referee signature attempted stale epoch or wrong case")
    check_window(statement["simulated_claimed_at"], statement["simulated_not_after"], "referee interval")
    authenticate({k: v for k, v in statement.items() if k != "signature"},
                 statement["signature"], policy["new_referee_public_key"],
                 FD, "new epoch-2 case referee")
    return not statement["simulated_claimed_at"] <= now <= statement["simulated_not_after"]


def make_owner(policy, choice, signer, *, action, selected=None,
               claimed_at=1400, not_after=5000):
    if public(signer.public_jwk()) != public(policy["new_owner_public_key"]):
        raise InvalidWorld("new case requires different locally pinned owner")
    if action not in ("REFUSE", "CONSENT") or (
        action == "REFUSE" and selected is not None
    ) or (action == "CONSENT" and selected not in policy["allowed_event_digests"]):
        raise InvalidWorld("owner decision must be explicit and case-bound")
    check_window(claimed_at, not_after, "new case owner")
    body = {
        "schema": OWNER, "scope": SCOPE, "case_id": policy["new_case_id"],
        "policy_digest": digest(policy), "referee_digest": digest(choice),
        "referee_epoch": 2, "action": action, "selected_event_digest": selected,
        "simulated_claimed_at": claimed_at, "simulated_not_after": not_after,
        "native_authority": False, "effect_permission": "NONE",
    }
    return {**body, "signature": sign(signer, body, OD)}


def verify_owner(policy, referee, owner, *, now):
    exact(owner, ("schema", "scope", "case_id", "policy_digest",
                  "referee_digest", "referee_epoch", "action",
                  "selected_event_digest", "simulated_claimed_at",
                  "simulated_not_after", "native_authority",
                  "effect_permission", "signature"), "020 owner-local consent")
    a, selected = owner["action"], owner["selected_event_digest"]
    if (owner["schema"] != OWNER or owner["scope"] != SCOPE
        or owner["case_id"] != policy["new_case_id"]
        or owner["policy_digest"] != digest(policy)
        or owner["referee_digest"] != digest(referee)
        or type(owner["referee_epoch"]) is not int or owner["referee_epoch"] != 2
        or a not in ("REFUSE", "CONSENT")
        or (a == "REFUSE" and selected is not None)
        or (a == "CONSENT" and selected not in policy["allowed_event_digests"])
        or owner["native_authority"] is not False
        or owner["effect_permission"] != "NONE"):
        raise InvalidWorld("owner consent cannot migrate across referee epochs or cases")
    check_window(owner["simulated_claimed_at"], owner["simulated_not_after"], "owner consent interval")
    authenticate({k: v for k, v in owner.items() if k != "signature"},
                 owner["signature"], policy["new_owner_public_key"], OD, "separate case owner")
    return not owner["simulated_claimed_at"] <= now <= owner["simulated_not_after"]


def assess(sources, old_receipt, policy, pinned_root, retirement,
           referee, owner, *, now):
    check_clock(now, "020 local synthetic clock")
    historical(sources, old_receipt)
    verify_policy(sources, old_receipt, policy, pinned_root)
    if retirement is not None:
        verify_retirement(policy, pinned_root, retirement)
    if referee is not None:
        if retirement is None:
            raise InvalidWorld("new referee must have independently signed retirement proof")
        referee_expired = verify_referee(policy, retirement, referee, now=now)
    else:
        referee_expired = False
    if owner is not None:
        if referee is None:
            raise InvalidWorld("owner consent needs a fresh, verified case referee")
        owner_expired = verify_owner(policy, referee, owner, now=now)
    else:
        owner_expired = False
    if retirement is None:
        decision = NO_RETIRE
    elif referee is None:
        decision = NO_REFEREE
    elif referee_expired or referee["action"] == "DECLINE":
        decision = REFUSED
    elif owner is None:
        decision = NO_OWNER
    elif owner_expired or owner["action"] == "REFUSE" or (
        owner["selected_event_digest"] != referee["selected_event_digest"]
    ):
        decision = OWNER_REFUSED
    else:
        decision = BOUNDED
    output = {
        "schema": ASSESSMENT, "scope": SCOPE, "new_case_id": CASE,
        "new_case_question_digest": policy["new_case_question_digest"],
        "historic_019_receipt_digest": digest(old_receipt),
        "historic_019_decision": old_receipt["assessment"]["decision"],
        "old_referee_public_key": policy["old_referee_public_key"],
        "retired_referee_epoch": 1, "new_referee_epoch": 2,
        "retirement_digest": digest(retirement) if retirement else None,
        "fresh_referee_digest": digest(referee) if referee else None,
        "fresh_owner_digest": digest(owner) if owner else None,
        "preserved_source_event_digests": list(policy["allowed_event_digests"]),
        "selected_for_new_archival_question_only": (
            referee["selected_event_digest"] if decision == BOUNDED else None
        ),
        "decision": decision, "historical_signatures_remain_verifiable": True,
        "old_signature_is_current_case_permission": False,
        "new_referee_creates_native_grant": False,
        "native_relatte_receive": False, "native_relatte_admission": False,
        "forwarding_permitted": False, "external_execution": False,
        "authority": "NONE", "effects": [], "simulated_local_clock": now,
    }
    output["assessment_digest"] = digest(output)
    return output


def make_receipt(outcome, signer):
    body = {"schema": RECEIPT, "scope": SCOPE, "index": 0,
            "previous_digest": GENESIS, "assessment": outcome}
    return {**body, "signature": sign(signer, body, RD)}


def verify_receipt(sources, old_receipt, policy, pinned_root, retirement,
                   referee, owner, receipt):
    exact(receipt, ("schema", "scope", "index", "previous_digest",
                    "assessment", "signature"), "020 cold receipt")
    if (receipt["schema"] != RECEIPT or receipt["scope"] != SCOPE
        or type(receipt["index"]) is not int or receipt["index"] != 0
        or receipt["previous_digest"] != GENESIS
        or type(receipt["assessment"]) is not dict):
        raise InvalidWorld("receipt attempted to replace genesis or expand scope")
    result = assess(sources, old_receipt, policy, pinned_root,
                    retirement, referee, owner,
                    now=receipt["assessment"].get("simulated_local_clock"))
    if result != receipt["assessment"]:
        raise InvalidWorld("cold new-case replay disagrees with signed local receipt")
    authenticate({k: v for k, v in receipt.items() if k != "signature"},
                 receipt["signature"], policy["neutral_recorder_public_key"],
                 RD, "new case neutral recorder")
    return result


def init_db(db):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS new_case_receipts(
        idx INTEGER PRIMARY KEY, case_digest TEXT UNIQUE NOT NULL,
        signed_json TEXT NOT NULL
    )""")


def read_receipts(path):
    with sqlite3.connect(str(path)) as db:
        init_db(db)
        return [json.loads(x[0]) for x in db.execute(
            "SELECT signed_json FROM new_case_receipts ORDER BY idx").fetchall()]


def record_once(path, sources, old_receipt, policy, pinned_root, retirement,
                referee, owner, signer, *, now):
    if public(signer.public_jwk()) != public(policy["neutral_recorder_public_key"]):
        raise InvalidWorld("historical referee or holder cannot be new neutral recorder")
    inputs = sources, old_receipt, policy, pinned_root, retirement, referee, owner
    outcome = assess(*inputs, now=now)
    with sqlite3.connect(str(path), isolation_level=None, timeout=10) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = [json.loads(x[0]) for x in db.execute(
                "SELECT signed_json FROM new_case_receipts ORDER BY idx").fetchall()]
            if len(rows) > 1:
                raise InvalidWorld("one case limit exceeded")
            if rows:
                signed = rows[0]
                verify_receipt(*inputs, signed)
                if signed["assessment"] != outcome:
                    raise InvalidWorld("new local ruling must not rewrite earlier signed result")
                status = "DUPLICATE_UNCHANGED"
            else:
                signed = make_receipt(outcome, signer)
                db.execute("INSERT INTO new_case_receipts VALUES(?,?,?)",
                           (0, policy["new_case_question_digest"],
                            json.dumps(signed, sort_keys=True, separators=(",", ":"))))
                status = "SIGNED_FRESH_CASE_HOLD_RECORDED"
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return {"status": status, "receipt": signed}


def build_fixture():
    tmp, sources, keys = fixture019()
    old_receipt = make_019_receipt(assess019(*sources, now=1350),
                                   keys["019-neutral-recorder"])
    for role in ("root", "referee", "owner", "neutral"):
        keys["020-" + role] = IdentityKey.load_or_create(
            Path(tmp.name) / ("020-" + role + ".pem"))
    policy = make_policy(sources, old_receipt, keys["020-root"],
                         keys["020-referee"], keys["020-owner"], keys["020-neutral"])
    retirement = make_retirement(policy, keys["020-root"])
    (Path(tmp.name) / "019-referee.pem").unlink(missing_ok=True)
    winner = sources[11]["selected_event_digest"]
    new_referee = make_referee(policy, retirement, keys["020-referee"],
                               action="SELECT", selected=winner)
    owner = make_owner(policy, new_referee, keys["020-owner"],
                       action="CONSENT", selected=winner)
    return tmp, sources, old_receipt, policy, keys["020-root"].public_jwk(), retirement, new_referee, owner, keys


def demo():
    tmp, sources, old, policy, root, retirement, referee, owner, keys = build_fixture()
    try:
        key_gone = not (Path(tmp.name) / "019-referee.pem").exists()
        verified_old = historical(sources, old)["decision"]
        without_epoch = assess(sources, old, policy, root, None, None, None, now=1500)
        without_referee = assess(sources, old, policy, root, retirement, None, None, now=1500)
        without_owner = assess(sources, old, policy, root, retirement, referee, None, now=1500)
        approved = assess(sources, old, policy, root, retirement, referee, owner, now=1500)
        db = Path(tmp.name) / "020-case.sqlite"
        saved = record_once(db, sources, old, policy, root, retirement,
                            referee, owner, keys["020-neutral"], now=1500)
        cold = verify_receipt(sources, old, policy, root, retirement, referee, owner, saved["receipt"])
        return {
            "old_private_file_deleted_in_fixture": key_gone,
            "old_signed_historical_decision": verified_old,
            "without_reconstitution": without_epoch["decision"],
            "without_fresh_referee": without_referee["decision"],
            "without_fresh_owner": without_owner["decision"],
            "with_fresh_separate_approvals": approved["decision"],
            "historic_receipt_preserved": cold["historic_019_receipt_digest"] == digest(old),
            "old_source_event_set_preserved": cold["preserved_source_event_digests"] == sources[8]["event_digest_set"],
            "public_cold_replay_without_old_private_file": cold["decision"] == BOUNDED,
            "one_neutral_durable_receipt": len(read_receipts(db)) == 1,
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
HISTORIC_NAMES = (
    "custody-policy", "custody-root", "holder-manifest",
    "roster", "roster-root", "local-view", "remote-view",
    "precedence-policy", "precedence-root", "epoch-certificates",
    "historic-referee", "historic-owner",
)
CURRENT_NAMES = ("historic-receipt", "replacement-policy", "replacement-root",
                 "retirement-notice", "fresh-referee", "fresh-owner", "receipt")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "verify"))
    for k in PRIOR_NAMES + HISTORIC_NAMES + CURRENT_NAMES:
        parser.add_argument("--" + k, type=Path)
    opt = parser.parse_args()
    try:
        if opt.command == "demo":
            out = demo()
        else:
            names = PRIOR_NAMES + HISTORIC_NAMES + CURRENT_NAMES
            if any(getattr(opt, n.replace("-", "_")) is None for n in names):
                parser.error("verify requires public 001–020 ancestry and local receipts")
            vals = [load(getattr(opt, n.replace("-", "_"))) for n in names]
            ancestors = (vals[:13], *vals[13:25])
            out = {"verified": True,
                   "decision": verify_receipt(ancestors, *vals[25:])["decision"]}
    except (InvalidWorld, IdentityProfileError, KeyError,
            TypeError, ValueError, sqlite3.Error, OSError) as error:
        parser.error(str(error))
    print(json.dumps(out, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
