#!/usr/bin/env python3
"""POSTAL-CORPS-003 trusted *synthetic* station reconciliation.

Input may arrive after two phones were air-gapped. The operator must provide
independently enrolled public-key pins: never blindly trust those in the
portable bundle. Late QR proofs are held without inventing trusted signing
times. No physical custody, money, PENNY or Full Measure effect.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from carrier_pocket import PocketJournal, verify_response
from postal_corps import replay, require, sha, verify_route
from relatte_identity import jcs_bytes, normalize_public_jwk


def reconcile(
    bundle: dict[str, Any], station_db: Path,
    trusted_origin: dict[str, Any],
    trusted_carrier1: dict[str, Any],
    at: int | None = None,
) -> dict[str, Any]:
    require(isinstance(bundle, dict) and set(bundle) == {
        "schema", "classification", "dispatch", "route", "events",
        "challenge", "response", "claimed_head", "physical_parcel_observed",
        "penny_units_released", "full_measure_deeds",
    }, "fieldkit structure rejected")
    require(bundle["schema"] == "postemahhn.two-phones-fieldkit/v0"
            and bundle["classification"] == "synthetic_no_real_carriage"
            and bundle["physical_parcel_observed"] is False
            and bundle["penny_units_released"] == 0
            and bundle["full_measure_deeds"] == 0,
            "fieldkit cannot authorize physical or economic effects")
    route, dispatch = bundle["route"], bundle["dispatch"]
    verify_route(route, dispatch)
    pins = route["role_pins"]
    require(normalize_public_jwk(pins["origin"]) == normalize_public_jwk(trusted_origin),
            "operator-enrolled origin key differs")
    require(normalize_public_jwk(pins["carrier1"]) == normalize_public_jwk(trusted_carrier1),
            "operator-enrolled first carrier key differs")
    events = bundle["events"]
    require(isinstance(events, list) and len(events) == 2
            and events[0]["body"]["action"] == "ACCEPT_LEG1"
            and events[1]["body"]["action"] == "PICKUP_LEG1",
            "unexpected two-phone event sequence")
    state = replay(route, dispatch, events)
    require(state["state"] == "LEG1_MOVING_CLAIM", "incomplete simulated route")
    require(state["history_head"] == bundle["claimed_head"], "two-phone head mismatch")
    challenge, response = bundle["challenge"], bundle["response"]
    exp = challenge["body"]["expires_at"]
    stamp = int(time.time()) if at is None else at
    require(type(exp) is int and type(stamp) is int, "bad reconciliation clock")
    # Even for a late artifact, inspect cryptographic facts at the QR expiry
    # boundary; do NOT admit a late signed claim based on untrusted phone time.
    audit_time = min(stamp, exp)
    _, packet = verify_response(route, dispatch, response, events[:1], now=audit_time)
    require(packet == events[1], "phone native event differs from returned response")
    if stamp > exp:
        return {
            "schema": "postemahhn.two-phones-station-review/v0",
            "state": "HOLD_EXPIRED",
            "reason": "no independent trusted time of offline co-signing",
            "route_id": route["route_id"],
            "history_head": state["history_head"],
            "station_accepted": False,
            "physical_delivery_observed": False,
            "penny_units": 0, "full_measure_deeds": 0,
        }
    journal = PocketJournal(station_db, route, dispatch)
    try:
        present = journal.events()
        require(events[:len(present)] == present
                or (len(present) == 2 and present == events),
                "HOLD_FORK: station history does not match phones")
        if len(present) == 0:
            journal.sync_history({
                "schema": "postemahhn.carrier-pocket-history/v0",
                "route_hash": sha(jcs_bytes(route)),
                "events": events[:1],
                "effect": "SYNTHETIC_CUSTODY_CLAIM_ONLY",
            })
        if len(present) <= 1:
            journal.register_browser_issued(challenge, now=stamp)
            journal.commit(response, now=stamp)
        actual = journal.events()
        require(actual == events, "HOLD_FORK: final station history differs")
        observed = journal.state()
        return {
            "schema": "postemahhn.two-phones-station-review/v0",
            "state": "SYNTHETIC_HANDOFF_ADMITTED",
            "route_id": route["route_id"],
            "history_head": observed["history_head"],
            "station_accepted": True,
            "event_count": observed["event_count"],
            "physical_delivery_observed": False,
            "penny_units": 0, "full_measure_deeds": 0,
        }
    finally:
        journal.close()


def main() -> None:
    p=argparse.ArgumentParser(description="Reconcile air-gapped phones to synthetic GHoT receipt journal")
    p.add_argument("--fieldkit", required=True, type=Path)
    p.add_argument("--origin-pin", required=True, type=Path,
                   help="independently enrolled origin PUBLIC P-256 JWK")
    p.add_argument("--carrier-pin", required=True, type=Path,
                   help="independently enrolled carrier1 PUBLIC P-256 JWK")
    p.add_argument("--journal", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a=p.parse_args()
    if a.out.exists():raise ValueError("report file already exists")
    result=reconcile(
        json.loads(a.fieldkit.read_text("utf-8")),a.journal,
        json.loads(a.origin_pin.read_text("utf-8")),
        json.loads(a.carrier_pin.read_text("utf-8")),
    )
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
