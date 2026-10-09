#!/usr/bin/env python3
"""Prepare synthetic PostEmahh'n 003 setup from two PUBLIC phone keys.

The four unused route roles have LOCAL TEST-ONLY keys; that does not create
four independent human participants or real delivery authorization.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ghot"))
from relatte_identity import IdentityKey, jcs_bytes, normalize_public_jwk
from postal_corps import dispatch_gate_candidate, sha


def main():
    p=argparse.ArgumentParser(description="Prepare six PUBLIC role pins for a strictly simulated route")
    p.add_argument("--dispatch",type=Path,required=True,
                   help="native LemonPRESS un-postaged selected-only fixture")
    p.add_argument("--origin-public",type=Path,required=True)
    p.add_argument("--carrier-public",type=Path,required=True)
    p.add_argument("--unused-fixture-keys",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():
        raise ValueError("never overwrite prior route setup")
    dispatch=json.loads(a.dispatch.read_text(encoding="utf-8"))
    dispatch_gate_candidate(dispatch)
    origin=normalize_public_jwk(json.loads(a.origin_public.read_text(encoding="utf-8")))
    carrier1=normalize_public_jwk(json.loads(a.carrier_public.read_text(encoding="utf-8")))
    if origin==carrier1:
        raise ValueError("two independently held device public keys are required")
    a.unused_fixture_keys.mkdir(parents=True,exist_ok=True,mode=0o700)
    pins={"origin":origin,"carrier1":carrier1}
    for role in ("relay","carrier2","recipient","witness"):
        pins[role]=IdentityKey.load_or_create(
            a.unused_fixture_keys/(role+".pem")
        ).public_jwk()
    if len({jcs_bytes(p) for p in pins.values()})!=6:
        raise ValueError("role public keys must be distinct")
    prepared={
        "dispatch":dispatch,"role_pins":pins,
        "parcel_sha256":sha(b"POSTAL-CORPS-003:SYNTHETIC-NO-PHYSICAL-PARCEL"),
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(prepared,indent=2,sort_keys=True)+"\n")
    print("Prepared only PUBLIC phone keys and four synthetic dormant test-role pins.")
    print("DO NOT upload private keys or infer possession, delivery, Deeds or PENNY backing.")

if __name__=="__main__":main()
