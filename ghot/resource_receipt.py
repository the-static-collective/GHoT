#!/usr/bin/env python3
"""GHoT RESOURCE WITNESS 001: credits-free, measured computer-work receipts.

Compare repeated answers from fully re-parsed evidence with evidence whose
content is SHA-256-checked before reusing an already validated summary.
Both produce byte-identical useful answers; all resource counters have units
and preserve unknown actual-energy as null. No device control, network call,
remote shell, cryptocurrency, money price, or execution assignment.
"""
from __future__ import annotations
import argparse
from hashlib import sha256,sha1
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc

from power_field import apply_power_policy, probe_power
from energy_scheduler import decide_from_candidates

SCHEMA="ghot.resource-witness/v1"
INPUT_SCHEMA="motif.question-kind-physical-test/v1"
EXPECTED_HOLD="HOLD_NO_INDEPENDENT_QUESTION_VALUE"
SOURCE_ID="motif-019-public-USGS-research-card"
SOURCE_COMMIT="1bb4028141eb20a8798bed338dcb3d851284de22"
SOURCE_BLOB="0cf1303cdeb83d9c29fe417ac19c66c217ddf63d"
MAX_BYTES=200_000
MAX_REPEATS=2000
MAX_TRIALS=11
# Specific kernel-maintained Intel package RAPL interface; may be unavailable.
# Never pretend the package-wide counter belongs to this Python process.
RAPL_ENERGY=Path("/sys/class/powercap/intel-rapl:0/energy_uj")
RAPL_RANGE=Path("/sys/class/powercap/intel-rapl:0/max_energy_range_uj")


class HOLD(ValueError):
    pass


def require(ok,why):
    if not ok:raise HOLD(why)


def checked_bytes(path):
    # Only read an existing local JSON regular file; no URL or arbitrary command.
    require(isinstance(path,Path) and path.is_file(),"SOURCE_NOT_LOCAL_FILE")
    require(not path.is_symlink(),"SYMLINK_SOURCE_NOT_ACCEPTED")
    require(0<path.stat().st_size<=MAX_BYTES,"SOURCE_TOO_LARGE")
    data=path.read_bytes()
    require(len(data)<=MAX_BYTES,"SOURCE_TOO_LARGE")
    return data


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True)


def safe_num(x):
    require(type(x) in (int,float) and math.isfinite(x) and x>=0,
            "INVALID_PHYSICAL_TEST_NUMBER")
    return float(x)


def validate_and_summarize(blob):
    try: data=json.loads(blob)
    except (ValueError,UnicodeError) as exc:raise HOLD("MALFORMED_PHYSICAL_REPORT") from exc
    require(type(data) is dict and data.get("schema")==INPUT_SCHEMA,
            "WRONG_SOURCE_REPORT_KIND")
    require(data.get("hypothesis_state")==EXPECTED_HOLD and
            data.get("authority") is False and
            data.get("automatic_admission") is False and
            data.get("actual_2026_forecasts_issued") is False and
            data.get("sensor_health_really_queried_at_issue_time") is False,
            "UNVERIFIED_OR_PROMOTED_SOURCE")
    density=data.get("downstream_complete_case_population",{})
    cases=density.get("complete_downstream_hours")
    require(type(cases) is int and 50<=cases<=10000,"INVALID_SOURCE_DENOMINATOR")
    alternatives=data.get("all_declared_policy_results_POSTHOC_DO_NOT_SELECT",{})
    require(type(alternatives) is dict and
            {"downstream","health_last3","sueur_only"}.issubset(alternatives),
            "MISSING_SOURCE_COMPARATORS")
    best=alternatives["health_last3"]
    baseline=alternatives["downstream"]
    require(baseline.get("count")==best.get("count")==cases,
            "INCOMPARABLE_TARGET_DENOMINATORS")
    base_error=safe_num(baseline.get("absolute_error_mae_cfs"))
    health_error=safe_num(best.get("absolute_error_mae_cfs"))
    require(abs(base_error-safe_num(data.get("baseline_mae_cfs")))<.0002,
            "MISLEADING_BASELINE")
    require(health_error<base_error and
            data.get("frozen_selection")=="downstream",
            "UNEXPECTED_INSTRUMENT_WITNESS")
    return {
       "report_schema":INPUT_SCHEMA,
       "observed_downstream_hours":cases,
       "frozen_question":"downstream",
       "frozen_disposition":EXPECTED_HOLD,
       "observed_raw_error_persistence_cfs":round(base_error,4),
       "observed_raw_error_health_proxy_cfs":round(health_error,4),
       "research_question":"What does it cost in real computation to reuse an already verified answer?",
       "safety_caveat":"Historical sensor availability is NOT actual issue-time sensor health.",
       "automatic_admission":False
    }


class Inspect:
    def __init__(self,source):
        self.source=source
        self.previous_digest=None
        self.previous_summary=None
        self.json_parses=0
        self.bytes_read=0
        self.hashes=0

    def answer(self,mode):
        require(mode in ("reparse","reuse"),"UNKNOWN_RESEARCH_MODE")
        blob=checked_bytes(self.source)
        self.bytes_read+=len(blob)
        key=sha256(blob).hexdigest()
        self.hashes+=1
        # With content mismatch, force a new validation, never reuse stale evidence.
        if mode=="reparse" or key!=self.previous_digest:
            self.previous_summary=validate_and_summarize(blob)
            self.previous_digest=key
            self.json_parses+=1
        # Immutable JSON answer across either full parse or verified reuse.
        return canonical(self.previous_summary)


def native_ghot_advice(power):
    """Feed the native GHoT body/willingness policy in explicit DRY-RUN MODE.

    This is a hypothetical candidate, not discovery/permission/a real offer.
    It demonstrates how pressure could inform placement once a real approved
    capability exists. No call to schedule() or execute().
    """
    require(type(power) is dict and power.get("willingness") in
            ("abundant","normal","conserve","critical"),"BAD_POWER_SNAPSHOT")
    offer=apply_power_policy([{"kind":"ghot.offer","version":"0",
          "capability":"llm.infer.small","available":True}],power)[0]
    candidate={"node_id":"hypothetical-local-resource-witness",
               "location":"local","field_state":"awake",
               "body":{"node_id":"hypothetical-local-resource-witness",
                       "power":power,"offers":[offer]}}
    decision=decide_from_candidates(
        [candidate],"llm.infer.small",
        urgency="background",deferrable=True,
        data_node_id="hypothetical-local-resource-witness")
    require(decision["action"] in ("hold","run_here","no_eligible_body"),
            "UNEXPECTED_NATIVE_ENERGY_DECISION")
    return {
       "kind":"ghot.resource-policy-observation/v1",
       "type":"HYPOTHETICAL_NATIVE_DRY_RUN_NOT_REAL_OFFER",
       "native_ghot_scheduler_action":decision["action"],
       "native_power_willingness":power["willingness"],
       "reported_power_source":power.get("source"),
       "power_pressure_reasons":power.get("willingness_reasons",[]),
       "offer_withdrawn_by_power":offer["available"] is False,
       "deferrable_background":True,
       "real_task_dispatched":False,
       "real_energy_budget_reserved":False
    }


def rapl_sample():
    if platform.system()!="Linux" or not RAPL_ENERGY.is_file() or not RAPL_RANGE.is_file():
        return None
    try:
        max_uj=int(RAPL_RANGE.read_text().strip())
        value=int(RAPL_ENERGY.read_text().strip())
        if not(0<max_uj<1_000_000_000_000 and 0<=value<max_uj):
            return None
        return (value,max_uj)
    except (OSError,ValueError):
        return None


def rapl_delta(before,after):
    if before is None or after is None or before[1]!=after[1]:
        return None
    # Wrap delta correct only if at most one wrap; no reliable guarantee.
    # These are whole-package counters with background co-tenant activity.
    start,limit=before;finish,_=after
    return round(((finish-start) % limit)/1_000_000,8)


def one_trial(source,mode,repeats):
    observer=Inspect(source)
    # Start before any hash, parse or cached answer: cold setup is included.
    # Warm OS-level cache uncontrolled; all modes use the same file, alternated.
    pre=rapl_sample()
    tracemalloc.start()
    cpu0=time.process_time_ns()
    wall0=time.perf_counter_ns()
    reference=None
    for _ in range(repeats):
        answer=observer.answer(mode)
        if reference is None:
            reference=answer
        else:
            require(answer==reference,"OUTPUT_DIFFERED_WITHIN_TRIAL")
    elapsed=time.perf_counter_ns()-wall0
    cpu=time.process_time_ns()-cpu0
    peak=tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    post=rapl_sample()
    return {
      "mode":mode,
      "answer_sha256":sha256(reference.encode("ascii")).hexdigest(),
      "cpu_time_ns":cpu,"wall_time_ns":elapsed,
      "python_tracemalloc_peak_bytes":peak,
      "actual_bytes_read":observer.bytes_read,
      "local_sha256_hash_operations":observer.hashes,
      "json_validation_parses":observer.json_parses,
      "package_rapl_joules_IF_VISIBLE":rapl_delta(pre,post),
      "package_energy_scope":"LINUX_INTEL_RAPL_WHOLE_CPU_PACKAGE_NOT_PER_PROCESS"
                             if pre is not None and post is not None else "NO_ENERGY_SENSOR",
      "repetitions":repeats
    }


def summarize(trials):
    out={}
    for mode in ("reparse","reuse"):
        series=[x for x in trials if x["mode"]==mode]
        require(series and len(series)==len(trials)//2,"UNBALANCED_TRIALS")
        out[mode]={
          "median_cpu_time_ns":statistics.median(x["cpu_time_ns"] for x in series),
          "median_wall_time_ns":statistics.median(x["wall_time_ns"] for x in series),
          "median_python_tracemalloc_peak_bytes":statistics.median(
              x["python_tracemalloc_peak_bytes"] for x in series),
          "bytes_read_per_trial":series[0]["actual_bytes_read"],
          "hashes_per_trial":series[0]["local_sha256_hash_operations"],
          "parses_per_trial":series[0]["json_validation_parses"],
          "rapl_package_joules_median_if_measured":(
              statistics.median(x["package_rapl_joules_IF_VISIBLE"]
                                for x in series)
              if all(x["package_rapl_joules_IF_VISIBLE"] is not None
                     for x in series) else None),
        }
    out["cpu_time_delta_ns_reparse_minus_reuse"]=round(
       out["reparse"]["median_cpu_time_ns"]-
       out["reuse"]["median_cpu_time_ns"])
    out["energy_joules_comparison_claim_available"]=(
        out["reparse"]["rapl_package_joules_median_if_measured"] is not None and
        out["reuse"]["rapl_package_joules_median_if_measured"] is not None)
    return out


def meter(source,trials=5,repeats=250, *,power=None):
    require(type(trials) is int and 2<=trials<=MAX_TRIALS and
            type(repeats) is int and 10<=repeats<=MAX_REPEATS,
            "MEASUREMENT_BUDGET_OUT_OF_RANGE")
    source_bytes=checked_bytes(source)
    # Refuse an incorrect/altered research record rather than measuring it
    # as if it were the actual known 019 evidence.
    expected=SOURCE_BLOB
    git_blob=sha1(b"blob "+str(len(source_bytes)).encode()+bytes([0])+source_bytes).hexdigest()
    require(git_blob==SOURCE_BLOB,"PINNED_PHYSICAL_SOURCE_BYTES_CHANGED")
    source_summary=validate_and_summarize(source_bytes)
    if power is None:
        power=probe_power()
    native=native_ghot_advice(power)
    # Alternate order to reduce systematic first-run caching bias.
    trials_out=[]
    for index in range(trials):
        modes=("reparse","reuse") if index%2==0 else ("reuse","reparse")
        for mode in modes:
            trials_out.append(one_trial(source,mode,repeats))
    results=summarize(trials_out)
    digest_set={r["answer_sha256"] for r in trials_out}
    require(len(digest_set)==1,"UNEQUAL_ANSWER_BODIES")
    # We do not choose a globally superior energy algorithm without joules
    # and independent repetitions on more bodies.
    resource_disposition=(
        "OBSERVED_LOCAL_CPU_REUSE_ADVANTAGE_NOT_POWER_SAVINGS_PROOF"
        if results["cpu_time_delta_ns_reparse_minus_reuse"]>0 else
        "HOLD_NO_MEASURED_CPU_ADVANTAGE"
    )
    return {
      "schema":SCHEMA,
      "purpose":"Replace invented research credits with witnessed physical-compute units",
      "source":{
        "source_id":SOURCE_ID,"source_commit":SOURCE_COMMIT,
        "source_file_sha256":sha256(source_bytes).hexdigest(),
        "git_blob_sha1_expected":expected,
        "source_length_bytes":len(source_bytes),
        "source_kind":INPUT_SCHEMA,
        "source_summary":source_summary,
      },
      "benchmark":{
        "shape":"same-answer-parse-every-time-vs-content-verified-reuse",
        "trials_each":trials,"repetitions_per_trial":repeats,
        "all_answers_bitwise_equal":True,
        "raw_trials":trials_out,"observed":results,
        "status":resource_disposition
      },
      "power":native,
      "resource_accounting":{
        "no_arbitrary_credit_prices":True,
        "cpu_time_ns":"MEASURED_PROCESS_CPU_TIME_NOT_ELECTRICAL_ENERGY",
        "wall_time_ns":"MEASURED_ELAPSED_TIME_NOT_NETWORK_LATENCY",
        "memory":"TRACEMALLOC_PEAK_PYTHON_ALLOCATIONS_NOT_FULL_RSS",
        "bytes_read":"READ_SOURCE_BYTES_NOT_STORAGE_ENERGY",
        "package_energy_joules":"NULL_IF_NO_SUPPORTED_SENSOR; IF_PRESENT IS_SHARED_PACKAGE_NOT_PYTHON",
        "real_energy_joules_measured":results["energy_joules_comparison_claim_available"],
        "grid_co2_kg_measured":False,
        "battery_consumption_joules_measured":False,
        "network_bytes_observed":0,
        "actual_energy_usage_attributed_to_this_task":False
      },
      "limits":[
        "The input is an archived source-owned research report, not live USGS sensor telemetry.",
        "Microbenchmarks do not measure user decision quality, river forecast skill, or real data-acquisition network latency.",
        "GHoT power status is an OS probe or explicitly identified manual hints; synthetic scheduler candidate is not a real offered executor.",
        "Thermal throttling, Python allocator overhead, OS page cache, filesystem caching and shared host contention affect timings.",
        "CPU time and local I/O bytes are not interchangeable units; resource preferences require actual operator constraints.",
        "Linux RAPL package counts, if readable, include other processes and cannot establish this task's power draw."
      ],
      "real_remote_tasks_executed":0,"source_code_self_modified":False,
      "model_weights_modified":False,"automatic_model_promotion":False,
      "authority":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=Path(__file__).resolve().parents[1]/
        "integrations/motif-019/physical-witness.json")
    p.add_argument("--trials",type=int,default=5)
    p.add_argument("--repeats",type=int,default=250)
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    try:
        report=meter(args.source,trials=args.trials,repeats=args.repeats)
        content=json.dumps(report,indent=2,sort_keys=True)+"\n"
        if args.out:args.out.write_text(content,encoding="utf8")
        print(content)
        return 0
    except (HOLD,OSError,ValueError,TypeError,KeyError) as e:
        print("HOLD: "+str(e)[:150],file=sys.stderr)
        return 2


if __name__=="__main__":raise SystemExit(main())
