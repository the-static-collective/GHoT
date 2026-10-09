"""POSTAL-CORPS-001 — role-signed synthetic physical route, no real delivery."""
from __future__ import annotations
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ghot"))
from relatte_identity import IdentityKey
from postal_corps import (
    ROLES, RULES, act, dispatch_gate_candidate, make_route,
    output_proposals, replay, sha, specimen, verify_route,
)


def fixture_dispatch():
    return {
        "dispatch_version":"dispatch-gate-001",
        "packet_id":"parcel-specimen-001",
        "work_id":"synthetic-work",
        "edition_id":"synthetic-edition",
        "recipient_id":"specimen:fictional-recipient",
        "packet_manifest_sha256":"f"*64,
        "carrier_selection":{
            "carrier":"POSTAL-CORPS-SIMULATION",
            "service":"offline-specimen",
            "state":"human_selected",
            "selected_at_utc":"2026-10-09T19:00:00+00:00",
        },
        "postage":None, "state":"service_selected",
        "events":[{"event":"service_selected","at_utc":"2026-10-09T19:00:00+00:00","note":"simulated"}],
        "privacy":{"record_disposition":"local_only","rule":"DELIVERY DATA != PUBLICATION METADATA"},
        "law":["LABEL != POSTAGE", "POSTAGE != TENDER", "TRACKING CREATED != IN TRANSIT",
               "TENDER != DELIVERY", "DELIVERED != READ"],
    }


class PostalCorpsTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        d=Path(t.name)
        self.signers={
            role:IdentityKey.load_or_create(d/(role+".pem"))
            for role in ROLES
        }
        self.stranger=IdentityKey.load_or_create(d/"stranger.pem")
        self.dispatch=fixture_dispatch()
        self.route=make_route(self.dispatch,"e"*64,self.signers)
        self.events=[]

    def step(self,action,roles=None,digest=None):
        self.events=act(
            self.route,self.dispatch,self.events,action,
            roles or {r:self.signers[r] for r in RULES[action][2]},
            digest or sha(action.encode()),
        )
        return self.events

    def through(self,actions):
        for a in actions: self.step(a)

    def to_relay(self):
        self.through(["ACCEPT_LEG1","PICKUP_LEG1","HANDOFF_RELAY"])

    def to_recipient(self):
        self.to_relay()
        self.through(["ACCEPT_LEG2","PICKUP_LEG2","DELIVER_RECIPIENT"])

    def completed(self):
        self.to_recipient()
        self.through(["REPORT_LEG1","REPORT_LEG2","WITNESS_LEG1","WITNESS_LEG2"])

    def test_complete_two_carrier_specimen_is_only_proposals(self):
        route, events, result=specimen(self.signers,self.dispatch,b"%PDF-1.4\nsynthetic")
        self.assertEqual(len(events),10)
        self.assertEqual(result["carrier"]["state"],"WORK_REVIEW_READY")
        fm,p=result["full_measure"],result["penny"]
        self.assertEqual(fm["deed_state"],"NOT_AWARDED")
        self.assertTrue(fm["eligible_for_human_review"])
        self.assertFalse(fm["official_full_measure_event_created"])
        self.assertEqual(p["status"],"NO_TREASURY_EVENT")
        self.assertEqual(p["active_units"],0)
        self.assertEqual(p["released_units"],0)
        self.assertEqual(p["book_coins"],0)
        self.assertIsNone(p["work_witness_proof"])
        self.assertEqual(len(p["candidate_work_payloads"]),2)
        self.assertEqual([v["holderId"] for v in p["candidate_work_payloads"]],
                         ["person:synthetic-carrier1","person:synthetic-carrier2"])
        self.assertEqual(replay(route,self.dispatch,events)["event_count"],10)

    def test_no_quest_reward_on_offer(self):
        p=output_proposals(self.route,self.dispatch,[])
        self.assertFalse(p["full_measure"]["eligible_for_human_review"])
        self.assertEqual(p["penny"]["candidate_work_payloads"],[])

    def test_carrier1_can_refuse_without_negative_score(self):
        self.step("REFUSE_LEG1")
        self.assertEqual(replay(self.route,self.dispatch,self.events)["state"],"REFUSED")
        with self.assertRaisesRegex(ValueError,"not admitted"):
            self.step("ACCEPT_LEG1")
        self.assertEqual(output_proposals(self.route,self.dispatch,self.events)["penny"]["candidate_work_payloads"],[])

    def test_carrier2_can_refuse_at_relay(self):
        self.to_relay()
        self.step("REFUSE_LEG2")
        self.assertEqual(replay(self.route,self.dispatch,self.events)["state"],"REFUSED_AT_RELAY")
        with self.assertRaisesRegex(ValueError,"not admitted"):
            self.step("PICKUP_LEG2")

    def test_carrier1_loss_holds(self):
        self.through(["ACCEPT_LEG1","PICKUP_LEG1","LOST_LEG1"])
        self.assertEqual(replay(self.route,self.dispatch,self.events)["state"],"LOSS_REPORTED")
        self.assertFalse(output_proposals(self.route,self.dispatch,self.events)["full_measure"]["eligible_for_human_review"])

    def test_carrier2_loss_holds(self):
        self.to_relay()
        self.through(["ACCEPT_LEG2","PICKUP_LEG2","LOST_LEG2"])
        self.assertEqual(replay(self.route,self.dispatch,self.events)["state"],"LOSS_REPORTED")
        self.assertEqual(output_proposals(self.route,self.dispatch,self.events)["penny"]["candidate_work_payloads"],[])

    def test_late_dispute_withdraws_work_proposal(self):
        self.completed()
        before=output_proposals(self.route,self.dispatch,self.events)
        self.assertEqual(len(before["penny"]["candidate_work_payloads"]),2)
        self.step("DISPUTE")
        after=output_proposals(self.route,self.dispatch,self.events)
        self.assertEqual(after["carrier"]["state"],"DISPUTED")
        self.assertEqual(after["penny"]["candidate_work_payloads"],[])
        self.assertNotEqual(before["carrier"]["history_head"],after["carrier"]["history_head"])
        self.assertFalse(after["full_measure"]["eligible_for_human_review"])

    def test_cannot_skip_receiver_or_handoff(self):
        with self.assertRaisesRegex(ValueError,"not admitted"):
            self.step("DELIVER_RECIPIENT")
        self.step("ACCEPT_LEG1")
        with self.assertRaisesRegex(ValueError,"not admitted"):
            self.step("HANDOFF_RELAY")

    def test_duplicate_handoff_refused(self):
        self.to_relay()
        with self.assertRaisesRegex(ValueError,"not admitted"):
            self.step("HANDOFF_RELAY")

    def test_wrong_role_signing_identity_refused(self):
        with self.assertRaisesRegex(ValueError,"wrong independent signing identity"):
            self.step("ACCEPT_LEG1",roles={"carrier1":self.stranger})

    def test_missing_joint_custody_signer_refused(self):
        self.step("ACCEPT_LEG1")
        with self.assertRaisesRegex(ValueError,"wrong signing roles"):
            self.step("PICKUP_LEG1",roles={"carrier1":self.signers["carrier1"]})

    def test_wrong_evidence_hash_refused(self):
        with self.assertRaisesRegex(ValueError,"exact evidence digest"):
            self.step("ACCEPT_LEG1",digest="not-hash")

    def test_tampered_handoff_refused_on_cold_replay(self):
        self.to_relay()
        altered=copy.deepcopy(self.events)
        altered[1]["body"]["evidence_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"invalid .* signature"):
            replay(self.route,self.dispatch,altered)

    def test_role_signatures_cannot_be_swapped(self):
        self.to_relay()
        altered=copy.deepcopy(self.events)
        pair=altered[2]["signatures"]
        pair["carrier1"],pair["relay"]=pair["relay"],pair["carrier1"]
        with self.assertRaisesRegex(ValueError,"invalid .* signature"):
            replay(self.route,self.dispatch,altered)

    def test_events_cannot_be_reordered(self):
        self.to_relay()
        altered=self.events[::-1]
        with self.assertRaisesRegex(ValueError,"stale or duplicate"):
            replay(self.route,self.dispatch,altered)

    def test_changed_lemon_dispatch_record_refused(self):
        changed=copy.deepcopy(self.dispatch)
        changed["packet_manifest_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"source LemonPRESS dispatch changed"):
            verify_route(self.route,changed)

    def test_fake_dispatch_tender_or_postage_refused(self):
        bad=copy.deepcopy(self.dispatch)
        bad["state"]="tendered"
        with self.assertRaisesRegex(ValueError,"un-postaged"):
            dispatch_gate_candidate(bad)
        bad=copy.deepcopy(self.dispatch)
        bad["postage"]={"source":"imaginary"}
        with self.assertRaisesRegex(ValueError,"un-postaged"):
            dispatch_gate_candidate(bad)

    def test_real_recipient_details_refused(self):
        bad=copy.deepcopy(self.dispatch)
        bad["recipient_id"]="real.person@example.com"
        with self.assertRaisesRegex(ValueError,"real recipient data prohibited"):
            dispatch_gate_candidate(bad)

    def test_other_service_selection_denied(self):
        bad=copy.deepcopy(self.dispatch)
        bad["carrier_selection"]["carrier"]="USPS"
        with self.assertRaisesRegex(ValueError,"simulated carrier"):
            dispatch_gate_candidate(bad)

    def test_source_route_cannot_be_rewritten(self):
        bad=copy.deepcopy(self.route)
        bad["parcel_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"route signature invalid"):
            verify_route(bad,self.dispatch)

    def test_distinct_signers_required(self):
        actors=dict(self.signers)
        actors["relay"]=actors["origin"]
        with self.assertRaisesRegex(ValueError,"cannot be reused"):
            make_route(self.dispatch,"e"*64,actors)

    def test_stale_prior_digest_denied(self):
        self.to_relay()
        bad=copy.deepcopy(self.events)
        bad[2]["body"]["prior_event_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"stale or duplicate"):
            replay(self.route,self.dispatch,bad)

    def test_penny_cannot_be_created_before_independent_witness(self):
        self.to_recipient()
        self.through(["REPORT_LEG1","REPORT_LEG2","WITNESS_LEG1"])
        p=output_proposals(self.route,self.dispatch,self.events)
        self.assertEqual(p["penny"]["candidate_work_payloads"],[])
        self.assertEqual(p["full_measure"]["deed_state"],"NOT_AWARDED")

if __name__=="__main__":
    unittest.main()
