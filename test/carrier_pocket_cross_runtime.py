#!/usr/bin/env python3
"""Cross-runtime POSTAL-CORPS-002:
WebCrypto-generated relay key signs a real offline QR; GHoT P-256 verifies it.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ghot"))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from carrier_pocket import PocketJournal, make_route_from_pins
from postal_corps import ROLES, RULES, act, sha
from relatte_identity import IdentityKey
from test_postal_corps import fixture_dispatch


def call(*args: str):
    subprocess.run(list(args),check=True)

with tempfile.TemporaryDirectory() as folder:
    d=Path(folder)
    web=Path(__file__).with_name("carrier_pocket_webcrypto.mjs")
    identity=d/"webcrypto-test-only.json"
    call("node",str(web),"generate",str(identity))
    pub=json.loads(identity.read_text())["public"]
    signers={role:IdentityKey.load_or_create(d/"keys"/(role+".pem"))
             for role in ROLES if role!="relay"}
    pins={role:(pub if role=="relay" else signers[role].public_jwk())
          for role in ROLES}
    dispatch=fixture_dispatch()
    route=make_route_from_pins(dispatch,sha(b"fictional-object"),pins,signers["origin"])
    routefile=d/"route.json"
    routefile.write_text(json.dumps(route))
    a=PocketJournal(d/"station.sqlite3",route,dispatch)
    remote=PocketJournal(d/"phone.sqlite3",route,dispatch)
    try:
        initial=[]
        for action in ["ACCEPT_LEG1","PICKUP_LEG1"]:
            roles=RULES[action][2]
            initial=act(route,dispatch,initial,action,
                        {r:signers[r] for r in roles},
                        sha(("synthetic-"+action).encode()))
        packet=a.export_history();packet["events"]=initial
        assert a.sync_history(packet)==2
        assert remote.sync_history(a.export_history())==2
        qr=a.issue("HANDOFF_RELAY",signers["carrier1"],sha(b"synthetic-seal-check"))
        qrfile=d/"qr.json";qrfile.write_text(json.dumps(qr))
        responsefile=d/"browser-response.json"
        call("node",str(web),"respond",str(identity),str(routefile),str(qrfile),str(responsefile))
        # The real GHoT Python verifier accepts signatures produced by
        # browser-style WebCrypto rather than OpenSSL keys.
        response=json.loads(responsefile.read_text())
        native_packet=a.commit(response)
        assert native_packet["body"]["action"]=="HANDOFF_RELAY"
        assert a.state()["state"]=="RELAY_HELD_CLAIM"
        assert a.state()["physical_parcel_observed"] is False
        assert remote.sync_history(a.export_history())==1
        assert remote.state()["state"]=="RELAY_HELD_CLAIM"
        print("PASS: WebCrypto-generated browser key -> QR signMessage -> native P-256 verification -> durable HELD simulated relay claim")
    finally:
        a.close();remote.close()
