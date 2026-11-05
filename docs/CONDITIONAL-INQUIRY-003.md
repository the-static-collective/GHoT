# GHOT-003 — The experiment actually stops asking

The previous GHOT-002 run queried three public USGS sources, then used those real responses to infer how much a hypothetical stop-on-first-source policy might have needed. That is a *counterfactual replay*, not a real reduction of calls.

**003 performs the strategy, rather than merely simulating it.** It uses the audited/whitelisted network requests from 002. Starting with Blue Earth, then Le Sueur, then Mankato, ask until the first public source report with an observation timestamped at most twelve hours before response. Record the measured latency, bytes, source status, and evidence provenance for each **actually executed** request. Never execute the remaining requests when the first acceptable source has replied.

The fixed useful output is **one evidence-backed recent public measurement**, or a HOLD if none are available. It does not forecast floods or measure user-perceived value. Source identity, parameter, units, UTC timestamps, response limits, and no redirects are preserved from 002; the date-only query bug is regression-guarded there.

If GHoT's native power state is `critical`, 003 sends **zero** requests and records a HOLD. No body assignment or remote execution; it is a bounded, read-only local process, not an autonomous network research agent.

```sh
python3 -m unittest discover -s ghot -p test_conditional_inquiry.py -v
python3 ghot/conditional_inquiry.py --out ghot-003-live.json
```

**Accuracy boundaries:** unlike an all-three run, this instrument cannot know whether its skipped sources would have reported an even fresher reading, and should not pretend it does. The objective only requires *any one* recent source-backed reading. Comparing its actual requests with 002's three calls from a different time is **noncontemporaneous** and does not establish the causal benefit of conditional stopping under a matched randomized study. Body payload bytes are not wire bytes. Joules stay `null` without a trustworthy power meter.

Follow-up: run a precommitted sequence of real conditional workloads over multiple days, optionally randomized against an explicit all-three query baseline when the operator allows extra network requests. Compare source-backed task completion and actual measured request costs by evidence and power state. Do not use purchased AI credits as an abstract value function.
