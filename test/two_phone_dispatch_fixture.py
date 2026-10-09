#!/usr/bin/env python3
"""Generate an actual native LemonPRESS *fictional* dispatch for 2-phone CI.

Never runs label purchase, carrier tender or physical mailing.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import tempfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--lemon",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    path=args.lemon/"tools"/"dispatch_gate.py"
    if not path.is_file():raise ValueError("native LemonPRESS tool missing")
    spec=importlib.util.spec_from_file_location("native_lemon_dispatch",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as tmp:
        packet=Path(tmp)/"parcel-specimen";packet.mkdir()
        (packet/"manifest.json").write_text(json.dumps({
            "packet_version":"recipient-mailer-001",
            "packet_id":"parcel-specimen-001",
            "state":"printed","work_id":"synthetic-work",
            "edition_id":"synthetic-edition",
            "recipient_id":"specimen:fictional-recipient",
        }))
        cmd=argparse.Namespace(
            packet_dir=str(packet),carrier="POSTAL-CORPS-SIMULATION",
            service="offline-specimen",
            note="Two phones synthetic offline QR only",
            allow_unprinted=False,
        )
        if mod.cmd_init(cmd)!=0:raise ValueError("native LemonPRESS refused synthetic dispatch")
        record=json.loads((packet/"dispatch.json").read_text())
        assert record["state"]=="service_selected" and record["postage"] is None
        args.out.write_text(json.dumps(record,sort_keys=True,indent=2)+"\n")
        print("native LemonPRESS source generated selected-only fictional dispatch")

if __name__=="__main__":main()
