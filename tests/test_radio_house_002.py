"""RADIO HOUSE 002: media-first, owner-local compute. No sockets/OBS/remote identity."""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from ghot.radio_house_002 import (
    CHUNK, MAX_INPUT, connect, enable, observe_media, enqueue, tick, offer,
    cancel, status, verify, favorable_lab_power, demo, digest,
)
from ghot.radio_house_001 import make_packet, spool, verify_spool

TEXT = "PUBLIC SYNTHETIC HASH DATA! " * 70
POWER = favorable_lab_power()


class TestRadioHouseDualNode(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ghot-radio-002-")
        self.root = Path(self.temp.name) / "node"
        self.db = connect(self.root)
        self.now = 1000.0

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def ready(self, text=TEXT, jid="test-hash"):
        enable(self.db, True)
        observe_media(self.db, "IDLE_CONFIRMED", at=self.now)
        enqueue(self.db, jid, text, operator_approved=True)
        return jid

    def work(self, jid="test-hash", power=None, at=None):
        return tick(self.db, jid, POWER if power is None else power,
                    at=self.now if at is None else at)

    def test_default_denies_offer_and_computation(self):
        enqueue(self.db, "test-hash", TEXT, operator_approved=True)
        gate = offer(self.db, POWER, at=self.now)
        self.assertEqual(gate["status"], "HOLD")
        self.assertIn("OWNER_COMPUTE_OPT_IN_ABSENT", gate["reasons"])
        result = self.work()
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["work_done_bytes"], 0)

    def test_enabling_cannot_inherit_old_idle_observation(self):
        observe_media(self.db, "IDLE_CONFIRMED", at=self.now)
        enable(self.db, True)
        self.assertEqual(status(self.db)["media_mode"], "UNKNOWN")
        self.assertEqual(offer(self.db, POWER, at=self.now)["status"], "HOLD")

    def test_operator_fresh_idle_and_true_power_permit_only_local_offer(self):
        self.ready()
        gate = offer(self.db, POWER, at=self.now)
        self.assertEqual(gate["status"], "OFFER_LOCAL_BOUNDED_ONLY")
        self.assertFalse(gate["external_dispatch"])
        self.assertFalse(gate["operator_identity_verified"])
        self.assertEqual(gate["capability"], "compute.public-hash/v0")

    def test_stale_and_future_idle_signal_holds(self):
        self.ready()
        self.assertEqual(self.work(at=self.now+46)["status"], "HOLD")
        self.assertEqual(self.work(at=self.now-1)["status"], "HOLD")
        self.assertEqual(self.work()["status"], "WAITING")

    def test_recording_streaming_editing_unknown_all_retract_compute(self):
        self.ready()
        for i, mode in enumerate(["RECORDING", "STREAMING", "EDITING", "UNKNOWN"]):
            observe_media(self.db, mode, at=self.now+i)
            self.assertEqual(self.work(at=self.now+i)["status"], "HOLD")
        self.assertEqual(status(self.db)["jobs"][0]["cursor"], 0)

    def test_critical_conserve_and_unavailable_gHot_power_holds(self):
        self.ready()
        for state in ["critical", "conserve"]:
            p=dict(POWER, willingness=state)
            r=self.work(power=p)
            self.assertEqual(r["status"], "HOLD")
            self.assertEqual(r["work_done_bytes"], 0)
        self.assertIn("GHOT_POWER_OFFER_WITHDRAWN",
                      self.work(power=dict(POWER,willingness="critical"))["gate"]["reasons"])

    def test_missing_or_battery_power_holds(self):
        self.ready()
        for p in [{}, dict(POWER,source="battery"),
                  dict(POWER,source=None),dict(POWER,temperature_c=None),
                  dict(POWER,load_per_cpu_1m=None)]:
            self.assertEqual(self.work(power=p)["status"], "HOLD")

    def test_high_cpu_and_hot_thermals_hold(self):
        self.ready()
        for p in [dict(POWER,load_per_cpu_1m=0.8),
                  dict(POWER,temperature_c=85)]:
            self.assertEqual(self.work(power=p)["status"], "HOLD")

    def test_one_local_tick_is_bounded_and_real_sha256_work(self):
        self.ready()
        a=self.work()
        self.assertEqual(a["work_done_bytes"], CHUNK)
        self.assertEqual(a["cursor"], CHUNK)
        self.assertEqual(a["status"], "WAITING")
        self.assertTrue(a["checkpoint_hash"].startswith("sha256:"))

    def test_capture_interrupts_midjob_then_resume_at_exact_cursor(self):
        self.ready()
        one=self.work()
        observe_media(self.db, "RECORDING", at=self.now+1)
        blocked=self.work(at=self.now+1)
        self.assertEqual(blocked["status"], "HOLD")
        self.assertEqual(blocked["cursor"], one["cursor"])
        observe_media(self.db, "IDLE_CONFIRMED", at=self.now+2)
        two=self.work(at=self.now+2)
        self.assertEqual(two["cursor"], one["cursor"]+CHUNK)
        self.assertEqual(two["work_done_bytes"], CHUNK)
        self.assertEqual(verify(self.db)["status"], "LOCAL_COLD_REPLAY_VERIFIED")

    def test_recording_priority_and_001_synthetic_media_spool_compose(self):
        self.ready()
        self.work()
        observe_media(self.db, "RECORDING", at=self.now+1)
        self.assertEqual(self.work(at=self.now+1)["work_done_bytes"], 0)
        data=b"SYNTHETIC LOCALLY OWNED AUDIO SAMPLE "*40
        pkt=make_packet(data)
        s={"node":"rock-nigeria","caps":["media.record-local"],"state":"awake"}
        r={"node":"kinship-minnesota","caps":["media.receive-review"],"state":"awake"}
        handoff=spool(pkt,data,self.root/"media",source_node=s,recipient_node=r,
                      source_operator_selected=True,recipient_operator_invited=True)
        result=verify_spool(pkt,handoff["output"])
        self.assertEqual(result["status"], "REVIEW_BYTES_COMPLETE")
        self.assertFalse(result["air_proven"])
        self.assertEqual(status(self.db)["jobs"][0]["cursor"], CHUNK)
        observe_media(self.db,"IDLE_CONFIRMED",at=self.now+2)
        self.assertGreater(self.work(at=self.now+2)["cursor"], CHUNK)

    def test_optout_immediately_holds_next_slice_without_erasing_work(self):
        self.ready()
        one=self.work()
        enable(self.db,False)
        after=self.work()
        self.assertEqual(after["status"],"HOLD")
        self.assertEqual(after["cursor"],one["cursor"])
        self.assertFalse(status(self.db)["operator_enabled"])

    def test_revoked_job_cannot_resume_after_optin(self):
        self.ready()
        self.work()
        self.assertEqual(cancel(self.db,"test-hash")["status"],"CANCELLED")
        self.assertEqual(self.work()["status"],"CANCELLED")
        self.assertRaisesRegex(ValueError,"CANNOT_CANCEL_COMPLETED_WORK",
                               lambda: self._cancel_completed())
        # Cancelled work is terminal even after a new operator consent epoch.
        enable(self.db,False)
        enable(self.db,True)
        observe_media(self.db,"IDLE_CONFIRMED",at=self.now)
        self.assertEqual(self.work()["work_done_bytes"],0)

    def _cancel_completed(self):
        self._complete()
        cancel(self.db,"another-job")

    def _complete(self):
        enqueue(self.db,"another-job","done",operator_approved=True)
        self.work(jid="another-job")

    def test_short_job_completes_with_exact_digest_and_no_further_work(self):
        self.ready(text="public",jid="test-hash")
        r=self.work()
        self.assertEqual(r["status"],"COMPLETE")
        self.assertEqual(r["output_sha256"],digest(b"public"))
        self.assertEqual(self.work()["work_done_bytes"],0)
        self.assertEqual(verify(self.db)["status"],"LOCAL_COLD_REPLAY_VERIFIED")

    def test_operator_can_refuse_per_job_approval_and_invalid_capabilities(self):
        with self.assertRaisesRegex(ValueError,"PER_JOB_APPROVAL_REQUIRED"):
            enqueue(self.db,"bad-job","hello",operator_approved=False)
        with self.assertRaisesRegex(ValueError,"TEXT_ONLY_CAPABILITY"):
            enqueue(self.db,"bad-job",{"execute":"shell"},operator_approved=True)
        self.assertEqual(status(self.db)["jobs"],[])

    def test_quota_duplicate_traversal_and_empty_inputs_refused(self):
        for name,msg in [("../secret","valid"),("BAD","valid"),("ok",""),
                         ("too-large","z"*(MAX_INPUT+1))]:
            with self.assertRaises(ValueError):
                enqueue(self.db,name,msg,operator_approved=True)
        enqueue(self.db,"okay","safe",operator_approved=True)
        with self.assertRaisesRegex(ValueError,"JOB_ALREADY_EXISTS"):
            enqueue(self.db,"okay","safe",operator_approved=True)

    def test_jobs_and_checkpoint_cold_replay_survive_database_restart(self):
        self.ready()
        old=self.work()
        self.db.close()
        self.db=connect(self.root)
        self.assertEqual(status(self.db)["jobs"][0]["cursor"],old["cursor"])
        self.assertEqual(verify(self.db)["status"],"LOCAL_COLD_REPLAY_VERIFIED")
        self.assertEqual(self.work()["cursor"],2*CHUNK)

    def test_two_independent_connections_cannot_duplicate_chunk_cursor(self):
        self.ready()
        outputs=[]
        errors=[]
        def worker():
            other=connect(self.root)
            try: outputs.append(tick(other,"test-hash",POWER,at=self.now))
            except Exception as e: errors.append(str(e))
            finally: other.close()
        threads=[threading.Thread(target=worker) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(errors,[])
        self.assertEqual(sorted(r["cursor"] for r in outputs),[CHUNK,2*CHUNK])
        self.assertEqual(verify(self.db)["status"],"LOCAL_COLD_REPLAY_VERIFIED")

    def test_tampered_job_bytes_or_frame_history_refused(self):
        self.ready()
        self.work()
        self.db.execute("UPDATE jobs SET input_text='malicious' WHERE job_id='test-hash'")
        with self.assertRaisesRegex(ValueError,"JOB_ORIGIN_MUTATED"):
            verify(self.db)
        with self.assertRaisesRegex(ValueError,"PERSISTED_SOURCE_MISMATCH"):
            self.work()

    def test_tampered_audit_link_refused(self):
        self.ready()
        self.work()
        self.db.execute("UPDATE events SET previous='NOPE' WHERE seq=2")
        with self.assertRaisesRegex(ValueError,"AUDIT_LINK_BROKEN"):
            verify(self.db)

    def test_audit_hash_change_refused(self):
        self.ready()
        self.work()
        self.db.execute("UPDATE events SET kind='FALSE_AIR_EVENT' WHERE seq=1")
        with self.assertRaisesRegex(ValueError,"AUDIT_EVENT_TAMPERED"):
            verify(self.db)

    def test_no_real_world_effect_claimed_in_full_demo(self):
        # Demo must use a fresh SQLite root.
        directory=Path(self.temp.name)/"demo2"
        outcome=demo(directory)
        self.assertEqual(outcome["recording_hold"],"HOLD")
        self.assertEqual(outcome["work_done_during_recording_bytes"],0)
        self.assertEqual(outcome["media_packet"],"REVIEW_BYTES_COMPLETE")
        self.assertFalse(outcome["media_aired"])
        self.assertEqual(outcome["compute_final"],"COMPLETE")
        self.assertEqual(outcome["cold_verify"],"LOCAL_COLD_REPLAY_VERIFIED")
        self.assertEqual(outcome["remote_compute_jobs"],0)

if __name__ == "__main__":
    unittest.main()
