# GHoT Resource Witness 001 — no credits, honest compute receipts

**Problem:** Previous MOTIF 019 experiments priced asking another river gauge in invented "cfs-equivalent credits". Those scores were research hypotheses, not resource costs. GHoT already models **BODY, offer, willingness, energy pressure, data locality, scheduling and HOLD**, but [GHoT's own ENERGY-AWARE-SCHEDULING](ENERGY-AWARE-SCHEDULING.md) states its +60, +40, +120 etc scheduling scores are *policy constants, not joules*. We should expose measured costs before replacing either policy with new assumptions.

## New source-owned GHoT resource observation

`ghot/resource_receipt.py` is a **stdlib-only read-only local benchmark**, with a fixed-size source witness. The bundled input comes from a public USGS-source-backed MOTIF-019 research report, source repo and exact Git blob pinned by CI. It extracts a fixed validated factual answer and evaluates two ways to answer repeated identical questions:

1. `reparse`: each time read file + SHA-256-check its content + JSON-parse, validate source status, derive summary.
2. `reuse`: each time read file + SHA-256-check its content; reuse the previous *validated* summary only when the bytes' digest matches. On change, full validation must run again. Never claim cache hit on stale content.

The **output must be identical** across both methods; otherwise HOLD. Both read the exact same file per question. Benchmark trials alternate order. Measured: process CPU nanoseconds, elapsed nanoseconds, Python tracemalloc peak allocated bytes, source bytes read, SHA operations, and JSON parse count. A narrow Linux Intel RAPL package-energy counter is attempted but **optional**. If unavailable, joules are `null`; if available, the counter includes other processes and cannot reliably be attributed to this particular task. CPU and wall time are *not* energy measurements. No fake watt-hours or greenhouse gas conversions.

Native GHoT integration uses **existing source-owned** `power_field.probe_power`, `apply_power_policy`, and `energy_scheduler.decide_from_candidates` to interpret a hypothetical local, deferrable medium-cost reasoning request against current power willingness. A `critical` state withdraws that hypothetical offer and yields HOLD. This is **explicitly a dry-run candidate, not a new GHOT capability offer, body assignment, execution or lease**. No assumed energy forecast.

```sh
python3 -m unittest discover -s ghot -p 'test_resource_receipt.py' -v
python3 ghot/resource_receipt.py --out ghot-resource-witness.json --trials 5 --repeats 250
```

Running the instrument consumes CPU and memory, as all measurement does. On a critical battery, an operator should avoid extended tests even if the simulated scheduling gate reports HOLD: this benchmark is not autonomously dispatched. The user/operator remains authoritative about whether to benchmark.

## Next correct step for MOTIF and GHoT

Expose the resource witness as a **GHoT-owned research receipt** consumed by MOTIF-020 through a source-pinned read-only interface. The next evidence-affordance policy should be multi-dimensional, **not** a token-credit scalar:

- measured CPU work (process ns)
- measured wall delay (ns)
- memory high-water (bytes, measurement scope documented)
- disk/network bytes (bytes; separate classes)
- actual energy in joules *only if trustworthy attributable hardware metering exists*
- physical battery/thermal/renewable pressure, source-labeled and possibly unavailable
- user-supplied urgency, deferrability, execution consent, and the consequence of waiting

A source that lacks energy sensing must say `unknown`, not zero joules. **Never use money or API credits as universal units of useful computation.** Process runtime does not imply energy, and the current GHoT willingness state is a policy rather than a physical wattmeter.

Real future crossbody comparisons require comparable workloads, repeatable bodies, heat/clock/load controls, actual data transfer times, and authenticated evidence receipts. One GitHub runner's cache microbenchmark cannot demonstrate lower energy across multiple bodies.

## Laws

```
EVIDENCE != EXECUTION
MEASUREMENT != CLAIM OF UNIVERSAL OPTIMALITY
PROCESS CPU TIME != ELECTRICAL ENERGY
UNKNOWN JOULES != ZERO JOULES
CACHE HIT != SOURCE UNCHANGED (VERIFY THE BYTES)
LOCAL WALL TIME != NETWORK RESPONSE TIME
BODY WISH != AVAILABLE CAPABILITY
POWER PRESSURE != PERMISSION TO ACT
MEASURED RESOURCE USE != THE VALUE OF A HUMAN OUTCOME
```

Source GHoT power/scheduler modules: `ghot/power_field.py`, `ghot/energy_scheduler.py`.
Source MOTIF-019 physical report: https://github.com/the-static-collective/MOTIF/blob/1bb4028141eb20a8798bed338dcb3d851284de22/experiments/019/evidence/final-value-function-diagnostic-2026-11-05.json
