"""Hostile boundary checks for RADIO HOUSE 001."""
import tempfile
import unittest
from pathlib import Path
from ghot.radio_house_001 import (make_packet, evaluate, spool,
                                  verify_spool, demo, digest, canonical)

BYTES = b"FAKE AUDIO / LOCAL PROVENANCE" * 23

def bodies():
    return (
        {"node": "rock-nigeria", "caps": ["media.record-local"], "state": "awake"},
        {"node": "kinship-minnesota", "caps": ["media.receive-review"], "state": "awake"},
    )

class TestRadioHouse(unittest.TestCase):
    def setUp(self):
        self.p = make_packet(BYTES)
        self.sender, self.receiver = bodies()
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def transfer(self, **kwargs):
        return spool(self.p, BYTES, self.dir.name,
                     source_node=self.sender, recipient_node=self.receiver,
                     source_operator_selected=True, recipient_operator_invited=True,
                     **kwargs)

    def test_first_gate_holds_without_both_humans(self):
        gate = evaluate(self.p, self.sender, self.receiver)
        self.assertEqual(gate["status"], "HOLD")
        self.assertIn("SOURCE_OWNER_SELECTION_ABSENT", gate["reasons"])
        self.assertIn("RECIPIENT_INVITATION_ABSENT", gate["reasons"])

    def test_operator_inputs_are_not_authenticated_roles(self):
        gate = evaluate(self.p, self.sender, self.receiver,
                        source_operator_selected=True, recipient_operator_invited=True)
        self.assertEqual(gate["status"], "READY_FOR_OFFLINE_REVIEW_SPOOL")
        self.assertFalse(gate["source_operator_selection_authenticated"])
        self.assertFalse(gate["station_air_authorized"])

    def test_first_real_file_is_review_only(self):
        r = self.transfer()
        self.assertEqual(r["status"], "HELD_FOR_RECIPIENT_LOCAL_REVIEW")
        out = verify_spool(self.p, r["output"])
        self.assertEqual(out["status"], "REVIEW_BYTES_COMPLETE")
        self.assertFalse(out["air_proven"])
        self.assertFalse(out["recipient_review_accepted"])

    def test_one_power_loss_resumes_without_double_copied_bytes(self):
        first = self.transfer(max_new_chunks=1)
        self.assertEqual(first["status"], "INCOMPLETE_RETRYABLE")
        second = self.transfer(max_new_chunks=1)
        self.assertEqual(second["receipt"]["chunks_present"], 2)
        last = self.transfer()
        self.assertEqual(last["status"], "HELD_FOR_RECIPIENT_LOCAL_REVIEW")
        replay = self.transfer()
        self.assertEqual(replay["receipt"]["chunks_written"], 0)

    def test_budget_can_hold_and_only_allow_finite_transfer(self):
        gate = evaluate(self.p, self.sender, self.receiver,
                        source_operator_selected=True, recipient_operator_invited=True,
                        local_budget_bytes=0)
        self.assertEqual(gate["status"], "HOLD")
        r = self.transfer(local_budget_bytes=32)
        self.assertEqual(r["receipt"]["chunks_written"], 1)

    def test_missing_recipient_invitation_never_writes_payload(self):
        r = spool(self.p, BYTES, self.dir.name, source_node=self.sender,
                  recipient_node=self.receiver, source_operator_selected=True)
        self.assertEqual(r["status"], "HOLD")
        self.assertEqual(list(Path(self.dir.name).iterdir()), [])

    def test_source_withdrawal_blocks_new_transfer(self):
        self.p["withdrawn"] = True
        r = self.transfer()
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("SOURCE_WITHDRAWN", r["gate"]["reasons"])

    def test_missing_capability_and_offline_power_hold(self):
        self.sender["caps"] = []
        self.assertEqual(self.transfer()["status"], "HOLD")
        self.sender["caps"] = ["media.record-local"]
        self.sender["state"] = "conserve"
        self.assertEqual(self.transfer()["status"], "HOLD")
        self.sender["state"] = "awake"
        self.receiver["state"] = "offline"
        self.assertEqual(self.transfer()["status"], "HOLD")

    def test_mismatched_node_declared_custody_holds(self):
        self.receiver["node"] = "third-party-node"
        self.assertEqual(self.transfer()["status"], "HOLD")

    def test_file_bytes_mutation_refused(self):
        original = self.transfer()
        p = Path(original["output"]) / "chunks" / "000000.bin"
        p.write_bytes(b"X" * 32)
        with self.assertRaisesRegex(ValueError, "CHUNK_REPLAY_TAMPERED"):
            self.transfer()
        with self.assertRaisesRegex(ValueError, "FINAL_HASH_MISMATCH"):
            verify_spool(self.p, original["output"])

    def test_packet_mutation_denied(self):
        self.transfer()
        self.p["rights_reference"] = "NOT THE ORIGINAL"
        with self.assertRaisesRegex(ValueError, "EXISTING_PACKET_TAMPERED"):
            self.transfer()

    def test_forged_bytes_and_digest_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_BYTES_MISMATCH"):
            spool(self.p, BYTES + b"more", self.dir.name,
                  source_node=self.sender, recipient_node=self.receiver,
                  source_operator_selected=True, recipient_operator_invited=True)

    def test_packet_does_not_accept_grants_or_pii_extensions(self):
        self.p["broadcast_authority"] = True
        with self.assertRaisesRegex(ValueError, "PACKET_FIELDS_INVALID"):
            self.transfer()
        del self.p["broadcast_authority"]
        self.p["donor_emails"] = ["synthetic@example.invalid"]
        with self.assertRaisesRegex(ValueError, "PACKET_FIELDS_INVALID"):
            self.transfer()

    def test_packet_path_traversal_or_full_url_rejected(self):
        for name in ("../evil", "http://destination", "UPPER", ""):
            with self.assertRaises(ValueError):
                make_packet(BYTES, packet_id=name)

    def test_receiver_unknown_extra_chunk_rejected(self):
        r = self.transfer()
        (Path(r["output"]) / "chunks" / "999999.bin").write_bytes(b"injected")
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_UNSAFE_CHUNK"):
            verify_spool(self.p, r["output"])

    def test_full_demo_no_network_no_air(self):
        d = demo(self.dir.name)
        self.assertEqual(d["first_gate"], "HOLD")
        self.assertEqual(d["first_transfer"], "INCOMPLETE_RETRYABLE")
        self.assertEqual(d["verification"], "REVIEW_BYTES_COMPLETE")
        self.assertEqual(d["air"], "NOT_PERFORMED")

if __name__ == "__main__":
    unittest.main()
