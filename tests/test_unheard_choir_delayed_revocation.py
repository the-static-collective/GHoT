#!/usr/bin/env python3
"""017 hostile matrix: unknown absence, signed late revocation and bounded local gossip."""
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
from unheard_choir_witness_custody import make_notice  # noqa: E402
from unheard_choir_delayed_revocation import (  # noqa: E402
    UNKNOWN, KNOWN, FUTURE, EXPIRED, OTHER, CONFLICT,
    build_fixture, demo, make_roster, verify_roster,
    make_snapshot, verify_snapshot, observe_once,
    compare, ingest_once, read_local, read_imports, verify_review,
)


class DelayedRevocationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.tmp, cls.prior, cls.p016, cls.root016, cls.manifest,
         cls.roster, cls.root, cls.notice, cls.keys) = build_fixture()
        cls.common = (cls.prior, cls.p016, cls.root016,
                      cls.manifest, cls.roster, cls.root)
        cls.west = make_snapshot(*cls.common, "west",
                                 cls.keys["017-west"], None, now=1250)
        cls.east = make_snapshot(*cls.common, "east",
                                 cls.keys["017-east"], cls.notice, now=1250)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.session = tempfile.TemporaryDirectory()
        self.west_db = Path(self.session.name) / "west.sqlite"
        self.east_db = Path(self.session.name) / "east.sqlite"

    def tearDown(self):
        self.session.cleanup()

    def create_west(self, *, notice=None, now=1250):
        return observe_once(self.west_db, *self.common, "west",
                            self.keys["017-west"], notice, now=now)

    def create_east(self, *, notice=None, now=1250):
        return observe_once(self.east_db, *self.common, "east",
                            self.keys["017-east"],
                            self.notice if notice is None else notice, now=now)

    def receive(self, peer=None, *, now=1250, signer=None):
        if read_local(self.west_db, "west") is None:
            self.create_west()
        return ingest_once(
            self.west_db, *self.common, "west",
            self.east if peer is None else peer,
            self.keys["017-west"] if signer is None else signer,
            now=now,
        )

    def test_west_old_signed_source_approval_remains_valid_but_revocation_unknown(self):
        self.assertEqual(self.west["revocation_knowledge"], UNKNOWN)
        self.assertEqual(self.west["016_decision"],
                         "HOLD_CUSTODY_EVIDENCE_ONLY_NOT_ADMITTED")
        self.assertFalse(self.west["lack_of_revocation_proves_never_revoked"])
        self.assertEqual(self.west["original_015_source_approval_preserved"], digest(self.prior[11]))

    def test_east_has_authenticated_notice_not_global_time_or_owner_proof(self):
        self.assertEqual(self.east["revocation_knowledge"], KNOWN)
        self.assertEqual(self.east["016_decision"],
                         "HOLD_SOURCE_REVOKED_CURRENT_ARCHIVE_REVIEW")
        self.assertFalse(self.east["native_relatte_receive"])
        self.assertFalse(self.east["forwarding_permitted"])

    def test_both_sides_signed_with_distinct_independently_pinned_keys(self):
        self.assertNotEqual(self.roster["sites"]["west"], self.roster["sites"]["east"])
        verify_roster(*self.common[:4], self.roster, self.root)
        verify_snapshot(*self.common, self.west, expected_site="west")
        verify_snapshot(*self.common, self.east, expected_site="east")

    def test_no_delivery_cannot_reclassify_sender_side_history(self):
        west = self.create_west()
        self.assertEqual(read_imports(self.west_db), [])
        self.assertEqual(read_local(self.west_db, "west"), west)
        self.assertEqual(west["revocation_knowledge"], UNKNOWN)

    def test_replayed_same_source_approval_does_not_prove_no_revocation(self):
        west = self.create_west()
        self.assertEqual(west["original_015_source_approval_preserved"], digest(self.prior[11]))
        self.assertTrue(west["lack_of_revocation_proves_never_revoked"] is False)

    def test_signed_gossip_changes_local_review_not_original_observation(self):
        original = self.create_west()
        result = self.receive()
        self.assertEqual(result["status"], "SIGNED_GOSSIP_REVIEW_DURABLY_WRITTEN")
        self.assertEqual(result["review"]["assessment"]["decision"], KNOWN)
        self.assertEqual(read_local(self.west_db, "west"), original)
        self.assertEqual(len(read_imports(self.west_db)), 1)

    def test_after_delivery_015_historical_approval_is_still_in_signed_review(self):
        review = self.receive()["review"]
        self.assertEqual(review["assessment"]["retained_historical_015_approval_digest"],
                         digest(self.prior[11]))
        self.assertFalse(review["assessment"]["past_observation_mutated"])

    def test_local_review_is_signed_by_local_observer_not_remote(self):
        review = self.receive()["review"]
        self.assertEqual(
            verify_review(*self.common, read_local(self.west_db, "west"),
                          self.east, review)["decision"], KNOWN)
        self.assertEqual(review["assessment"]["local_site"], "west")

    def test_gossip_duplicate_does_not_create_new_signature_or_receipt(self):
        first = self.receive()
        second = self.receive()
        self.assertEqual(first["review"], second["review"])
        self.assertEqual(second["status"], "DUPLICATE_SIGNED_REVIEW_UNCHANGED")
        self.assertEqual(len(read_imports(self.west_db)), 1)

    def test_duplicate_initial_observation_reuses_exact_signed_bytes(self):
        first = self.create_west()
        again = self.create_west()
        self.assertEqual(first, again)
        self.assertEqual(read_local(self.west_db, "west"), first)

    def test_original_observation_cannot_be_rewritten_with_revocation(self):
        self.create_west()
        with self.assertRaises(InvalidWorld):
            self.create_west(notice=self.notice)
        self.assertEqual(read_local(self.west_db, "west")["revocation_knowledge"], UNKNOWN)

    def test_revocation_recipient_must_be_separate_site(self):
        with self.assertRaises(InvalidWorld):
            compare(*self.common, self.west, self.west, now=1250)

    def test_source_notice_forgery_refused_even_with_valid_site_signature(self):
        altered = copy.deepcopy(self.east)
        altered["source_notice"]["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            compare(*self.common, self.west, altered, now=1250)

    def test_original_015_source_review_tampering_refused(self):
        prior = copy.deepcopy(self.prior)
        prior[11]["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            compare(prior, *self.common[1:], self.west, self.east, now=1250)

    def test_forged_revocation_target_rejected(self):
        altered = copy.deepcopy(self.east)
        altered["source_notice"]["review_target_digest"] = "0"*64
        with self.assertRaises(InvalidWorld):
            compare(*self.common, self.west, altered, now=1250)

    def test_source_notice_cannot_prove_global_world_absence(self):
        altered = copy.deepcopy(self.east)
        altered["source_notice"]["proves_nonresponse_elsewhere"] = True
        with self.assertRaises(InvalidWorld):
            compare(*self.common, self.west, altered, now=1250)

    def test_invalid_site_signer_cannot_create_observation(self):
        with self.assertRaises(InvalidWorld):
            make_snapshot(*self.common, "west", self.keys["017-east"], None, now=1250)

    def test_source_reviewer_key_cannot_impersonate_site(self):
        with self.assertRaises(InvalidWorld):
            make_snapshot(*self.common, "east",
                          self.keys["015-source-reviewer"], self.notice, now=1250)

    def test_unpinned_roster_root_does_not_validate_observations(self):
        with self.assertRaises(InvalidWorld):
            verify_snapshot(*self.common[:-1],
                            self.keys["gossip-root"].public_jwk(), self.east)

    def test_swapping_signed_roster_site_identity_refused(self):
        roster = copy.deepcopy(self.roster)
        roster["sites"]["east"] = roster["sites"]["west"]
        with self.assertRaises(InvalidWorld):
            verify_snapshot(*self.common[:4], roster, self.root, self.east)

    def test_roster_does_not_grant_effects(self):
        roster = copy.deepcopy(self.roster)
        roster["native_authority"] = True
        with self.assertRaises(InvalidWorld):
            verify_snapshot(*self.common[:4], roster, self.root, self.east)

    def test_forged_west_signature_refused(self):
        altered = copy.deepcopy(self.west)
        altered["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            compare(*self.common, altered, self.east, now=1250)

    def test_forged_east_signature_refused(self):
        altered = copy.deepcopy(self.east)
        altered["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            compare(*self.common, self.west, altered, now=1250)

    def test_observer_claims_no_revocation_ever_rejected(self):
        altered = copy.deepcopy(self.west)
        altered["lack_of_revocation_proves_never_revoked"] = True
        with self.assertRaises(InvalidWorld):
            compare(*self.common, altered, self.east, now=1250)

    def test_cold_comparison_replays_016_assessment_from_site(self):
        r = compare(*self.common, self.west, self.east, now=1250)
        self.assertEqual(r["decision"], KNOWN)
        self.assertEqual(r["local_site"], "west")
        self.assertEqual(r["remote_site"], "east")
        self.assertFalse(r["external_execution"])

    def test_premature_signed_revocation_is_history_not_active(self):
        west = make_snapshot(*self.common, "west", self.keys["017-west"], None, now=1150)
        east = make_snapshot(*self.common, "east", self.keys["017-east"],
                             self.notice, now=1150)
        r = compare(*self.common, west, east, now=1150)
        self.assertEqual(r["decision"], FUTURE)
        self.assertFalse(r["forwarding_permitted"])

    def test_expired_signed_notice_history_does_not_restore_permission(self):
        west = make_snapshot(*self.common, "west", self.keys["017-west"], None, now=5100)
        east = make_snapshot(*self.common, "east", self.keys["017-east"],
                             self.notice, now=5100)
        r = compare(*self.common, west, east, now=5100)
        self.assertEqual(r["decision"], EXPIRED)
        self.assertEqual(r["retained_historical_015_approval_digest"], digest(self.prior[11]))

    def test_signed_revocation_effective_at_boundary(self):
        self.assertEqual(compare(*self.common, self.west, self.east, now=1200)["decision"], KNOWN)

    def test_nonsigned_source_omission_is_not_signed_rejection(self):
        west = make_snapshot(*self.common, "west", self.keys["017-west"], None, now=1250)
        east = make_snapshot(*self.common, "east", self.keys["017-east"], None, now=1250)
        r = compare(*self.common, west, east, now=1250)
        self.assertEqual(r["decision"], UNKNOWN)
        self.assertEqual(r["source_notice_digests"], [])

    def test_source_unavailability_is_not_automatically_revocation(self):
        note = make_notice(self.prior, self.p016, self.keys["015-source-reviewer"],
                           "SOURCE_UNAVAILABLE_LOCAL")
        east = make_snapshot(*self.common, "east",
                             self.keys["017-east"], note, now=1250)
        r = compare(*self.common, self.west, east, now=1250)
        self.assertEqual(r["decision"], OTHER)

    def test_distinct_well_signed_source_notices_do_not_select_one_by_order(self):
        unavail = make_notice(self.prior, self.p016, self.keys["015-source-reviewer"],
                              "SOURCE_UNAVAILABLE_LOCAL")
        west = make_snapshot(*self.common, "west",
                             self.keys["017-west"], unavail, now=1250)
        self.assertEqual(compare(*self.common, west, self.east, now=1250)["decision"], CONFLICT)
        self.assertEqual(compare(*self.common, self.east, west, now=1250)["decision"], CONFLICT)

    def test_signed_site_recipient_cannot_import_into_other_site_db(self):
        self.create_west()
        with self.assertRaises(InvalidWorld):
            ingest_once(self.west_db, *self.common, "west",
                        self.east, self.keys["017-east"], now=1250)

    def test_no_local_observation_means_no_import(self):
        with self.assertRaises(InvalidWorld):
            ingest_once(self.west_db, *self.common, "west",
                        self.east, self.keys["017-west"], now=1250)

    def test_corrupted_stored_original_blocks_reconciliation(self):
        self.create_west()
        with sqlite3.connect(self.west_db) as db:
            db.execute("UPDATE original_observations SET snapshot_json=?",
                       (json.dumps({"fake": True}),))
        with self.assertRaises(InvalidWorld):
            self.receive()

    def test_corrupted_stored_signed_review_blocks_duplicate(self):
        self.receive()
        with sqlite3.connect(self.west_db) as db:
            db.execute("UPDATE imported_gossip SET review_json=?",
                       (json.dumps({"fake": True}),))
        with self.assertRaises(InvalidWorld):
            self.receive()

    def test_replay_with_different_peer_does_not_mutate_old_local_receipt(self):
        first = self.receive()
        different = make_snapshot(*self.common, "east",
                                  self.keys["017-east"], None, now=1250)
        with self.assertRaises(InvalidWorld):
            self.receive(different)
        self.assertEqual(read_imports(self.west_db)[0], first["review"])

    def test_signed_gossip_review_cannot_claim_execution(self):
        first = self.receive()
        receipt = copy.deepcopy(first["review"])
        receipt["assessment"]["external_execution"] = True
        with self.assertRaises(InvalidWorld):
            verify_review(*self.common, read_local(self.west_db, "west"),
                          self.east, receipt)

    def test_signed_gossip_review_bad_signer_rejected(self):
        first = self.receive()
        receipt = copy.deepcopy(first["review"])
        receipt["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            verify_review(*self.common, read_local(self.west_db, "west"),
                          self.east, receipt)

    def test_signed_review_clock_replay_cannot_reclassify_original(self):
        first = self.receive()
        with self.assertRaises(InvalidWorld):
            self.receive(now=1150)
        self.assertEqual(read_imports(self.west_db)[0], first["review"])

    def test_cold_verify_subprocess_with_public_only_evidence(self):
        r = self.receive()["review"]
        values = list(self.prior) + [
            self.p016, self.root016, self.manifest, self.roster, self.root,
            read_local(self.west_db, "west"), self.east, r,
        ]
        labels = (
            "parcel", "historical-local-package", "historical-pins",
            "succession-policy", "succession-root", "reviewer-selections",
            "candidate-archive-grants", "legacy-delegation", "third-party-policy",
            "third-party-root", "third-party-presentation", "fresh-source-review",
            "new-owner-consent", "custody-policy", "custody-root", "holder-manifest",
            "roster", "roster-root", "local-snapshot", "remote-snapshot", "gossip-review",
        )
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            flags = []
            for name, value in zip(labels, values):
                file = folder / (name + ".json")
                file.write_text(json.dumps(value), encoding="utf-8")
                flags.extend(["--" + name, str(file)])
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_delayed_revocation.py"),
                   "verify", *flags]
            run = subprocess.run(cmd, cwd=str(folder), text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout), {"verified": True, "decision": KNOWN})
            self.assertFalse(list(folder.glob("*.pem")))
            self.assertFalse(list(folder.glob("*.sqlite")))

    def test_demo_exercises_two_observer_isolation_and_recovery(self):
        result = demo()
        self.assertEqual(result["west_initial"], UNKNOWN)
        self.assertEqual(result["east_initial"], KNOWN)
        self.assertTrue(result["transport_drop_kept_sender_unknown"])
        self.assertEqual(result["signed_exchange_decision"], KNOWN)
        self.assertTrue(result["old_positive_approval_retained"])
        self.assertTrue(result["west_original_snapshot_preserved"])
        self.assertTrue(result["east_original_snapshot_preserved"])
        self.assertTrue(result["gossip_receipt_durable"])
        self.assertTrue(result["idempotent_duplicate"])
        self.assertTrue(result["public_cold_replay"])
        self.assertFalse(result["native_relatte_receive"])
        self.assertFalse(result["external_execution"])


if __name__ == "__main__":
    unittest.main()
