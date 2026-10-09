"""Radio House 003: signed source -> independently sovereign local queue -> result."""
import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from ghot.radio_house_002 import connect, enable, observe_media, favorable_lab_power, status, verify as verify_local, cancel
from ghot.radio_house_003 import (
    make_bundle, verify_bundle, accept, advance, settle, verify_return, demo,
)
from ghot.relatte_identity import IdentityKey, sign_crossing, verify_crossing, verify_receipt

POWER = favorable_lab_power()
PUBLIC_INPUT = "synthetic public work " * 41


class SignedWorkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rh3-")
        root = Path(self.tmp.name)
        self.requester = IdentityKey.load_or_create(root / "requester" / "identity" / "key.pem")
        self.receiver = IdentityKey.load_or_create(root / "worker" / "identity" / "key.pem")
        self.conn = connect(root / "worker")
        self.bundle = make_bundle(self.requester, self.receiver.public_jwk(),
                                  "public-001", PUBLIC_INPUT, at=1000)
        self.pin = self.requester.public_jwk()
        self.worker_pin = self.receiver.public_jwk()
        self.at = 1001

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def permit(self):
        enable(self.conn, True)
        observe_media(self.conn, "IDLE_CONFIRMED", at=1001)

    def received(self, *, approved=True, power=POWER):
        return accept(self.conn,self.bundle,receiver_key=self.receiver,
                      pinned_requester_public=self.pin,operator_approved=approved,
                      power=power,at=1001)

    def run(self, *, at=1001, power=POWER):
        return advance(self.conn,self.bundle,receiver_key=self.receiver,
                       pinned_requester_public=self.pin,power=power,at=at)

    def finish(self):
        last=None
        for _ in range(40):
            last=self.run()
            if last["status"]=="COMPLETE":
                break
        self.assertEqual(last["status"],"COMPLETE")
        return settle(self.conn,self.bundle,receiver_key=self.receiver,
                      pinned_requester_public=self.pin,at=1002)

    def test_crossing_is_native_reLATTE_and_payload_binds_exact_bytes(self):
        self.assertTrue(verify_crossing(self.bundle["crossing"]))
        self.assertEqual(self.bundle["crossing"]["schema"],"relatte.crossing-envelope/v0")
        self.assertEqual(self.bundle["crossing"]["signing"]["algorithm"],"ECDSA-P256-SHA256")
        self.assertEqual(verify_bundle(self.bundle,pinned_requester_public=self.pin,
                         expected_worker_public=self.worker_pin,at=1001),
                         self.bundle["crossing"]["crossing_id"])

    def test_signature_does_not_admit_without_local_operator_approval(self):
        with self.assertRaisesRegex(ValueError,"LOCAL_OPERATOR_APPROVAL_MISSING"):
            self.received(approved=False)
        self.assertEqual(status(self.conn)["jobs"],[])

    def test_optin_only_not_enough_media_and_power_must_be_favorable(self):
        enable(self.conn, True)
        with self.assertRaisesRegex(ValueError,"LOCAL_MEDIA_OR_POWER_HOLD"):
            self.received()
        observe_media(self.conn,"IDLE_CONFIRMED",at=1001)
        with self.assertRaisesRegex(ValueError,"LOCAL_MEDIA_OR_POWER_HOLD"):
            self.received(power=dict(POWER,willingness="critical"))
        self.assertEqual(status(self.conn)["jobs"],[])

    def test_two_orgs_separate_private_key_and_sqlite_directories(self):
        self.assertNotEqual(self.requester.particular(),self.receiver.particular())
        self.assertNotEqual(self.requester.private_key_path,self.receiver.private_key_path)
        self.permit()
        result=self.received()
        self.assertEqual(result["kind"],"HELD")
        self.assertEqual(result["semantic_effect"],"local-state-change")
        self.assertEqual(len(status(self.conn)["jobs"]),1)

    def test_media_recording_yields_then_resume_and_signs_real_result(self):
        self.permit()
        held=self.received()
        first=self.run()
        self.assertEqual(first["work_done_bytes"],256)
        observe_media(self.conn,"RECORDING",at=1002)
        blocked=self.run(at=1002)
        self.assertEqual(blocked["status"],"HOLD")
        self.assertEqual(blocked["work_done_bytes"],0)
        observe_media(self.conn,"IDLE_CONFIRMED",at=1003)
        final=None
        for _ in range(40):
            item=self.run(at=1003)
            if item["status"]=="COMPLETE":
                final=settle(self.conn,self.bundle,receiver_key=self.receiver,
                             pinned_requester_public=self.pin,at=1004)
                break
        self.assertIsNotNone(final)
        self.assertTrue(verify_receipt(held))
        self.assertTrue(verify_receipt(final,expected_public_key=self.worker_pin,
                                     expected_receiver_particular=self.receiver.particular()))
        summary=verify_return(self.bundle,held,final,pinned_requester_public=self.pin,
                              pinned_worker_public=self.worker_pin,at=1005)
        self.assertEqual(summary["status"],"SIGNED_CROSSING_AND_LOCAL_HASH_RETURN_VERIFIED")
        self.assertEqual(summary["actual_media_actions"],0)
        self.assertEqual(verify_local(self.conn)["status"],"LOCAL_COLD_REPLAY_VERIFIED")

    def test_manual_courier_bytes_recovered_from_independent_directory(self):
        self.permit()
        courier=Path(self.tmp.name)/"requester"/"courier.json"
        courier.write_text(json.dumps(self.bundle,sort_keys=True),encoding="utf8")
        incoming=json.loads(courier.read_text(encoding="utf8"))
        ack=accept(self.conn,incoming,receiver_key=self.receiver,
                   pinned_requester_public=self.pin,power=POWER,
                   operator_approved=True,at=1001)
        self.assertEqual(ack["kind"],"HELD")
        self.assertEqual(ack["crossing_id"],incoming["crossing"]["crossing_id"])

    def test_duplicate_bundle_is_idempotent_even_if_locally_no_second_approval(self):
        self.permit()
        a=self.received()
        b=self.received(approved=False)
        self.assertEqual(a,b)
        self.assertEqual(len(status(self.conn)["jobs"]),1)

    def test_signed_final_receipt_idempotent(self):
        self.permit()
        held=self.received()
        first=self.finish()
        second=settle(self.conn,self.bundle,receiver_key=self.receiver,
                      pinned_requester_public=self.pin,at=1003)
        self.assertEqual(first,second)
        self.assertEqual(len(status(self.conn)["jobs"]),1)
        self.assertEqual(verify_return(self.bundle,held,first,pinned_requester_public=self.pin,
                                      pinned_worker_public=self.worker_pin,at=1004)["result_sha256"],
                         first["post_state_ref"])

    def test_no_settle_before_finished_and_cancelled_job_cannot_claim_success(self):
        self.permit()
        self.received()
        with self.assertRaisesRegex(ValueError,"WORK_NOT_COMPLETE"):
            settle(self.conn,self.bundle,receiver_key=self.receiver,
                   pinned_requester_public=self.pin,at=1002)
        worker_id=status(self.conn)["jobs"][0]["job_id"]
        cancel(self.conn,worker_id)
        with self.assertRaisesRegex(ValueError,"WORK_NOT_COMPLETE"):
            settle(self.conn,self.bundle,receiver_key=self.receiver,
                   pinned_requester_public=self.pin,at=1002)

    def test_expiry_refused_without_local_admission(self):
        self.permit()
        with self.assertRaisesRegex(ValueError,"CROSSING_EXPIRED"):
            accept(self.conn,self.bundle,receiver_key=self.receiver,
                   pinned_requester_public=self.pin,power=POWER,
                   operator_approved=True,at=1201)
        self.assertEqual(status(self.conn)["jobs"],[])

    def test_wrong_recipient_and_wrong_source_pins_refused(self):
        self.permit()
        unrelated=IdentityKey.load_or_create(Path(self.tmp.name)/"third"/"key.pem")
        with self.assertRaisesRegex(ValueError,"WRONG_WORKER"):
            accept(self.conn,self.bundle,receiver_key=unrelated,
                   pinned_requester_public=self.pin,power=POWER,
                   operator_approved=True,at=1001)
        with self.assertRaisesRegex(ValueError,"REQUESTER_PIN_MISMATCH"):
            accept(self.conn,self.bundle,receiver_key=self.receiver,
                   pinned_requester_public=unrelated.public_jwk(),power=POWER,
                   operator_approved=True,at=1001)

    def test_altered_payload_or_extra_remote_commands_refused(self):
        self.permit()
        for mutate in (
            lambda b: b["payload"].update(text="forged"),
            lambda b: b["payload"].update(command="rm -rf /"),
            lambda b: b["payload"].update(capability="shell.execute"),
            lambda b: b.update(extra="authority"),
        ):
            changed=copy.deepcopy(self.bundle)
            mutate(changed)
            with self.assertRaises(ValueError):
                accept(self.conn,changed,receiver_key=self.receiver,
                       pinned_requester_public=self.pin,power=POWER,
                       operator_approved=True,at=1001)
        self.assertEqual(status(self.conn)["jobs"],[])

    def test_signed_new_effect_or_signature_replacement_not_inherit_authority(self):
        self.permit()
        changed=copy.deepcopy(self.bundle)
        changed["crossing"]["requested_effect"]["action"]="BROADCAST"
        with self.assertRaisesRegex(ValueError,"CROSSING_SIGNATURE_INVALID"):
            self.received_after(changed)
        # Same signer deliberately re-signing a forbidden effect is still denied by profile.
        changed["crossing"]=sign_crossing(changed["crossing"],self.requester)
        with self.assertRaisesRegex(ValueError,"WRONG_WORKER_OR_ACTION"):
            self.received_after(changed)

    def received_after(self,b):
        return accept(self.conn,b,receiver_key=self.receiver,
                      pinned_requester_public=self.pin,power=POWER,
                      operator_approved=True,at=1001)

    def test_wrong_receiver_receipt_key_rejected_by_requester(self):
        self.permit()
        ack=self.received()
        finished=self.finish()
        wrong=IdentityKey.load_or_create(Path(self.tmp.name)/"third"/"key.pem")
        with self.assertRaisesRegex(ValueError,"WORKER_RECEIPT_SIGNATURE_OR_PIN"):
            verify_return(self.bundle,ack,finished,pinned_requester_public=self.pin,
                          pinned_worker_public=wrong.public_jwk(),at=1004)

    def test_false_signed_completion_result_is_recomputed_and_rejected(self):
        self.permit()
        ack=self.received()
        result=self.finish()
        altered=copy.deepcopy(result)
        altered["post_state_ref"]="sha256:"+("1"*64)
        with self.assertRaisesRegex(ValueError,"WORKER_RECEIPT_SIGNATURE_OR_PIN_INVALID"):
            verify_return(self.bundle,ack,altered,pinned_requester_public=self.pin,
                          pinned_worker_public=self.worker_pin,at=1004)

    def test_corrupt_local_worker_data_refuses_final_signature(self):
        self.permit()
        self.received()
        self.finish()
        # Signature is already sealed; local historic worker validation still detects tamper.
        worker_id=status(self.conn)["jobs"][0]["job_id"]
        self.conn.execute("UPDATE jobs SET input_text='bad' WHERE job_id=?",(worker_id,))
        with self.assertRaisesRegex(ValueError,"JOB_ORIGIN_MUTATED"):
            verify_local(self.conn)

    def test_restart_preserves_signed_receipt_and_no_second_work(self):
        self.permit()
        ack=self.received()
        final=self.finish()
        self.conn.close()
        self.conn=connect(Path(self.tmp.name)/"worker")
        returned=settle(self.conn,self.bundle,receiver_key=self.receiver,
                        pinned_requester_public=self.pin,at=1004)
        self.assertEqual(returned,final)
        self.assertEqual(len(status(self.conn)["jobs"]),1)
        self.assertEqual(ack,self.received(approved=False))

    def test_power_loss_mid_crossing_and_stale_idle_holds(self):
        self.permit()
        self.received()
        before=self.run()
        blocked=self.run(at=1050)
        self.assertEqual(blocked["status"],"HOLD")
        self.assertEqual(blocked["cursor"],before["cursor"])
        self.assertEqual(verify_local(self.conn)["status"],"LOCAL_COLD_REPLAY_VERIFIED")

    def test_cold_demo_crosses_two_local_keys_but_zero_network_calls(self):
        out=Path(self.tmp.name)/"fresh_demo"
        result=demo(out)
        self.assertEqual(result["status"],"SIGNED_CROSSING_AND_LOCAL_HASH_RETURN_VERIFIED")
        self.assertEqual(result["media_interruption"],"HOLD")
        self.assertEqual(result["compute_during_recording_bytes"],0)
        self.assertEqual(result["final_compute"],"COMPLETE")
        self.assertEqual(result["live_network_calls"],0)
        self.assertEqual(result["media_broadcasts"],0)
        self.assertFalse(result["donated_work_claim"])

if __name__=="__main__":
    unittest.main()
