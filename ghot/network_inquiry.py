#!/usr/bin/env python3
"""GHoT-002 — physical network inquiry (no coins, credits or invented joules).

Question: can bounded public source requests produce one *recent source-backed*
observation, and what wall time, payload bytes and failures did the questions
physically consume? All sources are predeclared USGS river observations.

Running 'live' sends exactly three read-only public HTTPS queries. The policy
replay is COUNTERFACTUAL: it derives what a predeclared serial stopping rule
would have used from all three measured responses, and cannot claim saved
energy, actual prevented requests, or foreknowledge of failed queries.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import socket
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen

from power_field import probe_power

SCHEMA="ghot.public-network-inquiry/v1"
HOST="api.waterdata.usgs.gov"
ENDPOINT="https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items"
# Fixed first three options: no web searches and no owner private IPs.
STATIONS=[
 ("blue","USGS-05320000"),
 ("sueur","USGS-05320500"),
 ("mankato","USGS-05325000"),
]
CODE="00060"
MAX_BODY=1_500_000
MAX_FEATURES=700
MAX_RTT_NS=20_000_000_000
TIMEOUT_SECONDS=9
FRESH_SECONDS=12*3600
MAX_NEGATIVE_LAG_SECONDS=5*60
MAX_SOURCE_AGE_SECONDS=7*24*3600
STOP_POLICIES=("no_query","first_source_only","until_first_witness","all_three")
USER_AGENT="GHoT-002 read-only open public hydrology research (+the-static-collective/GHoT)"
VERSION="ghot.source-probe/v1"
VALID_UNITS={"ft3/s","ft^3/s","ft³/s","ft3 s-1"}
MAX_HOURS=4*24
SOURCE_LIMIT=1000

class HOLD(ValueError): pass

def require(ok,reason):
    if not ok:raise HOLD(reason)

def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def parse_utc(text):
    require(isinstance(text,str) and len(text)<65,"BAD_UTC_SOURCE_TIMESTAMP")
    try:dt=datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError as ex:raise HOLD("INVALID_TIME_FORMAT") from ex
    require(dt.tzinfo is not None,"TIMEZONE_ABSENT")
    return dt.astimezone(timezone.utc)

def query_url(site,start,end):
    require(site in dict(STATIONS),"UNLISTED_SOURCE")
    require(start.tzinfo is not None and end.tzinfo is not None and
            0<(end-start).total_seconds()<=MAX_HOURS*3600,
            "SOURCE_WINDOW_LIMIT")
    qs=urlencode({"monitoring_location_id":dict(STATIONS)[site],
                  "parameter_code":CODE,
                  "datetime":iso(start).split("T")[0]+"/"+iso(end).split("T")[0],
                  "limit":str(MAX_FEATURES),"f":"json"})
    return ENDPOINT+"?"+qs

def preflight_url(url,site):
    p=urlsplit(url)
    require(p.scheme=="https" and p.hostname==HOST and p.port is None and
            p.path=="/ogcapi/v1/collections/continuous/items" and
            not p.username and not p.password and not p.fragment,
            "UNAPPROVED_NETWORK_DESTINATION")
    from urllib.parse import parse_qs
    q=parse_qs(p.query,strict_parsing=True)
    require(set(q)=={"monitoring_location_id","parameter_code","datetime","limit","f"} and
            all(len(v)==1 for v in q.values()) and
            q["monitoring_location_id"]==[dict(STATIONS)[site]] and
            q["parameter_code"]==[CODE] and q["limit"]==[str(MAX_FEATURES)] and
            q["f"]==["json"],"INVALID_PUBLIC_SOURCE_QUERY")

def latest_observation(raw,site,received):
    """Validate agency record structure without asserting physical correctness."""
    require(isinstance(raw,dict) and raw.get("type")=="FeatureCollection" and
            isinstance(raw.get("features"),list) and
            len(raw["features"])<=MAX_FEATURES,"BAD_PUBLIC_FEATURE_COLLECTION")
    for link in raw.get("links",[]):
        require(not (isinstance(link,dict) and link.get("rel")=="next"),
                "PAGINATED_SOURCE_REFUSED")
    found={}
    for item in raw["features"]:
        require(isinstance(item,dict) and isinstance(item.get("properties"),dict),
                "MALFORMED_PUBLIC_READING")
        p=item["properties"]
        require(p.get("monitoring_location_id")==dict(STATIONS)[site] and
                p.get("parameter_code")==CODE and
                p.get("unit_of_measure") in VALID_UNITS,
                "WRONG_PUBLIC_READING_STATION_OR_UNIT")
        value=p.get("value")
        require(type(value) in (int,float,str),"INVALID_REPORTED_FLOW")
        try:flow=float(value)
        except ValueError as ex:raise HOLD("NONNUMERIC_PUBLIC_READING") from ex
        require(math.isfinite(flow) and 0<=flow<10_000_000,
                "OUT_OF_RANGE_PUBLIC_READING")
        dt=parse_utc(p.get("time"))
        require(dt<=received+timedelta(seconds=MAX_NEGATIVE_LAG_SECONDS),
                "PUBLIC_SOURCE_TIMESTAMP_FROM_FUTURE")
        if dt in found:
            require(found[dt]==flow,"CONFLICTING_SAME_TIMESTAMP")
        found[dt]=flow
    if not found:
        return {"station":site,"latest_observation_utc":None,
                "age_seconds":None,"latest_flow_cfs":None,
                "parsed_source_points":0,"fresh_source_witness":False,
                "evidence_is":"NO_RECORD_RETURNED"}
    last=max(found)
    age=max(0,round((received-last).total_seconds(),3))
    return {"station":site,"latest_observation_utc":iso(last),
            "age_seconds":age,"latest_flow_cfs":found[last],
            "parsed_source_points":len(found),
            "fresh_source_witness":age<=FRESH_SECONDS,
            "evidence_is":"USGS_REPORTED_VALUE_NOT_INDEPENDENTLY_AUTHENTICATED"}

def bounded_fetch(url,site,now=datetime.now):
    """Allowlisted HTTP GET; don't follow redirects to other hosts/protocols."""
    preflight_url(url,site)
    # urllib default redirect handler can move hosts: refuse all HTTP redirects.
    from urllib.request import build_opener,HTTPHandler,HTTPSHandler,HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            return None
    opener=build_opener(HTTPHandler(),HTTPSHandler(),NoRedirect())
    started=now(timezone.utc)
    start_ns=time.perf_counter_ns()
    cpu_ns=time.process_time_ns()
    status=None; data=b"";ctype=None;error=None
    try:
        req=Request(url,headers={"User-Agent":USER_AGENT,
                                "Accept":"application/json",
                                "Accept-Encoding":"identity"},
                    method="GET")
        with opener.open(req,timeout=TIMEOUT_SECONDS) as response:
            status=response.status
            ctype=response.headers.get("Content-Type","")
            require(status==200,"UNEXPECTED_HTTP_STATUS")
            # Never trust Content-Length alone, enforce bounded actual bytes.
            data=response.read(MAX_BODY+1)
            require(0<len(data)<=MAX_BODY,"UNBOUNDED_OR_EMPTY_HTTP_BODY")
    except (HTTPError,URLError,TimeoutError,OSError,socket.timeout,HOLD) as exc:
        if isinstance(exc,HTTPError):status=exc.code
        error=(exc.args[0] if isinstance(exc,HOLD) else type(exc).__name__)
    ended=now(timezone.utc)
    wall=time.perf_counter_ns()-start_ns
    cpu=time.process_time_ns()-cpu_ns
    receipt={
       "kind":VERSION,"site":site,
       "request_start_utc":iso(started),"response_end_utc":iso(ended),
       "http_status":status,"latency_wall_ns":wall,
       "local_cpu_ns":cpu,
       "body_bytes_received":len(data),
       "wire_network_bytes_total":None,
       "body_sha256":sha256(data).hexdigest() if data else None,
       "content_type_header":ctype,
       "error":str(error)[:80] if error is not None else None,
       "valid_source_response":False,
       "observation":None
    }
    if error is None:
        try:
            obj=json.loads(data)
            receipt["observation"]=latest_observation(obj,site,ended)
            receipt["valid_source_response"]=True
        except (UnicodeError,ValueError,TypeError,KeyError) as ex:
            receipt["error"]=("VALIDATION:"+str(ex))[:100]
    return receipt

def budget_guard(power):
    require(type(power) is dict and power.get("willingness") in
            {"critical","conserve","normal","abundant"},
            "INVALID_GHOT_NATIVE_POWER_PROBE")
    # Under conserve only lightweight bounded read-only measurements. Under
    # critical no extra network or compute on operator-controlled device.
    # The experiment is a *light* query probe, not an arbitrary GHOT executor.
    return power["willingness"]!="critical"

def summarize(receipts,clock_iso, power):
    require(isinstance(receipts,list) and len(receipts)==len(STATIONS) and
            [r.get("site") for r in receipts]==[x[0] for x in STATIONS],
            "REPLAY_REQUIRES_ALL_FIXED_SOURCE_SLOTS")
    d={}
    for r in receipts:
        require(r.get("kind")==VERSION and
                type(r.get("latency_wall_ns")) is int and
                0<=r["latency_wall_ns"]<=MAX_RTT_NS and
                type(r.get("local_cpu_ns")) is int and r["local_cpu_ns"]>=0 and
                type(r.get("body_bytes_received")) is int and
                0<=r["body_bytes_received"]<=MAX_BODY and
                r.get("wire_network_bytes_total") is None and
                r.get("request_start_utc") and r.get("response_end_utc") and
                isinstance(r.get("valid_source_response"),bool),
                "INVALID_PHYSICAL_REQUEST_RECEIPT")
        if r["valid_source_response"]:
            obs=r.get("observation")
            require(type(obs) is dict and obs.get("station")==r["site"] and
                    type(obs.get("fresh_source_witness")) is bool,
                    "INVALID_WITNESS_STATUS")
            if obs["fresh_source_witness"]:
                require(type(obs.get("latest_flow_cfs")) in (float,int) and
                        type(obs.get("latest_observation_utc")) is str,
                        "CLAIMED_FRESH_WITHOUT_REPORTED_MEASUREMENT")
        d[r["site"]]=r
    clock=parse_utc(clock_iso)
    # Do not convert source payload bytes to transport wire bytes, or time to energy.
    def policy(names):
        selected=[]
        for name in names:
            r=d[name]
            selected.append(r)
            if r["valid_source_response"] and r["observation"]["fresh_source_witness"]:
                break
        witness=next((r for r in selected if r["valid_source_response"] and
             r["observation"]["fresh_source_witness"]),None)
        return {
            "policy_sources_replayed":[r["site"] for r in selected],
            "inferred_query_count":len(selected),
            "inferred_wall_ns_serial_sum":sum(r["latency_wall_ns"] for r in selected),
            "inferred_local_cpu_ns_sum":sum(r["local_cpu_ns"] for r in selected),
            "inferred_response_payload_bytes_sum":sum(r["body_bytes_received"] for r in selected),
            "physical_source_witness":bool(witness),
            "witness_site":witness["site"] if witness else None,
            "not_actual_separate_policy_execution":True
        }
    policies={
       "no_query":{
           "policy_sources_replayed":[],"inferred_query_count":0,
           "inferred_wall_ns_serial_sum":0,"inferred_local_cpu_ns_sum":0,
           "inferred_response_payload_bytes_sum":0,
           "physical_source_witness":False,"witness_site":None,
           "not_actual_separate_policy_execution":True
       },
       "first_source_only":policy(["blue"]),
       "until_first_witness":policy(["blue","sueur","mankato"]),
       "all_three":{
           # This one physically queried all 3, regardless of earlier result.
           "policy_sources_replayed":[x[0] for x in STATIONS],
           "inferred_query_count":len(receipts),
           "inferred_wall_ns_serial_sum":sum(r["latency_wall_ns"] for r in receipts),
           "inferred_local_cpu_ns_sum":sum(r["local_cpu_ns"] for r in receipts),
           "inferred_response_payload_bytes_sum":sum(r["body_bytes_received"] for r in receipts),
           "physical_source_witness":any(r["valid_source_response"] and
             r["observation"]["fresh_source_witness"] for r in receipts),
           "witness_site":next((r["site"] for r in receipts if
             r["valid_source_response"] and r["observation"]["fresh_source_witness"]),None),
           "not_actual_separate_policy_execution":False
       }
    }
    freshness=[r for r in receipts if r["valid_source_response"] and
               r["observation"]["fresh_source_witness"]]
    failures=[r for r in receipts if not r["valid_source_response"]]
    measured_total_ns=sum(r["latency_wall_ns"] for r in receipts)
    measured_bytes=sum(r["body_bytes_received"] for r in receipts)
    return {
       "schema":SCHEMA,
       "question":"Can at least one named public river station provide a reported measurement within 12 hours of the GET?",
       "objective":"RETURN_AN_EVIDENCED_FRESH_PUBLIC_OBSERVATION_OR_ABSTAIN",
       "source_reporting_is_not_ground_truth":True,
       "completed_at_utc":clock_iso,
       "research_only_not_flood_warning":True,
       "hardware_decision":{
           "source":"GHOT_NATIVE_POWER_FIELD",
           "willingness":power["willingness"],
           "power_source":power.get("source"),
           "battery_percentage":power.get("battery_percent"),
           "thermal_c":power.get("temperature_c"),
           "measurement_hints":power.get("probe",{}).get("manual_hints",{}),
           "power_is_not_a_wattmeter":True
       },
       "actual_network_activity":{
          "allowed_host":HOST,"method":"GET",
          "source_sites":[site for site,_ in STATIONS],
          "requests_sent":len(receipts),
          "http_successes_with_valid_records":len(receipts)-len(failures),
          "fresh_public_source_count":len(freshness),
          "source_failures":len(failures),
          "sum_individually_observed_http_elapsed_ns":measured_total_ns,
          "received_body_payload_bytes":measured_bytes,
          "actual_on_wire_network_bytes":None,
          "energy_joules_attributable_to_requests":None,
          "cpu_time_ns_for_requests_only":sum(r["local_cpu_ns"] for r in receipts),
          "all_http_sources_bounded":True
       },
       "per_request_receipts":receipts,
       "strategy_comparison":{
          "evaluation_kind":"SAME_OBSERVED_RESPONSES_COUNTERFACTUAL_STOPPING_POLICY",
          "all_three_queries_actually_executed":True,
          "no_tokens_or_credits":True,
          "alternative_policies_NOT_ACTUALLY_RUN":policies
       },
       "source_snapshots_preserved":{
          "original_raw_json":"NOT_INCLUDED_IN_OUTPUT_TO_AVOID_UNBOUNDED_ARCHIVING",
          "payload_sha256_in_receipts":True,
          "http_status_codes_recorded":True
       },
       "next_question":(
          "Will a predeclared stop-when-first-fresh strategy actually reduce "
          "measured requests and latency on a new run without lowering the "
          "rate of obtaining source-backed current observations?"
       ),
       "disposition":(
          "HELD_FOR_PROSPECTIVE_CONDITIONAL_QUERY_TEST" if freshness else
          "HOLD_NO_FRESH_SOURCE_WITNESS_OBSERVED"
       ),
       "external_action":False,"automatic_model_promotion":False,
       "automatic_body_assignment":False,"not_a_public_hazard_prediction":True,
       "electrical_energy_measured":False,
       "permission_required_for_additional_sources":True
    }

def live():
    power=probe_power()
    if not budget_guard(power):
        raise HOLD("GHOT_POWER_CRITICAL_NO_EXTRA_NETWORK_WORK")
    started=datetime.now(timezone.utc)
    end=started-timedelta(hours=1)
    start=end-timedelta(hours=MAX_HOURS)
    receipts=[]
    for site,_ in STATIONS:
        url=query_url(site,start,end)
        receipts.append(bounded_fetch(url,site))
    return summarize(receipts,iso(datetime.now(timezone.utc)),power)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path)
    parser.add_argument("--from-captured",type=Path,
      help="synthetic fixture or archived identical receipts, no network")
    p=parser.parse_args()
    try:
        if p.from_captured:
            d=json.loads(p.from_captured.read_text())
            report=summarize(d["per_request_receipts"],d["completed_at_utc"],
                             {"willingness":"normal","source":None,
                              "battery_percent":None,"temperature_c":None,
                              "probe":{"manual_hints":{}}})
        else:report=live()
        encoded=json.dumps(report,sort_keys=True,indent=2)+"\n"
        if p.out:
            p.out.write_text(encoded,encoding="utf8")
        print(encoded)
        return 0
    except (HOLD,ValueError,TypeError,OSError,KeyError) as ex:
        print("HOLD: "+str(ex)[:180],file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
