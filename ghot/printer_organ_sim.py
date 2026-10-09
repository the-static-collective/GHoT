#!/usr/bin/env python3
"""Offline adversarial proof of the printer-organ/001 external adapter."""
from __future__ import annotations

import json
import os
import socketserver
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from external_adapters import external_executor_records, execute_external_adapter
from printer_organ import (
    act, digest, observe, normalize_endpoint, propose,
    verify_owner, verify_source_request, load_owner_manifest
)

ROOT=Path(__file__).resolve().parents[1]
OWNER=json.loads((ROOT/"fixtures/printer-organ-001/owner.json").read_text())
MANIFEST=ROOT/"adapters/printer-organ-001/adapter-manifest.json"


def request_fixture():
    nodes=[
      {"machine_id":OWNER["machine_id"],"technology":"FFF_FDM",
       "published_compatibility":"HOLD_MACHINE_PROFILE",
       "reason":"NO_VERIFIED_MODEL_FIRMWARE_AND_MATERIAL_PROFILE",
       "hardware_authenticated":False,"physical_print_permission":False},
      {"machine_id":"fixture:resin-02","technology":"MSLA",
       "published_compatibility":"HOLD_PROCESS_ADAPTER",
       "reason":"NO_VERIFIED_NATIVE_PROCESS_SPECIFIC_BUILD_PIPELINE",
       "hardware_authenticated":False,"physical_print_permission":False},
      {"machine_id":"fixture:another-03","technology":"FFF_FDM",
       "published_compatibility":"HOLD_MACHINE_PROFILE",
       "reason":"NO_VERIFIED_MODEL_FIRMWARE_AND_MATERIAL_PROFILE",
       "hardware_authenticated":False,"physical_print_permission":False}
    ]
    body={
      "schema":"static-os.fabrication-request/v0",
      "source_repository":"the-static-collective/static-os",
      "original_field_id":"static-os-printer-field-012:synthetic",
      "original_signed_cad_crossing_id":"fixture-source-crossing-id",
      "source_design_candidate_id":"fixture-design-candidate",
      "original_print_packet_id":"fixture-print-packet",
      "operator_ref":"fixture-operator",
      "purpose_ref":"fixture-trial",
      "requested_node_count":3,
      "selected_nodes":nodes,
      "source_selection_digest":"fixture-selection-digest",
      "state":"FABRICATION_PROPOSAL_ONLY",
      "owner_machine_grants_included":False,
      "fabrication_occurred":False,
      "physical_parts":0,
      "new_money":0
    }
    return {**body,"request_id":"static-os-fabrication-013:"+digest(body)}


class SpyHandler(BaseHTTPRequestHandler):
    paths=[]
    def do_GET(self):
        type(self).paths.append((self.command,self.path))
        if self.path == "/api/connection":
            body={"current":{"state":"Operational","port":"/dev/ttyUSB0"},
                  "apikey":"secret-from-device"}
        elif self.path == "/api/job":
            body={"state":"Operational","job":{"file":{"name":"private-customer.stl"}}}
        else:
            self.send_error(404);return
        content=json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(content)))
        self.end_headers()
        self.wfile.write(content)
    def do_POST(self):
        type(self).paths.append((self.command,self.path))
        self.send_error(405)
    def log_message(self,*args):
        pass


class PrinterOrganTest(unittest.TestCase):
    def test_owner_declares_custody_without_execution(self):
        record=verify_owner(OWNER)
        self.assertFalse(record["physical_execution_authorized"])
        self.assertIsNone(record["status_endpoint"])
        self.assertEqual(observe(OWNER)["status"],"NO_DEVICE_CONTACTED")
        self.assertFalse(observe(OWNER)["machine_authenticated"])

    def test_native_source_request_is_only_self_consistent_not_verified(self):
        original=request_fixture()
        self.assertEqual(verify_source_request(original), original)
        response=propose(OWNER,original)
        self.assertEqual(response["route"],"R3_HOLD")
        self.assertFalse(response["signed_cad_evidence_cold_verified_here"])
        self.assertFalse(response["native_owner_local_admission_obtained"])
        self.assertEqual(response["material_consumed"],0)
        self.assertEqual(response["parts_created"],0)
        self.assertEqual(response["treasury_inventory_added"],0)
        self.assertIsNone(response["driver_command"])
        self.assertFalse(response["automatic_start"])

    def test_unsigned_source_mutation_is_denied(self):
        original=request_fixture()
        original["source_design_candidate_id"]="mutated"
        with self.assertRaisesRegex(ValueError,"FABRICATION_REQUEST_ID_MISMATCH"):
            propose(OWNER,original)

    def test_authority_field_smuggling_is_denied(self):
        original=request_fixture()
        original["physical_parts"]=1
        with self.assertRaisesRegex(ValueError,"SOURCE_REQUEST_NOT_PROPOSAL_ONLY"):
            propose(OWNER,original)
        original=request_fixture()
        original["selected_nodes"][0]["physical_print_permission"]=True
        original["request_id"]="static-os-fabrication-013:"+digest({k:v for k,v in original.items() if k!="request_id"})
        with self.assertRaisesRegex(ValueError,"SOURCE_NODE_MAY_NOT_GRANT_PRINT"):
            propose(OWNER,original)

    def test_unselected_machine_cannot_be_auto_added(self):
        owner={**OWNER,"machine_id":"fixture:missing-99"}
        with self.assertRaisesRegex(ValueError,"PRINTER_NOT_EXPLICITLY_SELECTED"):
            propose(owner,request_fixture())

    def test_owner_conflict_means_hold(self):
        altered={**OWNER,"technology":"MSLA","materials":["STANDARD_RESIN"]}
        report=propose(altered,request_fixture())
        self.assertEqual(report["reason"],"OWNER_TECHNOLOGY_CONTRADICTION")
        self.assertEqual(report["route"],"R3_HOLD")

    def test_owner_proof_fields_cannot_self_grant(self):
        altered={**OWNER,"physical_execution_authorized":True}
        with self.assertRaisesRegex(ValueError,"DECLARATION_CANNOT_GRANT_PHYSICAL_AUTHORITY"):
            verify_owner(altered)
        altered={**OWNER,"machine_id":"fixture:fff-cabinet-01","grant":"START"}
        with self.assertRaisesRegex(ValueError,"OWNER_FIELDS_INVALID"):
            verify_owner(altered)

    def test_refuse_arbitrary_host_and_credentials(self):
        for url in [
            "http://printer.local:5000","http://192.168.0.5:5000",
            "http://127.0.0.1:5000/api/files",
            "http://user:secret@127.0.0.1:5000",
            "https://127.0.0.1:5000","http://127.0.0.1:5000?upload=true"
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_endpoint(url)

    def test_real_local_http_status_is_get_only_and_redacts_sensitive_fields(self):
        SpyHandler.paths=[]
        server=ThreadingHTTPServer(("127.0.0.1",0),SpyHandler)
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            owner={**OWNER,"endpoint_kind":"OCTOPRINT_LOOPBACK_READ_ONLY",
                   "status_endpoint":"http://127.0.0.1:"+str(server.server_port)}
            output=observe(owner,api_key="test-only")
            self.assertEqual(output["connection"],{"state":"Operational"})
            self.assertEqual(output["job"],{"state":"Operational"})
            self.assertEqual(output["status"],"READ_ONLY_STATUS_OBSERVED_NOT_DEVICE_AUTHENTICATED")
            self.assertEqual(SpyHandler.paths,[
                ("GET","/api/connection"),("GET","/api/job")])
            self.assertNotIn("private-customer.stl",json.dumps(output))
            self.assertNotIn("secret-from-device",json.dumps(output))
            self.assertFalse(output["physical_execution_authorized"])
        finally:
            server.shutdown();server.server_close();worker.join()

    def test_existing_ghot_external_adapters_register_both_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            own=Path(tmp)/"owner.json"
            own.write_text(json.dumps(OWNER))
            with patch.dict(os.environ,{
                "GHOT_ADAPTER_MANIFESTS":str(MANIFEST),
                "GHOT_PRINTER_OWNER_FILE":str(own),
            }):
                providers=external_executor_records()
                target=[v for v in providers if v["name"]=="external:printer-organ-001"]
                self.assertEqual(len(target),1)
                self.assertEqual(set(target[0]["capabilities"]),{
                    "printer.status.read","printer.fabrication.propose"
                })
                status=execute_external_adapter("printer.status.read",{
                    "schema":"ghot.printer-organ-command/v0","action":"status","request":None})
                self.assertEqual(status["result"]["status"],"NO_DEVICE_CONTACTED")
                crossing=execute_external_adapter("printer.fabrication.propose",{
                    "schema":"ghot.printer-organ-command/v0",
                    "action":"propose","request":request_fixture()})
                self.assertEqual(crossing["result"]["route"],"R3_HOLD")
                self.assertFalse(crossing["result"]["reLATTE_native_crossing_created"])

    def test_command_rejects_requests_with_unrelated_effects(self):
        with self.assertRaisesRegex(ValueError,"STATUS_COMMAND_MUST_NOT_HAVE_TASK"):
            act({"schema":"ghot.printer-organ-command/v0","action":"status",
                 "request":request_fixture()},OWNER,"printer.status.read")
        with self.assertRaisesRegex(ValueError,"PRINTER_ADAPTER_INPUT_FIELDS_INVALID"):
            act({"schema":"ghot.printer-organ-command/v0","action":"status",
                 "request":None,"heater":200},OWNER,"printer.status.read")


if __name__=="__main__":
    unittest.main(verbosity=2)
