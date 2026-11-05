#!/usr/bin/env python3
"""GHoT-004. An actual credits-free test of when further inquiry is useless.

Two FIXED, explicit user-style evidence contracts; two ACTUALLY EXECUTED
strategies per contract, not a retrospective counterfactual. A bounded public
USGS source read only, no background monitoring, private accounts or alerts.

A stop is justified when the goal is achieved; HOLD if the fixed remaining
sources cannot finish the goal. Every decision and resource has its own unit.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlsplit,parse_qs

from network_inquiry import (
    STATIONS, VERSION, MAX_HOURS, MAX_BODY, FRESH_SECONDS, iso,parse_utc,
    query_url,preflight_url,bounded_fetch,probe_power,budget_guard,
)

SCHEMA="ghot.goal-aware-inquiry/v1"
STEP_SCHEMA="ghot.goal-step/v1"
GOALS={
    "any_fresh": {
        "meaning":"Obtain one agency-reported public discharge observation no older than 12h",
        "kind":"any_of","required":["blue","sueur","mankato"],
        "optimized_order":["blue","sueur","mankato"],
    },
    "two_named_fresh": {
        "meaning":"Obtain separate recent public discharge reports for BOTH Blue Earth and Le Sueur",
        "kind":"all_of","required":["blue","sueur"],
        "optimized_order":["blue","sueur"],
    }
}
CONTROL_ORDER=["blue","sueur","mankato"]
POLICIES=("goal_aware","exhaustive")
# Limit first real proof to two goals x two policies, at most 10 actual
# public read-only GETs (1+3+2+3 expected on fresh sources).
MAX_CALLS_TOTAL=10
MAX_CALLS_TRIAL=3
MAX_TRIAL_NS=45_000_000_000
MAX_STORED_RESPONSE_BYTES=MAX_BODY
PHYSICAL_SOURCE_KIND="USGS_REPORTED_DISCHARGE_NOT_INDEPENDENTLY_CALIBRATED"

class HOLD(ValueError):pass
def require(ok,reason):
    if not ok:raise HOLD(reason)

def valid_recent(receipt,site):
    if not (type(receipt) is dict and receipt.get("kind")==VERSION and
            receipt.get("site")==site and
            receipt.get("valid_source_response") is True):
        return False
    o=receipt.get("observation")
    return type(o) is dict and o.get("station")==site and o.get("fresh_source_witness") is True

def observed_completion(goal,receipts):
    """Formal contract satisfaction; never infer completion from a mere HTTP 200."""
    g=GOALS[goal]
    available={r["site"] for r in receipts if valid_recent(r,r["site"])}
    required=set(g["required"])
    return bool(available & required) if g["kind"]=="any_of" else required <= available

def reachable(goal,receipts,remaining):
    """If this source fails, asking another unrelated one cannot complete AND."""
    g=GOALS[goal]
    available={r["site"] for r in receipts if valid_recent(r,r["site"])}
    if g["kind"]=="any_of":
        return bool(available & set(g["required"])) or bool(set(remaining)&set(g["required"]))
    return set(g["required"]) <= (available|set(remaining))

def validate_step(r,site,requested_url):
    require(type(r) is dict and r.get("kind")==VERSION and
            r.get("site")==site and type(r.get("valid_source_response")) is bool and
            type(r.get("latency_wall_ns")) is int and
            0<=r["latency_wall_ns"]<=20_000_000_000 and
            type(r.get("local_cpu_ns")) is int and r["local_cpu_ns"]>=0 and
            type(r.get("body_bytes_received")) is int and
            0<=r["body_bytes_received"]<=MAX_STORED_RESPONSE_BYTES and
            r.get("wire_network_bytes_total") is None and
            isinstance(r.get("request_start_utc"),str) and
            isinstance(r.get("response_end_utc"),str),
            "INVALID_PHYSICAL_SOURCE_STEP")
    require(parse_utc(r["request_start_utc"])<=parse_utc(r["response_end_utc"])+timedelta(seconds=1),
            "RESPONSE_BEFORE_REQUEST")
    # Live fetch returns a public-source receipt and never sends it elsewhere.
    # Check URL at callsite BEFORE executing it. Preserve public URL to
    # audit request-window encoding (GHoT-002 missed this).
    preflight_url(requested_url,site)
    if r["valid_source_response"]:
        obs=r.get("observation")
        require(type(obs) is dict and obs.get("station")==site and
                type(obs.get("fresh_source_witness")) is bool,
                "UNAUTHENTICATED_PHYSICAL_SOURCE_OUTCOME")
        if obs["fresh_source_witness"]:
            v=obs.get("latest_flow_cfs")
            require(type(v) in (int,float) and math.isfinite(v) and v>=0 and
                    isinstance(obs.get("latest_observation_utc"),str),
                    "FAKE_RECENT_READING")
            timestamp=parse_utc(obs["latest_observation_utc"])
            received=parse_utc(r["response_end_utc"])
            require(timestamp<=received+timedelta(minutes=5) and
                    (received-timestamp).total_seconds()<=FRESH_SECONDS+5*60,
                    "SOURCE_FRESHNESS_FLAG_CONTRADICTS_TIMESTAMPS")
    return r

def trial(goal,policy,fetch,clock,power):
    require(goal in GOALS and policy in POLICIES,"UNKNOWN_GOAL_OR_POLICY")
    require(callable(fetch) and callable(clock),"NO_BOUNDED_FETCHER")
    require(type(power) is dict and power.get("willingness") in
            {"critical","conserve","normal","abundant"},"INVALID_GHOT_POWER_STATE")
    g=GOALS[goal]
    order=(g["optimized_order"] if policy=="goal_aware" else CONTROL_ORDER)
    now=clock()
    require(isinstance(now,datetime) and now.tzinfo is not None,"NON_UTC_RESEARCH_CLOCK")
    end=now.astimezone(timezone.utc)-timedelta(hours=1)
    start=end-timedelta(hours=MAX_HOURS)
    receipts=[];steps=[];stop_reason=None
    if not budget_guard(power):
        stop_reason="HOLD_CRITICAL_POWER_BEFORE_QUERY"
    else:
        for index,site in enumerate(order):
            require(len(receipts)<MAX_CALLS_TRIAL,"UNBOUNDED_PLAN")
            url=query_url(site,start,end)
            preflight_url(url,site)
            # Each measured resource belongs to this ACTUAL GET, not another
            # run's simulated work.
            r=validate_step(fetch(url,site),site,url)
            receipts.append(r)
            completed=observed_completion(goal,receipts)
            left=order[index+1:]
            possible=reachable(goal,receipts,left)
            if policy=="goal_aware":
                if completed:action="STOP_GOAL_MET"
                elif not possible:action="HOLD_GOAL_UNREACHABLE_WITH_ALLOWED_SOURCES"
                elif left:action="ASK_NEXT_POSSIBLY_USEFUL_SOURCE"
                else:action="HOLD_EXHAUSTED_ALLOWED_SOURCES"
            else:
                action=("FINISH_CONTROL_AFTER_ALL_SOURCES"
                        if not left else "CONTROL_ASK_EXTRA_EVEN_IF_GOAL_MET")
            steps.append({
                "schema":STEP_SCHEMA,"step":index,"actual_site_requested":site,
                "public_request_url":url,
                "request_url_sha256":sha256(url.encode()).hexdigest(),
                "original_goal_satisfied_after_this_step":completed,
                "still_possible_to_finish":possible,
                "decision":action,
                "this_source_was_fresh":valid_recent(r,site),
                "received_http_body_bytes":r["body_bytes_received"],
                "measured_wall_ns":r["latency_wall_ns"],
            })
            if policy=="goal_aware" and action!="ASK_NEXT_POSSIBLY_USEFUL_SOURCE":
                stop_reason=action
                break
    if stop_reason is None:
        stop_reason=("CONTROL_ALL_THREE_COMPLETED" if policy=="exhaustive"
                     else "HOLD_NO_SOURCE")
    completion=observed_completion(goal,receipts)
    sent=[r["site"] for r in receipts]
    sums={
      "actual_get_requests":len(receipts),
      "http_response_body_bytes":sum(r["body_bytes_received"] for r in receipts),
      "sum_request_wall_ns":sum(r["latency_wall_ns"] for r in receipts),
      "sum_request_local_cpu_ns":sum(r["local_cpu_ns"] for r in receipts),
      "wire_bytes":None,"attributable_joules":None,
    }
    return {
       "schema":"ghot.goal-trial/v1","goal":goal,"goal_meaning":g["meaning"],
       "contract_kind":g["kind"],"required_public_stations":g["required"],
       "policy":policy,"predeclared_route":order,
       "actually_queried_public_sites":sent,
       "skipped_public_sites":[s for s in CONTROL_ORDER if s not in sent],
       "actual_steps":steps,"per_request_receipts":receipts,
       "actual_resource_units":sums,
       "task_contract_completed":completion,
       "stop_reason":stop_reason,
       "source_reporting_only_not_a_hazard_prediction":True,
       "power_willingness":power["willingness"],
       "no_monetary_or_api_credit_costs":True,
       "no_emergency_action":True,"authority":False,
    }

def compare_two_tasks(fetch,clock,power):
    require(callable(fetch) and callable(clock),"BAD_INSTRUMENT")
    # Predeclare order A/B then B/A to partially counter ordering/cache
    # effects; not randomized or contemporaneous matched hardware.
    plan=[
       ("any_fresh","goal_aware"),
       ("any_fresh","exhaustive"),
       ("two_named_fresh","exhaustive"),
       ("two_named_fresh","goal_aware"),
    ]
    out=[]
    for goal,policy in plan:
        out.append(trial(goal,policy,fetch,clock,power))
    total=sum(t["actual_resource_units"]["actual_get_requests"] for t in out)
    require(total<=MAX_CALLS_TOTAL,"EXPERIMENT_QUERY_BUDGET_EXCEEDED")
    by_goal={}
    for goal in GOALS:
        a=next(x for x in out if x["goal"]==goal and x["policy"]=="goal_aware")
        b=next(x for x in out if x["goal"]==goal and x["policy"]=="exhaustive")
        ra=a["actual_resource_units"];rb=b["actual_resource_units"]
        by_goal[goal]={
           "optimized_goal_satisfied":a["task_contract_completed"],
           "control_goal_satisfied":b["task_contract_completed"],
           "actual_optimized_get_count":ra["actual_get_requests"],
           "actual_control_get_count":rb["actual_get_requests"],
           "actual_optimized_body_bytes":ra["http_response_body_bytes"],
           "actual_control_body_bytes":rb["http_response_body_bytes"],
           "actual_optimized_wall_ns":ra["sum_request_wall_ns"],
           "actual_control_wall_ns":rb["sum_request_wall_ns"],
           "same_task_goal_both_runs":True,
           "run_order_not_simultaneous":True,
           "comparison_can_prove_general_causal_savings":False,
           "comparison_can_prove_electrical_savings":False
        }
    # Avoid calling it Pareto superiority across changing source conditions.
    return {
      "schema":SCHEMA,
      "question":"When does further inquiry cease to be useful for a fixed, explicit evidence contract?",
      "source_host":"api.waterdata.usgs.gov",
      "data_kind":PHYSICAL_SOURCE_KIND,
      "declared_goals":GOALS,
      "run_order":[list(x) for x in plan],
      "two_goal_comparisons":by_goal,
      "actually_executed_trials":out,
      "actual_network_requests_sent":total,
      "actual_http_response_body_bytes":sum(
         t["actual_resource_units"]["http_response_body_bytes"] for t in out),
      "actual_request_wall_time_ns_sum":sum(
         t["actual_resource_units"]["sum_request_wall_ns"] for t in out),
      "actual_energy_joules":None,"actual_wire_bytes":None,
      "power_willingness":power["willingness"],
      "answer_quality_scope":"FORMALLY_SATISFIED_NARROW_PUBLIC_EVIDENCE_GOAL_ONLY",
      "deferral_supported":"CRITICAL_POWER_REFUSES_NETWORK_WORK",
      "no_paid_credits_needed":True,
      "outcome_research_hold":"NO_CROSS_RUN_CAUSAL_ENERGY_CLAIM",
      "next_question":"Can a bounded planner prove that each next query is necessary for the requested answer before asking, and measure lost usefulness when it holds?",
      "limits":[
         "All source data are public historical reports, potentially revised and not independently calibrated.",
         "A source being fresh says nothing about flood risk or whether physical conditions are safe.",
         "The goal-aware and exhaustive arms run sequentially on a changing internet; this is not a randomized controlled study.",
         "Wall time is not real power. Response-body bytes are not entire transport-layer bytes.",
         "This measures goal satisfaction for two simple contracts, not human satisfaction or general intelligence.",
         "Requests avoided in one arm are not independently observed counterfactual network packets.",
      ],
      "source_code_autonomously_modified":False,
      "external_side_effects_other_than_readonly_public_GET":False,
      "automatic_model_promotion":False,
      "authority":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    try:
        result=compare_two_tasks(bounded_fetch,lambda:datetime.now(timezone.utc),probe_power())
        content=json.dumps(result,sort_keys=True,indent=2)+"\n"
        if args.out:args.out.write_text(content,encoding="utf8")
        print(content)
        return 0
    except (HOLD,ValueError,TypeError,OSError,KeyError) as exc:
        print("HOLD: "+str(exc)[:160],file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
