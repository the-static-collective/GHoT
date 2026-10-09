#!/usr/bin/env python3
"""018: source-signature fork preservation; no timestamp or arrival-order power."""
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
from unheard_choir_delayed_revocation import make_snapshot  # noqa: E402
from unheard_choir_witness_custody import make_notice  # noqa: E402
from unheard_choir_source_fork import (  # noqa: E402
    UNKNOWN, SINGLE, FORKED_NEGATIVE, FORKED_POLARITY,
    make_reinstatement, verify_reinstatement,
    make_view, verify_view, compare, stage_once, ingest_once,
    read_view, read_receipts, verify_receipt, build_fixture, demo,
)


class NegativeThatForkedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.tmp, cls.prior, cls.p016, cls.root016, cls.manifest,
         cls.roster, cls.root, cls.original, cls.later, cls.restore,
         cls.keys) = build_fixture()
        cls.common = (cls.prior, cls.p016, cls.root016,
                      cls.manifest, cls.roster, cls.root)
        cls.west_old = make_snapshot(*cls.common, "west",
                                     cls.keys["017-west"], None, now=1250)
        cls.east_old = make_snapshot(*cls.common, "east",
                                     cls.keys["017-east"], cls.original, now=1250)
        cls.west = make_view(*cls.common, cls.west_old, [cls.later], cls.keys["017-west"])
        cls.east = make_view(*cls.common, cls.east_old, [cls.restore], cls.keys["017-east"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.west_db = Path(self.dir.name) / "west.sqlite"
        self.east_db = Path(self.dir.name) / "east.sqlite"

    def tearDown(self):
        self.dir.cleanup()

    def stage_west(self):
        return stage_once(self.west_db, *self.common, self.west)

    def ingest(self, remote=None, *, now=1250, signer=None):
        if read_view(self.west_db, "west") is None:
            self.stage_west()
        return ingest_once(
            self.west_db, *self.common, "west",
            self.east if remote is None else remote,
            self.keys["017-west"] if signer is None else signer,
            now=now,
        )

    def test_source_signed_revocations_are_distinct_but_both_authentic(self):
        self.assertNotEqual(digest(self.original), digest(self.later))
        r = compare(*self.common, self.west, self.east, now=1250)
        self.assertEqual(len(r["revocation_digests"]), 2)
        self.assertIn(digest(self.original), r["revocation_digests"])
        self.assertIn(digest(self.later), r["revocation_digests"])

    def test_two_revocations_without_restoration_are_unordered_hold(self):
        east_only = make_view(*self.common, self.east_old, [], self.keys["017-east"])
        r = compare(*self.common, self.west, east_only, now=1250)
        self.assertEqual(r["decision"], FORKED_NEGATIVE)
        self.assertFalse(r["claimed_timestamp_is_precedence"])

    def test_reinstatement_and_revocation_are_conflicting_not_automatically_reinstated(self):
        r = compare(*self.common, self.west, self.east, now=1250)
        self.assertEqual(r["decision"], FORKED_POLARITY)
        self.assertEqual(len(r["reinstatement_claim_digests"]), 1)
        self.assertFalse(r["has_valid_native_reinstatement"])
        self.assertFalse(r["native_relatte_admission"])

    def test_arrival_order_does_not_change_disposition(self):
        a = compare(*self.common, self.west, self.east, now=1250)
        b = compare(*self.common, self.east, self.west, now=1250)
        self.assertEqual(a["decision"], b["decision"])
        self.assertEqual(a["source_event_digests"], b["source_event_digests"])
        self.assertFalse(a["arrival_order_is_precedence"])

    def test_later_claimed_reinstatement_clock_does_not_win(self):
        r = compare(*self.common, self.west, self.east, now=1900)
        self.assertEqual(r["decision"], FORKED_POLARITY)
        self.assertFalse(r["claimed_timestamp_is_precedence"])
        self.assertEqual(r["effects"], [])
        self.assertEqual(r["authority"], "NONE")

    def test_missing_source_events_is_unknown_not_unrevoked(self):
        w = make_view(*self.common, self.west_old, [], self.keys["017-west"])
        e = make_view(*self.common, make_snapshot(*self.common, "east",
                      self.keys["017-east"], None, now=1250),
                      [], self.keys["017-east"])
        self.assertEqual(compare(*self.common, w, e, now=1250)["decision"], UNKNOWN)

    def test_one_distinct_revocation_remains_hold(self):
        w = make_view(*self.common, self.west_old, [], self.keys["017-west"])
        e = make_view(*self.common, self.east_old, [], self.keys["017-east"])
        self.assertEqual(compare(*self.common, w, e, now=1250)["decision"], SINGLE)

    def test_deduplicated_same_revocation_does_not_become_equivocation(self):
        w = make_view(*self.common, self.west_old, [self.original], self.keys["017-west"])
        e = make_view(*self.common, self.east_old, [], self.keys["017-east"])
        r = compare(*self.common, w, e, now=1250)
        self.assertEqual(r["decision"], SINGLE)
        self.assertEqual(len(r["source_event_digests"]), 1)

    def test_old_015_approval_survives_every_disposition(self):
        r = compare(*self.common, self.west, self.east, now=1250)
        self.assertEqual(r["historical_015_approval_digest"], digest(self.prior[11]))
        self.assertFalse(r["original_017_snapshots_mutated"])

    def test_reinstatement_is_signed_by_original_source_and_bound_to_revocation(self):
        verify_reinstatement(self.prior, self.p016, self.roster, self.restore)
        self.assertEqual(self.restore["revocation_notice_digest"], digest(self.original))
        self.assertFalse(self.restore["restores_native_source_authority"])

    def test_holder_cannot_impersonate_source_reinstatement(self):
        with self.assertRaises(InvalidWorld):
            make_reinstatement(self.prior, self.p016, self.roster,
                               self.original, self.keys["delegation-holder"])

    def test_successor_cannot_impersonate_source_reinstatement(self):
        with self.assertRaises(InvalidWorld):
            make_reinstatement(self.prior, self.p016, self.roster,
                               self.original, self.keys["east-reconstituted"])

    def test_source_reinstatement_signature_tamper_refused(self):
        claim = copy.deepcopy(self.restore)
        claim["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            verify_reinstatement(self.prior, self.p016, self.roster, claim)

    def test_reinstatement_attempt_to_activate_native_permission_refused(self):
        claim = copy.deepcopy(self.restore)
        claim["restores_native_source_authority"] = True
        with self.assertRaises(InvalidWorld):
            verify_reinstatement(self.prior, self.p016, self.roster, claim)

    def test_reinstatement_attempt_to_forward_refused(self):
        claim = copy.deepcopy(self.restore)
        claim["effect_permission"] = "FORWARD"
        with self.assertRaises(InvalidWorld):
            verify_reinstatement(self.prior, self.p016, self.roster, claim)

    def test_reinstatement_wrong_revocation_digest_refused(self):
        claim = copy.deepcopy(self.restore)
        claim["revocation_notice_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            verify_reinstatement(self.prior, self.p016, self.roster, claim)

    def test_reinstatement_not_bound_to_different_source_roster(self):
        claim = copy.deepcopy(self.restore)
        claim["roster_digest"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            verify_reinstatement(self.prior, self.p016, self.roster, claim)

    def test_reinstatement_signed_before_original_revocation_refused(self):
        with self.assertRaises(InvalidWorld):
            make_reinstatement(self.prior, self.p016, self.roster,
                               self.original, self.keys["015-source-reviewer"],
                               claimed_at=1000, effective_at=1100, not_after=5000)

    def test_reinstatement_time_boolean_refused(self):
        with self.assertRaises(InvalidWorld):
            make_reinstatement(self.prior, self.p016, self.roster,
                               self.original, self.keys["015-source-reviewer"],
                               claimed_at=True)

    def test_reinstatement_cannot_reference_unsigned_016_notice(self):
        old = copy.deepcopy(self.original)
        old["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            make_reinstatement(self.prior, self.p016, self.roster,
                               old, self.keys["015-source-reviewer"])

    def test_other_016_notice_cannot_be_laundered_as_revocation(self):
        other = make_notice(self.prior, self.p016, self.keys["015-source-reviewer"],
                            "SOURCE_UNAVAILABLE_LOCAL")
        with self.assertRaises(InvalidWorld):
            make_reinstatement(self.prior, self.p016, self.roster,
                               other, self.keys["015-source-reviewer"])

    def test_018_view_signed_by_only_its_observer(self):
        with self.assertRaises(InvalidWorld):
            make_view(*self.common, self.west_old, [self.later], self.keys["017-east"])

    def test_018_view_original_017_signature_cannot_be_forged(self):
        v = copy.deepcopy(self.west)
        v["original_017_snapshot"]["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            verify_view(*self.common, v)

    def test_018_view_cannot_claim_native_receive(self):
        v = copy.deepcopy(self.east)
        v["native_relatte_receive"] = True
        with self.assertRaises(InvalidWorld):
            verify_view(*self.common, v)

    def test_view_cannot_claim_absence_is_world_fact(self):
        v = copy.deepcopy(self.west)
        v["lack_of_seen_revocation_proves_no_revocation"] = True
        with self.assertRaises(InvalidWorld):
            verify_view(*self.common, v)

    def test_view_wrong_source_event_digest_set_refused(self):
        v = copy.deepcopy(self.east)
        v["observed_source_digest_set"] = []
        with self.assertRaises(InvalidWorld):
            verify_view(*self.common, v)

    def test_view_invalid_evidence_order_rejected(self):
        v = make_view(*self.common, self.west_old,
                      [self.original, self.later], self.keys["017-west"])
        broken = copy.deepcopy(v)
        broken["additional_source_events"].reverse()
        if broken["additional_source_events"] == v["additional_source_events"]:
            self.skipTest("canonical order coincidentally unchanged")
        with self.assertRaises(InvalidWorld):
            verify_view(*self.common, broken)

    def test_view_duplicate_source_event_denied(self):
        with self.assertRaises(InvalidWorld):
            make_view(*self.common, self.west_old,
                      [self.later, copy.deepcopy(self.later)],
                      self.keys["017-west"])

    def test_view_wrong_observer_signature_refused(self):
        v = copy.deepcopy(self.east)
        v["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            verify_view(*self.common, v)

    def test_source_revocation_016_signature_corruption_cannot_be_republished(self):
        v = copy.deepcopy(self.west)
        v["additional_source_events"][0]["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            verify_view(*self.common, v)

    def test_observer_roster_root_swapping_denied(self):
        with self.assertRaises(InvalidWorld):
            compare(self.prior, self.p016, self.root016, self.manifest,
                    self.roster, self.keys["017-west"].public_jwk(),
                    self.west, self.east, now=1250)

    def test_same_site_two_018_views_not_a_remote_exchange(self):
        with self.assertRaises(InvalidWorld):
            compare(*self.common, self.west, self.west, now=1250)

    def test_signed_initial_view_stored_and_duplicate_byte_identical(self):
        a = self.stage_west()
        b = stage_once(self.west_db, *self.common, self.west)
        self.assertEqual(a, b)
        self.assertEqual(read_view(self.west_db, "west"), a)

    def test_old_view_cannot_be_rewritten_with_additional_source_notice(self):
        self.stage_west()
        alt = make_view(*self.common, self.west_old, [], self.keys["017-west"])
        with self.assertRaises(InvalidWorld):
            stage_once(self.west_db, *self.common, alt)

    def test_signed_local_receipt_durable_no_mutation(self):
        self.stage_west()
        first = self.ingest()
        self.assertEqual(first["status"], "SIGNED_SOURCE_FORK_RECEIPT_STORED")
        self.assertEqual(first["receipt"]["assessment"]["decision"], FORKED_POLARITY)
        self.assertEqual(read_view(self.west_db, "west"), self.west)
        self.assertEqual(len(read_receipts(self.west_db)), 1)

    def test_duplicate_remote_review_preserves_original_receipt(self):
        first = self.ingest()
        second = self.ingest()
        self.assertEqual(first["receipt"], second["receipt"])
        self.assertEqual(second["status"], "DUPLICATE_IDENTICAL_RECEIPT")

    def test_wrong_local_signer_may_not_receive_source_fork(self):
        with self.assertRaises(InvalidWorld):
            self.ingest(signer=self.keys["017-east"])

    def test_remote_view_swap_does_not_rewrite_signed_local_disposition(self):
        self.ingest()
        other = make_view(*self.common, self.east_old, [], self.keys["017-east"])
        with self.assertRaises(InvalidWorld):
            self.ingest(other)

    def test_changed_replay_clock_does_not_reclassify_existing_receipt(self):
        self.ingest()
        with self.assertRaises(InvalidWorld):
            self.ingest(now=1450)

    def test_corrupted_sqlite_local_view_refuses_followup(self):
        self.stage_west()
        with sqlite3.connect(self.west_db) as db:
            db.execute("UPDATE original_view SET view_json=?",
                       (json.dumps({"fake": True}),))
        with self.assertRaises(InvalidWorld):
            self.ingest()

    def test_corrupted_sqlite_receipt_refuses_followup(self):
        self.ingest()
        with sqlite3.connect(self.west_db) as db:
            db.execute("UPDATE local_reviews SET review_json=?",
                       (json.dumps({"fake": True}),))
        with self.assertRaises(InvalidWorld):
            self.ingest()

    def test_signature_forged_local_receipt_refused_on_public_replay(self):
        saved = self.ingest()["receipt"]
        saved = copy.deepcopy(saved)
        saved["signature"] = "fake"
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.common, self.west, self.east, saved)

    def test_forged_local_receipt_cannot_claim_execution(self):
        saved = copy.deepcopy(self.ingest()["receipt"])
        saved["assessment"]["external_execution"] = True
        with self.assertRaises(InvalidWorld):
            verify_receipt(*self.common, self.west, self.east, saved)

    def test_public_verify_in_separate_process_without_signer_or_db(self):
        receipt = self.ingest()["receipt"]
        values = list(self.prior) + [
            self.p016, self.root016, self.manifest, self.roster, self.root,
            self.west, self.east, receipt,
        ]
        names = (
            "parcel", "historical-local-package", "historical-pins",
            "succession-policy", "succession-root", "reviewer-selections",
            "candidate-archive-grants", "legacy-delegation", "third-party-policy",
            "third-party-root", "third-party-presentation", "fresh-source-review",
            "new-owner-consent", "custody-policy", "custody-root", "holder-manifest",
            "roster", "roster-root", "local-view", "remote-view", "fork-receipt",
        )
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            flags = []
            for name, value in zip(names, values):
                p = folder / (name + ".json")
                p.write_text(json.dumps(value), encoding="utf-8")
                flags.extend(("--" + name, str(p)))
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_source_fork.py"),
                   "verify", *flags]
            result = subprocess.run(cmd, cwd=str(folder), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             {"verified": True, "decision": FORKED_POLARITY})
            self.assertFalse(list(folder.glob("*.pem")))
            self.assertFalse(list(folder.glob("*.sqlite")))

    def test_standalone_demo_preserves_signed_conflict(self):
        out = demo()
        self.assertEqual(out["two_valid_source_revocations"], FORKED_NEGATIVE)
        self.assertEqual(out["signed_reinstatement_and_revocations"], FORKED_POLARITY)
        self.assertTrue(out["both_original_017_snapshots_retained"])
        self.assertTrue(out["historical_015_approval_retained"])
        self.assertTrue(out["local_receipt_written"])
        self.assertTrue(out["idempotent_replay"])
        self.assertTrue(out["cold_public_verification"])
        self.assertFalse(out["native_relatte_receive"])
        self.assertFalse(out["external_execution"])


if __name__ == "__main__":
    unittest.main()
