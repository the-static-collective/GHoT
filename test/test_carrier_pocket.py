"""POSTAL-CORPS-002: offline handoff QR, two-device exchange, durable recovery."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ghot"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from relatte_identity import IdentityKey, jcs_bytes
from postal_corps import ROLES, RULES, act, make_route, replay, sha
from carrier_pocket import (
    PocketJournal, make_challenge, make_response, verify_challenge,
    verify_response, DOMAIN_EVENT, DOMAIN_RESPONSE, DOMAIN_CHALLENGE
)
from test_postal_corps import fixture_dispatch


class PocketTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir=Path(d.name)
        self.keys={role:IdentityKey.load_or_create(self.dir/"keys"/(role+".pem"))
                   for role in ROLES}
        self.stranger=IdentityKey.load_or_create(self.dir/"keys"/"stranger.pem")
        self.dispatch=fixture_dispatch()
        self.route=make_route(self.dispatch,"e"*64,self.keys)
        self.a=self.open("station-a")
        self.b=self.open("carrier-phone")
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def open(self,name):
        return PocketJournal(self.dir/(name+".sqlite3"),self.route,self.dispatch)

    def seed_accept(self, action="ACCEPT_LEG1"):
        events=act(self.route,self.dispatch,self.a.events(),action,
                   {r:self.keys[r] for r in RULES[action][2]},
                   sha(action.encode()))
        envelope=self.a.export_history()
        envelope["events"]=events
        self.a.sync_history(envelope)
        self.b.sync_history(envelope)

    def first_qr(self):
        self.seed_accept()
        return self.a.issue("PICKUP_LEG1",self.keys["origin"],sha(b"synthetic-seal"))

    def first_ack(self):
        qr=self.first_qr()
        reply=self.b.respond(qr,self.keys["carrier1"])
        return qr,reply

    def test_two_device_qr_round_trip_is_native_legacy_event(self):
        qr,reply=self.first_ack()
        self.assertEqual(reply["response_body"]["nonce"],qr["body"]["nonce"])
        nonce,pkt=verify_response(self.route,self.dispatch,reply,self.a.events())
        self.assertEqual(nonce,qr["body"]["nonce"])
        self.assertEqual(set(pkt["signatures"]),{"origin","carrier1"})
        self.a.commit(reply)
        self.assertEqual(self.a.state()["state"],"LEG1_MOVING_CLAIM")
        self.assertEqual(self.b.state()["state"],"LEG1_ACCEPTED")
        self.assertEqual(self.b.sync_history(self.a.export_history()),1)
        self.assertEqual(self.b.state()["state"],"LEG1_MOVING_CLAIM")
        self.assertFalse(self.a.state()["physical_parcel_observed"])
        self.assertFalse(self.a.state()["deed_awarded"])
        self.assertEqual(self.a.state()["penny_released"],0)

    def test_interruption_after_reply_cold_restart_recovery(self):
        qr,reply=self.first_ack()
        nonce=qr["body"]["nonce"]
        self.assertEqual(self.a.state()["pending_issued"],1)
        self.b.close()
        self.b=self.open("carrier-phone")
        self.assertEqual(self.b.state()["outgoing_unsynced"],1)
        recovered=self.b.recover_outbox(nonce)
        self.assertEqual(recovered,reply)
        self.a.close()
        self.a=self.open("station-a")
        self.a.commit(recovered)
        self.assertEqual(self.a.state()["pending_issued"],0)
        self.assertEqual(self.a.state()["state"],"LEG1_MOVING_CLAIM")

    def test_repeated_ack_is_idempotent_not_a_second_handoff(self):
        _,reply=self.first_ack()
        one=self.a.commit(reply)
        two=self.a.commit(reply)
        self.assertEqual(one,two)
        self.assertEqual(self.a.state()["event_count"],2)

    def test_double_qr_competing_for_same_state_is_held(self):
        self.seed_accept()
        q1=self.a.issue("PICKUP_LEG1",self.keys["origin"],sha(b"evidence1"))
        q2=self.a.issue("PICKUP_LEG1",self.keys["origin"],sha(b"evidence2"))
        r1=self.b.respond(q1,self.keys["carrier1"])
        self.a.commit(r1)
        with self.assertRaisesRegex(ValueError,"stale"):
            self.a.commit(make_response(self.route,self.dispatch,
                                        self.b.events(),q2,self.keys["carrier1"]))
        self.assertEqual(self.a.state()["event_count"],2)

    def test_tampered_parcel_hash_invalidates_qr(self):
        q=self.first_qr()
        q=copy.deepcopy(q)
        q["body"]["parcel_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"QR route or effect mismatch"):
            verify_challenge(self.route,self.dispatch,q,self.b.events())

    def test_wrong_responding_role_denied(self):
        qr=self.first_qr()
        with self.assertRaisesRegex(ValueError,"does not match role"):
            self.b.respond(qr,self.keys["carrier2"])

    def test_tampered_ack_signature_denied(self):
        qr,reply=self.first_ack()
        r=copy.deepcopy(reply)
        r["response_body"]["nonce"]="f"*32
        with self.assertRaisesRegex(ValueError,"does not acknowledge"):
            self.a.commit(r)

    def test_wrong_event_signature_denied(self):
        qr,reply=self.first_ack()
        r=copy.deepcopy(reply)
        r["event_proof"]=self.stranger.sign(DOMAIN_EVENT+jcs_bytes(qr["body"]["event"]))
        with self.assertRaisesRegex(ValueError,"responder event signature"):
            self.a.commit(r)

    def test_relay_must_have_compatible_signed_history(self):
        self.seed_accept()
        divergent=act(self.route,self.dispatch,self.b.events(),"PICKUP_LEG1",
                      {"origin":self.keys["origin"],"carrier1":self.keys["carrier1"]},
                      sha(b"alternate"))
        other=act(self.route,self.dispatch,self.a.events(),"PICKUP_LEG1",
                  {"origin":self.keys["origin"],"carrier1":self.keys["carrier1"]},
                  sha(b"different"))
        env=self.a.export_history()
        env["events"]=other
        self.a.sync_history(env)
        env2=self.b.export_history()
        env2["events"]=divergent
        with self.assertRaisesRegex(ValueError,"HOLD_FORK"):
            self.a.sync_history(env2)
        self.assertEqual(self.a.state()["event_count"],2)

    def test_bad_history_source_or_signature_refused(self):
        self.seed_accept()
        wrong=self.a.export_history()
        wrong["route_hash"]="a"*64
        with self.assertRaisesRegex(ValueError,"wrong route"):
            self.b.sync_history(wrong)
        wrong=self.a.export_history()
        wrong["events"][0]["body"]["evidence_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"invalid .* signature"):
            self.b.sync_history(wrong)

    def test_expired_qr_refused(self):
        q=self.first_qr()
        with self.assertRaisesRegex(ValueError,"expired"):
            verify_challenge(self.route,self.dispatch,q,self.b.events(),
                             now=q["body"]["expires_at"]+1)

    def test_future_dated_qr_refused(self):
        q=self.first_qr()
        with self.assertRaisesRegex(ValueError,"future"):
            verify_challenge(self.route,self.dispatch,q,self.b.events(),
                             now=q["body"]["issued_at"]-61)

    def test_stale_scan_before_sync_is_refused(self):
        self.seed_accept()
        q=self.a.issue("PICKUP_LEG1",self.keys["origin"],sha(b"e"))
        c=self.open("new-unsynced-phone")
        try:
            with self.assertRaisesRegex(ValueError,"stale"):
                c.respond(q,self.keys["carrier1"])
        finally:
            c.close()

    def test_challenge_cannot_turn_into_delivery_or_financial_effect(self):
        q=self.first_qr()
        changed=copy.deepcopy(q)
        changed["body"]["scope"]="PAID_REAL_DELIVERY"
        with self.assertRaisesRegex(ValueError,"QR route or effect mismatch"):
            verify_challenge(self.route,self.dispatch,changed,self.b.events())

    def test_unknown_qr_cannot_be_committed_by_another_station(self):
        q,r=self.first_ack()
        other=self.open("unregistered-station")
        try:
            other.sync_history(self.a.export_history())
            with self.assertRaisesRegex(ValueError,"never issued"):
                other.commit(r)
        finally:
            other.close()

    def test_single_route_bound_to_db_across_restarts(self):
        q=self.first_qr()
        alt=copy.deepcopy(self.route)
        alt["parcel_sha256"]="0"*64
        with self.assertRaises(ValueError):
            PocketJournal(self.dir/"station-a.sqlite3",alt,self.dispatch)

    def test_cannot_issue_qr_instead_of_first_acceptance(self):
        with self.assertRaisesRegex(ValueError,"handoff not permitted"):
            self.a.issue("PICKUP_LEG1",self.keys["origin"],sha(b"evidence"))

    def test_recover_unknown_outbox_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"outgoing receipt missing"):
            self.b.recover_outbox("0"*32)

    def test_receipt_replay_can_advance_only_once_after_restart(self):
        q,r=self.first_ack()
        self.a.commit(r)
        self.a.close()
        self.a=self.open("station-a")
        self.assertEqual(self.a.state()["event_count"],2)
        self.a.commit(r)
        self.assertEqual(self.a.state()["event_count"],2)

    def test_legacy_handoffs_still_support_refusal_and_loss(self):
        self.seed_accept()
        q,r=self.first_ack() if False else (None,None)
        with self.assertRaisesRegex(ValueError,"handoff not permitted"):
            self.a.issue("HANDOFF_RELAY",self.keys["carrier1"],sha(b"test"))


if __name__=="__main__":
    unittest.main()
