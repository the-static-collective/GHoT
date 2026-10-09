#!/usr/bin/env python3
"""011 hostile drop, recovery, anti-entropy, forgery and replay matrix."""
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
from unheard_choir_gossip import (  # noqa: E402
    check_roster, compare_views, fork_fixture, make_package, observe_once, read_local,
)
from unheard_choir_vanishing import (  # noqa: E402
    demo, make_envelope, verify_envelope, init_outbox, init_inbox,
    stage_once, read_outbox, read_inbox, receive_once, verify_ack,
    verify_inbox, confirm_once, make_inventory, verify_inventory, reconcile,
)


class VanishingWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys_tmp, cls.west, cls.east, cls.keys, cls.roster = fork_fixture()
        cls.root = cls.keys["gossip-root"].public_jwk()
        cls.common, cls.policy, cls.log_root = cls.west[:17], cls.west[17], cls.west[18]
        cls.west_observations = Path(cls.keys_tmp.name) / "west-site.sqlite"
        cls.east_observations = Path(cls.keys_tmp.name) / "east-site.sqlite"
        observe_once(cls.west_observations, cls.west, cls.roster, cls.root, "west",
                     cls.keys["gossip-west"], now=1001)
        observe_once(cls.east_observations, cls.east, cls.roster, cls.root, "east",
                     cls.keys["gossip-east"], now=1001)
        cls.pwest = make_package(cls.west, cls.roster, "west", cls.west_observations)
        cls.peast = make_package(cls.east, cls.roster, "east", cls.east_observations)
        cls.env = make_envelope(cls.common, cls.policy, cls.log_root, cls.roster,
                                cls.root, cls.pwest, "east", cls.keys["gossip-west"])

    @classmethod
    def tearDownClass(cls):
        cls.keys_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.outbox = Path(self.tmp.name) / "outbox.sqlite"
        self.inbox = Path(self.tmp.name) / "inbox.sqlite"
        self.stage()

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, envelope=None):
        return stage_once(self.outbox, self.common, self.policy,
                          self.log_root, self.roster, self.root,
                          self.env if envelope is None else envelope, now=1001)

    def receive(self, envelope=None, recipient_package=None, signer=None):
        return receive_once(self.inbox, self.common, self.policy,
                            self.log_root, self.roster, self.root,
                            self.env if envelope is None else envelope,
                            self.peast if recipient_package is None else recipient_package,
                            self.keys["gossip-east"] if signer is None else signer,
                            now=1001)

    def confirm(self, ack):
        return confirm_once(self.outbox, self.common, self.policy, self.log_root,
                            self.roster, self.root, ack, now=1001)

    def inventory(self):
        return make_inventory(self.inbox, self.common, self.policy, self.log_root,
                              self.roster, self.root,
                              self.keys["gossip-east"], now=1001)

    def test_first_drop_never_becomes_delivery_success(self):
        self.assertEqual(len(reconcile(self.outbox, self.roster)["pending_resend"]), 1)
        self.assertEqual(read_inbox(self.inbox), [])
        self.assertIsNone(read_outbox(self.outbox)[0]["ack"])

    def test_local_outbox_persisted_across_reopen_without_signing_key(self):
        pending = read_outbox(self.outbox)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["envelope"], self.env)
        self.assertIsNone(pending[0]["ack"])

    def test_actual_delivery_results_in_valid_fork_hold_and_signed_ack(self):
        r = self.receive()
        self.assertEqual(r["status"], "RECEIVED_LOCALLY")
        proof = verify_ack(self.common, self.policy, self.log_root, self.roster,
                           self.root, self.env, r["ack"], now=1001)
        self.assertEqual(proof["decision"], "HOLD_GOSSIP_REVEALS_UNSEEN_FORK")
        self.assertEqual(r["ack"]["sender"], "west")
        self.assertEqual(r["ack"]["recipient"], "east")
        self.assertEqual(len(read_inbox(self.inbox)), 1)

    def test_ack_dropped_sender_remains_pending(self):
        self.receive()
        self.assertEqual(len(reconcile(self.outbox, self.roster)["pending_resend"]), 1)
        self.assertIsNone(read_outbox(self.outbox)[0]["ack"])

    def test_inventory_reports_received_hint_without_granting_delivery(self):
        self.receive()
        inventory = self.inventory()
        hint = reconcile(self.outbox, self.roster, inventory)
        self.assertEqual(len(hint["ack_recovery_needed"]), 1)
        self.assertTrue(hint["inventory_only_not_proof"])
        self.assertIsNone(read_outbox(self.outbox)[0]["ack"])

    def test_repeated_receive_is_idempotent_and_return_exact_original_ack(self):
        first = self.receive()
        second = self.receive()
        self.assertEqual(second["status"], "DUPLICATE_ALREADY_RECEIVED")
        self.assertEqual(second["ack"], first["ack"])
        self.assertEqual(len(read_inbox(self.inbox)), 1)

    def test_duplicate_ack_after_confirm_is_idempotent(self):
        r = self.receive()
        self.assertEqual(self.confirm(r["ack"]), "ACKNOWLEDGED")
        self.assertEqual(self.confirm(r["ack"]), "ALREADY_ACKNOWLEDGED")
        self.assertEqual(reconcile(self.outbox, self.roster)["pending_resend"], [])
        self.assertEqual(len(reconcile(self.outbox, self.roster)["acknowledged"]), 1)

    def test_inventory_unreceived_item_is_not_proof_of_missing_record(self):
        self.receive()
        new_inventory = self.inventory()
        new_inventory["items"] = []
        with self.assertRaises(InvalidWorld):
            reconcile(self.outbox, self.roster, new_inventory)

    def test_unsent_packet_can_be_redelivered_after_process_state_loss(self):
        persisted = read_outbox(self.outbox)
        response = self.receive(persisted[0]["envelope"])
        self.assertEqual(response["status"], "RECEIVED_LOCALLY")
        self.assertEqual(self.confirm(response["ack"]), "ACKNOWLEDGED")
        self.assertEqual(len(read_inbox(self.inbox)), 1)

    def test_ack_recovery_after_receiver_reopens_db(self):
        self.receive()
        with sqlite3.connect(str(self.inbox)) as reopened:
            count = reopened.execute("SELECT COUNT(*) FROM received_shipments").fetchone()[0]
        self.assertEqual(count, 1)
        saved = read_inbox(self.inbox)[0]["ack"]
        self.assertEqual(self.confirm(saved), "ACKNOWLEDGED")

    def test_receiver_signed_inventory_validated_cryptographically(self):
        self.receive()
        inventory = self.inventory()
        verify_inventory(self.roster, inventory, "east")
        self.assertEqual(inventory["receipt_count"], 1)

    def test_inventory_omitting_ack_does_not_mark_delivered(self):
        inventory = self.inventory()
        r = reconcile(self.outbox, self.roster, inventory)
        self.assertEqual(len(r["pending_resend"]), 1)
        self.assertEqual(r["ack_recovery_needed"], [])

    def test_inventory_wrong_signing_key_denied(self):
        self.receive()
        inventory = self.inventory()
        inventory["signature"] = "forged"
        with self.assertRaises(InvalidWorld):
            reconcile(self.outbox, self.roster, inventory)

    def test_inventory_wrong_recipient_denied(self):
        self.receive()
        inventory = self.inventory()
        with self.assertRaises(InvalidWorld):
            verify_inventory(self.roster, inventory, "west")

    def test_inventory_reordered_or_duplicated_ids_denied(self):
        self.receive()
        inv = self.inventory()
        inv["items"].append(copy.deepcopy(inv["items"][0]))
        inv["receipt_count"] += 1
        with self.assertRaises(InvalidWorld):
            verify_inventory(self.roster, inv, "east")

    def test_sender_rejects_recipient_ack_signature_tampering(self):
        r = self.receive()
        fake = copy.deepcopy(r["ack"])
        fake["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            self.confirm(fake)
        self.assertIsNone(read_outbox(self.outbox)[0]["ack"])

    def test_sender_rejects_forged_recipient_claim_of_other_fork(self):
        r = self.receive()
        fake = copy.deepcopy(r["ack"])
        fake["comparison_decision"] = "REVIEW_MATCHING_WITNESSED_LOGS_NOT_ADMITTED"
        with self.assertRaises(InvalidWorld):
            self.confirm(fake)

    def test_sender_rejects_ack_with_wrong_delivery_digest(self):
        r = self.receive()
        fake = copy.deepcopy(r["ack"])
        fake["delivery_id"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.confirm(fake)

    def test_sender_rejects_ack_for_different_origin(self):
        r = self.receive()
        fake = copy.deepcopy(r["ack"])
        fake["sender"] = "east"
        with self.assertRaises(InvalidWorld):
            self.confirm(fake)

    def test_sender_rejects_undelivered_ack_without_staged_outbox(self):
        r = self.receive()
        other = Path(self.tmp.name) / "empty.sqlite"
        with self.assertRaises(InvalidWorld):
            confirm_once(other, self.common, self.policy, self.log_root,
                         self.roster, self.root, r["ack"], now=1001)

    def test_wrong_recipient_private_key_cannot_record_ack(self):
        with self.assertRaises(InvalidWorld):
            self.receive(signer=self.keys["gossip-west"])

    def test_envelope_sender_cannot_be_audit_root(self):
        with self.assertRaises(InvalidWorld):
            make_envelope(self.common, self.policy, self.log_root, self.roster,
                          self.root, self.pwest, "east", self.keys["gossip-root"])

    def test_envelope_must_have_different_recipient(self):
        with self.assertRaises(InvalidWorld):
            make_envelope(self.common, self.policy, self.log_root, self.roster,
                          self.root, self.pwest, "west", self.keys["gossip-west"])

    def test_corrupted_envelope_signature_is_refused(self):
        e = copy.deepcopy(self.env)
        e["signature"] = "bad"
        with self.assertRaises(InvalidWorld):
            self.receive(envelope=e)

    def test_corrupted_origin_history_is_refused_even_under_existing_envelope(self):
        e = copy.deepcopy(self.env)
        e["origin_package"]["checkpoints"][0]["head"] = "0" * 64
        with self.assertRaises(InvalidWorld):
            self.receive(envelope=e)

    def test_envelope_cannot_grant_native_execution(self):
        e = copy.deepcopy(self.env)
        e["native_relatte_admission"] = True
        with self.assertRaises(InvalidWorld):
            self.receive(envelope=e)

    def test_peer_must_present_contradictory_not_matching_log(self):
        with self.assertRaises(InvalidWorld):
            self.receive(recipient_package=self.pwest)

    def test_inbox_row_mutation_detected_before_future_delivery(self):
        self.receive()
        with sqlite3.connect(str(self.inbox)) as db:
            db.execute("UPDATE received_shipments SET acknowledgement_json=? WHERE receipt_index=0",
                       (json.dumps({"schema": "forged"}),))
        with self.assertRaises(InvalidWorld):
            self.receive()

    def test_staged_envelope_cannot_be_changed_by_reusing_delivery_id(self):
        staged = self.stage()
        self.assertEqual(staged["status"], "ALREADY_STAGED")
        self.assertEqual(len(read_outbox(self.outbox)), 1)

    def test_untrusted_inventory_cannot_add_peer_to_010_roster(self):
        inv = self.inventory()
        inv["site"] = "outsider"
        with self.assertRaises(InvalidWorld):
            reconcile(self.outbox, self.roster, inv)

    def test_two_distinct_sqlite_stores_survive_exchange_unchanged(self):
        self.receive()
        self.assertEqual(len(read_local(self.west_observations, "west")), 1)
        self.assertEqual(len(read_local(self.east_observations, "east")), 1)

    def test_signed_ack_replay_in_readonly_new_process(self):
        received = self.receive()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = ("parent", "roster", "challenge", "statements",
                     "primary_anchor", "primary_precommit", "primary_measurement",
                     "pinset", "primary_custody", "secondary_custody",
                     "secondary_measurement", "manifest", "attestations",
                     "audit_policy", "audit_commits", "audit_reports", "trusted_root")
            items = {}
            items.update(dict(zip(names, self.common)))
            items.update({"log_policy": self.policy, "log_root": self.log_root,
                          "gossip_roster": self.roster, "gossip_root": self.root,
                          "envelope": self.env, "ack": received["ack"]})
            flags = []
            for name, value in items.items():
                file = root / (name + ".json")
                file.write_text(json.dumps(value), encoding="utf-8")
                flags += ["--" + name.replace("_", "-"), str(file)]
            flags += ["--now", "1001"]
            cmd = [sys.executable, str(ROOT / "ghot" / "unheard_choir_vanishing.py")]
            out = subprocess.run(cmd + ["verify"] + flags, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout),
                             {"verified": True, "decision": "HOLD_GOSSIP_REVEALS_UNSEEN_FORK"})

    def test_deep_recheck_inbox_with_public_material(self):
        self.receive()
        previous = verify_inbox(self.common, self.policy, self.log_root, self.roster,
                                self.root, read_inbox(self.inbox), now=1001, recipient="east")
        self.assertEqual(previous, digest(read_inbox(self.inbox)[0]["ack"]))

    def test_demo_drop_loss_resumption_inventory_and_no_native_effect(self):
        r = demo()
        self.assertTrue(r["staged_durably"])
        self.assertTrue(r["first_message_dropped_pending"])
        self.assertTrue(r["restored_from_outbox"])
        self.assertEqual(r["fork_detected_at_recipient"], "HOLD_GOSSIP_REVEALS_UNSEEN_FORK")
        self.assertTrue(r["lost_ack_kept_pending"])
        self.assertTrue(r["anti_entropy_reports_ack_recovery"])
        self.assertTrue(r["inventory_alone_not_ack"])
        self.assertTrue(r["repeat_is_idempotent"])
        self.assertEqual(r["recorded_ack"], "ACKNOWLEDGED")
        self.assertTrue(r["outbox_cleared_by_signed_ack"])
        self.assertTrue(r["recipient_inbox_preserved"])
        self.assertFalse(r["native_external_execution"])


if __name__ == "__main__":
    unittest.main()
