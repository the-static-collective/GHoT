#!/usr/bin/env python3
"""GHoT-003 — actually stop asking after the first adequate public answer.

Unlike 002's same-responses counterfactual, this loop actually executes the
conditional policy on new public requests. It sends 1-3 fixed HTTPS GETs
depending on whether each public gauge provides a timestamp-recent reading.
The measured resource receipt describes *only the work actually done*.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
import json
import time
from pathlib import Path
import sys

from network_inquiry import (
  STATIONS,SCHEMA as PREVIOUS_SCHEMA,
  VERSION,STOP_POLICIES,query_url,bounded_fetch,budget_guard,
  iso,parse_utc,probe_power,FRESH_SECONDS,MAX_HOURS
)

SCHEMA="ghot.actual-conditional-inquiry/v1"
POLICY="BLUE_SUEUR_MANKATO_STOP_ON_FIRST_RECENT_SOURCE"
MAX_WALL_NS=40_000_000_000

class HOLD(ValueError):pass

def require(ok,reason):
    if not ok:raise HOLD(reason)

def _recent(r):
    return (r.get("valid_source_response") is True and
            isinstance(r.get("observation"),dict) and
            r["observation"].get("fresh_source_witness") is True)

def execute_question(fetch,clock,power):
    """Injected fetch function permits offline adversarial tests. No forecast."""
    require(callable(fetch) and callable(clock),"INVALID_TEST_INSTRUMENT")
    require(isinstance(power,dict) and power.get("willingness") in
            {"critical","conserve","normal","abundant"},"BAD_POWER_OBSERVATION")
    if not budget_guard(power):
        return {
            "schema":SCHEMA,"research_question":"Obtain one timestamp-recent public river reading, or abstain.",
            "status":"HOLD_GHOT_CRITICAL_POWER_NO_NETWORK_REQUESTS",
            "policy":POLICY,"actually_executed_sites":[],"skipped_sites":[s for s,_ in STATIONS],
            "requests_sent":0,"source_witness_found":False,"witness":None,
            "recorded_query_windows":[],"per_request_receipts":[],
            "body_payload_bytes_received":0,"actual_request_elapsed_ns_sum":0,
            "local_request_cpu_ns_sum":0,"actual_on_wire_bytes":None,
            "electrical_energy_joules":None,"power_source":power.get("source"),
            "GHOT_willingness":power["willingness"],
            "stopped_early":False,"new_requests_avoided_vs_previous_run":"NOT_MEASURED_AS_PARALLEL_CONTROL",
            "credit_cost_used":False,"automatic_model_promotion":False,
            "physical_action":False,"authority":False,
        }
    now=clock()
    require(isinstance(now,datetime) and now.tzinfo is not None,
            "CLOCK_MUST_BE_AWARE")
    endpoint=now-timedelta(hours=1)
    start=endpoint-timedelta(hours=MAX_HOURS)
    receipts=[];intervals=[]
    witness=None
    for site,_ in STATIONS:
        url=query_url(site,start,endpoint)
        intervals.append({"site":site,"start_utc":iso(start),
                          "end_utc":iso(endpoint)})
        item=fetch(url,site)
        require(isinstance(item,dict) and item.get("kind")==VERSION and
                item.get("site")==site and
                isinstance(item.get("valid_source_response"),bool) and
                type(item.get("body_bytes_received")) is int and
                0<=item["body_bytes_received"]<=1_500_000 and
                type(item.get("latency_wall_ns")) is int and
                0<=item["latency_wall_ns"]<=20_000_000_000 and
                type(item.get("local_cpu_ns")) is int and
                item["local_cpu_ns"]>=0 and
                item.get("wire_network_bytes_total") is None,
                "INVALID_PUBLIC_SOURCE_RECEIPT")
        if item["valid_source_response"]:
            obs=item.get("observation")
            require(type(obs) is dict and obs.get("station")==site and
                    type(obs.get("fresh_source_witness")) is bool,
                    "MALFORMED_REPORTING_STATUS")
            if obs["fresh_source_witness"]:
                require(type(obs.get("latest_flow_cfs")) in (int,float) and
                        obs.get("latest_observation_utc"),
                        "NO_PHYSICAL_WITNESS_BEHIND_ASSERTION")
        receipts.append(item)
        if _recent(item):
            witness={
                "site":site,
                "observation_utc":item["observation"]["latest_observation_utc"],
                "reported_discharge_cfs":item["observation"]["latest_flow_cfs"],
                "observed_age_seconds":item["observation"]["age_seconds"],
                "response_sha256":item.get("body_sha256"),
                "not_a_hazard_prediction":True
            }
            break
    sent=[r["site"] for r in receipts]
    return {
        "schema":SCHEMA,
        "research_question":"Obtain one timestamp-recent public river reading, or abstain.",
        "status":("HELD_SINGLE_CURRENT_SOURCE_WITNESS_OBTAINED" if witness
                  else "HOLD_NO_RECENT_SOURCE_IN_FIXED_THREE"),
        "policy":POLICY,"actually_executed_sites":sent,
        "skipped_sites":[s for s,_ in STATIONS if s not in sent],
        "requests_sent":len(sent),"source_witness_found":bool(witness),"witness":witness,
        "recorded_query_windows":intervals,
        "per_request_receipts":receipts,
        "body_payload_bytes_received":sum(x["body_bytes_received"] for x in receipts),
        "actual_request_elapsed_ns_sum":sum(x["latency_wall_ns"] for x in receipts),
        "local_request_cpu_ns_sum":sum(x["local_cpu_ns"] for x in receipts),
        "actual_on_wire_bytes":None,"electrical_energy_joules":None,
        "power_source":power.get("source"),"GHOT_willingness":power["willingness"],
        "stopped_early":len(sent)<len(STATIONS) and bool(witness),
        "new_requests_avoided_vs_previous_run":"NOT_MEASURED_AS_PARALLEL_CONTROL",
        "credit_cost_used":False,"automatic_model_promotion":False,
        "physical_action":False,"authority":False,
        "source_limitations":[
            "The only knowledge goal was any one source-reported timestamp-recent value, not flood prediction.",
            "Public USGS reported discharge may be provisional or revised; source authenticity is not independently confirmed.",
            "Actual UDP/TCP overhead, radio energy, process electrical power and network wire bytes remain unknown.",
            "Comparing this result to another run with three calls is noncontemporaneous; saved requests are not experimentally isolated.",
            "Only the predeclared source sequence is searched. The inability to find a measurement is not proof no such measurement exists."
        ]
    }

def live():
    return execute_question(
      bounded_fetch,lambda: datetime.now(timezone.utc),probe_power())

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    try:
        result=live()
        encoded=json.dumps(result,sort_keys=True,indent=2)+"\n"
        if a.out:a.out.write_text(encoded,encoding="utf8")
        print(encoded)
        return 0
    except (HOLD,ValueError,OSError,TypeError,KeyError) as ex:
        print("HOLD: "+str(ex)[:170],file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
