# GHOT Network Inquiry 002 — Evidence, not credits

The prior physical resource witness proved that verified reuse reduced CPU time for one repeated local answer, but could not determine the cost of obtaining a **new answer** from outside. This experiment is deliberately *smaller than an agent*: send three known, read-only public HTTPS GET requests, record the physical latency and payload bytes, validate USGS streamflow timestamps, then evaluate a predetermined set of decision policies on those same observed responses.

## The human-useful question

> Can at least one public river station provide a **reported measurement timestamped within the past twelve hours** right now?

A source-backed response says which agency station reported what, and when. It does **not** say whether water is safe, whether a flood is likely, whether an evacuation is needed, or whether the USGS instrument is physically infallible. A missing source is "unavailable to this inquiry", not "no water".

Three fixed public station IDs: Blue Earth `USGS-05320000`, Le Sueur `USGS-05320500`, Minnesota River at Mankato `USGS-05325000`. Single endpoint: `https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items`. Data range max four days; request cap 700 features, cap 1.5MB per response, max 9-second timeout each, refuse redirects and nonallowlisted URLs. Requires source identity, parameter `00060`, discharge unit, valid non-future UTC timestamp, finite flow, no pagination and valid source JSON. Failures and absent results are **observable**; never invent a missing answer.

## Measured resources (no credit prices)

Each actually performed GET records:
- UTC start/end, elapsed monotonic wall nanoseconds, process CPU nanoseconds,
- **received HTTP response body bytes** (not necessarily bytes transferred on the wire),
- HTTP status, SHA256 of returned bytes (not independent agency authentication),
- any bounded error and whether the source contained a timestamp-recent observation.

The live program **actually performs all three** bounded GETs. It then computes what four *predeclared serial strategies would have done with those same observations*: ask nobody; ask Blue Earth only; ask Blue Earth then Le Sueur then Mankato until the first recent source; or ask all three. These are ***counterfactual sums of physically measured individual requests***, not actual executions of the alternative algorithms. In particular, it does not pretend it physically saved HTTP requests by stopping early. One new trial of an actual conditional requester is required before crediting any source-work savings.

It records a real GHoT native power snapshot, including manual-hint status. A `critical` local power state stops the live probe before network requests. Other willingness levels are for transparency; these are low-volume public research calls, not an automatic capability assignment. No arbitrary money/token/credits required. **Electrical joules and actual network wire bytes stay null until separately instrumented.**

## Verification and safeguards

```sh
python3 -m unittest discover -s ghot -p test_network_inquiry.py -v
python3 ghot/network_inquiry.py --out network-002.json
```

The GitHub Action runs offline adversarial tests, then a separate actual read-only public-source instrument and uploads the machine receipt. Source availability can fail; output still distinguishes source errors from no fresh measurements. Persistent source data are only cryptographic hashes and the newest public result summary; raw whole source bodies are not archived by this version. That provenance limitation is explicit.

The next logical experiment should run a **genuine conditional requester**, not a simulated strategy, and compare task-completion reliability, response freshness, CPU/time/bytes, and eventual metered watt-hours across separately scheduled tasks or devices with the same requirements. On an unavailable meter, Joules means `null`, never zero.

The objective is an *evidence-backed useful answer*, not raw inference throughput or a purchased credit token. Measurement is not a proof of real-world benefit beyond the narrowly declared question.

## First empirical failure: our own query manufactured stale evidence

The first read-only GHOT-002 USGS request run [42049678911](https://github.com/the-static-collective/GHoT/actions/runs/42049678911) returned valid HTTP 200 and **824,285 received JSON body bytes** across three sources, with total sequential request elapsed **1.567 seconds**. Yet each source's apparently latest observation was `2026-11-05T00:00Z`, roughly fifteen hours before the run. The pipeline reported no <12-hour witness.

**Root cause discovered from the code, not an agency outage:** the original URL query used `YYYY-MM-DD/YYYY-MM-DD` dates, chopping the end of the requested interval down to **midnight**. The program had not actually asked for the more recent records it wanted. There was no justified inference that USGS sensors were lagging. We preserved the exact first machine receipt under `evidence/002-initial-window-truncation-2026-11-05.json`, marked as a reproducible reasoning/protocol counterexample, **not** a valid test of realtime freshness.

Repair: use full UTC timestamp intervals `YYYY-MM-DDTHH:MM:SSZ/YYYY-MM-DDTHH:MM:SSZ`; reject *any* date-only request in the URL preflight; add a negative test demonstrating that midnight truncation is refused. Repeat live observation as a new run; do not quietly erase or reinterpret the first result.

**Generalizable research lesson:** Asking the right question includes *encoding that question correctly in the protocol*. The instrument's own time-window representation can create an epistemic failure indistinguishable from bad physical sensors unless the evidence boundary is audited.
