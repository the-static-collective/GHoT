#!/usr/bin/env python3
"""010 adversarial tests for isolated journals and cross-store signed gossip."""
from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ghot"))

from unheard_choir import InvalidWorld, digest  # noqa: E402
from unheard_choir_timestamp import append_entries, make_checkpoint  # noqa: E402
from unheard_choir_gossip import (  # noqa: E402
    check_roster, check_view, cold_verify, compare_views, demo, fork_fixture,
    init_db, make_package, make_roster, observe_once, read_local,
    signed_observation, verify_observations,
)


class UnseenForkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.west, cls.east, cls.keys, cls.roster = fork_fixture()
        cls.root = cls.keys["gossip-root"].public_jwk()
        cls.west_db = Path(cls.tmp.name) / "west.sqlite"
        cls.east_db = Path(cls.tmp.name) / "east.sqlite"
        cls.west_receipt = observe_once(
            cls.west_db, cls.west, cls.roster, cls.root, "west",
            cls.keys["gossip-west"], now=1001)
        cls.east_receipt = observe_once(
            cls.east_db, cls.east, cls.roster, cls.root, "east",
            cls.keys["gossip-east"], now=1001)
        cls.pwest = make_package(cls.west, cls.roster, "west", cls.west_db)
        cls.peast = make_package(cls.east, cls.roster, "east", cls.east_db)
        cls.common = cls.west[:17]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def compare(self, local=None, peer=None, *, roster=None, root=None):
        return compare_views(
            self.common, self.west[17], self.west[18],
            self.roster if roster is None else roster,
            self.root if root is None else root,
            self.pwest if local is None else local,
            self.peast if peer is None else peer,
            now=1001,
        )

    def test_isolated_sites_both_have_valid_witnessed_009_histories(self):
        a, ca = check_view(self.west, now=1001)
        b, cb = check_view(self.east, now=1001)
        self.assertEqual(a["decision"], "REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED")
        self.assertEqual(b["decision"], "REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED")
        self.assertEqual(ca["size"], cb["size"])
        self.assertNotEqual(ca["head"], cb["head"])
        self.assertEqual(ca["epoch"], cb["epoch"])
        self.assertEqual(ca["policy_digest"], cb["policy_digest"])

    def test_before_gossip_fork_is_not_known(self):
        r = compare_views(
            self.common, self.west[17], self.west[18],
            self.roster, self.root, self.pwest, None, now=1001)
        self.assertEqual(r["decision"], "HOLD_NO_PEER_GOSSIP_EVIDENCE")
        self.assertFalse(r["same_epoch_same_size_conflicting_heads"])

    def test_cross_site_gossip_exposes_signed_same_size_fork(self):
        r = self.compare()
        self.assertEqual(r["decision"], "HOLD_GOSSIP_REVEALS_UNSEEN_FORK")
        self.assertTrue(r["same_epoch_same_size_conflicting_heads"])
        self.assertEqual(r["local_tip"]["size"], 6)
        self.assertEqual(r["peer_tip"]["size"], 6)
        self.assertNotEqual(r["local_tip"]["head"], r["peer_tip"]["head"])

    def test_gossip_symmetric_both_sites_can_independently_verify_fork(self):
        r = self.compare(local=self.peast, peer=self.pwest)
        self.assertEqual(r["decision"], "HOLD_GOSSIP_REVEALS_UNSEEN_FORK")
        self.assertEqual(r["local_site"], "east")

    def test_matching_view_gossiped_never_admitted_as_truth(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "new-east.sqlite"
            observe_once(file, self.west, self.roster, self.root,
                         "east", self.keys["gossip-east"], now=1001)
            east_copy = make_package(self.west, self.roster, "east", file)
            r = self.compare(peer=east_copy)
            self.assertEqual(r["decision"], "REVIEW_MATCHING_WITNESSED_LOGS_NOT_ADMITTED")
            self.assertFalse(r["same_epoch_same_size_conflicting_heads"])
            self.assertEqual(r["effects"], [])

    def test_peers_do_not_write_to_each_others_sqlite_stores(self):
        self.compare()
        self.assertEqual(len(read_local(self.west_db, "west")), 1)
        self.assertEqual(len(read_local(self.east_db, "east")), 1)
        self.assertEqual(read_local(self.west_db, "west")[0], self.west_receipt)
        self.assertEqual(read_local(self.east_db, "east")[0], self.east_receipt)

    def test_durable_sqlite_reopens_with_safely_signed_history(self):
        current = read_local(self.west_db, "west")
        self.assertEqual(len(current), 1)
        verify_observations(current, self.roster, "west")
        self.assertEqual(current[0]["previous_receipt_digest"],
                         digest({"domain": "ghot.unheard-choir-010-observer-genesis/v0"}))

    def test_duplicate_checkpoint_cannot_insert_twice(self):
        with self.assertRaisesRegex(InvalidWorld, "cannot be recorded twice"):
            observe_once(self.west_db, self.west, self.roster, self.root,
                         "west", self.keys["gossip-west"], now=1001)
        self.assertEqual(len(read_local(self.west_db, "west")), 1)

    def test_distinct_second_view_links_previous_locally_durable_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "observation.sqlite"
            first = observe_once(db, self.west, self.roster, self.root,
                                 "west", self.keys["gossip-west"], now=1001)
            second = observe_once(db, self.east, self.roster, self.root,
                                  "west", self.keys["gossip-west"], now=1001)
            self.assertEqual(second["local_index"], 1)
            self.assertEqual(second["previous_receipt_digest"], digest(first))
            self.assertNotEqual(first["checkpoint_head"], second["checkpoint_head"])
            verify_observations(read_local(db, "west"), self.roster, "west")
            package = make_package(self.east, self.roster, "west", db)
            # The tip and prior observation are both authenticated.
            result = compare_views(self.common, self.west[17], self.west[18],
                                   self.roster, self.root, package, self.peast,
                                   now=1001)
            self.assertEqual(result["decision"], "REVIEW_MATCHING_WITNESSED_LOGS_NOT_ADMITTED")

    def test_bad_gossip_root_signature_refused(self):
        x = copy.deepcopy(self.roster)
        x["signature"] = "bogus"
        with self.assertRaises(InvalidWorld):
            self.compare(roster=x)

    def test_pretend_owner_is_independent_gossip_root_refused(self):
        with self.assertRaises(InvalidWorld):
            self.compare(root=self.keys["owner"].public_jwk())

    def test_duplicate_observer_keys_refused(self):
        r = copy.deepcopy(self.roster)
        r["sites"]["east"] = r["sites"]["west"]
        with self.assertRaises(InvalidWorld):
            self.compare(roster=r)

    def test_existing_009_witness_cannot_be_gossip_observer(self):
        r = copy.deepcopy(self.roster)
        r["sites"]["east"] = self.keys["log-witness-a"].public_jwk()
        with self.assertRaises(InvalidWorld):
            self.compare(roster=r)

    def test_unrecognized_gossip_site_denied(self):
        p = copy.deepcopy(self.peast)
        p["site"] = "third"
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_same_pinned_site_cannot_impersonate_peer(self):
        with self.assertRaises(InvalidWorld):
            self.compare(peer=self.pwest)

    def test_forged_gossip_envelope_scope_refused(self):
        p = copy.deepcopy(self.peast)
        p["scope"] = "NATIVE_RELATTE_ADMISSION"
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_forged_observer_signature_refused(self):
        p = copy.deepcopy(self.peast)
        p["observations"][0]["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_forged_local_index_refused(self):
        p = copy.deepcopy(self.peast)
        p["observations"][0]["local_index"] = 12
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_missing_local_receipt_refused(self):
        p = copy.deepcopy(self.peast)
        p["observations"] = []
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_wrong_gossip_receipt_chain_prev_refused(self):
        p = copy.deepcopy(self.peast)
        p["observations"][0]["previous_receipt_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_gossip_receipt_head_must_match_checkpoint(self):
        p = copy.deepcopy(self.peast)
        p["observations"][0]["checkpoint_head"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_gossip_receipt_009_assessment_digest_cannot_be_replaced(self):
        p = copy.deepcopy(self.peast)
        p["observations"][0]["009_assessment_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_one_missing_009_checkpoint_cosigner_refused(self):
        p = copy.deepcopy(self.peast)
        del p["checkpoints"][0]["witness_signatures"]["b"]
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_peer_unvalidated_fake_checkpoint_refused(self):
        p = copy.deepcopy(self.peast)
        p["checkpoints"][0]["head"] = "f" * 64
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_gossip_replayed_under_new_009_log_cut_refused(self):
        p = copy.deepcopy(self.peast)
        p["log_entries"][0]["submission"]["artifact_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_peer_corrupted_hash_chain_refused(self):
        p = copy.deepcopy(self.peast)
        p["log_entries"][3]["head"] = "1" * 64
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_gossip_receipt_cannot_assert_execution(self):
        p = copy.deepcopy(self.peast)
        p["observations"][0]["external_execution"] = True
        with self.assertRaises(InvalidWorld):
            self.compare(peer=p)

    def test_one_site_only_proves_no_peer_evidence_not_no_fork(self):
        alone = compare_views(self.common, self.west[17], self.west[18],
                              self.roster, self.root, self.pwest, None, now=1001)
        self.assertEqual(alone["decision"], "HOLD_NO_PEER_GOSSIP_EVIDENCE")
        self.assertFalse(alone["gossip_received_by_all_peers_proven"])

    def test_not_actual_wall_clock_or_physical_truth(self):
        result = self.compare()
        self.assertTrue(result["signature_authenticates_publication_not_truth"])
        self.assertFalse(result["independent_human_witnesses_proven"])
        self.assertFalse(result["sqlite_is_immutable_external_ledger"])
        self.assertFalse(result["gossip_received_by_all_peers_proven"])
        self.assertFalse(result["native_relatte_admission"])
        self.assertTrue(result["no_external_execution"])

    def test_separately_signed_receipt_requires_pinned_site_signer(self):
        verified, checkpoint = check_view(self.east, now=1001)
        with self.assertRaises(InvalidWorld):
            signed_observation(self.east, self.roster, "east",
                               self.keys["gossip-west"], checkpoint, verified,
                               index=0, previous="0" * 64)

    def test_db_tamper_with_signed_receipt_prevents_followup_write(self):
        with tempfile.TemporaryDirectory() as temp:
            dbpath = Path(temp) / "obs.sqlite"
            observe_once(dbpath, self.west, self.roster, self.root,
                         "west", self.keys["gossip-west"], now=1001)
            with sqlite3.connect(dbpath) as db:
                db.execute("UPDATE observations SET signed_receipt=? WHERE site='west'",
                           (json.dumps({"schema": "fake"}),))
            with self.assertRaises(InvalidWorld):
                observe_once(dbpath, self.east, self.roster, self.root,
                             "west", self.keys["gossip-west"], now=1001)

    def test_valid_same_sized_heads_are_not_mistaken_for_sensor_calibration(self):
        r = self.compare()
        self.assertEqual(r["decision"], "HOLD_GOSSIP_REVEALS_UNSEEN_FORK")
        self.assertEqual(r["authority"], "NONE")
        self.assertEqual(r["effects"], [])

    def test_forged_review_digest_recomputed_is_still_denied(self):
        r = self.compare()
        r["native_relatte_admission"] = True
        r["assessment_digest"] = digest({k: v for k, v in r.items() if k != "assessment_digest"})
        self.assertFalse(cold_verify(self.common, self.west[17], self.west[18],
                                     self.roster, self.root, self.pwest, self.peast,
                                     r, now=1001))

    def test_complete_cold_verify_without_private_keys(self):
        r = self.compare()
        self.assertTrue(cold_verify(self.common, self.west[17], self.west[18],
                                    self.roster, self.root, self.pwest, self.peast,
                                    r, now=1001))

    def test_process_replay_public_packages_only(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            names = ("parent", "roster", "challenge", "statements",
                     "primary_anchor", "primary_precommit", "primary_measurement", "pinset",
                     "primary_custody", "secondary_custody", "secondary_measurement",
                     "manifest", "attestations", "audit_policy", "audit_commits",
                     "audit_reports", "trusted_root")
            flags = []
            for name, val in zip(names, self.common):
                path = folder / (name + ".json")
                path.write_text(json.dumps(val), encoding="utf-8")
                flags.extend(("--" + name.replace("_", "-"), str(path)))
            others = {"log-policy": self.west[17], "log-root": self.west[18],
                      "gossip-roster": self.roster, "gossip-root": self.root,
                      "local-package": self.pwest, "peer-package": self.peast}
            for name, val in others.items():
                file = folder / (name + ".json")
                file.write_text(json.dumps(val), encoding="utf-8")
                flags.extend(("--" + name, str(file)))
            flags += ["--now", "1001"]
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_gossip.py")]
            first = subprocess.run(cmd + ["compare"] + flags, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            result = json.loads(first.stdout)
            self.assertEqual(result["decision"], "HOLD_GOSSIP_REVEALS_UNSEEN_FORK")
            filepath = folder / "receipt.json"
            filepath.write_text(first.stdout, encoding="utf-8")
            again = subprocess.run(cmd + ["verify"] + flags + [
                "--receipt", str(filepath)], capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(json.loads(again.stdout), {"verified": True})

    def test_demo_two_local_stores_then_gossip(self):
        report = demo()
        self.assertEqual(report["before_gossip"], "HOLD_NO_PEER_GOSSIP_EVIDENCE")
        self.assertEqual(report["after_gossip"], "HOLD_GOSSIP_REVEALS_UNSEEN_FORK")
        self.assertTrue(report["different_heads"])
        self.assertTrue(report["local_west_record_retained"])
        self.assertTrue(report["local_east_record_retained"])
        self.assertTrue(report["cold_replay_verified"])
        self.assertFalse(report["native_execution"])


if __name__ == "__main__":
    unittest.main()
