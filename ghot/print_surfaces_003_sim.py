#!/usr/bin/env python3
"""Hostile, no-device proof of three heterogeneous printer surfaces.

These fixtures are synthetic. No actual Zebra label, Kodak photograph,
Kodak Portrait part, native signed source or manufacturing approval exists.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from external_adapters import external_executor_records, execute_external_adapter
from print_surfaces_003 import (
    ZEBRA_CAP, KODAK_PHOTO_CAP, KODAK_FFF_CAP,
    ZEBRA_ZD421, KODAK_P300R, KODAK_PORTRAIT,
    dispatch, image_dimensions, zebra_label, kodak_photo, kodak_portrait,
)
from printer_organ import digest

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"adapters/zebra-kodak-surfaces-003/adapter-manifest.json"


def input_for(capability, details):
    return {"schema":"ghot.print-surface-command-003/v0","action":capability,"input":details}


def zebra(text="HAUNTED JUBILEE 003"):
    return {"text":text,"source_ref":"test:zebra-label-001",
            "width_mm":80,"height_mm":50,"dpi":203,
            "human_reviewed_source":True}


def photo_bytes(w=32,h=32):
    # Only PNG signature+IHDR skeleton; it is NOT an authenticated or fully decoded PNG.
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I",13) + b"IHDR" + struct.pack(">II",w,h) + b"\x08\x02\x00\x00\x00" + b"\0\0\0\0"


def photo(w=32,h=32):
    return {"image_base64":base64.b64encode(photo_bytes(w,h)).decode(),
            "source_ref":"test:kodak-photo-001","rights_reviewed":True,
            "crop_policy":"NONE_REQUIRE_SQUARE"}


def request_with(selected_kodak=False):
    nodes=[
        ("example:machine-01","FFF_FDM","HOLD_MACHINE_PROFILE"),
        ("example:machine-02","MSLA","HOLD_PROCESS_ADAPTER"),
        ("reference:kodak-portrait-3d" if selected_kodak else "virtual:fff-pla-180",
         "FFF_FDM","HOLD_MACHINE_PROFILE" if selected_kodak else "SOFTWARE_TOOLPATH_ONLY")
    ]
    selection=[{"machine_id":n,"technology":tech,
                "published_compatibility":compat,"reason":"REF_ONLY_NO_EXECUTION",
                "hardware_authenticated":False,"physical_print_permission":False}
               for n,tech,compat in nodes]
    body={"schema":"static-os.fabrication-request/v0",
        "source_repository":"the-static-collective/static-os",
        "original_field_id":"static-os-printer-field-012:test-fixture",
        "original_signed_cad_crossing_id":"test-original-cad-crossing",
        "source_design_candidate_id":"test-design-id",
        "original_print_packet_id":"test-print-packet-id",
        "operator_ref":"test-human-selector","purpose_ref":"test-propose-only",
        "requested_node_count":3,"selected_nodes":selection,
        "source_selection_digest":"test-selection",
        "state":"FABRICATION_PROPOSAL_ONLY",
        "owner_machine_grants_included":False,
        "fabrication_occurred":False,"physical_parts":0,"new_money":0}
    return {**body,"request_id":"static-os-fabrication-013:"+digest(body)}


def portrait(req=None):
    return {"source_ref":"test:kodak-portrait-001",
            "source_request":req,"requested_machine_id":"reference:kodak-portrait-3d"}


class Surfaces003(unittest.TestCase):
    def test_reference_profiles_are_explicit_and_not_physical_assertions(self):
        self.assertEqual(ZEBRA_ZD421["technology"],"THERMAL_LABEL")
        self.assertEqual(KODAK_P300R["technology"],"FOUR_PASS_DYE_SUBLIMATION")
        self.assertEqual(KODAK_PORTRAIT["technology"],"FFF_FDM")
        self.assertEqual(KODAK_PORTRAIT["build_volume_mm"],{"x":200,"y":200,"z":235})
        for p in (ZEBRA_ZD421,KODAK_P300R,KODAK_PORTRAIT):
            self.assertFalse(p["verified_device"])
            self.assertFalse(p["hardware_transport_enabled"])

    def test_zebra_generates_sanitized_zpl_without_sending_and_binds_source(self):
        r=zebra_label(zebra())
        self.assertTrue(r["zpl"].startswith("^XA\n"))
        self.assertTrue(r["zpl"].endswith("^XZ\n"))
        self.assertIn("^FDHAUNTED JUBILEE 003^FS",r["zpl"])
        self.assertEqual(r["status"],"HELD_ZPL_SOURCE_NOT_SENT")
        self.assertFalse(r["transport_authorized"])
        self.assertFalse(r["device_profile_matches_actual_hardware"])
        self.assertEqual(r["paper_consumed"],0)
        self.assertEqual(r["labels_physically_printed"],0)
        self.assertEqual(len(r["zpl_sha256"]),64)

    def test_zebra_blocks_template_command_smuggling(self):
        for attack in ("HELLO^XZ^XA^PQ100", "HELLO~JA", "HELLO\n^XA", "^XA", "⼀", ""):
            with self.subTest(attack=attack),self.assertRaisesRegex(ValueError,"ZPL_COMMAND_INJECTION"):
                zebra_label(zebra(attack))

    def test_zebra_explicit_source_review_and_media_dpi_required(self):
        for change in ({"human_reviewed_source":False},{"width_mm":1000},
                       {"height_mm":0},{"dpi":999},{"arbitrary_usb_port":"/dev/lp0"}):
            trial={**zebra(),**change}
            with self.subTest(change=change),self.assertRaises(ValueError):
                zebra_label(trial)

    def test_kodak_p300r_image_header_only_and_no_raw_image_in_result(self):
        original=photo_bytes()
        result=kodak_photo(photo())
        self.assertEqual(result["image"],{"mime":"image/png","width_px":32,"height_px":32})
        self.assertEqual(result["source_image_sha256"],hashlib.sha256(original).hexdigest())
        self.assertEqual(result["status"],"HELD_PHOTO_METADATA_NO_KODAK_TRANSPORT")
        self.assertFalse(result["photo_bytes_transmitted"])
        self.assertFalse(result["pixels_decoded"])
        self.assertFalse(result["transport_authorized"])
        self.assertEqual(result["photographs_physically_printed"],0)
        self.assertNotIn("image_base64",result)

    def test_kodak_photo_no_inferred_auto_crop(self):
        with self.assertRaisesRegex(ValueError,"KODAK_P300R_3X3"):
            kodak_photo(photo(40,32))
        item={**photo(),"crop_policy":"AUTO_CROP"}
        with self.assertRaisesRegex(ValueError,"NO_AUTOMATIC_CROP"):
            kodak_photo(item)

    def test_kodak_photo_needs_local_image_consent(self):
        item={**photo(),"rights_reviewed":False}
        with self.assertRaisesRegex(ValueError,"PHOTO_RIGHTS_REVIEW_REQUIRED"):
            kodak_photo(item)
        item={**photo(),"image_base64":"not-base64"}
        with self.assertRaisesRegex(ValueError,"INVALID_BASE64_PHOTO"):
            kodak_photo(item)

    def test_kodak_bounded_image_input_and_nonimage(self):
        with self.assertRaisesRegex(ValueError,"PHOTO_INPUT_TOO_LARGE"):
            kodak_photo({**photo(),"image_base64":"a" * 2_000_000})
        with self.assertRaisesRegex(ValueError,"PNG_OR_JPEG_REQUIRED"):
            image_dimensions(b"not a photo" + b"j" * 100)

    def test_kodak_portrait_without_source_stays_hold(self):
        result=kodak_portrait(portrait())
        self.assertEqual(result["state"],"HOLD_NO_NATIVE_STATIC_OS_FABRICATION_REQUEST")
        self.assertFalse(result["printer_connected"])
        self.assertEqual(result["physical_parts"],0)

    def test_kodak_portrait_not_selected_cannot_inherit_generic_gcode(self):
        result=kodak_portrait(portrait(request_with()))
        self.assertEqual(result["state"],"HOLD_KODAK_PORTRAIT_NOT_SELECTED_BY_SOURCE")
        self.assertFalse(result["source_cold_verified_here"])
        self.assertFalse(result["transport_authorized"])

    def test_self_consistent_kodak_selection_is_still_not_native_authentication(self):
        result=kodak_portrait(portrait(request_with(True)))
        self.assertEqual(result["state"],"HOLD_KODAK_PRINTER_PROFILE_AND_OWNER_AUTH_REQUIRED")
        self.assertFalse(result["safe_gcode_verified_for_model"])
        self.assertFalse(result["machine_authenticated"])
        self.assertEqual(result["material_reserved"],0)
        self.assertEqual(result["prints_started"],0)

    def test_kodak_source_authority_smuggling_denied(self):
        req=request_with(True)
        req["selected_nodes"][2]["physical_print_permission"]=True
        req["request_id"]="static-os-fabrication-013:"+digest({k:v for k,v in req.items() if k!="request_id"})
        with self.assertRaisesRegex(ValueError,"SOURCE_NODE_MAY_NOT_GRANT_PRINT"):
            kodak_portrait(portrait(req))

    def test_no_cross_class_cast_of_kodak_photo_to_fff(self):
        with self.assertRaisesRegex(ValueError,"INPUT_OBJECT_REQUIRED"):
            dispatch(KODAK_FFF_CAP,input_for(KODAK_FFF_CAP,None))
        with self.assertRaisesRegex(ValueError,"KODAK_3D_INPUT_FIELDS_INVALID"):
            dispatch(KODAK_FFF_CAP,input_for(KODAK_FFF_CAP,photo()))

    def test_missing_or_mismatched_ghot_capability_denied(self):
        with self.assertRaisesRegex(ValueError,"CAPABILITY_OR_ACTION_MISMATCH"):
            dispatch(ZEBRA_CAP,input_for(KODAK_PHOTO_CAP,zebra()))
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_PRINT_SURFACE_CAPABILITY"):
            dispatch("printer.auto.start",input_for("printer.auto.start",{}))

    def test_real_ghot_external_adapter_discovers_and_executes_all_three_without_effect(self):
        with patch.dict(os.environ,{"GHOT_ADAPTER_MANIFESTS":str(MANIFEST)}):
            providers=external_executor_records()
            target=[v for v in providers if v["name"]=="external:zebra-kodak-surfaces-003"]
            self.assertEqual(len(target),1)
            self.assertEqual(set(target[0]["capabilities"]),{ZEBRA_CAP,KODAK_PHOTO_CAP,KODAK_FFF_CAP})
            z=execute_external_adapter(ZEBRA_CAP,input_for(ZEBRA_CAP,zebra()))
            self.assertEqual(z["result"]["status"],"HELD_ZPL_SOURCE_NOT_SENT")
            k=execute_external_adapter(KODAK_PHOTO_CAP,input_for(KODAK_PHOTO_CAP,photo()))
            self.assertEqual(k["result"]["status"],"HELD_PHOTO_METADATA_NO_KODAK_TRANSPORT")
            f=execute_external_adapter(KODAK_FFF_CAP,input_for(KODAK_FFF_CAP,portrait()))
            self.assertEqual(f["result"]["state"],"HOLD_NO_NATIVE_STATIC_OS_FABRICATION_REQUEST")
            for response in (z,k,f):
                self.assertEqual(response["adapter_id"],"zebra-kodak-surfaces-003")
                self.assertNotIn("printer_io",json.dumps(response))


if __name__=="__main__":
    unittest.main(verbosity=2)
