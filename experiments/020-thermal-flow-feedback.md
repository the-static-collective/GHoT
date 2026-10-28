# Experiment 020 — Thermal Flow Feedback (offline read-only)

**Question:** Given one finite heat input and multiple energy stores, can we design a schedule where several processes get value from the same energy **sequentially** without inventing joules?

**Implementation:** `ghot/flow_feedback_sim.py` imports `thermal_cascade_sim.py` (experiment 019). It accepts the upstream **single-burn** outputs as opening inventory, then models a hypothetical passive masonry discharge, room/outdoor heat split, small electric optional compute, recovered indoor electronics warmth, and an **advisory** GHoT RUN/HOLD decision based on modeled battery reserve and demand. No data are measured. No hardware or safety actuation exists.

**This is information feedback, not a real pressure, flue, combustion, pump, thermostat, chimney or thermal-store control loop.** No DIY closed steam loop, relief device, combustion tuning, or improvised pressure vessel is proposed.

Run:
```bash
python3 ghot/flow_feedback_sim.py
python3 -m unittest discover -s ghot -p 'test_flow_feedback_sim.py'
```

Pass conditions: all input energy appears in only one account at the end; indoor dissipated electronics heat increases delivered room warmth without increasing total energy; high electrical reserve HOLDs optional work; passive mass discharge is never controlled by GHoT; zero fuel yields zero modeled energy and nonzero unmet heat; unsafe or impossible input values fail.

**Working hypothesis for a future lab:** A commercially rated *noncombustion* demonstration at a qualified educational site can measure how much heat is reasonably recoverable. A real house or wood stove is not an experimental target without all professional, fire and electrical approvals.
