#!/usr/bin/env python3
"""RADIO-EAR-002: hostile integration using a FAKE rtl_sdr executable.

The fake binary never opens real radio hardware. Actual GHoT Instrument Rack
dispatch, signed receipts, portable packet replay and (optionally) native
Autodisco preparation are exercised without simulated evidence being treated
as actual on-air reception.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from instrument_rack import build_instrument_rack
from radio_ear import (
    CAPABILITY, REQUEST_SCHEMA, capture, energy_windows, validate_request, verify_capture,
)
from radio_ear_bridge import (
    execute_selected_capture, make_proposal, native_autodisco_request, prepare_autodisco,
    _hash as hash_summary,
)

COUNT = 0


def yes(value: bool, meaning: str) -> None:
    global COUNT
    assert value, meaning
    COUNT += 1


def no(fn, *args, **kwargs) -> None:
    global COUNT
    try:
        fn(*args, **kwargs)
    except (ValueError, RuntimeError, FileNotFoundError):
        COUNT += 1
        return
    raise AssertionError("hostile case accepted")


def fake_rtl(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys\n"
        "argv=sys.argv[1:]\n"
        "if len(argv)!=9 or argv[0]!='-d' or argv[2]!='-f' or "
        "argv[4]!='-s' or argv[6]!='-n' or argv[8]!='-': sys.exit(9)\n"
        "count=int(argv[7]);mode=os.environ.get('RADIO_FAKE_MODE','ok')\n"
        "if mode=='fail':sys.exit(7)\n"
        "if mode=='truncate':count=count-2\n"
        "if mode=='extra':count=count+2\n"
        "output=bytes((128+(j%3), 128-(j%4)) for j in range(0)) if False else "
        "bytes(x for i in range(count) for x in (128+i%3,128-i%4))\n"
        "sys.stdout.buffer.write(output)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def main() -> None:
    request = {
        "schema": REQUEST_SCHEMA,
        "action": "capture_rx_iq",
        "device_index": 0,
        "frequency_hz": 162_550_000,
        "sample_rate_hz": 1_024_000,
        "complex_samples": 4096,
        "rx_scope": "public-or-otherwise-authorized",
    }
    root = Path(__file__).resolve().parent.parent
    native_manifest = root / "integrations" / "radio-ear-002" / "adapter-manifest.json"
    with tempfile.TemporaryDirectory(prefix="radio-ear-hostile-") as raw:
        home = Path(raw)
        driver = home / "rtl_sdr_fake"
        fake_rtl(driver)
        names = ("GHOT_HOME", "GHOT_ADAPTER_MANIFESTS", "GHOT_RTLSDR_BIN", "RADIO_FAKE_MODE")
        previous = {key: os.environ.get(key) for key in names}
        os.environ["GHOT_HOME"] = str(home / "ghot-home")
        os.environ["GHOT_ADAPTER_MANIFESTS"] = str(native_manifest)
        os.environ["GHOT_RTLSDR_BIN"] = str(driver)
        os.environ.pop("RADIO_FAKE_MODE", None)
        try:
            yes(validate_request(request) == request, "valid bounded RX parameters")
            no(validate_request, {**request, "action": "transmit"})
            no(validate_request, {**request, "tx": True})
            no(validate_request, {**request, "rx_scope": "all-signals"})
            no(validate_request, {**request, "frequency_hz": True})
            no(validate_request, {**request, "frequency_hz": 2_000_000_000})
            no(validate_request, {**request, "complex_samples": 4097})
            no(validate_request, {**request, "complex_samples": 262144})
            no(validate_request, {**request, "device_index": -1})
            no(validate_request, {**request, "sample_rate_hz": 0})

            rack = build_instrument_rack()
            yes(len(rack["cards"]) == 1 and rack["cards"][0]["capability"] == CAPABILITY,
                "native GHoT card present")
            proposal = make_proposal(rack, request)
            yes(proposal["status"] == "PROPOSAL_ONLY" and proposal["transmission"] == "FORBIDDEN",
                "proposal has no RF effect")
            yes(not (home / "ghot-home" / "instrument-rack").exists(),
                "making a proposal invokes no driver")
            selection = {
                "kind": "operator-explicit-radio-rx/v0",
                "approved": True,
                "proposal_id": proposal["proposal_id"],
                "card_id": proposal["card_id"],
            }
            no(execute_selected_capture, proposal, request, rack, selection={
                **selection, "approved": False,
            }, dispatch_source="operator")
            no(execute_selected_capture, proposal, request, rack, selection={
                **selection, "card_id": "different",
            }, dispatch_source="operator")
            no(execute_selected_capture, proposal, request, rack, selection=selection,
               dispatch_source="")
            no(execute_selected_capture, proposal, {**request, "frequency_hz": 162_400_000},
               rack, selection=selection, dispatch_source="operator")
            tampered_rack = copy.deepcopy(rack)
            tampered_rack["cards"][0]["limits"]["transmit"] = True
            no(execute_selected_capture, proposal, request, tampered_rack,
               selection=selection, dispatch_source="operator")
            yes(not (home / "ghot-home" / "instrument-rack").exists(),
                "all selection refusals precede execution")

            # Isolated fake backend tests before the signed GHoT execution path.
            os.environ["RADIO_FAKE_MODE"] = "fail"
            no(capture, request)
            os.environ["RADIO_FAKE_MODE"] = "truncate"
            no(capture, request)
            os.environ["RADIO_FAKE_MODE"] = "extra"
            no(capture, request)
            os.environ.pop("RADIO_FAKE_MODE")
            direct = capture(request)
            yes(direct["status"] == "HOST_REPORTED_RX_CAPTURE", "backend result explicitly unverified")
            yes(direct["hardware_identity_verified"] is False, "no hardware identity proof")
            yes(direct["tx_enabled"] is False, "no transmitter")
            yes(verify_capture(direct)["iq_sha256"] == direct["iq_sha256"], "raw IQ replay verified")
            yes(energy_windows(bytes([128, 128] * 4096)) == [0] * 8,
                "DC-centered zero amplitude remains zero")
            bad = copy.deepcopy(direct)
            bad["iq_sha256"] = "0" * 64
            no(verify_capture, bad)
            bad = copy.deepcopy(direct)
            bad["amplitude_windows"][0] += 1
            no(verify_capture, bad)
            bad = copy.deepcopy(direct)
            bad["origin_assurance"] = "verified-hardware"
            no(verify_capture, bad)
            bad = copy.deepcopy(direct)
            bad["hardware_identity_verified"] = True
            no(verify_capture, bad)

            # Native signed reLATTE-shaped dispatch happens only here.
            result = execute_selected_capture(
                proposal, request, rack, selection=selection, dispatch_source="operator"
            )
            summary, packet = result["summary"], result["portable_packet"]
            yes(summary["mode"] == "RECEIVE_ONLY" and summary["transmission"] == "FORBIDDEN",
                "no TX grant via signed crossing")
            yes(summary["physical_signal_verified"] is False,
                "driver output not promoted to RF truth")
            yes(packet["schema"] == "ghot.portable-seed-packet/v0", "portable GHoT packet")
            yes(packet["dispatch_crossing_id"] == summary["crossing_id"],
                "native signed GHoT crossing retained")
            yes(packet["status"] == "PORTABLE_NOT_ADMITTED",
                "no receiver semantic admission")
            yes(packet["donor_result"]["result"]["iq_sha256"] == summary["iq_sha256"],
                "exact samples travel in GHoT packet")
            replay = execute_selected_capture(
                proposal, request, rack, selection=selection, dispatch_source="operator"
            )
            yes(replay["summary"]["summary_id"] == summary["summary_id"],
                "exact replay does not create another observation")
            yes(replay["summary"]["dispatch_id"] == summary["dispatch_id"],
                "exact replay reuses native dispatch identity")

            prepare = native_autodisco_request(result)
            yes(prepare["schema"] == "autodisco.look-twice-prepare-request/v0",
                "native LOOK-TWICE request")
            yes(hashlib.sha256(prepare["artifact"]["text"].encode()).hexdigest() ==
                prepare["artifact"]["sha256"], "exact SVG input bytes")
            yes("NOT RF ORIGIN PROOF" in prepare["artifact"]["text"],
                "uncertain physical origin explicitly labeled")
            modified = copy.deepcopy(result)
            modified["summary"]["amplitude_windows"][0] += 1
            no(native_autodisco_request, modified)
            modified = copy.deepcopy(result)
            modified["portable_packet"]["donor_result"]["result"]["iq_sha256"] = "0" * 64
            no(native_autodisco_request, modified)

            # Signed dispatch metadata cannot be replaced while pretending the
            # displayed SVG came from the same execution.
            modified = copy.deepcopy(result)
            modified["summary"]["crossing_id"] = "forged-crossing"
            modified["summary"]["summary_id"] = (
                "radio-ear-summary-v0:" + hash_summary({
                    k: v for k, v in modified["summary"].items() if k != "summary_id"
                })
            )
            no(native_autodisco_request, modified)

            # Operator CLI is an actual two-action process boundary. Planning
            # never captures; a saved exact plan and explicit confirmation are
            # necessary for the second invocation.
            request_file = home / "operator-request.json"
            saved_plan = home / "saved-plan.json"
            request_file.write_text(json.dumps(request), encoding="utf-8")
            operator_cli = Path(__file__).with_name("radio_ear_operator.py")
            base_cmd = [
                sys.executable, str(operator_cli),
                "plan", "--request-file", str(request_file),
            ]
            planned = subprocess.run(base_cmd, text=True, capture_output=True)
            yes(planned.returncode == 0, "operator planning subprocess works")
            saved_plan.write_text(planned.stdout, encoding="utf-8")
            confirmed_cmd = [
                sys.executable, str(operator_cli), "capture",
                "--request-file", str(request_file),
                "--plan-file", str(saved_plan),
                "--operator-label", "human-operator-test",
            ]
            denied = subprocess.run(confirmed_cmd, text=True, capture_output=True)
            yes(denied.returncode != 0, "missing explicit operator confirmation blocks hardware")
            approved = subprocess.run(
                confirmed_cmd + ["--confirm-rx-only"], text=True, capture_output=True
            )
            yes(approved.returncode == 0, "independent CLI capture crosses native GHoT")
            cli_result = json.loads(approved.stdout) if approved.returncode == 0 else {}
            yes(cli_result.get("schema") == "ghot.radio-ear-capture-output/v0",
                "operator receives bound observation summary")
            yes(cli_result.get("summary", {}).get("physical_signal_verified") is False,
                "CLI preserves unverified physical-origin claim")

            autodisco = "exact-native-input-prepared-only"
            script = os.environ.get("AUTODISCO_LOOK_TWICE_SCRIPT")
            if script:
                pair = prepare_autodisco(result, script)
                yes(pair["schema"] == "autodisco.look-twice-pair/v0",
                    "real Autodisco LOOK-TWICE prepared pair")
                yes(len(pair["packets"]) == 2 and
                    pair["packets"][0]["packet_id"] != pair["packets"][1]["packet_id"],
                    "two independent packet identities")
                autodisco = "native-prepare-verified"
            print(json.dumps({
                "status": "PASS",
                "assertions": COUNT,
                "transport": "GHoT signed reLATTE-shaped local dispatch",
                "source": "FAKE-RTLSDR-EXECUTABLE / NO PHYSICAL RF",
                "iq_byte_count": 2 * request["complex_samples"],
                "portable_packet_digest_present": bool(packet["packet_id"]),
                "autodisco": autodisco,
                "actual_rf_confirmed": False,
                "ai_first_listen_responses": False,
                "transmitter_present": False,
            }, indent=2))
        finally:
            for name, old in previous.items():
                if old is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old


if __name__ == "__main__":
    main()
