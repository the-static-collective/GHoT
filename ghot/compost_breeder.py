#!/usr/bin/env python3
"""COMPOST-BREEDER-001: bounded orchestration across Toaster history,
Blender possibility ecology, explicit human KEEP, Instrument Rack seed material,
and a generation-2 Toaster return.

GHoT carries evidence and dispatches exact cards. It does not reinterpret donor
semantics, choose a film, or turn provenance into continuation authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from instrument_rack import MATERIAL_SCHEMA, PACKET_SCHEMA

SESSION_SCHEMA = "ghot.compost-breeder-session/v0"
BREED_REQUEST_SCHEMA = "ghot.compost-breeder-request/v0"
KEEP_REQUEST_SCHEMA = "ghot.compost-breeder-keep-request/v0"
GENERATION2_REQUEST_SCHEMA = "ghot.compost-breeder-generation2-request/v0"
GENERATION2_WITNESS_SCHEMA = "ghot.compost-breeder-generation2-witness/v0"

TOASTER_HISTORY_SCHEMA = "static-collective/rendered-history-capsule/v0"
BLENDER_ECOLOGY_SCHEMA = "haunted-blender/dream-ecology/v1"
BLENDER_SIXUP_SCHEMA = "haunted-blender/dream-sixup-preview/v1"
BLENDER_DESCENDANT_SCHEMA = "haunted-blender/dream-descendant/v1"

BREED_CAPABILITY = "creative.blender.dreambreed.sixup"
KEEP_CAPABILITY = "creative.blender.dreambreed.keep"
GENERATION2_CAPABILITY = "creative.toaster.history-render-generation2"

DONOR_REFS = {
    "toaster_history_compost": {
        "repo": "the-static-collective/the-haunted-toaster",
        "ref": "experiment/nextgen-toaster-013-history-compost",
        "sha": "923b536d068c8daf85e9d960469405e17c4d56f7",
    },
    "blender_dreambreeder": {
        "repo": "the-static-collective/the-haunted-blender",
        "ref": "integration/franken-blender-003-dreambreeder",
        "sha": "5227ffe7b59240bb3daa5527eb4881969091f073",
    },
    "blender_sixup": {
        "repo": "the-static-collective/the-haunted-blender",
        "ref": "integration/franken-blender-004-cutout-compiler",
        "sha": "2b17439c12d87493455596d0dfa2b11bbbb1bfa0",
    },
    "instrument_rack": {
        "repo": "the-static-collective/GHoT",
        "ref": "feat/instrument-rack-001",
        "sha": "3d64e5d486d9324ec6086da69889a81ab2e48cd8",
    },
}

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_id(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)
    return value.strip()


def _sha(value: Any, code: str) -> str:
    text = _require_id(value, code).lower()
    if not SHA256_RE.fullmatch(text):
        raise ValueError(code)
    return text


def _history_ref(capsule: Any) -> dict[str, Any]:
    """Observe the bounded identity surface of a donor-owned Toaster capsule.

    This is structural crossing validation only. GHoT deliberately does not
    recompute Toaster's capsule hash or reinterpret its render-cause semantics.
    """
    if not isinstance(capsule, dict):
        raise ValueError("INVALID_TOASTER_HISTORY_CAPSULE")
    if (
        capsule.get("schema") != TOASTER_HISTORY_SCHEMA
        or capsule.get("authority") != "provenance-only"
    ):
        raise ValueError("INVALID_TOASTER_HISTORY_CAPSULE")
    generation = capsule.get("generation")
    if not isinstance(generation, int) or generation < 1:
        raise ValueError("INVALID_TOASTER_HISTORY_GENERATION")
    rendered = capsule.get("renderedMedia")
    if not isinstance(rendered, dict):
        raise ValueError("INVALID_TOASTER_HISTORY_CAPSULE")
    parents = capsule.get("parents") or []
    if not isinstance(parents, list):
        raise ValueError("INVALID_TOASTER_HISTORY_CAPSULE")
    parent_hashes = []
    for item in parents:
        if not isinstance(item, dict):
            raise ValueError("INVALID_TOASTER_HISTORY_PARENT")
        parent_hashes.append(
            _sha(item.get("capsuleHash"), "INVALID_TOASTER_HISTORY_PARENT")
        )
    return {
        "schema": TOASTER_HISTORY_SCHEMA,
        "capsuleHash": _sha(capsule.get("capsuleHash"), "INVALID_TOASTER_HISTORY_HASH"),
        "generation": generation,
        "renderedMediaSha256": _sha(
            rendered.get("sha256"), "INVALID_TOASTER_RENDERED_MEDIA_HASH"
        ),
        "parentCapsuleHashes": sorted(parent_hashes),
        "authority": "provenance-only",
    }


def _packet_from_dispatch(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("status") != "EXECUTED":
        raise ValueError("INSTRUMENT_DISPATCH_NOT_EXECUTED")
    packet = result.get("packet")
    if not isinstance(packet, dict) or packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("INSTRUMENT_DISPATCH_MISSING_PACKET")
    return packet


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _find_schema(value: Any, schema: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in _walk(value)
            if isinstance(item, dict) and item.get("schema") == schema
        ),
        None,
    )


def _validate_ecology(ecology: Any) -> dict[str, Any]:
    if not isinstance(ecology, dict) or ecology.get("schema") != BLENDER_ECOLOGY_SCHEMA:
        raise ValueError("INVALID_DREAM_ECOLOGY")
    proposals = ecology.get("proposals")
    if not isinstance(proposals, list) or len(proposals) != 6:
        raise ValueError("DREAM_ECOLOGY_REQUIRES_SIX_PROPOSALS")
    ids = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise ValueError("INVALID_DREAM_PROPOSAL")
        proposal_id = _require_id(proposal.get("id"), "INVALID_DREAM_PROPOSAL")
        if proposal.get("authorityClass") != "proposal":
            raise ValueError("DREAM_PROPOSAL_AUTHORITY_ESCALATION")
        ids.append(proposal_id)
    if len(ids) != len(set(ids)):
        raise ValueError("DREAM_PROPOSALS_MUST_BE_UNIQUE")
    if ecology.get("disposition") is not None:
        raise ValueError("BREEDING_RESULT_MUST_REMAIN_UNRESOLVED")
    return copy.deepcopy(ecology)


def _validate_sixup(sixup: Any, ecology: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(sixup, dict) or sixup.get("schema") != BLENDER_SIXUP_SCHEMA:
        raise ValueError("INVALID_DREAM_SIXUP")
    if sixup.get("authorityClass") != "proposal-preview":
        raise ValueError("DREAM_SIXUP_AUTHORITY_ESCALATION")
    if sixup.get("ecologyId") != ecology.get("id"):
        raise ValueError("DREAM_SIXUP_ECOLOGY_MISMATCH")
    previews = sixup.get("previews")
    if not isinstance(previews, list) or len(previews) != 6:
        raise ValueError("DREAM_SIXUP_REQUIRES_SIX_PREVIEWS")
    proposal_ids = {item["id"] for item in ecology["proposals"]}
    observed = []
    for preview in previews:
        if not isinstance(preview, dict):
            raise ValueError("INVALID_DREAM_SIXUP_PREVIEW")
        proposal_id = _require_id(
            preview.get("proposalId"), "INVALID_DREAM_SIXUP_PREVIEW"
        )
        if proposal_id not in proposal_ids:
            raise ValueError("DREAM_SIXUP_UNKNOWN_PROPOSAL")
        if preview.get("authorityClass") != "proposal-preview":
            raise ValueError("DREAM_SIXUP_AUTHORITY_ESCALATION")
        observed.append(proposal_id)
    if set(observed) != proposal_ids:
        raise ValueError("DREAM_SIXUP_MUST_COVER_ECOLOGY_EXACTLY_ONCE")
    _sha(sixup.get("contactSheetSha256"), "INVALID_DREAM_SIXUP_HASH")
    return copy.deepcopy(sixup)


def prepare_breed_request(
    *,
    parent_history_capsule: dict[str, Any],
    relation_id: str,
    source_receipt_ids: list[str],
) -> dict[str, Any]:
    parent = _history_ref(parent_history_capsule)
    relation = _require_id(relation_id, "RELATION_ID_REQUIRED")
    if not isinstance(source_receipt_ids, list) or not source_receipt_ids:
        raise ValueError("SOURCE_RECEIPT_IDS_REQUIRED")
    receipts = sorted(
        {
            _require_id(item, "INVALID_SOURCE_RECEIPT_ID")
            for item in source_receipt_ids
        }
    )
    return {
        "schema": BREED_REQUEST_SCHEMA,
        "authority": "proposal-request-only",
        "parentHistoryRef": parent,
        "relationId": relation,
        "sourceReceiptIds": receipts,
        "requestedEffect": "GROW_SIX_UNBORN_FILM_PREVIEWS",
        "donorContractRefs": copy.deepcopy(DONOR_REFS),
        "laws": [
            "PARENT HISTORY != CHILD DESTINY",
            "BREED REQUEST != BREED EXECUTION",
            "SIX PREVIEWS != SIX HISTORIES",
            "WATCHING != KEEP",
        ],
    }


def open_session(
    *,
    parent_history_capsule: dict[str, Any],
    relation_id: str,
    breeder_dispatch_result: dict[str, Any],
) -> dict[str, Any]:
    parent = _history_ref(parent_history_capsule)
    relation = _require_id(relation_id, "RELATION_ID_REQUIRED")
    packet = _packet_from_dispatch(breeder_dispatch_result)
    if packet.get("capability") != BREED_CAPABILITY:
        raise ValueError("BREED_RESULT_CAPABILITY_MISMATCH")
    ecology = _find_schema(packet.get("donor_result"), BLENDER_ECOLOGY_SCHEMA)
    sixup = _find_schema(packet.get("donor_result"), BLENDER_SIXUP_SCHEMA)
    ecology = _validate_ecology(ecology)
    if ecology.get("commonCheckpointId") != parent["capsuleHash"]:
        raise ValueError("BREED_RESULT_PARENT_HISTORY_MISMATCH")
    if ecology.get("relationId") != relation:
        raise ValueError("BREED_RESULT_RELATION_MISMATCH")
    if ecology.get("generation") != parent["generation"] + 1:
        raise ValueError("BREED_RESULT_GENERATION_MISMATCH")
    sixup = _validate_sixup(sixup, ecology)
    core = {
        "schema": SESSION_SCHEMA,
        "authority": "orchestration-only",
        "status": "AWAITING_HUMAN_KEEP",
        "parentHistoryRef": parent,
        "breederEvidence": {
            "packetId": packet["packet_id"],
            "adapterId": packet.get("adapter_id"),
            "capability": packet.get("capability"),
            "donorResultSha256": packet.get("donor_result_sha256"),
        },
        "ecologyEvidence": ecology,
        "sixupEvidence": sixup,
        "keepEvidence": None,
        "externalSeed": None,
        "generation2Evidence": None,
        "donorContractRefs": copy.deepcopy(DONOR_REFS),
        "laws": [
            "ORCHESTRATION != DONOR SEMANTICS",
            "PREVIEW != KEEP",
            "KEEP REQUIRES EXPLICIT HUMAN SELECTION",
            "PACKET != ADMISSION",
            "ANCESTRY != AUTHORITY",
        ],
    }
    return {
        **core,
        "session_id": "compost-breeder-v0:" + _digest(core),
    }


def prepare_keep_request(
    session: dict[str, Any],
    *,
    proposal_id: str,
) -> dict[str, Any]:
    if not isinstance(session, dict) or session.get("schema") != SESSION_SCHEMA:
        raise ValueError("INVALID_COMPOST_BREEDER_SESSION")
    if session.get("status") != "AWAITING_HUMAN_KEEP":
        raise ValueError("SESSION_NOT_AWAITING_HUMAN_KEEP")
    selected = _require_id(proposal_id, "PROPOSAL_ID_REQUIRED")
    proposals = session["ecologyEvidence"]["proposals"]
    if selected not in {item["id"] for item in proposals}:
        raise ValueError("KEEP_PROPOSAL_NOT_IN_ECOLOGY")
    return {
        "schema": KEEP_REQUEST_SCHEMA,
        "authority": "human-selection-request",
        "sourceSessionId": session["session_id"],
        "proposalId": selected,
        "ecology": copy.deepcopy(session["ecologyEvidence"]),
        "laws": [
            "PREVIEW != KEEP",
            "GHOT != SELECTOR",
            "KEEP REQUEST != KEEP RESULT",
        ],
    }


def accept_keep_result(
    session: dict[str, Any],
    *,
    selected_proposal_id: str,
    keep_source: str,
    keep_dispatch_result: dict[str, Any],
) -> dict[str, Any]:
    if session.get("status") != "AWAITING_HUMAN_KEEP":
        raise ValueError("SESSION_NOT_AWAITING_HUMAN_KEEP")
    selected = _require_id(selected_proposal_id, "PROPOSAL_ID_REQUIRED")
    source = _require_id(keep_source, "KEEP_SOURCE_REQUIRED")
    if selected not in {p["id"] for p in session["ecologyEvidence"]["proposals"]}:
        raise ValueError("KEEP_PROPOSAL_NOT_IN_ECOLOGY")
    packet = _packet_from_dispatch(keep_dispatch_result)
    if packet.get("capability") != KEEP_CAPABILITY:
        raise ValueError("KEEP_RESULT_CAPABILITY_MISMATCH")
    descendant = _find_schema(packet.get("donor_result"), BLENDER_DESCENDANT_SCHEMA)
    ecology = _find_schema(packet.get("donor_result"), BLENDER_ECOLOGY_SCHEMA)
    if not isinstance(descendant, dict) or not isinstance(ecology, dict):
        raise ValueError("KEEP_RESULT_MISSING_BLENDER_EVIDENCE")
    if descendant.get("keptProposalId") != selected:
        raise ValueError("KEEP_RESULT_PROPOSAL_MISMATCH")
    if descendant.get("sourceEcologyId") != session["ecologyEvidence"].get("id"):
        raise ValueError("KEEP_RESULT_ECOLOGY_MISMATCH")
    disposition = ecology.get("disposition") or {}
    if disposition.get("kind") != "KEEP" or disposition.get("proposalId") != selected:
        raise ValueError("KEEP_RESULT_DISPOSITION_MISMATCH")
    if descendant.get("authorityClass") != "continuation-permission":
        raise ValueError("KEEP_RESULT_AUTHORITY_MISMATCH")
    next_session = copy.deepcopy(session)
    next_session["status"] = "KEPT_DESCENDANT_AWAITING_EXTERNAL_SEED"
    next_session["keepEvidence"] = {
        "selectedBy": source,
        "selectedProposalId": selected,
        "packetId": packet["packet_id"],
        "donorResultSha256": packet.get("donor_result_sha256"),
        "descendant": copy.deepcopy(descendant),
        "resolvedEcology": copy.deepcopy(ecology),
    }
    return next_session


def attach_seed_material(
    session: dict[str, Any],
    *,
    seed_material: dict[str, Any],
) -> dict[str, Any]:
    if session.get("status") != "KEPT_DESCENDANT_AWAITING_EXTERNAL_SEED":
        raise ValueError("SESSION_NOT_AWAITING_EXTERNAL_SEED")
    if (
        not isinstance(seed_material, dict)
        or seed_material.get("schema") != MATERIAL_SCHEMA
        or seed_material.get("status") != "ADMITTED_NOT_EXECUTED"
        or seed_material.get("semantic_effect") != "local-material-only"
    ):
        raise ValueError("INVALID_EXTERNAL_SEED_MATERIAL")
    next_session = copy.deepcopy(session)
    next_session["externalSeed"] = {
        "materialId": _require_id(
            seed_material.get("material_id"), "INVALID_EXTERNAL_SEED_MATERIAL"
        ),
        "sourcePacketId": _require_id(
            seed_material.get("source_packet_id"), "INVALID_EXTERNAL_SEED_MATERIAL"
        ),
        "sourceCardId": seed_material.get("source_card_id"),
        "adapterId": seed_material.get("adapter_id"),
        "capability": seed_material.get("capability"),
        "donorResultSha256": _sha(
            seed_material.get("donor_result_sha256"),
            "INVALID_EXTERNAL_SEED_MATERIAL",
        ),
        "status": "ADMITTED_NOT_EXECUTED",
        "authority": "material-only",
    }
    next_session["status"] = "READY_FOR_GENERATION2_REQUEST"
    return next_session


def prepare_generation2_request(session: dict[str, Any]) -> dict[str, Any]:
    if session.get("status") != "READY_FOR_GENERATION2_REQUEST":
        raise ValueError("SESSION_NOT_READY_FOR_GENERATION2")
    keep = session.get("keepEvidence") or {}
    seed = session.get("externalSeed") or {}
    descendant = keep.get("descendant") or {}
    request = {
        "schema": GENERATION2_REQUEST_SCHEMA,
        "authority": "proposal-request-only",
        "sourceSessionId": session["session_id"],
        "parentHistoryRef": copy.deepcopy(session["parentHistoryRef"]),
        "keptDescendantRef": {
            "descendantId": _require_id(
                descendant.get("id"), "MISSING_KEPT_DESCENDANT"
            ),
            "keptProposalId": keep["selectedProposalId"],
            "sourceEcologyId": descendant.get("sourceEcologyId"),
            "keepPacketId": keep["packetId"],
        },
        "externalSeedRef": copy.deepcopy(seed),
        "requestedHistoryParents": [{
            "capsuleHash": session["parentHistoryRef"]["capsuleHash"],
            "generation": session["parentHistoryRef"]["generation"],
        }],
        "requestedEffect": "RENDER_GENERATION2_WITH_PARENT_HISTORY_AND_EXTERNAL_SEED",
        "laws": [
            "KEEP != RENDER",
            "SEED MATERIAL != EXECUTION",
            "EXTERNAL SEED != HISTORICAL PARENT",
            "PARENT HISTORY != FUTURE AUTHORITY",
            "GENERATION2 REQUEST != GENERATION2 RESULT",
        ],
    }
    return request


def accept_generation2_result(
    session: dict[str, Any],
    *,
    generation2_dispatch_result: dict[str, Any],
) -> dict[str, Any]:
    if session.get("status") != "READY_FOR_GENERATION2_REQUEST":
        raise ValueError("SESSION_NOT_READY_FOR_GENERATION2")
    packet = _packet_from_dispatch(generation2_dispatch_result)
    if packet.get("capability") != GENERATION2_CAPABILITY:
        raise ValueError("GENERATION2_RESULT_CAPABILITY_MISMATCH")
    capsule = _find_schema(packet.get("donor_result"), TOASTER_HISTORY_SCHEMA)
    if not isinstance(capsule, dict):
        raise ValueError("GENERATION2_RESULT_MISSING_HISTORY_CAPSULE")
    child = _history_ref(capsule)
    parent = session["parentHistoryRef"]
    if child["generation"] != parent["generation"] + 1:
        raise ValueError("GENERATION2_HISTORY_GENERATION_MISMATCH")
    if parent["capsuleHash"] not in child["parentCapsuleHashes"]:
        raise ValueError("GENERATION2_HISTORY_PARENT_MISMATCH")

    marker = _find_schema(
        packet.get("donor_result"),
        "static-collective/compost-breeder-generation2-result/v0",
    )
    if not isinstance(marker, dict):
        raise ValueError("GENERATION2_RESULT_MISSING_COMPOST_MARKER")
    if marker.get("keptDescendantId") != session["keepEvidence"]["descendant"]["id"]:
        raise ValueError("GENERATION2_KEPT_DESCENDANT_MISMATCH")
    if marker.get("externalSeedMaterialId") != session["externalSeed"]["materialId"]:
        raise ValueError("GENERATION2_EXTERNAL_SEED_MISMATCH")
    if marker.get("historyCapsuleHash") != child["capsuleHash"]:
        raise ValueError("GENERATION2_MARKER_HISTORY_MISMATCH")

    witness_core = {
        "schema": GENERATION2_WITNESS_SCHEMA,
        "authority": "evidence-index-only",
        "sourceSessionId": session["session_id"],
        "parentHistoryRef": copy.deepcopy(parent),
        "childHistoryRef": copy.deepcopy(child),
        "keepEvidenceRef": {
            "packetId": session["keepEvidence"]["packetId"],
            "descendantId": session["keepEvidence"]["descendant"]["id"],
            "selectedProposalId": session["keepEvidence"]["selectedProposalId"],
        },
        "externalSeedRef": copy.deepcopy(session["externalSeed"]),
        "generation2ReturnEvidence": {
            "packetId": packet["packet_id"],
            "donorResultSha256": packet.get("donor_result_sha256"),
        },
        "laws": [
            "WITNESS != DONOR SEMANTICS",
            "EXTERNAL SEED PROVENANCE != HISTORICAL ANCESTRY",
            "CHILD HISTORY != KEEP AUTHORITY",
            "EVIDENCE INDEX != PUBLICATION AUTHORITY",
        ],
    }
    witness = {
        **witness_core,
        "witness_id": "compost-breeder-witness-v0:" + _digest(witness_core),
    }
    next_session = copy.deepcopy(session)
    next_session["status"] = "GENERATION2_WITNESSED"
    next_session["generation2Evidence"] = witness
    return next_session


__all__ = [
    "BREED_CAPABILITY",
    "DONOR_REFS",
    "GENERATION2_CAPABILITY",
    "KEEP_CAPABILITY",
    "SESSION_SCHEMA",
    "GENERATION2_WITNESS_SCHEMA",
    "accept_generation2_result",
    "accept_keep_result",
    "attach_seed_material",
    "open_session",
    "prepare_breed_request",
    "prepare_generation2_request",
    "prepare_keep_request",
]
