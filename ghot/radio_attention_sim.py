#!/usr/bin/env python3
"""RADIO-ATTENTION-003: fake driver, REAL GHoT signed dispatch and native v20 prep.

No actual radio receiver / emission / waveform is tested.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from instrument_rack import build_instrument_rack
from radio_attention import (
    SPEC, APPROVAL, autodisco_comparison_request, compare_and_propose, next_attention,
    plan_focus, plan_survey, rank_survey, run_focus, run_survey, validate_spec,
    verify_focus, verify_survey, native_autodisco_comparison, _hash, _seal,
)
from radio_ear import verify_capture
from radio_ear_sim import fake_rtl

PASS = 0


def ok(value: bool, label: str) -> None:
    global PASS
    assert value, label
    PASS += 1


def refuse(fn, *args, **kwargs) -> None:
    global PASS
    try:
        fn(*args, **kwargs)
    except (ValueError, RuntimeError):
        PASS += 1
        return
    raise AssertionError("accepted forbidden case")


def write_fake(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys\n"
        "v=sys.argv[1:]\n"
        "if len(v)!=9 or v[0]!='-d' or v[2]!='-f' or v[4]!='-s' or v[6]!='-n' or v[8]!='-': sys.exit(9)\n"
        "device=int(v[1]);freq=int(v[3]);count=int(v[7])\n"
        "if device not in (0,1): sys.exit(10)\n"
        "if freq not in (162400000,162475000,162550000): sys.exit(11)\n"
        "if os.getenv('RADIO_FAKE_LOG'):\n"
        " with open(os.environ['RADIO_FAKE_LOG'],'a') as f: f.write(f'{device}:{freq}:{count}\\n')\n"
        "amplitude={162400000:8,162475000:24,162550000:48}[freq]\n"
        "if device==1 and not os.environ.get('RADIO_FAKE_AGREE'): amplitude=16\n"
        "sys.stdout.buffer.write(bytes([128+amplitude,128+amplitude])*count)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def count_calls(log: Path) -> int:
    return len(log.read_text().splitlines()) if log.exists() else 0


def approval(plan: dict, purpose: str, *, approved: bool = True) -> dict:
    return {
        "schema": APPROVAL, "approved": approved,
        "plan_id": plan["plan_id"], "purpose": purpose,
    }


def run() -> None:
    spec = {
        "schema": SPEC,
        "surveyor_index": 0,
        "listener_index": 1,
        "frequencies_hz": [162400000, 162475000, 162550000],
        "sample_rate_hz": 1_024_000,
        "survey_complex_samples": 4096,
        "focus_complex_samples": 8192,
        "rx_scope": "public-or-otherwise-authorized",
    }
    with tempfile.TemporaryDirectory(prefix="ghot-radio-attention-") as raw:
        root = Path(raw)
        driver = root / "rtl_sdr_fake"
        log = root / "driver-invocations.txt"
        write_fake(driver)
        repo = Path(__file__).resolve().parent.parent
        names = ["GHOT_HOME", "GHOT_ADAPTER_MANIFESTS", "GHOT_RTLSDR_BIN",
                 "RADIO_FAKE_LOG", "RADIO_FAKE_AGREE"]
        saved = {name: os.environ.get(name) for name in names}
        os.environ["GHOT_HOME"] = str(root / "state")
        os.environ["GHOT_ADAPTER_MANIFESTS"] = str(
            repo / "integrations" / "radio-ear-002" / "adapter-manifest.json"
        )
        os.environ["GHOT_RTLSDR_BIN"] = str(driver)
        os.environ["RADIO_FAKE_LOG"] = str(log)
        os.environ.pop("RADIO_FAKE_AGREE", None)
        try:
            rack = build_instrument_rack()
            ok(validate_spec(spec) == spec, "typed bounded radio field")
            refuse(validate_spec, {**spec, "listener_index": 0})
            refuse(validate_spec, {**spec, "surveyor_index": True})
            refuse(validate_spec, {**spec, "frequencies_hz": [162400000, 162400000]})
            refuse(validate_spec, {**spec, "frequencies_hz": [162400000]})
            refuse(validate_spec, {**spec, "frequencies_hz": [162400000] * 4})
            refuse(validate_spec, {**spec, "frequencies_hz": [162400000, 162475000, 0]})
            refuse(validate_spec, {**spec, "focus_complex_samples": 65_544})
            refuse(validate_spec, {**spec, "rx_scope": "anything"})
            refuse(validate_spec, {**spec, "transmit": True})

            p = plan_survey(spec, rack)
            ok(p["status"] == "PROPOSAL_ONLY", "survey merely proposes")
            ok(count_calls(log) == 0, "planning does no hardware work")
            refuse(run_survey, spec, rack, p, approval=approval(p,"survey",approved=False),
                   operator="observer")
            refuse(run_survey, spec, rack, p, approval=approval(p,"focus"), operator="observer")
            refuse(run_survey, spec, rack, p, approval=approval(p,"survey"), operator="")
            refuse(run_survey, spec, rack, p,
                   approval={**approval(p,"survey"),"plan_id":"forged"}, operator="observer")
            refuse(run_survey, {**spec,"sample_rate_hz":250_000}, rack, p,
                   approval=approval(p,"survey"),operator="observer")
            tampered_rack = copy.deepcopy(rack)
            tampered_rack["cards"][0]["limits"]["transmit"] = True
            refuse(run_survey, spec, tampered_rack, p, approval=approval(p,"survey"),
                   operator="observer")
            ok(count_calls(log)==0, "all hostile survey plans refused before physical work")

            sweep = run_survey(spec, rack, p, approval=approval(p, "survey"), operator="observer")
            ok(len(sweep["observations"]) == 3, "bounded three-frequency sweep")
            ok(count_calls(log) == 3, "three exact native GHoT dispatches")
            ok(sweep["capture_gap_between_frequencies"]=="UNOBSERVED", "gaps preserved")
            ok(sweep["hardware_identity_verified"] is False, "no hardware-ID inflation")
            observed = log.read_text().splitlines()
            ok(all(line.startswith("0:") for line in observed), "survey index zero")
            ok([int(x.split(":")[1]) for x in observed] == spec["frequencies_hz"],
               "all operator-named survey centers captured in order")
            for observation in sweep["observations"]:
                packet = observation["capture"]["portable_packet"]
                ok(packet["schema"]=="ghot.portable-seed-packet/v0", "native signed portable packet")
                ok(packet["status"]=="PORTABLE_NOT_ADMITTED", "no semantic source admission")
                verify_capture(packet["donor_result"]["result"])
                ok(packet["dispatch_crossing_id"]==observation["capture"]["summary"]["crossing_id"],
                   "signed crossing retained")

            ok(rank_survey(sweep)[0]["frequency_hz"]==162550000,
               "uncalibrated amplitude target wins")
            ok(rank_survey(sweep)[1]["frequency_hz"]==162475000,
               "runner-up available for next attention")
            survey_replay=run_survey(spec,rack,p,approval=approval(p,"survey"),operator="observer")
            ok(survey_replay["survey_id"]==sweep["survey_id"],"cold survey replay same identity")
            ok(count_calls(log)==3, "replayed sweep produces no new physical actions")

            fp=plan_focus(sweep,rack)
            ok(fp["frequency_hz"]==162550000,"target proposed from measured evidence")
            ok(fp["status"]=="PROPOSAL_ONLY","focus plan does not listen")
            ok(count_calls(log)==3,"focus proposal invokes no device")
            refuse(run_focus,sweep,rack,fp,approval=approval(fp,"focus",approved=False),
                   operator="observer")
            refuse(run_focus,sweep,rack,fp,approval=approval(fp,"survey"),operator="observer")
            refuse(run_focus,sweep,rack,{**fp,"frequency_hz":162400000},
                   approval=approval(fp,"focus"),operator="observer")
            ok(count_calls(log)==3,"refused focus cannot activate receiver")
            focus=run_focus(sweep,rack,fp,approval=approval(fp,"focus"),operator="observer")
            ok(count_calls(log)==4,"focus invokes exactly once")
            ok(log.read_text().splitlines()[-1]=="1:162550000:8192",
               "independent device index gets longer focused sample")
            ok(focus["physical_independence_verified"] is False,
               "different index is not physical independence proof")
            focus_replay=run_focus(sweep,rack,fp,approval=approval(fp,"focus"),operator="observer")
            ok(focus_replay["focus_id"]==focus["focus_id"],"focus cold replay exact")
            ok(count_calls(log)==4,"focus replay no extra driver run")

            comparison=compare_and_propose(sweep,focus)
            ok(comparison["delta"]>=16 and comparison["disagreement_flag"] is True,
               "disagreement flagged by predeclared threshold")
            ok(comparison["status"]=="DETERMINISTIC_HEURISTIC_NOT_AUTODISCO_MODEL_OUTPUT",
               "do not impersonate Autodisco model")
            next_plan=next_attention(sweep,focus)
            ok(next_plan["proposed_frequency_hz"]==162550000,
               "disagreement proposes re-observation")
            ok(next_plan["status"]=="PROPOSAL_ONLY", "next frequency not authorized")
            ok(count_calls(log)==4,"next plan does not dispatch")

            v=autodisco_comparison_request(sweep,focus)
            ok(v["schema"]=="autodisco.look-twice-prepare-request/v0",
               "native Autodisco exact request")
            ok(hashlib.sha256(v["artifact"]["text"].encode()).hexdigest()==v["artifact"]["sha256"],
               "artifact hash binds exact visual bytes")
            ok("NOT RF ORIGIN PROOF" in v["artifact"]["text"],
               "visual representation does not assert physical origin")

            tampered_sweep=copy.deepcopy(sweep)
            tampered_sweep["observations"][0]["capture"]["summary"]["amplitude_windows"][0] += 1
            refuse(verify_survey,tampered_sweep)
            tampered_focus=copy.deepcopy(focus)
            tampered_focus["capture"]["summary"]["iq_sha256"]="0"*64
            refuse(verify_focus,sweep,tampered_focus)
            tampered_sweep=copy.deepcopy(sweep)
            tampered_sweep["observations"][2]["capture"]["portable_packet"]["donor_result"]["result"]["iq_sha256"]="1"*64
            tampered_sweep=_seal({k:v for k,v in tampered_sweep.items() if k!="survey_id"},
                                 "survey_id","radio-attention-survey-v0:")
            refuse(rank_survey,tampered_sweep)
            tampered_focus=copy.deepcopy(focus)
            tampered_focus["frequency_hz"]=162475000
            tampered_focus=_seal({k:v for k,v in tampered_focus.items() if k!="focus_id"},
                                 "focus_id","radio-attention-focus-v0:")
            refuse(compare_and_propose,sweep,tampered_focus)

            # Alternate physical outcome under the SAME survey evidence, using
            # another explicit owner action. This keeps the decision adaptive
            # without pretending a learning model was called.
            os.environ["RADIO_FAKE_AGREE"]="1"
            agree_focus=run_focus(sweep,rack,fp,approval=approval(fp,"focus"),
                                  operator="observer-agree")
            ok(compare_and_propose(sweep,agree_focus)["disagreement_flag"] is False,
               "no discrepancy in alternate source outcome")
            ok(next_attention(sweep,agree_focus)["proposed_frequency_hz"]==162475000,
               "agreement proposes ranked alternative, not a repeat")
            ok(count_calls(log)==5,"different operator action gets distinct dispatch")

            status="exact-native-input-only"
            script=os.environ.get("AUTODISCO_LOOK_TWICE_SCRIPT")
            if script:
                pair=native_autodisco_comparison(sweep,focus,script)
                ok(pair["schema"]=="autodisco.look-twice-pair/v0",
                   "native Autodisco v20 accepts comparative artifact")
                ok(len(pair["packets"])==2 and pair["packets"][0]["packet_id"] !=
                   pair["packets"][1]["packet_id"],"two first-encounter packets")
                status="native-look-twice-packets-verified"

            print(json.dumps({
                "status":"PASS",
                "assertions":PASS,
                "observations":3,
                "focused_capture":1,
                "source":"FAKE_RTLSDR_ONLY",
                "survey_receiver_index":0,
                "focus_receiver_index":1,
                "chosen_frequency_hz":fp["frequency_hz"],
                "comparison_disagreed":comparison["disagreement_flag"],
                "next_frequency_hz":next_plan["proposed_frequency_hz"],
                "autodisco":status,
                "real_rf_verified":False,
                "ai_responses_present":False,
                "automatic_capture":False,
                "transmitter_present":False,
            },indent=2))
        finally:
            for name, original in saved.items():
                if original is None:
                    os.environ.pop(name,None)
                else:
                    os.environ[name]=original


if __name__=="__main__":
    run()
