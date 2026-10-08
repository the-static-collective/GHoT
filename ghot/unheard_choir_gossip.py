#!/usr/bin/env python3
"""UNHEARD CHOIR 010 — The Unseen Fork.

Two separately keyed observers store signed *publication observations* in
owner-local SQLite journals. Each observer first accepts a different, internally
valid 009 log view. A challenge/policy-bound exchange of signed observation
packages reveals incompatible co-witnessed heads. Neither site receives
authority to change or delete the other's record. Simulated evidence only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_timestamp import (
    assess as assess_009, append_entries, build_fixture_for_tests,
    make_checkpoint, verify_policy as verify_009_policy,
)
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk,
    particular_for_public_key, verify_p256,
)

ROSTER_SCHEMA = "ghot.unheard-choir-010-gossip-roster/v0"
RECEIPT_SCHEMA = "ghot.unheard-choir-010-local-observation/v0"
PACKAGE_SCHEMA = "ghot.unheard-choir-010-gossip-envelope/v0"
ASSESS_SCHEMA = "ghot.unheard-choir-010-cross-site-assessment/v0"
RD = b"GHOT-CHOIR-010-ROSTER-v0|"
OD = b"GHOT-CHOIR-010-OBSERVATION-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-010-observer-genesis/v0"})
SITES = ("west", "east")


def exact(obj: Any, keys: Any, what: str):
    if type(obj) is not dict or set(obj) != set(keys):
        raise InvalidWorld(f"{what}: unknown or missing fields")


def jwk(value: Any):
    try:
        return normalize_public_jwk(value)
    except (IdentityProfileError, ValueError, TypeError) as exc:
        raise InvalidWorld("unusable P-256 key") from exc


def key_id(value: Any):
    return particular_for_public_key(jwk(value))


def sign(key: IdentityKey, body: dict, domain: bytes):
    return key.sign(domain + jcs_bytes(body))


def authenticate(body: dict, signature: Any, key: dict, domain: bytes, label: str):
    if type(signature) is not str or not verify_p256(jwk(key), domain + jcs_bytes(body), signature):
        raise InvalidWorld(f"{label}: signature not valid under pinned key")


def all_prior_keys(inputs: list):
    roster, pins, manifest, audit_policy, audit_root, log_policy, log_root = (
        inputs[1], inputs[7], inputs[11], inputs[13], inputs[16],
        inputs[17], inputs[18],
    )
    keys = [roster["owner_public_key"], audit_root, log_root,
            log_policy["sequencer_public_key"]]
    keys += [roster["actors"][r] for r in ("source", "observer-east", "observer-west")]
    keys += [audit_policy["auditors"][r] for r in ("primary", "secondary")]
    keys += list(log_policy["witnesses"].values())
    keys += [entry["controller_public_key"] for entry in manifest["entries"]]
    for channel in ("primary", "secondary"):
        keys += [pins["channels"][channel]["instrument_public_key"],
                 pins["channels"][channel]["custodian_public_key"]]
    return keys


def make_roster(inputs: list, root: IdentityKey, site_keys: dict[str, IdentityKey],
                *, epoch: int = 1):
    if (set(site_keys) != set(SITES) or type(epoch) is not int or
        not 0 <= epoch <= 999999):
        raise InvalidWorld("two distinct pinned observation sites required")
    keys = all_prior_keys(inputs) + [root.public_jwk()]
    keys += [site_keys[s].public_jwk() for s in SITES]
    if len({key_id(k) for k in keys}) != len(keys):
        raise InvalidWorld("gossip root or observers share an inherited signing key")
    if len(inputs) != 21:
        raise InvalidWorld("010 binds exactly one 009 input view")
    body = {
        "schema": ROSTER_SCHEMA, "scope": "SIMULATED_GOSSIP_ONLY",
        "008_cut": digest({"parent": inputs[0]["proposal_digest"],
                           "challenge": digest(inputs[2]),
                           "manifest": digest(inputs[11]),
                           "audit_policy": digest(inputs[13])}),
        "009_policy_digest": digest(inputs[17]),
        "epoch": epoch,
        "sites": {site: site_keys[site].public_jwk() for site in SITES},
    }
    return {**body, "signature": sign(root, body, RD)}


def check_roster(inputs: list, roster: Any, external_root: Any):
    exact(roster, ("schema", "scope", "008_cut", "009_policy_digest",
                   "epoch", "sites", "signature"), "gossip roster")
    exact(roster["sites"], SITES, "site identities")
    if (roster["schema"] != ROSTER_SCHEMA or
        roster["scope"] != "SIMULATED_GOSSIP_ONLY" or
        type(roster["epoch"]) is not int or
        not 0 <= roster["epoch"] <= 999999 or
        roster["009_policy_digest"] != digest(inputs[17]) or
        roster["008_cut"] != digest({
            "parent": inputs[0]["proposal_digest"],
            "challenge": digest(inputs[2]),
            "manifest": digest(inputs[11]),
            "audit_policy": digest(inputs[13]),
        })):
        raise InvalidWorld("gossip pinset not bound to current 008/009 cut")
    keys = all_prior_keys(inputs) + [external_root]
    keys += [roster["sites"][site] for site in SITES]
    if len({key_id(k) for k in keys}) != len(keys):
        raise InvalidWorld("gossip keys collide with inherited signers")
    body = {k: v for k, v in roster.items() if k != "signature"}
    authenticate(body, roster["signature"], external_root, RD, "gossip trust root")


def check_view(inputs: list, *, now: int):
    if len(inputs) != 21:
        raise InvalidWorld("site view must include all 009 source inputs")
    output = assess_009(*inputs, now=now)
    if output["decision"] != "REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED":
        raise InvalidWorld("site may only record a fully authenticated 009 REVIEW view")
    if len(inputs[20]) != 1:
        raise InvalidWorld("one co-witnessed checkpoint per isolated site view")
    checkpoint = inputs[20][0]
    if checkpoint["size"] != len(inputs[19]) or checkpoint["head"] != inputs[19][-1]["head"]:
        raise InvalidWorld("observation checkpoint must authenticate the supplied full tip")
    return output, checkpoint


def signed_observation(inputs: list, roster: dict, site: str,
                       private: IdentityKey, checkpoint: dict,
                       assessment: dict, *, index: int, previous: str):
    if site not in SITES or jwk(private.public_jwk()) != jwk(roster["sites"][site]):
        raise InvalidWorld("observation signer does not own pinned site identity")
    if type(index) is not int or index < 0:
        raise InvalidWorld("invalid monotonic local observation index")
    body = {
        "schema": RECEIPT_SCHEMA, "scope": "LOCAL_ATTESTATION_NO_EFFECT",
        "roster_digest": digest(roster), "site": site,
        "local_index": index, "previous_receipt_digest": previous,
        "checkpoint_digest": digest(checkpoint),
        "checkpoint_size": checkpoint["size"],
        "checkpoint_head": checkpoint["head"],
        "log_entries_digest": digest(inputs[19]),
        "009_assessment_digest": assessment["receipt_digest"],
        "009_decision": assessment["decision"],
    }
    return {**body, "signature": sign(private, body, OD)}


def verify_observations(observations: Any, roster: dict, site: str):
    if type(observations) is not list or not 1 <= len(observations) <= 64:
        raise InvalidWorld("bounded nonempty local signed observation history required")
    previous = GENESIS
    for i, receipt in enumerate(observations):
        exact(receipt, ("schema", "scope", "roster_digest", "site", "local_index",
                        "previous_receipt_digest", "checkpoint_digest",
                        "checkpoint_size", "checkpoint_head", "log_entries_digest",
                        "009_assessment_digest", "009_decision", "signature"),
              "observation receipt")
        if (receipt["schema"] != RECEIPT_SCHEMA or
            receipt["scope"] != "LOCAL_ATTESTATION_NO_EFFECT" or
            receipt["roster_digest"] != digest(roster) or
            receipt["site"] != site or
            type(receipt["local_index"]) is not int or
            receipt["local_index"] != i or
            receipt["previous_receipt_digest"] != previous or
            receipt["009_decision"] != "REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED"):
            raise InvalidWorld("local observation receipt chain is broken")
        body = {k: v for k, v in receipt.items() if k != "signature"}
        authenticate(body, receipt["signature"], roster["sites"][site], OD,
                     "local observation")
        previous = digest(receipt)


def init_db(db: sqlite3.Connection):
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS observations (
                site TEXT NOT NULL,
                local_index INTEGER NOT NULL,
                checkpoint_digest TEXT NOT NULL,
                signed_receipt TEXT NOT NULL,
                PRIMARY KEY(site, local_index),
                UNIQUE(site, checkpoint_digest)
                )""")


def read_local(db_path: Path, site: str):
    with sqlite3.connect(str(db_path)) as db:
        init_db(db)
        rows = db.execute("SELECT signed_receipt FROM observations WHERE site=? ORDER BY local_index",
                          (site,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def observe_once(db_path: Path, inputs: list, roster: dict, external_root: dict,
                 site: str, private: IdentityKey, *, now: int):
    check_roster(inputs, roster, external_root)
    report, checkpoint = check_view(inputs, now=now)
    if site not in SITES:
        raise InvalidWorld("unrecognized local store")
    with sqlite3.connect(str(db_path), timeout=8, isolation_level=None) as db:
        init_db(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            existing = [json.loads(row[0]) for row in db.execute(
                "SELECT signed_receipt FROM observations WHERE site=? ORDER BY local_index",
                (site,)).fetchall()]
            if existing:
                verify_observations(existing, roster, site)
            if any(receipt["checkpoint_digest"] == digest(checkpoint) for receipt in existing):
                raise InvalidWorld("same checkpoint cannot be recorded twice at one site")
            if len(existing) >= 64:
                raise InvalidWorld("local record exceeds bounded capacity")
            predecessor = digest(existing[-1]) if existing else GENESIS
            observation = signed_observation(inputs, roster, site, private,
                                              checkpoint, report, index=len(existing),
                                              previous=predecessor)
            db.execute("INSERT INTO observations VALUES (?,?,?,?)",
                       (site, observation["local_index"], digest(checkpoint),
                        json.dumps(observation, sort_keys=True, separators=(",", ":"))))
            db.execute("COMMIT")
            return observation
        except BaseException:
            db.execute("ROLLBACK")
            raise


def make_package(inputs: list, roster: dict, site: str,
                 db_path: Path):
    observations = read_local(db_path, site)
    if not observations:
        raise InvalidWorld("cannot gossip an unobserved checkpoint")
    return {
        "schema": PACKAGE_SCHEMA,
        "scope": "PUBLIC_SIGNED_EVIDENCE_ONLY",
        "site": site, "roster_digest": digest(roster),
        "log_entries": inputs[19],
        "checkpoints": inputs[20],
        "observations": observations,
    }


def verify_package(common_inputs: list, policy: dict, log_root: dict,
                   roster: dict, site: str, package: Any, *, now: int):
    exact(package, ("schema", "scope", "site", "roster_digest",
                    "log_entries", "checkpoints", "observations"), "gossip envelope")
    if (site not in SITES or package["schema"] != PACKAGE_SCHEMA or
        package["scope"] != "PUBLIC_SIGNED_EVIDENCE_ONLY" or
        package["site"] != site or package["roster_digest"] != digest(roster)):
        raise InvalidWorld("envelope identity not pinned to observation role")
    view = list(common_inputs) + [policy, log_root,
                                   package["log_entries"], package["checkpoints"]]
    if len(view) != 21:
        raise InvalidWorld("required full 008 public ancestry absent")
    check_roster(view, roster, common_inputs[0]["_unused"] if False else _ROOT_NOT_USED) if False else None
    verified, checkpoint = check_view(view, now=now)
    verify_observations(package["observations"], roster, site)
    latest = package["observations"][-1]
    if (latest["checkpoint_digest"] != digest(checkpoint) or
        latest["checkpoint_head"] != checkpoint["head"] or
        latest["checkpoint_size"] != checkpoint["size"] or
        latest["log_entries_digest"] != digest(package["log_entries"]) or
        latest["009_assessment_digest"] != verified["receipt_digest"]):
        raise InvalidWorld("gossip tip does not match signed local observation")
    return checkpoint


def compare_views(common_inputs: list, policy: dict, log_root: dict,
                  roster: dict, external_root: dict,
                  local_package: dict, peer_package: dict | None,
                  *, now: int):
    local_site = local_package.get("site") if type(local_package) is dict else None
    if local_site not in SITES:
        raise InvalidWorld("invalid invoking observer")
    check_roster(common_inputs + [policy, log_root, [], []], roster, external_root)
    local_tip = verify_package(common_inputs, policy, log_root, roster,
                               local_site, local_package, now=now)
    fork = False
    peer_tip = None
    if peer_package is not None:
        peer_site = peer_package.get("site") if type(peer_package) is dict else None
        if peer_site not in SITES or peer_site == local_site:
            raise InvalidWorld("peer must be differently pinned observer")
        peer_tip = verify_package(common_inputs, policy, log_root, roster,
                                  peer_site, peer_package, now=now)
        fork = (
            local_tip["size"] == peer_tip["size"]
            and local_tip["head"] != peer_tip["head"]
            and local_tip["epoch"] == peer_tip["epoch"]
            and local_tip["policy_digest"] == peer_tip["policy_digest"]
        )
        if fork:
            decision = "HOLD_GOSSIP_REVEALS_UNSEEN_FORK"
        elif local_tip["head"] == peer_tip["head"] and local_tip["size"] == peer_tip["size"]:
            decision = "REVIEW_MATCHING_WITNESSED_LOGS_NOT_ADMITTED"
        else:
            decision = "HOLD_PEER_LOG_CONSISTENCY_NOT_PROVEN"
    else:
        decision = "HOLD_NO_PEER_GOSSIP_EVIDENCE"
    report = {
        "schema": ASSESS_SCHEMA,
        "008_cut": roster["008_cut"],
        "009_policy_digest": digest(policy),
        "roster_digest": digest(roster),
        "local_site": local_site,
        "local_tip": {"size": local_tip["size"], "head": local_tip["head"],
                       "checkpoint_digest": digest(local_tip)},
        "peer_site": peer_package["site"] if peer_package is not None else None,
        "peer_tip": {"size": peer_tip["size"], "head": peer_tip["head"],
                      "checkpoint_digest": digest(peer_tip)} if peer_tip else None,
        "same_epoch_same_size_conflicting_heads": fork,
        "decision": decision,
        "signature_authenticates_publication_not_truth": True,
        "gossip_received_by_all_peers_proven": False,
        "sqlite_is_immutable_external_ledger": False,
        "independent_human_witnesses_proven": False,
        "no_external_execution": True,
        "native_relatte_admission": False,
        "authority": "NONE", "effects": [],
    }
    report["assessment_digest"] = digest(report)
    return report


def cold_verify(common_inputs: list, policy: dict, log_root: dict,
                roster: dict, external_root: dict, local: dict, peer: dict | None,
                report: Any, *, now: int):
    if type(report) is not dict:
        return False
    try:
        return canonical(report) == canonical(compare_views(
            common_inputs, policy, log_root, roster, external_root,
            local, peer, now=now))
    except (ValueError, TypeError, KeyError, IdentityProfileError, sqlite3.Error):
        return False


def fork_fixture():
    """Two valid 009 log histories. Neither site has received the other's tip."""
    tmp, base, keys = build_fixture_for_tests(earlier_audit_matches=True,
                                              log_order_lie=False)
    folder = Path(tmp.name)
    for name in ("gossip-root", "gossip-west", "gossip-east"):
        keys[name] = IdentityKey.load_or_create(folder / (name + ".pem"))
    west = list(base)
    east = list(base)
    submissions = [e["submission"] for e in base[19]]
    alternate_entries = append_entries(submissions[:4] + [submissions[5], submissions[4]])
    east[19] = alternate_entries
    east[20] = [make_checkpoint(
        base[17], len(alternate_entries), alternate_entries[-1]["head"],
        keys["log-sequencer"], keys["log-witness-a"], keys["log-witness-b"],
    )]
    roster = make_roster(west, keys["gossip-root"],
                         {"west": keys["gossip-west"], "east": keys["gossip-east"]})
    return tmp, west, east, keys, roster


def demo():
    tmp, west, east, keys, roster = fork_fixture()
    try:
        western = Path(tmp.name) / "west.sqlite"
        eastern = Path(tmp.name) / "east.sqlite"
        root = keys["gossip-root"].public_jwk()
        observe_once(western, west, roster, root, "west", keys["gossip-west"], now=1001)
        observe_once(eastern, east, roster, root, "east", keys["gossip-east"], now=1001)
        pwest = make_package(west, roster, "west", western)
        peast = make_package(east, roster, "east", eastern)
        common = west[:17]
        alone = compare_views(common, west[17], west[18], roster, root,
                              pwest, None, now=1001)
        after = compare_views(common, west[17], west[18], roster, root,
                              pwest, peast, now=1001)
        return {
            "isolated_west_009": check_view(west, now=1001)[0]["decision"],
            "isolated_east_009": check_view(east, now=1001)[0]["decision"],
            "before_gossip": alone["decision"],
            "after_gossip": after["decision"],
            "both_checkpoint_signatures_authentic": True,
            "same_size": after["local_tip"]["size"] == after["peer_tip"]["size"],
            "different_heads": after["same_epoch_same_size_conflicting_heads"],
            "local_west_record_retained": len(read_local(western, "west")) == 1,
            "local_east_record_retained": len(read_local(eastern, "east")) == 1,
            "cold_replay_verified": cold_verify(common, west[17], west[18], roster,
                                                 root, pwest, peast, after, now=1001),
            "native_execution": bool(after["effects"]),
        }
    finally:
        tmp.cleanup()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "compare", "verify"))
    names = ("parent", "roster", "challenge", "statements",
             "primary_anchor", "primary_precommit", "primary_measurement", "pinset",
             "primary_custody", "secondary_custody", "secondary_measurement",
             "manifest", "attestations", "audit_policy", "audit_commits",
             "audit_reports", "trusted_root")
    for name in names + ("log_policy", "log_root", "gossip_roster",
                         "gossip_root", "local_package", "peer_package", "receipt"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path)
    parser.add_argument("--now", type=int)
    opts = parser.parse_args()
    try:
        if opts.command == "demo":
            output = demo()
        else:
            needed = names + ("log_policy", "log_root", "gossip_roster",
                              "gossip_root", "local_package")
            if any(getattr(opts, x) is None for x in needed) or opts.now is None:
                parser.error("compare/verify need all 008 ancestor files and 010 public evidence")
            common = [read(getattr(opts, n)) for n in names]
            tail = [read(getattr(opts, n)) for n in ("log_policy", "log_root", "gossip_roster", "gossip_root", "local_package")]
            peer = read(opts.peer_package) if opts.peer_package else None
            if opts.command == "compare":
                output = compare_views(common, tail[0], tail[1], tail[2], tail[3], tail[4],
                                       peer, now=opts.now)
            else:
                if opts.receipt is None:
                    parser.error("verify also requires --receipt")
                output = {"verified": cold_verify(common, tail[0], tail[1], tail[2], tail[3], tail[4],
                                                  peer, read(opts.receipt), now=opts.now)}
    except (ValueError, KeyError, OSError, TypeError, IdentityProfileError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if opts.command != "verify" or output["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
