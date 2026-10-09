#!/usr/bin/env python3
"""Native LemonPRESS dispatch -> GHoT postal route -> proposal JSON.

Requires path to an independently checked-out LemonPRESS Dispatch Gate.
Uses synthetic fields only; does not buy postage or tender any parcel.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ghot"))
from postal_corps import ROLES, specimen
from relatte_identity import IdentityKey


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--lemon",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    module_path=a.lemon/"tools"/"dispatch_gate.py"
    if not module_path.is_file():
        raise ValueError("native LemonPRESS dispatch module absent")
    spec=importlib.util.spec_from_file_location("native_lemon_dispatch",module_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as folder:
        base=Path(folder)
        packet=base/"parcel-specimen"
        packet.mkdir()
        manifest={
            "packet_version":"recipient-mailer-001",
            "packet_id":"parcel-specimen-001",
            "state":"printed",
            "work_id":"synthetic-work",
            "edition_id":"synthetic-edition",
            "recipient_id":"specimen:fictional-recipient",
        }
        (packet/"manifest.json").write_text(json.dumps(manifest))
        # Invokes the real source's cmd_init; no postage/tender operations.
        cmd=argparse.Namespace(
            packet_dir=str(packet),
            carrier="POSTAL-CORPS-SIMULATION",
            service="offline-specimen",
            note="synthetic verification only",
            allow_unprinted=False
        )
        assert module.cmd_init(cmd)==0
        dispatch=json.loads((packet/"dispatch.json").read_text())
        assert dispatch["state"]=="service_selected"
        assert dispatch["postage"] is None
        signers={role:IdentityKey.load_or_create(base/"keys"/(role+".pem"))
                 for role in ROLES}
        route,events,result=specimen(signers,dispatch,b"%PDF-1.4\nsynthetic\n%%EOF")
        assert result["carrier"]["state"]=="WORK_REVIEW_READY"
        assert result["penny"]["book_coins"]==0
        assert result["penny"]["active_units"]==0
        assert len(result["penny"]["candidate_work_payloads"])==2
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps({
            "source":"LEMONPRESS_NATIVE_DISPATCH_001",
            "source_dispatch_state":dispatch["state"],
            "route_state":result["carrier"]["state"],
            "full_measure":result["full_measure"],
            "penny":result["penny"],
            "private_addresses_in_output":False,
            "real_postage_acquired":False,
            "physical_delivery_claimed":False,
        },indent=2)+"\n",encoding="utf-8")
        print("REAL SOURCE CONTRACT PASS: LemonPRESS Dispatch init -> 10 signed GHoT events -> Full Measure and PENNY HOLD proposals")


if __name__=="__main__":
    main()
