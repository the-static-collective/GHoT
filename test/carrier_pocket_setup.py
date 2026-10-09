#!/usr/bin/env python3
"""Operator helper for a *fictional* carrier route with enrolled browser keys.

Never stores browser private keys or initiates real-world carriage.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ghot"))
from carrier_pocket import make_route_from_pins
from relatte_identity import IdentityKey


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="action",required=True)
    a=sub.add_parser("sign-route")
    a.add_argument("--dispatch",type=Path,required=True)
    a.add_argument("--public-roles",type=Path,required=True)
    a.add_argument("--origin-key",type=Path,required=True)
    a.add_argument("--parcel-sha256",required=True)
    a.add_argument("--out",type=Path,required=True)
    a=sub.add_parser("qr-png")
    a.add_argument("--challenge",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise ValueError("output already exists")
    if args.action=="sign-route":
        route=make_route_from_pins(
            json.loads(args.dispatch.read_text()),
            args.parcel_sha256,
            json.loads(args.public_roles.read_text()),
            IdentityKey(args.origin_key),
        )
        args.out.write_text(json.dumps(route,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("signed synthetic carrier route: "+str(args.out))
    else:
        try:
            import qrcode
            from qrcode.constants import ERROR_CORRECT_M
        except ImportError as e:
            raise RuntimeError("install optional 'qrcode[pil]' to render test QR") from e
        contents=json.loads(args.challenge.read_text())
        from carrier_pocket import MAX_QR_JSON
        from relatte_identity import jcs_bytes
        raw=jcs_bytes(contents)
        if len(raw)>MAX_QR_JSON:
            raise ValueError("QR payload exceeds size limit")
        q=qrcode.QRCode(error_correction=ERROR_CORRECT_M,box_size=6,border=4)
        q.add_data(raw.decode("utf-8"))
        q.make(fit=True)
        q.make_image(fill_color="black",back_color="white").save(args.out)
        print("QR image contains only signed synthetic handoff data: "+str(args.out))


if __name__=="__main__":
    main()
