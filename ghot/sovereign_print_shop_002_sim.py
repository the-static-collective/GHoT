#!/usr/bin/env python3
"""Hostile contract tests for the independent native multi-repo shop bridge.

The synthetic fixture below is NOT a native CAD or Ed25519 verifier. Only the
run_lab path may assert successful native verification after executing donors.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from printer_organ import digest, load_owner_manifest, observe, propose, verify_source_request
from sovereign_print_shop_002 import (
    NATIVE_SELECTED, validate_binding, pin_checkout, run_lab, file_json
)

ROOT=Path(__file__).resolve().parents[1]
OWNER_PATH=ROOT/"fixtures/sovereign-print-shop-002/fff-owner.json"
OWNER=json.loads(OWNER_PATH.read_text())


def source():
    nodes=[]
    for name,tech,compat in [
        ("example:machine-01","FFF_FDM","HOLD_MACHINE_PROFILE"),
        ("example:machine-02","MSLA","HOLD_PROCESS_ADAPTER"),
        ("virtual:fff-pla-180","FFF_FDM","SOFTWARE_TOOLPATH_ONLY")
    ]:
        nodes.append({
            "machine_id":name,"technology":tech,"published_compatibility":compat,
            "reason":"SOURCE_SELECTED_UNVERIFIED",
            "hardware_authenticated":False,"physical_print_permission":False
        })
    body={
        "schema":"static-os.fabrication-request/v0",
        "source_repository":"the-static-collective/static-os",
        "original_field_id":"static-os-printer-field-012:simulated-source",
        "original_signed_cad_crossing_id":"relatte-original-crossing-ref-simulated",
        "source_design_candidate_id":"fixture-cad-proposal-id",
        "original_print_packet_id":"fixture-prusa-slicer-packet",
        "operator_ref":"fixture-human-operator",
        "purpose_ref":"fixture-propose-only",
        "requested_node_count":3,"selected_nodes":nodes,
        "source_selection_digest":"fixture-selection-digest",
        "state":"FABRICATION_PROPOSAL_ONLY",
        "owner_machine_grants_included":False,
        "fabrication_occurred":False,
        "physical_parts":0,
        "new_money":0
    }
    return {**body,"request_id":"static-os-fabrication-013:"+digest(body)}


def pieces():
    req=source()
    status=observe(OWNER)
    proposal=propose(OWNER,req)
    static={"status":"THREE_NODE_FABRICATION_PROPOSAL_ONLY",
            "request_id":req["request_id"],"selected_nodes":list(NATIVE_SELECTED),
            "native_cad_cold_verified":True,"physical_print_grants_issued":0,
            "physical_parts_created":0}
    lab={"request":req,"proof_id":"lab-crypto-fixture-NOT_NATIVE",
         "fresh_ticket":{"operation":"propose","permission":"propose"},
         "claims":{"grants_for_physical_print":0,"machine_dispatched":False,
                   "physical_parts":0,"actual_native_013_crossing_to_remote_printer":False},
         "decisions":[
             {"target_machine_id":name,"decision":decision}
             for name,decision in zip([*NATIVE_SELECTED,NATIVE_SELECTED[2]],
                 ["R3_HOLD","R3_HOLD","R3_HOLD","PROPOSAL_ONLY"])]}
    verified={"status":"SIGNED_SIMULATED_OWNER_HOLD_AND_RECONSTITUTION_VERIFIED",
              "request_id":req["request_id"],"hold_decisions":3,
              "software_review_proposals":1,"physical_parts":0,
              "physical_prints_started":0,"stale_grants_restored":0,
              "requires_external_trust":True}
    return req, OWNER, status, proposal, static, lab, verified


class PrintShop(unittest.TestCase):
    def test_composition_records_exact_three_owners_without_executing(self):
        parts=pieces()
        r=validate_binding(*parts)
        self.assertEqual(r["state"],"R3_HOLD_COMPOSED_PROPOSAL_NOT_NATIVE_CROSSING")
        self.assertFalse(r["actual_remote_printer_crossing"])
        self.assertFalse(r["physical_execution_approved"])
        self.assertEqual(r["physical_parts"],0)
        self.assertEqual(r["material_consumed"],0)
        self.assertEqual(r["cash_or_token_minted"],0)
        self.assertEqual(r["lab_owner_trust_pins"],"EPHEMERAL_SELF_GENERATED_NOT_INDEPENDENTLY_VERIFIED")
        self.assertIn("source_request_id",r)

    def test_static_os_request_id_cannot_change(self):
        values=list(pieces())
        values[0]["source_design_candidate_id"]="altered"
        with self.assertRaisesRegex(ValueError,"FABRICATION_REQUEST_ID_MISMATCH"):
            validate_binding(*values)

    def test_owner_cannot_shift_to_unselected_machine(self):
        values=list(pieces())
        values[1]=copy.deepcopy(OWNER)
        values[1]["machine_id"]="elsewhere:printer-new"
        with self.assertRaisesRegex(ValueError,"PRINTER_NOT_EXPLICITLY_SELECTED"):
            validate_binding(*values)

    def test_native_original_verifier_cannot_be_omitted(self):
        values=list(pieces())
        values[4]["native_cad_cold_verified"]=False
        with self.assertRaisesRegex(ValueError,"SOURCE_NATIVE_RECEIPT_WRONG"):
            validate_binding(*values)

    def test_native_source_claim_must_identify_exact_request(self):
        values=list(pieces())
        values[4]["request_id"]="forged"
        with self.assertRaisesRegex(ValueError,"SOURCE_NATIVE_RECEIPT_WRONG"):
            validate_binding(*values)

    def test_unsigned_ghot_status_cannot_claim_machine_identity(self):
        values=list(pieces())
        values[2]["machine_authenticated"]=True
        with self.assertRaisesRegex(ValueError,"GHOT_MACHINE_OBSERVATION_NOT_CURRENT"):
            validate_binding(*values)

    def test_ghot_proposal_cannot_be_tampered_even_to_change_only_reason(self):
        values=list(pieces())
        values[3]["reason"]="READY_FOR_AUTONOMOUS_START"
        with self.assertRaisesRegex(ValueError,"GHOT_PROPOSAL_OR_AUTHORITY_MISMATCH"):
            validate_binding(*values)

    def test_native_signed_proof_must_bind_original_source(self):
        values=list(pieces())
        values[5]["request"]["request_id"]="other"
        with self.assertRaisesRegex(ValueError,"RELATTE_PROOF_SOURCE_CHANGED"):
            validate_binding(*values)

    def test_native_receipt_must_have_three_holds_and_one_review_proposal(self):
        values=list(pieces())
        values[6]["software_review_proposals"]=2
        with self.assertRaisesRegex(ValueError,"RELATTE_NATIVE_VERIFIER_NOT_HOLDING"):
            validate_binding(*values)

    def test_native_lab_cannot_claim_print_or_material(self):
        values=list(pieces())
        values[5]["claims"]["physical_parts"]=1
        with self.assertRaisesRegex(ValueError,"PHYSICAL_GRANT_LAUNDERING"):
            validate_binding(*values)

    def test_fresh_ticket_only_allows_propose(self):
        values=list(pieces())
        values[5]["fresh_ticket"]["operation"]="physical_start"
        with self.assertRaisesRegex(ValueError,"PHYSICAL_GRANT_LAUNDERING"):
            validate_binding(*values)

    def test_three_independent_machine_decisions_bound_to_selection(self):
        values=list(pieces())
        values[5]["decisions"][0]["target_machine_id"]="elsewhere:machine"
        with self.assertRaisesRegex(ValueError,"OWNER_DECISION_TOPOLOGY_WRONG"):
            validate_binding(*values)

    def test_checkout_must_be_pinned_before_native_verification(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"MISSING_SOURCE_REPOSITORY_CHECKOUT"):
                pin_checkout(root,"0"*40)

    def test_run_refuses_missing_native_original_and_cannot_create_approval(self):
        with tempfile.TemporaryDirectory() as root:
            request_file=Path(root)/"request.json"
            request_file.write_text(json.dumps(source()))
            with self.assertRaisesRegex(ValueError,"MISSING_SOURCE_REPOSITORY_CHECKOUT"):
                run_lab(root, root,root,root,root,root,request_file,OWNER_PATH,
                        Path(root)/"result", "a"*40,"b"*40)
            self.assertFalse((Path(root)/"result").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
