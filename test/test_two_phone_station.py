"""POSTAL-CORPS-003: actual Node WebCrypto two phone evidence -> GHoT import."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ghot"))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from two_phone_station import reconcile
from relatte_identity import jcs_bytes
from test_postal_corps import fixture_dispatch


class StationReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.dispatch=cls.root/"native-dispatch.json"
        cls.dispatch.write_text(json.dumps(fixture_dispatch()))
        cls.artifact=cls.root/"fieldkit.json"
        result=subprocess.run(
            ["node",str(Path(__file__).with_name("two_phones_webcrypto.cjs")),
             str(cls.dispatch),str(cls.artifact)],
            capture_output=True,text=True
        )
        if result.returncode:
            raise RuntimeError(result.stdout+"\n"+result.stderr)
        cls.bundle=json.loads(cls.artifact.read_text())
        cls.origin=cls.bundle["route"]["role_pins"]["origin"]
        cls.carrier=cls.bundle["route"]["role_pins"]["carrier1"]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.journal=self.root/(self.id().replace(".","-")+".sqlite3")

    def run_review(self,payload=None,pin_a=None,pin_b=None,at=None):
        return reconcile(payload or self.bundle,self.journal,
                         pin_a or self.origin,pin_b or self.carrier,at)

    def test_both_phones_match_native_authoritative_history(self):
        result=self.run_review()
        self.assertEqual(result["state"],"SYNTHETIC_HANDOFF_ADMITTED")
        self.assertTrue(result["station_accepted"])
        self.assertEqual(result["history_head"],self.bundle["claimed_head"])
        self.assertEqual(result["event_count"],2)
        self.assertFalse(result["physical_delivery_observed"])
        self.assertEqual(result["penny_units"],0)
        self.assertEqual(result["full_measure_deeds"],0)

    def test_duplicate_reconciliation_is_idempotent(self):
        self.assertEqual(self.run_review(),self.run_review())

    def test_restart_recovers_native_journal(self):
        from carrier_pocket import PocketJournal
        self.run_review()
        journal=PocketJournal(self.journal,self.bundle["route"],self.bundle["dispatch"])
        try:
            self.assertEqual(journal.state()["state"],"LEG1_MOVING_CLAIM")
            self.assertEqual(journal.state()["event_count"],2)
        finally:journal.close()

    def test_false_human_identity_trust_pin_is_refused(self):
        wrong=copy.deepcopy(self.carrier)
        wrong["x"]="A"*43
        with self.assertRaises(ValueError):
            self.run_review(pin_b=wrong)
        self.assertFalse(self.journal.exists())

    def test_other_origin_pin_is_refused(self):
        with self.assertRaisesRegex(ValueError,"origin key differs"):
            self.run_review(pin_a=self.carrier)

    def test_reported_financial_effect_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["penny_units_released"]=1
        with self.assertRaisesRegex(ValueError,"economic"):
            self.run_review(bogus)

    def test_forged_full_measure_deed_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["full_measure_deeds"]=1
        with self.assertRaisesRegex(ValueError,"economic"):
            self.run_review(bogus)

    def test_real_physical_delivery_claim_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["physical_parcel_observed"]=True
        with self.assertRaisesRegex(ValueError,"physical"):
            self.run_review(bogus)

    def test_untrusted_address_leak_rejected(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["recipient_home_address"]="real address"
        with self.assertRaisesRegex(ValueError,"structure"):
            self.run_review(bogus)

    def test_altered_response_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["response"]["response_body"]["nonce"]="0"*32
        with self.assertRaisesRegex(ValueError,"response does not acknowledge"):
            self.run_review(bogus)

    def test_missing_b_signer_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["events"][0]["signatures"]["carrier1"]="forged"
        with self.assertRaisesRegex(ValueError,"invalid .* signature"):
            self.run_review(bogus)

    def test_head_mismatch_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["claimed_head"]="f"*64
        with self.assertRaisesRegex(ValueError,"head mismatch"):
            self.run_review(bogus)

    def test_stale_after_offline_delay_is_held_without_writing(self):
        late=self.bundle["challenge"]["body"]["expires_at"]+60
        result=self.run_review(at=late)
        self.assertEqual(result["state"],"HOLD_EXPIRED")
        self.assertFalse(result["station_accepted"])
        self.assertFalse(self.journal.exists())

    def test_alt_parcel_hash_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["route"]["parcel_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"route signature invalid"):
            self.run_review(bogus)

    def test_duplicate_leg_replay_refused(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["events"]=[self.bundle["events"][0],self.bundle["events"][0]]
        with self.assertRaisesRegex(ValueError,"impossible|stale|unexpected two-phone event sequence"):
            self.run_review(bogus)

    def test_new_carrier_witness_cannot_be_minted(self):
        bogus=copy.deepcopy(self.bundle)
        bogus["route"]["role_pins"]["carrier1"]=self.origin
        with self.assertRaises(ValueError):
            self.run_review(bogus)


if __name__=="__main__":unittest.main()
