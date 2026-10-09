#!/usr/bin/env python3
"""Native PDF and GHoT external adapter adversarial tests for print venues 004."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter

from external_adapters import external_executor_records, execute_external_adapter
from public_print_venues_004 import CAPABILITIES, compile_handoff, preflight_pdf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "adapters/public-print-venues-004/adapter-manifest.json"


def sample_pdf(width=612, height=792, pages=2):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def request(capability, method, *, sensitivity="PUBLIC", paper="LETTER"):
    return {"schema": "ghot.public-print-input-004/v0", "action": capability,
            "input": {
                "relative_pdf": "reviewed/sample.pdf",
                "source_ref": "witness:document-004",
                "venue_ref": "local:unknown-site-004",
                "method": method, "copies": 1,
                "color": "MONOCHROME", "duplex": "DUPLEX_LONG_EDGE",
                "paper": paper, "sensitivity": sensitivity,
                "operator_review": True
            }}


class PublicPrintVenueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "reviewed").mkdir()
        self.pdf = sample_pdf()
        (self.root / "reviewed/sample.pdf").write_bytes(self.pdf)
        self.env = patch.dict(os.environ, {"GHOT_PUBLIC_PRINT_INBOX": str(self.root),
                                          "GHOT_ADAPTER_MANIFESTS": str(MANIFEST)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def candidate(self, route="printer.venue.library.public.prepare",
                  method="MANUAL_WEB_RELEASE", **args):
        return compile_handoff(route, request(route, method, **args))

    def test_native_pypdf_reads_real_two_page_pdf(self):
        result = self.candidate()
        self.assertEqual(result["pdf_preflight"]["pages"], 2)
        self.assertTrue(result["pdf_preflight"]["uniform_page_dimensions"])
        self.assertEqual(result["pdf_preflight"]["media_boxes_pt"],
                         [{"width":612.0, "height":792.0}])
        self.assertEqual(result["local_pdf_sha256"], hashlib.sha256(self.pdf).hexdigest())
        self.assertTrue(result["paper_size_matches_pdf_boxes"])
        self.assertFalse(result["pdf_preflight"]["raster_preview_verified"])

    def test_xerox_mfp_is_a_manual_printer_and_not_a_library_queue(self):
        result = self.candidate("printer.venue.xerox.mfp.prepare",
                                "MANUAL_LOCAL_PRINT_DIALOG")
        self.assertEqual(result["venue_kind"], "XEROX_MFP")
        self.assertEqual(result["state"], "PREPARED_LOCAL_HANDOFF_R3_HOLD")
        self.assertFalse(result["machine_vendor_and_model_verified"])
        self.assertFalse(result["native_relatte_owner_admitted"])
        self.assertEqual(result["network_requests"], 0)

    def test_library_route_requires_unknown_release_system_confirmation(self):
        result = self.candidate()
        self.assertEqual(result["venue_kind"], "LIBRARY_PUBLIC")
        self.assertFalse(result["retrieval_code_issued"])
        self.assertEqual(result["human_next_step"],
                         "VERIFY_LOCAL_LIBRARY_PORTAL_AND_RELEASE_POLICY")
        self.assertFalse(result["actual_print_order_submitted"])

    def test_fedex_is_retail_manual_not_executable_web_api(self):
        result = self.candidate("printer.venue.fedex-office.prepare",
                                "MANUAL_EMAIL_PRINT_AND_GO")
        self.assertEqual(result["venue_kind"], "FEDEX_OFFICE")
        self.assertEqual(result["emails_sent"], 0)
        self.assertFalse(result["payment_taken"])
        self.assertFalse(result["document_data_uploaded"])
        self.assertFalse(result["external_vendor_receipt_obtained"])
        self.assertEqual(result["paper_consumed"], 0)

    def test_fedex_cloud_and_usb_routes_are_distinct_manual_choices(self):
        for mode in ("MANUAL_USB","MANUAL_CLOUD_KIOSK","MANUAL_STAFF_COUNTER"):
            with self.subTest(mode=mode):
                result = self.candidate("printer.venue.fedex-office.prepare", mode)
                self.assertEqual(result["print_intent"]["manual_intake_method"],mode)

    def test_cross_venue_transport_laundering_refused(self):
        for cap, method in [
            ("printer.venue.library.public.prepare","MANUAL_EMAIL_PRINT_AND_GO"),
            ("printer.venue.fedex-office.prepare","MANUAL_WEB_RELEASE"),
            ("printer.venue.xerox.mfp.prepare","MANUAL_CLOUD_KIOSK")
        ]:
            with self.subTest(capability=cap):
                with self.assertRaisesRegex(ValueError,"VENUE_METHOD_UNSUPPORTED"):
                    self.candidate(cap,method)

    def test_capability_mismatch_rejected(self):
        p=request("printer.venue.library.public.prepare","MANUAL_USB")
        with self.assertRaisesRegex(ValueError,"VENUE_ACTION_CAPABILITY_CONTRADICTION"):
            compile_handoff("printer.venue.xerox.mfp.prepare",p)
        with self.assertRaisesRegex(ValueError,"PRINT_VENUE_CAPABILITY_NOT_REGISTERED"):
            compile_handoff("printer.venue.start",p)

    def test_path_escape_and_absolute_path_refused(self):
        for path in ("../outside.pdf","/etc/passwd","reviewed/../../evil.pdf",
                     ".secrets.pdf","reviewed/.hidden.pdf","reviewed/sample.txt"):
            with self.subTest(path=path):
                p=request("printer.venue.library.public.prepare","MANUAL_USB")
                p["input"]["relative_pdf"]=path
                with self.assertRaises(ValueError):
                    compile_handoff(p["action"],p)

    def test_symbolic_link_denied(self):
        (self.root/"reviewed"/"shortcut.pdf").symlink_to(self.root/"reviewed/sample.pdf")
        p=request("printer.venue.xerox.mfp.prepare","MANUAL_USB")
        p["input"]["relative_pdf"]="reviewed/shortcut.pdf"
        with self.assertRaisesRegex(ValueError,"PRINT_INBOX_SYMLINK_DENIED"):
            compile_handoff(p["action"],p)

    def test_disallow_missing_operator_inbox(self):
        with patch.dict(os.environ,{"GHOT_PUBLIC_PRINT_INBOX":""}):
            with self.assertRaisesRegex(ValueError,"LOCAL_OPERATOR_PRINT_INBOX_REQUIRED"):
                self.candidate()

    def test_restricted_documents_never_get_public_handoff(self):
        for cap,method in (
            ("printer.venue.xerox.mfp.prepare","MANUAL_USB"),
            ("printer.venue.library.public.prepare","MANUAL_USB"),
            ("printer.venue.fedex-office.prepare","MANUAL_USB")
        ):
            with self.subTest(capability=cap):
                with self.assertRaisesRegex(ValueError,"RESTRICTED_DOCUMENT_PUBLIC_PRINT_DENIED"):
                    self.candidate(cap, method, sensitivity="RESTRICTED")

    def test_private_work_cannot_be_sent_to_public_portal_or_email(self):
        for cap,method in (
            ("printer.venue.library.public.prepare","MANUAL_WEB_RELEASE"),
            ("printer.venue.fedex-office.prepare","MANUAL_CLOUD_KIOSK"),
            ("printer.venue.fedex-office.prepare","MANUAL_EMAIL_PRINT_AND_GO"),
        ):
            with self.subTest(capability=cap,method=method):
                with self.assertRaisesRegex(ValueError,"PRIVATE_DOC_REMOTE_THIRD_PARTY_INTAKE_DENIED"):
                    self.candidate(cap, method, sensitivity="PRIVATE")
        allowed=self.candidate("printer.venue.fedex-office.prepare",
                               "MANUAL_USB", sensitivity="PRIVATE")
        self.assertIn("NO_ASSUMED_CONFIDENTIALITY",allowed["privacy_notice"])

    def test_not_reviewed_and_silent_copy_escalation_refused(self):
        p=request("printer.venue.library.public.prepare","MANUAL_USB")
        p["input"]["operator_review"]=False
        with self.assertRaisesRegex(ValueError,"EXPLICIT_OPERATOR_REVIEW_REQUIRED"):
            compile_handoff(p["action"],p)
        p=request("printer.venue.library.public.prepare","MANUAL_USB")
        p["input"]["copies"]=1000
        with self.assertRaisesRegex(ValueError,"UNBOUNDED_COPIES_DENIED"):
            compile_handoff(p["action"],p)

    def test_mismatched_paper_is_disclosed_not_silently_cropped(self):
        outcome=self.candidate(paper="TABLOID")
        self.assertTrue(outcome["scaling_or_crop_review_required"])
        self.assertFalse(outcome["paper_size_matches_pdf_boxes"])

    def test_corrupt_or_oversized_pdf_rejected(self):
        (self.root/"reviewed/sample.pdf").write_bytes(b"%PDF-1.7\nnot a pdf")
        with self.assertRaisesRegex(ValueError,"PDF_PARSE_OR_PAGE_GEOMETRY_FAILED"):
            self.candidate()
        (self.root/"reviewed/sample.pdf").write_bytes(b"%PDF-" + b"X"*12_000_001)
        with self.assertRaisesRegex(ValueError,"DOCUMENT_MUST_BE_BOUNDED_REGULAR_PDF"):
            self.candidate()

    def test_encrypted_pdf_denied(self):
        writer=PdfWriter()
        writer.add_blank_page(width=612,height=792)
        writer.encrypt("password")
        path=self.root/"reviewed/sample.pdf"
        with path.open("wb") as output:
            writer.write(output)
        with self.assertRaisesRegex(ValueError,"ENCRYPTED_PDF_HOLD"):
            self.candidate()

    def test_invalid_page_count_rejected(self):
        with self.assertRaisesRegex(ValueError,"PAGE_COUNT_OUT_OF_BOUNDS"):
            preflight_pdf(sample_pdf(pages=0))

    def test_results_never_disclose_local_path_or_file_content(self):
        data=self.candidate()
        serialized=json.dumps(data)
        self.assertNotIn("reviewed/sample.pdf",serialized)
        self.assertNotIn(self.tmp.name,serialized)
        self.assertNotIn("%PDF-",serialized)
        self.assertFalse(data["payment_taken"])
        self.assertFalse(data["document_data_uploaded"])
        self.assertFalse(data["machine_vendor_and_model_verified"])
        self.assertEqual(data["physical_copies_collected"],0)

    def test_ghot_pantry_discovers_exact_three_venue_capabilities(self):
        ex=external_executor_records()
        match=[x for x in ex if x["name"]=="external:public-print-venues-004"]
        self.assertEqual(len(match),1)
        self.assertEqual(set(match[0]["capabilities"]),set(CAPABILITIES))

    def test_actual_ghot_external_process_executes_each_venue(self):
        mapping={
            "printer.venue.xerox.mfp.prepare":"MANUAL_LOCAL_PRINT_DIALOG",
            "printer.venue.library.public.prepare":"MANUAL_WEB_RELEASE",
            "printer.venue.fedex-office.prepare":"MANUAL_EMAIL_PRINT_AND_GO"
        }
        for cap,method in mapping.items():
            with self.subTest(capability=cap):
                outcome=execute_external_adapter(cap,request(cap,method))
                self.assertEqual(outcome["adapter_id"],"public-print-venues-004")
                self.assertEqual(outcome["result"]["state"],"PREPARED_LOCAL_HANDOFF_R3_HOLD")
                self.assertEqual(outcome["result"]["network_requests"],0)
                self.assertEqual(outcome["result"]["pages_physically_printed"],0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
