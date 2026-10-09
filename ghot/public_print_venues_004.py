#!/usr/bin/env python3
"""PUBLIC-PRINT-VENUES-004: local PDF -> held Xerox/library/FedEx handoff.

Runs through the ordinary GHoT external-adapter stdin/out JSON interface.
Actual PDF pages are inspected with pypdf, but no printing, uploads, web,
email, IPP, CUPS, USB, release-code issuance, payment or third-party booking
can happen here. Printed-device make, vendor and physical output are unknown.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = "ghot.public-print-input-004/v0"
RESULT = "ghot.public-print-handoff-004/v0"
CAPABILITIES = {
    "printer.venue.xerox.mfp.prepare": "XEROX_MFP",
    "printer.venue.library.public.prepare": "LIBRARY_PUBLIC",
    "printer.venue.fedex-office.prepare": "FEDEX_OFFICE",
}
METHODS = {
    "XEROX_MFP": ("MANUAL_LOCAL_PRINT_DIALOG", "MANUAL_USB"),
    "LIBRARY_PUBLIC": ("MANUAL_WEB_RELEASE", "MANUAL_USB", "MANUAL_STAFF_DESK"),
    "FEDEX_OFFICE": ("MANUAL_USB", "MANUAL_CLOUD_KIOSK",
                     "MANUAL_EMAIL_PRINT_AND_GO", "MANUAL_STAFF_COUNTER"),
}
PAPER_SIZES = {"LETTER": (612,792), "LEGAL":(612,1008),
               "TABLOID":(792,1224), "A4":(595.28,841.89)}
MAX_PDF_BYTES = 12_000_000
MAX_PAGES = 250
SAFE_RELPATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]{0,199}\.pdf$", re.I)
SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,119}$")


def need(test, message):
    if not test:
        raise ValueError(message)


def exact(value, names, message):
    need(type(value) is dict and set(value) == set(names), message)


def identity(value, message):
    need(type(value) is str and SAFE_REF.fullmatch(value) is not None, message)
    return value


def json_digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def locally_read_document(relative_path):
    """Fail-closed under an owner-configured document directory, not arbitrary task path.

    No filename/directory from the private file is returned in the public
    receipt. The path may have subdirectories but never symlinks or dot parents.
    """
    owner_root = os.environ.get("GHOT_PUBLIC_PRINT_INBOX")
    need(type(owner_root) is str and Path(owner_root).is_absolute(),
         "LOCAL_OPERATOR_PRINT_INBOX_REQUIRED")
    need(type(relative_path) is str and SAFE_RELPATH.fullmatch(relative_path) is not None,
         "PDF_RELATIVE_PATH_REQUIRED")
    bits = Path(relative_path).parts
    need(all(x not in ("", ".", "..") and not x.startswith(".") for x in bits),
         "HIDDEN_PARENT_OR_TRAVERSAL_DENIED")
    root = Path(owner_root)
    need(root.is_dir() and not root.is_symlink(), "OWNER_PRINT_INBOX_NOT_DIRECTORY")
    root = root.resolve(strict=True)
    target = root
    for bit in bits:
        target = target / bit
        need(not target.is_symlink(), "PRINT_INBOX_SYMLINK_DENIED")
    resolved = target.resolve(strict=True)
    need(resolved.is_relative_to(root), "PRINT_PATH_ESCAPES_OWNER_ROOT")
    fd = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        props = os.fstat(fd)
        need(stat.S_ISREG(props.st_mode) and 0 < props.st_size <= MAX_PDF_BYTES,
             "DOCUMENT_MUST_BE_BOUNDED_REGULAR_PDF")
        with os.fdopen(fd, "rb", closefd=False) as inp:
            data = inp.read(MAX_PDF_BYTES + 1)
        need(len(data) <= MAX_PDF_BYTES and data.startswith(b"%PDF-"),
             "INVALID_OR_OVERSIZED_PDF")
        return data
    finally:
        os.close(fd)


def preflight_pdf(data):
    """Read real page boxes; not rasterization, PDF/A or print-device validation."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PYPDF_REQUIRED_FOR_NATIVE_PAGE_PREFLIGHT") from exc
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        need(not reader.is_encrypted, "ENCRYPTED_PDF_HOLD")
        count = len(reader.pages)
        need(1 <= count <= MAX_PAGES, "PAGE_COUNT_OUT_OF_BOUNDS")
        sizes = []
        for page in reader.pages:
            # An absent/degenerate media box must not be silently interpreted.
            box = page.mediabox
            width, height = float(box.width), float(box.height)
            need(36 <= width <= 3600 and 36 <= height <= 3600,
                 "PDF_PAGE_BOX_INVALID")
            sizes.append((round(width,2), round(height,2)))
        unique = sorted(set(sizes))
        return {
            "pages": count,
            "media_boxes_pt": [{"width": w, "height": h} for w,h in unique],
            "uniform_page_dimensions": len(unique) == 1,
            "parser": "pypdf-structural-preflight",
            "raster_preview_verified": False,
            "fonts_embedded_verified": False,
            "bleed_and_crop_verified": False,
            "accessibility_verified": False,
        }
    except (ValueError, ImportError):
        raise
    except Exception as exc:
        raise ValueError("PDF_PARSE_OR_PAGE_GEOMETRY_FAILED") from exc


def compile_handoff(capability, payload):
    need(capability in CAPABILITIES, "PRINT_VENUE_CAPABILITY_NOT_REGISTERED")
    exact(payload, ("schema", "action", "input"), "EXACT_PRINT_VENUE_COMMAND")
    need(payload["schema"] == SCHEMA and payload["action"] == capability,
         "VENUE_ACTION_CAPABILITY_CONTRADICTION")
    item = payload["input"]
    exact(item, ("relative_pdf", "source_ref", "venue_ref", "method", "copies",
                 "color", "duplex", "paper", "sensitivity", "operator_review"),
          "EXACT_PRINT_INTENT")
    venue = CAPABILITIES[capability]
    identity(item["source_ref"], "SOURCE_REF_INVALID")
    identity(item["venue_ref"], "VENUE_REF_INVALID")
    need(item["method"] in METHODS[venue], "VENUE_METHOD_UNSUPPORTED")
    need(type(item["copies"]) is int and 1 <= item["copies"] <= 20,
         "UNBOUNDED_COPIES_DENIED")
    need(item["color"] in ("COLOR", "MONOCHROME") and
         item["duplex"] in ("SIMPLEX", "DUPLEX_LONG_EDGE") and
         item["paper"] in PAPER_SIZES, "PRINT_OPTIONS_INVALID")
    need(item["sensitivity"] in ("PUBLIC", "PRIVATE", "RESTRICTED"),
         "SENSITIVITY_REQUIRED")
    need(item["operator_review"] is True, "EXPLICIT_OPERATOR_REVIEW_REQUIRED")
    need(item["sensitivity"] != "RESTRICTED",
         "RESTRICTED_DOCUMENT_PUBLIC_PRINT_DENIED")
    # Avoid silently sending sensitive documents to third-party cloud/email.
    need(not (item["sensitivity"] == "PRIVATE" and
              item["method"] in ("MANUAL_WEB_RELEASE", "MANUAL_CLOUD_KIOSK",
                                 "MANUAL_EMAIL_PRINT_AND_GO")),
         "PRIVATE_DOC_REMOTE_THIRD_PARTY_INTAKE_DENIED")
    data = locally_read_document(item["relative_pdf"])
    preflight = preflight_pdf(data)
    target = PAPER_SIZES[item["paper"]]
    # Exact page sizes are not required for printing, but no silent scaling:
    # operator must decide about fit-to-page and potential clipping.
    off_target = any(
        not (abs(m["width"] - target[0]) <= 4 and
             abs(m["height"] - target[1]) <= 4 or
             abs(m["width"] - target[1]) <= 4 and
             abs(m["height"] - target[0]) <= 4)
        for m in preflight["media_boxes_pt"]
    )
    privacy = {
        "PUBLIC": "VENUE_MAY_RETAIN_JOB_CHECK_POSTED_POLICY",
        "PRIVATE": "ONLY_PERSON_PRESENT_OR_USB_NO_ASSUMED_CONFIDENTIALITY",
    }[item["sensitivity"]]
    route = {
        "XEROX_MFP": "VERIFY_EXACT_MODEL_AND_ADMIN_ACCESS_THEN_MANUAL_PRINT_DIALOG",
        "LIBRARY_PUBLIC": "VERIFY_LOCAL_LIBRARY_PORTAL_AND_RELEASE_POLICY",
        "FEDEX_OFFICE": "VERIFY_STORE_SERVICE_PRICING_AND_COMPLETE_KIOSK_PAYMENT",
    }[venue]
    body = {
        "schema": RESULT,
        "venue_kind": venue, "venue_ref": item["venue_ref"],
        "source_ref": item["source_ref"],
        "local_pdf_sha256": hashlib.sha256(data).hexdigest(),
        "local_pdf_bytes": len(data),
        "pdf_preflight": preflight,
        "print_intent": {
            "copies": item["copies"], "color": item["color"],
            "duplex": item["duplex"], "paper": item["paper"],
            "sensitivity": item["sensitivity"],
            "manual_intake_method": item["method"],
        },
        "paper_size_matches_pdf_boxes": not off_target,
        "scaling_or_crop_review_required": off_target,
        "privacy_notice": privacy,
        "human_next_step": route,
        "state": "PREPARED_LOCAL_HANDOFF_R3_HOLD",
        "machine_vendor_and_model_verified": False,
        "venue_capabilities_and_fees_verified": False,
        "native_relatte_owner_admitted": False,
        "actual_print_order_submitted": False,
        "document_data_uploaded": False,
        "emails_sent": 0, "network_requests": 0,
        "payment_taken": False, "retrieval_code_issued": False,
        "paper_consumed": 0, "pages_physically_printed": 0,
        "physical_copies_collected": 0,
        "external_vendor_receipt_obtained": False,
    }
    return {**body, "packet_id": "ghot-print-venue-004:" + json_digest(body)}


def main():
    payload = sys.stdin.buffer.read(32_769)
    need(len(payload) <= 32_768, "PRINT_COMMAND_TOO_LARGE")
    output = compile_handoff(os.environ.get("GHOT_EXTERNAL_CAPABILITY"),
                             json.loads(payload.decode("utf-8")))
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, TypeError, KeyError, UnicodeError,
            json.JSONDecodeError) as error:
        print("R3_HOLD / " + str(error)[:220], file=sys.stderr)
        raise SystemExit(2)
