#!/usr/bin/env python3
"""COMPOST-BREEDER-002: real Blender DREAMBREEDER 004 crossing.

The breed/six-up capability is loaded from a real Haunted Blender GHoT adapter
manifest supplied by BLENDER_GHOT_ADAPTER_MANIFEST. The remaining KEEP, seed,
and generation-2 legs stay deterministic local simulations so this proof
isolates the first physical donor replacement.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from compost_breeder import (
    accept_generation2_result,
    accept_keep_result,
    attach_seed_material,
    open_session,
    prepare_breed_request,
    prepare_generation2_request,
    prepare_keep_request,
)
from instrument_rack import admit_seed_packet, build_instrument_rack, dispatch_instrument_card


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    if not isinstance(value, str):
        value = canonical(value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parent_history():
    return {
        "schema": "static-collective/rendered-history-capsule/v0",
        "policy": "render-authority-plus-context/v0",
        "authority": "provenance-only",
        "generation": 1,
        "renderedMedia": {
            "sha256": digest("live-blender-generation-1-bytes"),
            "byteLength": 4096,
        },
        "renderAuthority": {
            "authority": "render-cause-reference",
            "planHash": digest("live-blender-generation-1-plan"),
            "planSchema": "static-collective/franken-composition/v0",
            "planPolicy": "franken-composer-001",
            "fps": 24,
            "durationFrames": 1152,
            "kind": "remotion",
            "projectionHash": digest("live-blender-generation-1-projection"),
        },
        "historicalContext": {"authority": "context-reference-only"},
        "parents": [],
        "laws": ["PROVENANCE != BEHAVIOR"],
        "capsuleHash": digest("live-blender-generation-1-history"),
    }


def card(rack, capability):
    matches = [item for item in rack["cards"] if item["capability"] == capability]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one card for {capability}, got {len(matches)}")
    return matches[0]


def main() -> int:
    blender_manifest = Path(
        os.environ.get("BLENDER_GHOT_ADAPTER_MANIFEST", "")
    ).expanduser().resolve()
    if not blender_manifest.is_file():
        raise RuntimeError("BLENDER_GHOT_ADAPTER_MANIFEST must name the real Blender adapter manifest")

    with tempfile.TemporaryDirectory(prefix="ghot-compost-breeder-live-blender-") as raw:
        root = Path(raw)
        home = root / "home"
        local = root / "local-donors"
        local.mkdir()
        adapter = local / "adapter.py"
        local_manifest = local / "adapter-manifest.json"
        counts = local / "counts.json"
        blender_output = root / "blender-output"

        adapter.write_text(
            """import hashlib,json,os,pathlib,sys
root=pathlib.Path(__file__).resolve().parent
counts_path=root/'counts.json'
counts=json.loads(counts_path.read_text()) if counts_path.exists() else {}
cap=os.environ['GHOT_EXTERNAL_CAPABILITY']
counts[cap]=counts.get(cap,0)+1
counts_path.write_text(json.dumps(counts,sort_keys=True))
payload=json.load(sys.stdin)
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def h(v):
    if not isinstance(v,str): v=canonical(v)
    return hashlib.sha256(v.encode()).hexdigest()
if cap=='creative.blender.dreambreed.keep':
    ecology=json.loads(json.dumps(payload['ecology']))
    selected=payload['proposalId']
    proposal=next(p for p in ecology['proposals'] if p['id']==selected)
    descendant={
        'schema':'haunted-blender/dream-descendant/v1',
        'id':'dream-descendant:'+h({'ecology':ecology['id'],'proposal':selected})[:24],
        'parentCheckpointId':ecology['commonCheckpointId'],
        'sourceEcologyId':ecology['id'],
        'keptProposalId':selected,
        'relationId':ecology['relationId'],
        'worldPatch':proposal['worldPatch'],
        'motionGrammar':proposal['motionGrammar'],
        'traits':proposal['traits'],
        'donorId':proposal.get('donorId'),
        'authorityClass':'continuation-permission',
        'status':'unrendered-descendant',
    }
    ecology['disposition']={
        'kind':'KEEP','proposalId':selected,
        'authorityClass':'continuation-permission',
        'resultDescendantId':descendant['id'],
        'createsHistory':False,
    }
    ecology['ghostCandidates']=[
        {'proposalId':p['id'],'state':'inert-unselected-possibility'}
        for p in ecology['proposals'] if p['id']!=selected
    ]
    result={'schema':'compost-breeder.live-blender.keep/v0','ecology':ecology,'descendant':descendant}
elif cap=='creative.mineral.seed':
    seed={
        'schema':'simulation.mineral-seed/v0',
        'requestHash':h(payload),
        'field':'mandelbrot-x-lucas',
        'tileIdentity':'mineral:'+h('mineral:'+h(payload))[:24],
        'authority':'material-proposal-only',
    }
    result={'schema':'compost-breeder.live-blender.seed/v0','seed':seed}
elif cap=='creative.toaster.history-render-generation2':
    parent=payload['parentHistoryRef']
    child_hash=h({
        'parent':parent['capsuleHash'],
        'descendant':payload['keptDescendantRef']['descendantId'],
        'seed':payload['externalSeedRef']['materialId'],
    })
    capsule={
        'schema':'static-collective/rendered-history-capsule/v0',
        'policy':'render-authority-plus-context/v0',
        'authority':'provenance-only',
        'generation':parent['generation']+1,
        'renderedMedia':{'sha256':h('generation-2-bytes:'+child_hash),'byteLength':8192},
        'renderAuthority':{
            'authority':'render-cause-reference',
            'planHash':h('generation-2-plan:'+child_hash),
            'planSchema':'static-collective/franken-composition/v0',
            'planPolicy':'franken-composer-001',
            'fps':24,'durationFrames':1152,
            'kind':'remotion','projectionHash':h('generation-2-projection:'+child_hash),
        },
        'historicalContext':{'authority':'context-reference-only'},
        'parents':[{'capsuleHash':parent['capsuleHash'],'generation':parent['generation']}],
        'laws':['PROVENANCE != BEHAVIOR'],
        'capsuleHash':child_hash,
    }
    marker={
        'schema':'static-collective/compost-breeder-generation2-result/v0',
        'historyCapsuleHash':child_hash,
        'keptDescendantId':payload['keptDescendantRef']['descendantId'],
        'externalSeedMaterialId':payload['externalSeedRef']['materialId'],
        'authority':'donor-result-evidence',
    }
    result={'schema':'compost-breeder.live-blender.generation2/v0','historyCapsule':capsule,'marker':marker}
else:
    raise SystemExit('unsupported local simulation capability')
print(json.dumps(result,sort_keys=True,separators=(',',':')))
""",
            encoding="utf-8",
        )

        local_capabilities = [
            "creative.blender.dreambreed.keep",
            "creative.mineral.seed",
            "creative.toaster.history-render-generation2",
        ]
        local_manifest.write_text(
            json.dumps(
                {
                    "schema": "ghot.external-adapter-manifest/v0",
                    "adapter_id": "simulation.compost-breeder-remaining-legs",
                    "capabilities": [
                        {
                            "capability": capability,
                            "protocol": "stdin-json/stdout-json-v0",
                            "command": "python3",
                            "args": ["adapter.py"],
                            "timeout_seconds": 10,
                            "limits": {
                                "network": False,
                                "arbitrary_shell": False,
                                "writes_only_requested_output_dir": False,
                            },
                        }
                        for capability in local_capabilities
                    ],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        old_home = os.environ.get("GHOT_HOME")
        old_manifests = os.environ.get("GHOT_ADAPTER_MANIFESTS")
        old_blender_output = os.environ.get("HAUNTED_BLENDER_GHOT_OUTPUT_DIR")
        os.environ["GHOT_HOME"] = str(home)
        os.environ["GHOT_ADAPTER_MANIFESTS"] = os.pathsep.join(
            [str(blender_manifest), str(local_manifest)]
        )
        os.environ["HAUNTED_BLENDER_GHOT_OUTPUT_DIR"] = str(blender_output)
        try:
            rack = build_instrument_rack()
            assert len(rack["cards"]) == 4
            breed_card = card(rack, "creative.blender.dreambreed.sixup")
            assert breed_card["adapter_id"] == "haunted-blender.compost-breeder"
            assert breed_card["status"] == "PROPOSAL_ONLY"

            parent = parent_history()
            relation_id = "relation:history-compost:real-blender-004"
            breed_request = prepare_breed_request(
                parent_history_capsule=parent,
                relation_id=relation_id,
                source_receipt_ids=["receipt:render:g1"],
            )
            breed_result = dispatch_instrument_card(
                breed_card,
                breed_request,
                dispatch_source="simulation-human",
            )
            assert breed_result["status"] == "EXECUTED"
            assert breed_result["packet"]["adapter_id"] == "haunted-blender.compost-breeder"

            session = open_session(
                parent_history_capsule=parent,
                relation_id=relation_id,
                breeder_dispatch_result=breed_result,
            )
            assert session["status"] == "AWAITING_HUMAN_KEEP"
            assert session["ecologyEvidence"]["disposition"] is None
            assert len(session["ecologyEvidence"]["proposals"]) == 6
            assert len(session["sixupEvidence"]["previews"]) == 6
            assert Path(session["sixupEvidence"]["contactSheetVideo"]).is_file()
            for preview in session["sixupEvidence"]["previews"]:
                assert Path(preview["videoPath"]).is_file()

            request_dirs = [item for item in blender_output.iterdir() if item.is_dir()]
            assert len(request_dirs) == 1

            breed_replay = dispatch_instrument_card(
                breed_card,
                breed_request,
                dispatch_source="simulation-human",
            )
            assert breed_replay["dispatch_id"] == breed_result["dispatch_id"]
            assert breed_replay["packet"]["packet_id"] == breed_result["packet"]["packet_id"]
            assert len([item for item in blender_output.iterdir() if item.is_dir()]) == 1

            selected = session["ecologyEvidence"]["proposals"][2]["id"]
            keep_request = prepare_keep_request(session, proposal_id=selected)
            keep_result = dispatch_instrument_card(
                card(rack, "creative.blender.dreambreed.keep"),
                keep_request,
                dispatch_source="simulation-human",
            )
            session = accept_keep_result(
                session,
                selected_proposal_id=selected,
                keep_source="simulation-human",
                keep_dispatch_result=keep_result,
            )
            assert session["keepEvidence"]["selectedProposalId"] == selected

            seed_result = dispatch_instrument_card(
                card(rack, "creative.mineral.seed"),
                {
                    "descendantId": session["keepEvidence"]["descendant"]["id"],
                    "request": "mandelbrot-x-lucas texture mineral",
                },
                dispatch_source="simulation-human",
            )
            seed_material = admit_seed_packet(
                seed_result["packet"],
                admission_source="simulation-human",
            )
            session = attach_seed_material(session, seed_material=seed_material)
            assert session["status"] == "READY_FOR_GENERATION2_REQUEST"

            generation2_request = prepare_generation2_request(session)
            generation2_result = dispatch_instrument_card(
                card(rack, "creative.toaster.history-render-generation2"),
                generation2_request,
                dispatch_source="simulation-human",
            )
            session = accept_generation2_result(
                session,
                generation2_dispatch_result=generation2_result,
            )
            witness = session["generation2Evidence"]
            assert session["status"] == "GENERATION2_WITNESSED"
            assert witness["parentHistoryRef"]["capsuleHash"] == parent["capsuleHash"]
            assert witness["childHistoryRef"]["generation"] == 2
            assert witness["externalSeedRef"]["materialId"] == seed_material["material_id"]
            assert witness["keepEvidenceRef"]["selectedProposalId"] == selected

            local_counts = json.loads(counts.read_text(encoding="utf-8"))
            assert local_counts["creative.blender.dreambreed.keep"] == 1
            assert local_counts["creative.mineral.seed"] == 1
            assert local_counts["creative.toaster.history-render-generation2"] == 1
        finally:
            if old_home is None:
                os.environ.pop("GHOT_HOME", None)
            else:
                os.environ["GHOT_HOME"] = old_home
            if old_manifests is None:
                os.environ.pop("GHOT_ADAPTER_MANIFESTS", None)
            else:
                os.environ["GHOT_ADAPTER_MANIFESTS"] = old_manifests
            if old_blender_output is None:
                os.environ.pop("HAUNTED_BLENDER_GHOT_OUTPUT_DIR", None)
            else:
                os.environ["HAUNTED_BLENDER_GHOT_OUTPUT_DIR"] = old_blender_output

    print(
        json.dumps(
            {
                "status": "ok",
                "specimen": "COMPOST-BREEDER-002-LIVE-BLENDER",
                "real_donor": "creative.blender.dreambreed.sixup",
                "laws": [
                    "REAL DONOR != GHOT SEMANTICS",
                    "PREVIEW != KEEP",
                    "WATCHING != KEEP",
                    "REPLAY != REEXECUTION",
                    "ONE LIVE LEG != ALL LIVE LEGS",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
