#!/usr/bin/env python3
"""Durable end-to-end contract specimen for COMPOST-BREEDER-001."""

from __future__ import annotations

import copy
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
from instrument_rack import (
    admit_seed_packet,
    build_instrument_rack,
    dispatch_instrument_card,
)


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parent_history() -> dict:
    media_sha = _sha_text("generation-1-render-bytes")
    capsule_hash = _sha_text("generation-1-history-capsule")
    return {
        "schema": "static-collective/rendered-history-capsule/v0",
        "policy": "render-authority-plus-context/v0",
        "authority": "provenance-only",
        "generation": 1,
        "renderedMedia": {
            "sha256": media_sha,
            "byteLength": 4096,
        },
        "renderAuthority": {
            "authority": "render-cause-reference",
            "planHash": _sha_text("generation-1-plan"),
            "planSchema": "static-collective/franken-composition/v0",
            "planPolicy": "franken-composer-001",
            "fps": 24,
            "durationFrames": 1152,
            "kind": "remotion",
            "projectionHash": _sha_text("generation-1-projection"),
        },
        "historicalContext": {
            "authority": "context-reference-only",
        },
        "parents": [],
        "laws": ["PROVENANCE != BEHAVIOR"],
        "capsuleHash": capsule_hash,
    }


def _card(rack: dict, capability: str) -> dict:
    matches = [item for item in rack["cards"] if item["capability"] == capability]
    if len(matches) != 1:
        raise AssertionError(f"expected one instrument card for {capability}")
    return matches[0]


def _counter(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ghot-compost-breeder-") as raw:
        root = Path(raw)
        home = root / "home"
        donor = root / "donor"
        donor.mkdir()
        adapter = donor / "adapter.py"
        manifest = donor / "adapter-manifest.json"
        counter = donor / "counts.json"

        adapter.write_text(
            """import hashlib,json,os,pathlib,sys
root=pathlib.Path(__file__).resolve().parent
counter=root/'counts.json'
counts=json.loads(counter.read_text()) if counter.exists() else {}
cap=os.environ['GHOT_EXTERNAL_CAPABILITY']
counts[cap]=counts.get(cap,0)+1
counter.write_text(json.dumps(counts,sort_keys=True))
payload=json.load(sys.stdin)
def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def h(v):
    if not isinstance(v,str): v=canonical(v)
    return hashlib.sha256(v.encode()).hexdigest()
def artifact(name,obj):
    text=json.dumps(obj,sort_keys=True,separators=(',',':'))+'\\n'
    return {name+'_text':text,name+'_sha256':h(text)}

if cap=='creative.blender.dreambreed.sixup':
    seed=h(payload)
    ecology_id='dream-ecology:'+seed[:24]
    proposals=[]
    previews=[]
    for i in range(6):
        pid='dream-proposal:'+h(seed+':'+str(i+1))[:24]
        proposals.append({
            'id':pid,'slot':i+1,'authorityClass':'proposal',
            'label':['Late Bloom','Hinge Weather','Ghost Negative','Room From Difference','Stained Memory','Cardboard Ascension'][i],
            'invitation':'sim-'+str(i+1),
            'worldPatch':{'surface':'specimen-'+str(i+1)},
            'motionGrammar':['hold','drift-'+str(i+1)],
            'traits':['simulated','slot-'+str(i+1)],
            'donorId':None,
        })
        previews.append({
            'slot':i+1,'proposalId':pid,'label':'preview-'+str(i+1),
            'compiledPlanId':'dream-cutout-plan:'+h(pid)[:24],
            'videoSha256':h('preview-video:'+pid),
            'authorityClass':'proposal-preview',
        })
    ecology={
        'schema':'haunted-blender/dream-ecology/v1',
        'id':ecology_id,
        'relationId':payload['relationId'],
        'commonCheckpointId':payload['parentHistoryRef']['capsuleHash'],
        'generation':payload['parentHistoryRef']['generation']+1,
        'capsule':{
            'id':'dream-haunt-capsule:'+seed[:24],
            'kind':'static-collective/causal-capsule/v1',
            'authorityClass':'influence-only',
        },
        'proposals':proposals,'disposition':None,'ghostCandidates':[],
    }
    sixup={
        'schema':'haunted-blender/dream-sixup-preview/v1',
        'ecologyId':ecology_id,'authorityClass':'proposal-preview',
        'previews':previews,
        'contactSheetVideo':'six-up.mp4',
        'contactSheetSha256':h('six-up:'+ecology_id),
        'laws':['WATCHING != KEEP'],
    }
    art={}
    art.update(artifact('ecology',ecology))
    art.update(artifact('sixup',sixup))
    result={'schema':'compost-breeder.blender-sixup-result/v0','ecology':ecology,'sixup':sixup,'artifact':art}
elif cap=='creative.blender.dreambreed.keep':
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
        'donorId':proposal['donorId'],
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
    art={}
    art.update(artifact('kept_descendant',descendant))
    result={'schema':'compost-breeder.blender-keep-result/v0','ecology':ecology,'descendant':descendant,'artifact':art}
elif cap=='creative.mineral.seed':
    seed={
        'schema':'simulation.mineral-seed/v0',
        'requestHash':h(payload),
        'field':'mandelbrot-x-lucas',
        'tileIdentity':'mineral:'+h('mineral:'+h(payload))[:24],
        'authority':'material-proposal-only',
    }
    result={'schema':'simulation.mineral-result/v0','seed':seed,'artifact':artifact('mineral_seed',seed)}
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
    art={}
    art.update(artifact('generation2_history',capsule))
    art.update(artifact('generation2_marker',marker))
    result={'schema':'compost-breeder.toaster-generation2-result/v0','historyCapsule':capsule,'marker':marker,'artifact':art}
else:
    raise SystemExit('unsupported capability')
print(json.dumps(result,sort_keys=True,separators=(',',':')))
""",
            encoding="utf-8",
        )

        capabilities = [
            "creative.blender.dreambreed.sixup",
            "creative.blender.dreambreed.keep",
            "creative.mineral.seed",
            "creative.toaster.history-render-generation2",
        ]
        manifest.write_text(
            json.dumps(
                {
                    "schema": "ghot.external-adapter-manifest/v0",
                    "adapter_id": "simulation.compost-breeder-donors",
                    "capabilities": [
                        {
                            "capability": capability,
                            "protocol": "stdin-json/stdout-json-v0",
                            "command": "python3",
                            "args": ["adapter.py"],
                            "timeout_seconds": 5,
                            "limits": {
                                "network": False,
                                "arbitrary_shell": False,
                                "writes_only_requested_output_dir": False,
                            },
                        }
                        for capability in capabilities
                    ],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        old_home = os.environ.get("GHOT_HOME")
        old_manifests = os.environ.get("GHOT_ADAPTER_MANIFESTS")
        os.environ["GHOT_HOME"] = str(home)
        os.environ["GHOT_ADAPTER_MANIFESTS"] = str(manifest)
        try:
            parent = _parent_history()
            rack = build_instrument_rack()
            assert len(rack["cards"]) == 4
            assert counter.exists() is False

            breed_request = prepare_breed_request(
                parent_history_capsule=parent,
                relation_id="relation:history-compost:gen1",
                source_receipt_ids=["receipt:render:g1"],
            )
            breed_card = _card(rack, "creative.blender.dreambreed.sixup")
            breed_result = dispatch_instrument_card(
                breed_card,
                breed_request,
                dispatch_source="simulation-human",
            )
            assert _counter(counter)["creative.blender.dreambreed.sixup"] == 1

            session = open_session(
                parent_history_capsule=parent,
                relation_id="relation:history-compost:gen1",
                breeder_dispatch_result=breed_result,
            )
            assert session["status"] == "AWAITING_HUMAN_KEEP"
            assert len(session["ecologyEvidence"]["proposals"]) == 6
            assert len(session["sixupEvidence"]["previews"]) == 6
            assert session["parentHistoryRef"]["capsuleHash"] == parent["capsuleHash"]

            wrong_relation_session = None
            try:
                wrong_relation_session = open_session(
                    parent_history_capsule=parent,
                    relation_id="relation:wrong",
                    breeder_dispatch_result=breed_result,
                )
                raise AssertionError("wrong relation must not open the breeder session")
            except ValueError as exc:
                assert "BREED_RESULT_RELATION_MISMATCH" in str(exc)
            assert wrong_relation_session is None

            selected = session["ecologyEvidence"]["proposals"][3]["id"]
            keep_request = prepare_keep_request(session, proposal_id=selected)
            keep_card = _card(rack, "creative.blender.dreambreed.keep")

            wrong_keep_payload = copy.deepcopy(keep_request)
            wrong_keep_payload["proposalId"] = session["ecologyEvidence"]["proposals"][0]["id"]
            wrong_keep_result = dispatch_instrument_card(
                keep_card,
                wrong_keep_payload,
                dispatch_source="simulation-human-wrong-branch",
            )
            try:
                accept_keep_result(
                    session,
                    selected_proposal_id=selected,
                    keep_source="simulation-human",
                    keep_dispatch_result=wrong_keep_result,
                )
                raise AssertionError("mismatched KEEP result must refuse")
            except ValueError as exc:
                assert "KEEP_RESULT_PROPOSAL_MISMATCH" in str(exc)

            keep_result = dispatch_instrument_card(
                keep_card,
                keep_request,
                dispatch_source="simulation-human",
            )
            session = accept_keep_result(
                session,
                selected_proposal_id=selected,
                keep_source="simulation-human",
                keep_dispatch_result=keep_result,
            )
            assert session["status"] == "KEPT_DESCENDANT_AWAITING_EXTERNAL_SEED"
            assert session["keepEvidence"]["selectedProposalId"] == selected
            assert session["keepEvidence"]["descendant"]["authorityClass"] == "continuation-permission"

            seed_card = _card(rack, "creative.mineral.seed")
            seed_result = dispatch_instrument_card(
                seed_card,
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
            assert seed_material["status"] == "ADMITTED_NOT_EXECUTED"
            session = attach_seed_material(session, seed_material=seed_material)
            assert session["status"] == "READY_FOR_GENERATION2_REQUEST"

            generation2_request = prepare_generation2_request(session)
            assert generation2_request["parentHistoryRef"]["capsuleHash"] == parent["capsuleHash"]
            assert generation2_request["externalSeedRef"]["materialId"] == seed_material["material_id"]
            assert (
                generation2_request["keptDescendantRef"]["descendantId"]
                == session["keepEvidence"]["descendant"]["id"]
            )
            assert generation2_request["requestedHistoryParents"] == [{
                "capsuleHash": parent["capsuleHash"],
                "generation": 1,
            }]

            toaster_card = _card(rack, "creative.toaster.history-render-generation2")
            generation2_result = dispatch_instrument_card(
                toaster_card,
                generation2_request,
                dispatch_source="simulation-human",
            )
            session = accept_generation2_result(
                session,
                generation2_dispatch_result=generation2_result,
            )
            assert session["status"] == "GENERATION2_WITNESSED"
            witness = session["generation2Evidence"]
            assert witness["parentHistoryRef"]["capsuleHash"] == parent["capsuleHash"]
            assert witness["childHistoryRef"]["generation"] == 2
            assert parent["capsuleHash"] in witness["childHistoryRef"]["parentCapsuleHashes"]
            assert witness["externalSeedRef"]["materialId"] == seed_material["material_id"]
            assert witness["keepEvidenceRef"]["selectedProposalId"] == selected
            assert witness["authority"] == "evidence-index-only"

            replay = dispatch_instrument_card(
                toaster_card,
                generation2_request,
                dispatch_source="simulation-human",
            )
            assert replay["packet"]["packet_id"] == generation2_result["packet"]["packet_id"]

            counts = _counter(counter)
            assert counts["creative.blender.dreambreed.sixup"] == 1
            assert counts["creative.blender.dreambreed.keep"] == 2
            assert counts["creative.mineral.seed"] == 1
            assert counts["creative.toaster.history-render-generation2"] == 1

            bad_material = copy.deepcopy(seed_material)
            bad_material["status"] = "EXECUTED"
            pre_seed_session = accept_keep_result(
                open_session(
                    parent_history_capsule=parent,
                    relation_id="relation:history-compost:gen1",
                    breeder_dispatch_result=breed_result,
                ),
                selected_proposal_id=selected,
                keep_source="simulation-human",
                keep_dispatch_result=keep_result,
            )
            try:
                attach_seed_material(pre_seed_session, seed_material=bad_material)
                raise AssertionError("executed material must not masquerade as admitted seed")
            except ValueError as exc:
                assert "INVALID_EXTERNAL_SEED_MATERIAL" in str(exc)
        finally:
            if old_home is None:
                os.environ.pop("GHOT_HOME", None)
            else:
                os.environ["GHOT_HOME"] = old_home
            if old_manifests is None:
                os.environ.pop("GHOT_ADAPTER_MANIFESTS", None)
            else:
                os.environ["GHOT_ADAPTER_MANIFESTS"] = old_manifests

    print(
        json.dumps(
            {
                "status": "ok",
                "specimen": "COMPOST-BREEDER-001",
                "laws": [
                    "ORCHESTRATION != SELECTION",
                    "PREVIEW != KEEP",
                    "PACKET != ADMISSION",
                    "EXTERNAL SEED != HISTORICAL PARENT",
                    "ANCESTRY != AUTHORITY",
                    "GENERATION2 WITNESS != PUBLICATION AUTHORITY",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
