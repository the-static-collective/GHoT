#!/usr/bin/env python3
"""PRINTER-ORGAN-001: GHoT read-only physical-printer aperture.

One operator-owned descriptor -> GHoT bounded capabilities -> proposal-only
reLATTE handoff candidate. Hardware state is observed with GET only.
NO upload, start, G-code send, heater/motor control, print-queue mutation,
execution authority, source authentication, or physical part claim.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

MANIFEST_SCHEMA = "ghot.printer-owner-declaration/v0"
REQUEST_SCHEMA = "static-os.fabrication-request/v0"
RESULT_SCHEMA = "ghot.printer-organ-observation/v0"
PROPOSAL_SCHEMA = "ghot.printer-organ-proposal/v0"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,99}$")
TECHNOLOGIES = frozenset((
    "FFF_FDM", "MSLA", "LASER_SLA", "DLP", "SLS_POLYMER",
    "MJF_POLYMER", "BINDER_JETTING", "MATERIAL_JETTING", "METAL_PBF", "DED"
))
MATERIALS = frozenset((
    "PLA", "PETG", "ABS", "TPU", "NYLON_FILAMENT", "STANDARD_RESIN",
    "ENGINEERING_RESIN", "NYLON_POWDER", "POLYMER_POWDER",
    "METAL_POWDER", "CERAMIC_POWDER", "PROPRIETARY", "UNKNOWN"
))
MAX_MANIFEST = 10_000
MAX_HTTP_BYTES = 32_768


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(item, fields, name):
    require(type(item) is dict and set(item) == set(fields), name + "_FIELDS_INVALID")


def canonical(item):
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf8")


def digest(item):
    return hashlib.sha256(canonical(item)).hexdigest()


def safe_id(value, name):
    require(type(value) is str and SAFE_ID.fullmatch(value) is not None, name + "_INVALID")
    return value


def load_owner_manifest(path):
    target = Path(path).resolve(strict=True)
    require(target.is_file() and not target.is_symlink(), "OWNER_MANIFEST_FILE_REQUIRED")
    require(target.stat().st_size <= MAX_MANIFEST, "OWNER_MANIFEST_TOO_LARGE")
    item = json.loads(target.read_text(encoding="utf8"))
    return verify_owner(item)


def verify_owner(item):
    keys(item, {
        "schema", "machine_id", "owner_ref", "manufacturer", "model", "technology",
        "build_volume_mm", "materials", "profile_ref", "endpoint_kind",
        "status_endpoint", "hardware_authenticated", "physical_execution_authorized",
        "physical_output_created"
    }, "OWNER")
    require(item["schema"] == MANIFEST_SCHEMA, "OWNER_SCHEMA_INVALID")
    safe_id(item["machine_id"], "MACHINE_ID")
    safe_id(item["owner_ref"], "OWNER_REF")
    for label in ("manufacturer", "model"):
        require(type(item[label]) is str and 1 <= len(item[label]) <= 100
                and not any(ord(ch) < 32 for ch in item[label]), "MACHINE_LABEL_INVALID")
    require(item["technology"] in TECHNOLOGIES, "UNKNOWN_PRINTER_TECHNOLOGY")
    dims = item["build_volume_mm"]
    keys(dims, ("x", "y", "z"), "DIMENSIONS")
    require(all(type(dims[k]) in (int, float) and 1 <= dims[k] <= 5000 for k in dims),
            "DIMENSIONS_INVALID")
    mats = item["materials"]
    require(type(mats) is list and 1 <= len(mats) <= 12 and
            len(mats) == len(set(mats)) and all(type(x) is str and x in MATERIALS for x in mats),
            "MATERIAL_CLASSES_INVALID")
    require(item["profile_ref"] is None or safe_id(item["profile_ref"], "PROFILE_REF"),
            "PROFILE_REFERENCE_INVALID")
    require(item["endpoint_kind"] in ("NONE", "OCTOPRINT_LOOPBACK_READ_ONLY"),
            "ENDPOINT_KIND_INVALID")
    if item["endpoint_kind"] == "NONE":
        require(item["status_endpoint"] is None, "ENDPOINT_MUST_BE_NONE")
    else:
        normalize_endpoint(item["status_endpoint"])
    require(item["hardware_authenticated"] is False and
            item["physical_execution_authorized"] is False and
            item["physical_output_created"] is False,
            "DECLARATION_CANNOT_GRANT_PHYSICAL_AUTHORITY")
    return item


def normalize_endpoint(value):
    require(type(value) is str and len(value) < 150, "ENDPOINT_URL_INVALID")
    parsed = urlsplit(value)
    # No DNS, credentials, fragments, queries or path from a payload. No LAN SSRF.
    require(parsed.scheme == "http" and not parsed.username and not parsed.password and
            not parsed.query and not parsed.fragment and parsed.path in ("", "/") and
            parsed.hostname in ("127.0.0.1", "::1"), "ONLY_LITERAL_LOOPBACK_HTTP_ALLOWED")
    require(parsed.port is not None and 1 <= parsed.port <= 65535, "PORT_REQUIRED")
    return "http://127.0.0.1:" + str(parsed.port) if parsed.hostname == "127.0.0.1" else "http://[::1]:" + str(parsed.port)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_status(base, suffix, opener, api_key):
    url = base + suffix
    headers = {"Accept": "application/json", "User-Agent": "GHoT-Printer-Organ-001-ReadOnly"}
    if api_key:
        require(type(api_key) is str and len(api_key) <= 256 and "\n" not in api_key,
                "OCTOPRINT_KEY_INVALID")
        headers["X-Api-Key"] = api_key
    req = Request(url, method="GET", headers=headers)
    response = opener.open(req, timeout=2)
    with response as r:
        require(r.status == 200, "PRINTER_STATUS_NON_200")
        require(r.headers.get_content_type() == "application/json", "PRINTER_STATUS_NOT_JSON")
        data = r.read(MAX_HTTP_BYTES + 1)
    require(len(data) <= MAX_HTTP_BYTES, "PRINTER_STATUS_TOO_LARGE")
    return json.loads(data)


def observe(owner, *, opener=None, api_key=None):
    owner = verify_owner(owner)
    status = {
        "schema": RESULT_SCHEMA, "machine_id": owner["machine_id"],
        "owner_manifest_sha256": digest(owner), "technology": owner["technology"],
        "profile_ref": owner["profile_ref"],
        "status": "NO_DEVICE_CONTACTED", "source": "OWNER_DECLARATION_ONLY",
        "machine_authenticated": False, "physical_execution_authorized": False,
        "hardware_actions": [], "print_started": False,
        "material_custody_verified": False, "physical_output_created": False,
        "connection": None, "job": None
    }
    if owner["endpoint_kind"] == "NONE":
        return status
    base = normalize_endpoint(owner["status_endpoint"])
    opener = opener or build_opener(ProxyHandler({}), NoRedirect())
    connection = _get_status(base, "/api/connection", opener, api_key)
    job = _get_status(base, "/api/job", opener, api_key)
    require(type(connection) is dict and type(job) is dict and
            type(connection.get("current")) is dict and
            type(job.get("state")) is str, "DEVICE_STATUS_SHAPE_INVALID")
    current = connection["current"]
    allowed_state = current.get("state")
    require(type(allowed_state) is str and len(allowed_state) <= 100, "CONNECTION_STATE_INVALID")
    # Minimal normalized observations only; never leak filenames, camera URLs,
    # API keys, contacts, origin IP, plugin info or connection metadata.
    status.update({
        "status": "READ_ONLY_STATUS_OBSERVED_NOT_DEVICE_AUTHENTICATED",
        "source": "OCTOPRINT_LOOPBACK_GET",
        "connection": {"state": allowed_state},
        "job": {"state": job["state"][:100]},
    })
    return status


def verify_source_request(request):
    # A self-consistent request hash is not author authenticity!
    require(type(request) is dict, "FABRICATION_REQUEST_OBJECT_REQUIRED")
    fields = {
        "schema", "source_repository", "original_field_id",
        "original_signed_cad_crossing_id", "source_design_candidate_id",
        "original_print_packet_id", "operator_ref", "purpose_ref",
        "requested_node_count", "selected_nodes", "source_selection_digest",
        "state", "owner_machine_grants_included", "fabrication_occurred",
        "physical_parts", "new_money", "request_id"
    }
    keys(request, fields, "SOURCE_REQUEST")
    require(request["schema"] == REQUEST_SCHEMA and
            request["source_repository"] == "the-static-collective/static-os" and
            request["state"] == "FABRICATION_PROPOSAL_ONLY" and
            request["owner_machine_grants_included"] is False and
            request["fabrication_occurred"] is False and
            request["physical_parts"] == 0 and request["new_money"] == 0 and
            request["requested_node_count"] == 3, "SOURCE_REQUEST_NOT_PROPOSAL_ONLY")
    for item in ("original_field_id", "original_signed_cad_crossing_id",
                 "source_design_candidate_id", "original_print_packet_id",
                 "source_selection_digest", "operator_ref", "purpose_ref"):
        require(type(request[item]) is str and 3 <= len(request[item]) <= 180,
                "SOURCE_IDENTIFIER_INVALID")
    selection = request["selected_nodes"]
    require(type(selection) is list and len(selection) == 3, "THREE_SOURCE_NODES_REQUIRED")
    ids = []
    for node in selection:
        keys(node, {"machine_id", "technology", "published_compatibility", "reason",
                    "hardware_authenticated", "physical_print_permission"}, "SELECTED_NODE")
        safe_id(node["machine_id"], "SELECTED_MACHINE")
        require(node["technology"] in TECHNOLOGIES and
                type(node["published_compatibility"]) is str and
                type(node["reason"]) is str and
                node["hardware_authenticated"] is False and
                node["physical_print_permission"] is False, "SOURCE_NODE_MAY_NOT_GRANT_PRINT")
        ids.append(node["machine_id"])
    require(len(set(ids)) == 3, "DUPLICATE_SOURCE_NODE")
    body = {k:v for k,v in request.items() if k != "request_id"}
    require(request["request_id"] == "static-os-fabrication-013:" + digest(body),
            "FABRICATION_REQUEST_ID_MISMATCH")
    return request


def propose(owner, request):
    owner = verify_owner(owner)
    request = verify_source_request(request)
    matches = [node for node in request["selected_nodes"] if node["machine_id"] == owner["machine_id"]]
    require(len(matches) == 1, "PRINTER_NOT_EXPLICITLY_SELECTED")
    match = matches[0]
    reason = "OWNER_DECLARED_COMPATIBILITY_NOT_CALIBRATION"
    if match["technology"] != owner["technology"]:
        reason = "OWNER_TECHNOLOGY_CONTRADICTION"
    elif owner["profile_ref"] is None:
        reason = "MISSING_MODEL_AND_MATERIAL_PROFILE"
    elif match["published_compatibility"] != "SOFTWARE_TOOLPATH_ONLY":
        reason = "SOURCE_PRINTER_COMPATIBILITY_UNVERIFIED"
    # No source-native trust proof or current owner grant exists in this organ.
    body = {
        "schema": PROPOSAL_SCHEMA,
        "machine_id": owner["machine_id"], "owner_ref": owner["owner_ref"],
        "owner_declaration_sha256": digest(owner),
        "source_request_id": request["request_id"],
        "source_request_digest": digest(request),
        "source_recomputed_in_static_os": False,
        "signed_cad_evidence_cold_verified_here": False,
        "local_machine_identity_authenticated": False,
        "reLATTE_native_crossing_created": False,
        "native_owner_local_admission_obtained": False,
        "route": "R3_HOLD",
        "reason": reason,
        "proposed_capability": "fabrication.propose-only",
        "driver_command": None, "automatic_start": False,
        "material_consumed": 0, "parts_created": 0, "treasury_inventory_added": 0,
    }
    return {**body, "proposal_id": "ghot-printer-proposal-001:" + digest(body)}


def act(payload, owner, capability):
    keys(payload, {"schema", "action", "request"}, "PRINTER_ADAPTER_INPUT")
    require(payload["schema"] == "ghot.printer-organ-command/v0", "COMMAND_SCHEMA_INVALID")
    if capability == "printer.status.read":
        require(payload["action"] == "status" and payload["request"] is None,
                "STATUS_COMMAND_MUST_NOT_HAVE_TASK")
        return observe(owner, api_key=os.environ.get("GHOT_PRINTER_OCTOPRINT_API_KEY"))
    if capability == "printer.fabrication.propose":
        require(payload["action"] == "propose", "PROPOSAL_COMMAND_ONLY")
        return propose(owner, payload["request"])
    raise ValueError("CAPABILITY_NOT_EXPOSED")


def main():
    # External adapters inherit a manifest configured by the local owner,
    # not from a network-provided job. Missing owner config means no machine.
    owner_file = os.environ.get("GHOT_PRINTER_OWNER_FILE")
    require(type(owner_file) is str and owner_file, "EXPLICIT_OWNER_FILE_REQUIRED")
    raw = sys.stdin.buffer.read(200_001)
    require(len(raw) <= 200_000, "BOUNDED_STDIN_EXCEEDED")
    payload = json.loads(raw.decode("utf8"))
    owner = load_owner_manifest(owner_file)
    result = act(payload, owner, os.environ.get("GHOT_EXTERNAL_CAPABILITY"))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, URLError, HTTPError, UnicodeError) as exc:
        print("HOLD / " + str(exc), file=sys.stderr)
        raise SystemExit(2)
