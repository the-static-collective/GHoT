#!/usr/bin/env python3
"""Deterministic proof for INSTRUMENT-RACK-001."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from instrument_rack import (
    _digest,
    _packet_core,
    admit_seed_packet,
    build_instrument_rack,
    dispatch_instrument_card,
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ghot-instrument-rack-") as raw:
        root = Path(raw)
        home = root / "home"
        donor = root / "donor"
        donor.mkdir()
        counter = donor / "count.txt"
        adapter = donor / "adapter.py"
        manifest = donor / "adapter-manifest.json"

        adapter.write_text(
            "import hashlib,json,pathlib,sys\n"
            "root=pathlib.Path(__file__).resolve().parent\n"
            "counter=root/'count.txt'\n"
            "n=int(counter.read_text() or '0') if counter.exists() else 0\n"
            "counter.write_text(str(n+1))\n"
            "payload=json.load(sys.stdin)\n"
            "story='seed:'+json.dumps(payload,sort_keys=True,separators=(',',':'))+'\\n'\n"
            "story_sha=hashlib.sha256(story.encode()).hexdigest()\n"
            "receipt=json.dumps({'schema':'simulation.receipt/v0','story_sha256':story_sha},sort_keys=True,separators=(',',':'))+'\\n'\n"
            "receipt_sha=hashlib.sha256(receipt.encode()).hexdigest()\n"
            "print(json.dumps({'kind':'simulation.donor-result','status':'ok','artifact':{'story_text':story,'story_sha256':story_sha,'receipt_text':receipt,'receipt_sha256':receipt_sha}}))\n",
            encoding="utf-8",
        )
        manifest.write_text(json.dumps({
            "schema": "ghot.external-adapter-manifest/v0",
            "adapter_id": "simulation.seed-maker",
            "capabilities": [{
                "capability": "creative.simulation.seed",
                "protocol": "stdin-json/stdout-json-v0",
                "command": "python3",
                "args": ["adapter.py"],
                "timeout_seconds": 5,
                "limits": {
                    "network": False,
                    "arbitrary_shell": False,
                    "writes_only_requested_output_dir": False,
                },
            }],
        }), encoding="utf-8")

        old_home = os.environ.get("GHOT_HOME")
        old_manifests = os.environ.get("GHOT_ADAPTER_MANIFESTS")
        os.environ["GHOT_HOME"] = str(home)
        os.environ["GHOT_ADAPTER_MANIFESTS"] = str(manifest)
        try:
            rack = build_instrument_rack()
            assert rack["schema"] == "ghot.instrument-rack/v0"
            assert len(rack["cards"]) == 1
            card = rack["cards"][0]
            assert card["schema"] == "ghot.instrument-card/v0"
            assert card["status"] == "PROPOSAL_ONLY"
            assert card["semantic_effect"] == "none"
            assert card["capability"] == "creative.simulation.seed"
            assert counter.exists() is False

            stale = copy.deepcopy(card)
            stale["limits"]["network"] = True
            try:
                dispatch_instrument_card(
                    stale,
                    {"phrase": "house takes attendance"},
                    dispatch_source="simulation-human",
                )
                raise AssertionError("tampered card must refuse")
            except ValueError as exc:
                assert "STALE_OR_TAMPERED_INSTRUMENT_CARD" in str(exc)
            assert counter.exists() is False

            result = dispatch_instrument_card(
                card,
                {"phrase": "house takes attendance"},
                dispatch_source="simulation-human",
            )
            assert result["status"] == "EXECUTED"
            assert counter.read_text() == "1"
            packet = result["packet"]
            assert packet["schema"] == "ghot.portable-seed-packet/v0"
            assert packet["source_card_id"] == card["card_id"]
            assert packet["adapter_id"] == "simulation.seed-maker"
            assert packet["capability"] == "creative.simulation.seed"
            assert len(packet["artifacts"]) == 2
            assert {item["name"] for item in packet["artifacts"]} == {"story", "receipt"}
            for item in packet["artifacts"]:
                assert item["sha256"] == sha256_text(item["text"])

            replay = dispatch_instrument_card(
                card,
                {"phrase": "house takes attendance"},
                dispatch_source="simulation-human",
            )
            assert replay["packet"]["packet_id"] == packet["packet_id"]
            assert replay["dispatch_id"] == result["dispatch_id"]
            assert counter.read_text() == "1"

            tampered = copy.deepcopy(packet)
            tampered["artifacts"][0]["text"] += "tampered"
            try:
                admit_seed_packet(tampered, admission_source="simulation-human")
                raise AssertionError("tampered packet must refuse")
            except ValueError as exc:
                assert "INVALID_PORTABLE_SEED_PACKET" in str(exc)
            assert counter.read_text() == "1"

            relabeled = copy.deepcopy(packet)
            relabeled["capability"] = "creative.simulation.other"
            relabeled["packet_id"] = "portable-seed-v0:" + _digest(_packet_core(relabeled))
            try:
                admit_seed_packet(relabeled, admission_source="simulation-human")
                raise AssertionError("re-labeled packet must refuse signed-binding mismatch")
            except ValueError as exc:
                assert "INVALID_PORTABLE_SEED_PACKET" in str(exc)
            assert counter.read_text() == "1"

            material = admit_seed_packet(
                packet,
                admission_source="simulation-human",
            )
            assert material["schema"] == "ghot.seed-material/v0"
            assert material["status"] == "ADMITTED_NOT_EXECUTED"
            assert material["semantic_effect"] == "local-material-only"
            assert material["source_packet_id"] == packet["packet_id"]
            assert counter.read_text() == "1"

            replay_material = admit_seed_packet(
                packet,
                admission_source="simulation-human",
            )
            assert replay_material["material_id"] == material["material_id"]
            assert counter.read_text() == "1"
        finally:
            if old_home is None:
                os.environ.pop("GHOT_HOME", None)
            else:
                os.environ["GHOT_HOME"] = old_home
            if old_manifests is None:
                os.environ.pop("GHOT_ADAPTER_MANIFESTS", None)
            else:
                os.environ["GHOT_ADAPTER_MANIFESTS"] = old_manifests

    print(json.dumps({
        "status": "ok",
        "laws": [
            "RACK != EXECUTION",
            "CARD != ASSIGNMENT",
            "PACKET != ADMISSION",
            "ADMISSION != EXECUTION",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
