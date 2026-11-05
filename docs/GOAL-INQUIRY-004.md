# GHoT-004: The physical cost of knowing when to stop asking

A user supplies a **precise information contract**, not a token balance or invented willingness price. Two fixed research questions are predeclared:

1. `any_fresh`: obtain ONE public agency-reported discharge observation timestamped within 12 hours, from any of three named gauges.
2. `two_named_fresh`: obtain reports specifically from BOTH Blue Earth and Le Sueur stations; one observation is insufficient.

A read-only deterministic **goal-aware** query route stops once the contract is satisfied (or logically impossible given one allowed attempt per necessary source). An **exhaustive** route performs all three allowed USGS requests even after success. Both routes *actually execute network requests* in separate sequential trials, unlike GHoT-002's counterfactual replay. The four trial order is A/B then B/A, fixed before first run. There are at most 10 public GETs, no scheduled monitoring.

Uses source-owned GHoT-002 HTTP bounds: fixed USGS HTTPS host, 3 station IDs and unit 00060, full UTC time-window bounds and regression guard against date-only truncation, no redirects, 9-second timeout, bounded content and pagination, validation of observed source dates and flow range. Query URLs are included in the receipt to make the original malformed time-window bug auditable.

Each action records: request URL SHA256 and exact public URL, station, success/failure, stop/continue/HOLD reasoning step, actual HTTP response-body bytes, wall nanoseconds, local CPU nanoseconds, recent public observation timestamps if any. Units are separate and real Joules/actual network wire bytes are **null**. GHoT's native power willingness can refuse the entire experiment when critical.

No fabricated money/AI credits. The task value is **binary evidence-contract completion**, not general human usefulness. It is deliberately not a hydrology model and not a flood alert. A goal-aware route that asks only one gauge must not claim success for a two-named-gauge contract. It will fail closed on unknown or unsafe user tasks.

An exhaustive and a goal-aware run at different moments cannot causally identify network or energy savings due to changed source and hardware conditions. The number of actual requests, HTTP body bytes and elapsed time are measured in both arms; this is a narrow feasibility experiment, not a randomized general performance study. A controlled future experiment needs repeated counterbalanced tasks, real meter hardware, operator-defined usefulness, and a source reporting/verification contract.

Run from GHoT repo root:

    python3 -m unittest discover -s ghot -p test_goal_inquiry.py -v
    python3 ghot/goal_inquiry.py --out ghot-goal-inquiry.json

The CI runner executes offline tests before the live bounded public request and archives the receipt for 30 days. The code is exploratory; no merge/deploy, remote task dispatch, rate-limit bypass or actuation.
