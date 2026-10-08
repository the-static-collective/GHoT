#!/usr/bin/env python3
"""LISTENING-HEAP-001: real GHoT Rack execution over fake radio, with hostile gates."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from instrument_rack import build_instrument_rack
from listening_heap import (
    autodisco_prepare_request, demo_survey, explicit_listen, plan_attention,
    prepare_via_native_autodisco, validate_survey,
)
from listening_heap_mock_rx import run as fake_rx

TESTS = 0


def check(condition: bool, description: str) -> None:
    global TESTS
    assert condition, description
    TESTS += 1


def refused(fn, *args, **kwargs) -> None:
    global TESTS
    try:
        fn(*args, **kwargs)
    except (ValueError, RuntimeError):
        TESTS += 1
        return
    raise AssertionError("hostile case was accepted")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ghot-listening-heap-") as temp:
        root = Path(temp)
        manifest = root / "adapter-manifest.json"
        adapter = Path(__file__).with_name("listening_heap_mock_rx.py").resolve()
        capabilities = [
            {
                "capability": "radio.rx.simulated." + band,
                "protocol": "stdin-json/stdout-json-v0",
                "command": "python3",
                "args": [str(adapter)],
                "timeout_seconds": 5,
                "limits": {
                    "network": False,
                    "transmit": False,
                    "simulation_only": True,
                    "attention_cost": 2,
                },
            }
            for band in ("weather", "ism")
        ]
        manifest.write_text(json.dumps({
            "schema": "ghot.external-adapter-manifest/v0",
            "adapter_id": "simulated.radio.ears",
            "capabilities": capabilities,
        }), encoding="utf-8")
        previous = {key: os.environ.get(key) for key in ("GHOT_HOME", "GHOT_ADAPTER_MANIFESTS")}
        os.environ["GHOT_HOME"] = str(root / "home")
        os.environ["GHOT_ADAPTER_MANIFESTS"] = str(manifest)
        try:
            rack = build_instrument_rack()
            check(len(rack["cards"]) == 2, "two native Instrument Rack cards")
            survey = demo_survey()
            proposal = plan_attention(survey, rack)
            check(proposal["status"] == "PROPOSAL_ONLY", "planning effects nothing")
            check(proposal["selected"]["band"] == "ism", "attention selects higher forecast score")
            check(not (root / "home" / "instrument-rack").exists(), "planning does not dispatch")
            refused(plan_attention, survey, rack, budget=0)
            refused(validate_survey, {**survey, "source": "PHYSICAL_RF"})
            refused(validate_survey, {**survey, "windows": survey["windows"] + [survey["windows"][0]]})

            # An ordinary fixed-scan baseline chooses the first window. The
            # comparison labels are withheld from the planner and scored afterward.
            truth_fixture = {"weather": 0, "ism": 3}
            check(
                truth_fixture[proposal["selected"]["band"]] > truth_fixture[survey["windows"][0]["band"]],
                "predeclared toy attention utility exceeds fixed-scan baseline",
            )

            selection = {
                "kind": "operator-explicit-listen/v0",
                "approved": True,
                "proposal_id": proposal["proposal_id"],
                "card_id": proposal["selected"]["card_id"],
            }
            refused(explicit_listen, proposal, survey, rack,
                    selection={**selection, "approved": False}, dispatch_source="operator")
            refused(explicit_listen, proposal, survey, rack,
                    selection={**selection, "proposal_id": "other"}, dispatch_source="operator")
            refused(explicit_listen, proposal, survey, rack,
                    selection=selection, dispatch_source="")
            check(not (root / "home" / "instrument-rack").exists(), "refusals cause no dispatch")
            refused(explicit_listen, proposal, {**survey, "windows": list(reversed(survey["windows"]))},
                    rack, selection=selection, dispatch_source="operator")

            tampered = copy.deepcopy(rack)
            for card in tampered["cards"]:
                if card["card_id"] == selection["card_id"]:
                    card["limits"]["attention_cost"] = 1
            refused(explicit_listen, proposal, survey, tampered,
                    selection=selection, dispatch_source="operator")

            # Deliberate operator selection invokes the existing GHoT signed
            # Instrument Rack dispatch. Never call the fake receiver directly
            # to manufacture a GHoT crossing.
            observation = explicit_listen(proposal, survey, rack,
                                          selection=selection, dispatch_source="operator")
            check(observation["source"] == "SIMULATION", "no physical RF claim")
            check(observation["status"] == "SIMULATED_OBSERVATION_ONLY", "no real encounter claim")
            check(observation["band"] == "ism", "selected capability respected")
            check(len(observation["bins"]) == 8, "bounded bins carried")
            check(observation["crossing_id"] != "", "GHoT reLATTE-shaped signed dispatch occurred")
            check(observation["portable_packet_id"] != "", "GHoT packet survived")
            replay = explicit_listen(proposal, survey, rack,
                                     selection=selection, dispatch_source="operator")
            check(replay["observation_id"] == observation["observation_id"], "exact replay preserves identity")
            check(replay["dispatch_id"] == observation["dispatch_id"], "replay does not create new dispatch")

            # Mandatory native Autodisco artifact contract: SVG bytes and SHA.
            request = autodisco_prepare_request(observation)
            art = request["artifact"]
            check(request["schema"] == "autodisco.look-twice-prepare-request/v0",
                  "exact native prepare request schema")
            check(art["media_type"] == "image/svg+xml", "native LOOK-TWICE SVG requirement")
            check(hashlib.sha256(art["text"].encode()).hexdigest() == art["sha256"],
                  "Autodisco input is exact bytes")
            check("SIMULATED RF" in art["text"], "source is not presented as live reception")
            refused(autodisco_prepare_request, {**observation, "bins": [100] * 8})
            refused(autodisco_prepare_request, {**observation, "observation_id": "false"})

            # The donor refuses transmit, arbitrary input, mismatched band.
            refused(fake_rx, {"action": "transmit", "band": "ism"}, "radio.rx.simulated.ism")
            refused(fake_rx, {"action": "receive_simulation", "band": "weather"}, "radio.rx.simulated.ism")
            refused(fake_rx, {"action": "receive_simulation", "band": "ism", "tx": True},
                    "radio.rx.simulated.ism")

            # No Autodisco code or key is silently assumed. When its actual
            # script path is supplied, invoke native 'prepare', not an invented DJ.
            script = os.environ.get("AUTODISCO_LOOK_TWICE_SCRIPT")
            if script:
                pair = prepare_via_native_autodisco(request, script)
                check(len(pair["packets"]) == 2, "actual Autodisco makes two distinct packets")
                check(
                    pair["packets"][0]["packet_id"] != pair["packets"][1]["packet_id"],
                    "native first-listen contexts are independent",
                )
            print(json.dumps({
                "status": "PASS",
                "assertions": TESTS,
                "selected_band": observation["band"],
                "simulated_baseline_utility": truth_fixture["weather"],
                "simulated_selected_utility": truth_fixture[observation["band"]],
                "signed_ghot_crossing": observation["crossing_id"],
                "autodisco": "native-prepare-verified" if script else "exact-native-input-prepared-only",
                "live_rf": False,
                "ai_first_listens": False,
                "tx_enabled": False,
            }, indent=2))
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    main()
