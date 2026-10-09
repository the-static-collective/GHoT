#!/usr/bin/env python3
"""PRINT-SURFACES-003: Zebra thermal labels + Kodak photo/FFF reference profiles.

Opt-in GHoT external adapter: pure bounded artifact/proposal generation, no
printer I/O, USB/Bluetooth/serial connection, print queue or physical output.
Kodak photo and 3D are intentionally DIFFERENT technology families.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path

from printer_organ import (
    digest, require, keys, verify_owner, verify_source_request, propose
)

COMMAND_SCHEMA = "ghot.print-surface-command-003/v0"
PROFILE_SCHEMA = "ghot.print-surface-profile-003/v0"
ZEBRA_CAP = "printer.surface.zebra.label.prepare"
KODAK_PHOTO_CAP = "printer.surface.kodak.photo.inspect"
KODAK_FFF_CAP = "printer.surface.kodak.portrait3d.propose"
CAPABILITIES = (ZEBRA_CAP, KODAK_PHOTO_CAP, KODAK_FFF_CAP)
MAX_INPUT = 2_000_000
MAX_PHOTO_BYTES = 1_000_000
LABEL_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/()+,-]{0,79}$")
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,119}$")

# These are *reference examples*, never authenticated or commissioned owners.
ZEBRA_ZD421 = {
    "schema": PROFILE_SCHEMA,
    "profile_id": "reference:zebra-zd421-zpl203",
    "manufacturer": "Zebra Technologies",
    "model": "ZD421 (reference profile only)",
    "technology": "THERMAL_LABEL",
    "protocol": "ZPL_II_OFFLINE_ARTIFACT",
    "dpi": 203,
    "media": "OPERATOR_SELECTED_NOT_CONFIRMED",
    "verified_device": False,
    "hardware_transport_enabled": False,
}
KODAK_P300R = {
    "schema": PROFILE_SCHEMA,
    "profile_id": "reference:kodak-mini-3-retro-p300r",
    "manufacturer": "Kodak licensed photo device",
    "model": "Mini 3 Retro P300R",
    "technology": "FOUR_PASS_DYE_SUBLIMATION",
    "protocol": "NOT_VERIFIED_NO_BLUETOOTH_USB_DRIVER",
    "photo_width_in": 3,
    "photo_height_in": 3,
    "marketing_resolution_dpi": 300,
    "verified_device": False,
    "hardware_transport_enabled": False,
}
KODAK_PORTRAIT = {
    "schema": PROFILE_SCHEMA,
    "profile_id": "reference:kodak-portrait-fff",
    "manufacturer": "Kodak / Smart International licensed 3D product",
    "model": "Kodak Portrait 3D",
    "technology": "FFF_FDM",
    "protocol": "NOT_VERIFIED_NO_FIRMWARE_OR_MACHINE_PROFILE",
    "build_volume_mm": {"x": 200, "y": 200, "z": 235},
    "dual_extruder": True,
    "nominal_nozzle_mm": 0.4,
    "verified_device": False,
    "hardware_transport_enabled": False,
}


def exact_command(payload, action):
    keys(payload, ("schema", "action", "input"), "PRINT_SURFACE_COMMAND")
    require(payload["schema"] == COMMAND_SCHEMA and payload["action"] == action,
            "CAPABILITY_OR_ACTION_MISMATCH")
    require(type(payload["input"]) is dict, "INPUT_OBJECT_REQUIRED")
    return payload["input"]


def source_ref(value):
    require(type(value) is str and REF.fullmatch(value) is not None,
            "SOURCE_REFERENCE_INVALID")
    return value


def zebra_label(inp):
    """Return a ZPL source artifact, NEVER submit it to a printer."""
    keys(inp, ("text", "source_ref", "width_mm", "height_mm", "dpi",
               "human_reviewed_source"), "ZEBRA_LABEL")
    source_ref(inp["source_ref"])
    text = inp["text"]
    # Deliberately exclude ^, ~, control characters, RTL and arbitrary ZPL.
    require(type(text) is str and LABEL_TEXT.fullmatch(text) is not None,
            "ZPL_COMMAND_INJECTION_OR_TEXT_BOUNDS")
    require(inp["human_reviewed_source"] is True, "HUMAN_SOURCE_REVIEW_REQUIRED")
    require(type(inp["width_mm"]) is int and 25 <= inp["width_mm"] <= 100 and
            type(inp["height_mm"]) is int and 25 <= inp["height_mm"] <= 150 and
            type(inp["dpi"]) is int and inp["dpi"] in (203, 300),
            "LABEL_MEDIA_DIMENSIONS_OR_DPI_INVALID")
    # An actual printer's DPI, origin, printable area and stock are not known.
    pw = round(inp["width_mm"] / 25.4 * inp["dpi"])
    ll = round(inp["height_mm"] / 25.4 * inp["dpi"])
    require(pw >= 190 and ll >= 190, "LABEL_TOO_SMALL")
    # Source ref may not be placed inside ZPL: it's provenance, not printer text.
    rendered = "\n".join((
        "^XA",
        f"^PW{pw}", f"^LL{ll}",
        "^FO24,35^A0N,30,30^FD" + text + "^FS",
        "^XZ", ""
    ))
    body = {
        "schema": "ghot.zebra-label-candidate-003/v0",
        "device_profile": ZEBRA_ZD421["profile_id"],
        "profile_is_unverified_reference": True,
        "source_ref": inp["source_ref"],
        "source_text_sha256": hashlib.sha256(text.encode("ascii")).hexdigest(),
        "command_language": "ZPL_II",
        "zpl": rendered,
        "zpl_sha256": hashlib.sha256(rendered.encode("ascii")).hexdigest(),
        "width_mm": inp["width_mm"], "height_mm": inp["height_mm"], "dpi": inp["dpi"],
        "physical_device_verified": False,
        "paper_consumed": 0, "labels_physically_printed": 0,
        "human_reviewed_source": True,
        "device_profile_matches_actual_hardware": False,
        "status": "HELD_ZPL_SOURCE_NOT_SENT",
        "transport_authorized": False,
        "reLATTE_owner_admitted": False
    }
    return {**body, "candidate_id": "ghot-zebra-003:" + digest(body)}


def image_dimensions(data):
    """Syntactic dimension check only; DOES NOT decode or authenticate pixels."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 33:
        require(data[12:16] == b"IHDR" and data[8:12] == b"\x00\x00\x00\x0d",
                "PNG_IHDR_MISSING")
        width, height = struct.unpack(">II", data[16:24])
        kind = "image/png"
    elif data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        pos = 2
        width = height = None
        kind = "image/jpeg"
        # Scan bounded JPEG marker segments, without decoding pixel data or EXIF.
        while pos < len(data) - 2:
            require(data[pos] == 0xff, "JPEG_MARKER_INVALID")
            while pos < len(data) and data[pos] == 0xff:
                pos += 1
            require(pos < len(data), "JPEG_TRUNCATED")
            marker = data[pos]
            pos += 1
            require(marker not in (0xd8, 0xd9, 0xda), "JPEG_DIMENSIONS_MISSING")
            if marker in range(0xd0, 0xd8) or marker == 0x01:
                continue
            require(pos + 2 <= len(data), "JPEG_SEGMENT_TRUNCATED")
            segment_len = struct.unpack(">H", data[pos:pos + 2])[0]
            require(segment_len >= 2 and pos + segment_len <= len(data),
                    "JPEG_SEGMENT_LENGTH_INVALID")
            if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7,
                          0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                require(segment_len >= 7, "JPEG_SOF_TRUNCATED")
                height, width = struct.unpack(">HH", data[pos + 3:pos + 7])
                break
            pos += segment_len
        require(width is not None, "JPEG_DIMENSIONS_MISSING")
    else:
        raise ValueError("PNG_OR_JPEG_REQUIRED")
    require(16 <= width <= 10_000 and 16 <= height <= 10_000,
            "IMAGE_DIMENSIONS_INVALID")
    return {"mime": kind, "width_px": width, "height_px": height}


def kodak_photo(inp):
    keys(inp, ("image_base64", "source_ref", "rights_reviewed", "crop_policy"),
         "KODAK_PHOTO")
    source_ref(inp["source_ref"])
    require(inp["rights_reviewed"] is True, "PHOTO_RIGHTS_REVIEW_REQUIRED")
    require(inp["crop_policy"] == "NONE_REQUIRE_SQUARE", "NO_AUTOMATIC_CROP_AUTHORITY")
    encoded = inp["image_base64"]
    require(type(encoded) is str and len(encoded) <= MAX_PHOTO_BYTES * 4 // 3 + 8,
            "PHOTO_INPUT_TOO_LARGE")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("INVALID_BASE64_PHOTO") from error
    require(0 < len(data) <= MAX_PHOTO_BYTES, "PHOTO_BYTES_TOO_LARGE")
    image = image_dimensions(data)
    require(image["width_px"] == image["height_px"],
            "KODAK_P300R_3X3_REQUIRES_SQUARE_INPUT")
    body = {
        "schema": "ghot.kodak-photo-candidate-003/v0",
        "device_profile": KODAK_P300R["profile_id"],
        "source_ref": inp["source_ref"],
        "source_image_sha256": hashlib.sha256(data).hexdigest(),
        "source_image_bytes": len(data), "image": image,
        "photo_inches": [3, 3], "crop_policy": "NONE_REQUIRE_SQUARE",
        "rights_reviewed": True, "pixels_decoded": False,
        "photo_bytes_transmitted": False,
        "bluetooth_or_usb_driver": False,
        "hardcopy_verified": False, "photographs_physically_printed": 0,
        "status": "HELD_PHOTO_METADATA_NO_KODAK_TRANSPORT",
        "transport_authorized": False, "reLATTE_owner_admitted": False
    }
    return {**body, "candidate_id": "ghot-kodak-photo-003:" + digest(body)}


def kodak_portrait(inp):
    """Kodak 3D is FFF, not Kodak 4PASS and not generic PrusaSlicer target."""
    keys(inp, ("source_ref", "source_request", "requested_machine_id"), "KODAK_3D")
    source_ref(inp["source_ref"])
    require(inp["requested_machine_id"] == "reference:kodak-portrait-3d",
            "KODAK_3D_REFERENCE_ID_REQUIRED")
    if inp["source_request"] is None:
        status = "HOLD_NO_NATIVE_STATIC_OS_FABRICATION_REQUEST"
        request_id = None
    else:
        req = verify_source_request(inp["source_request"])
        request_id = req["request_id"]
        selected = [m for m in req["selected_nodes"] if m["machine_id"] == inp["requested_machine_id"]]
        if len(selected) != 1:
            status = "HOLD_KODAK_PORTRAIT_NOT_SELECTED_BY_SOURCE"
        elif selected[0]["technology"] != "FFF_FDM":
            status = "HOLD_KODAK_PROCESS_MISMATCH"
        else:
            # Although source selected this exact descriptive machine,
            # there is no verified model firmware/material toolpath profile.
            status = "HOLD_KODAK_PRINTER_PROFILE_AND_OWNER_AUTH_REQUIRED"
    body = {
        "schema": "ghot.kodak-portrait-candidate-003/v0",
        "device_profile": KODAK_PORTRAIT["profile_id"],
        "source_ref": inp["source_ref"], "source_request_id": request_id,
        "requested_machine_id": inp["requested_machine_id"],
        "source_cold_verified_here": False,
        "native_owner_admission_obtained": False,
        "machine_authenticated": False, "firmware_profile_verified": False,
        "safe_gcode_verified_for_model": False,
        "gcode_transmitted": False, "printer_connected": False,
        "prints_started": 0, "physical_parts": 0,
        "material_reserved": 0, "inventory_increment": 0,
        "state": status, "transport_authorized": False
    }
    return {**body, "candidate_id": "ghot-kodak-portrait-003:" + digest(body)}


def dispatch(capability, payload):
    require(capability in CAPABILITIES, "UNSUPPORTED_PRINT_SURFACE_CAPABILITY")
    inp = exact_command(payload, capability)
    if capability == ZEBRA_CAP:
        return zebra_label(inp)
    if capability == KODAK_PHOTO_CAP:
        return kodak_photo(inp)
    return kodak_portrait(inp)


def main():
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    require(len(raw) <= MAX_INPUT, "UNBOUNDED_ADAPTER_INPUT")
    data = json.loads(raw.decode("utf8"))
    print(json.dumps(dispatch(os.environ.get("GHOT_EXTERNAL_CAPABILITY"), data),
                     sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        print("R3_HOLD / " + str(error)[:240], file=sys.stderr)
        raise SystemExit(2)
