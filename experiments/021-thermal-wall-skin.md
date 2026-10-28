# Experiment 021 — Thermal Wall Skin 004

Purpose: classify and account separately for (a) radiant wall heat distribution, (b) phase-change thermal buffering, and (c) experimental thermoelectric harvesting of temperature gradients.

The starting energy is the **same** physical source from GHoT Thermal Cascade 002. All heat allocated to panels is debited from its masonry bank. Illustrative indoor vs outdoor losses accumulate over 24 synthetic hours; GHoT optional compute scheduling is an **advisory decision only**.

**No appliance, wall, plumbing, pump, pressure vessel, electric circuit or life-safety control can be actuated.** This is theoretical data, not a bill of materials or physical installation plan.

Run:
```bash
python3 ghot/wall_skin_sim.py
python3 -m unittest discover -s ghot -p 'test_wall_skin_sim.py'
```

Tests must prove the single input closes exactly; PCM delays a release rather than generating energy; changing TEG share to zero eliminates its generated battery Wh; wall TEG's hypothetical electricity is much smaller than the heat debited from the house; impossible energy allocations fail closed.

Education-path follow-up: trained building science and HVAC evaluators can compare rated, non-combustion radiant/PCM demonstration panels on an interior mock wall, using room heat flow sensors and temperature logging. Do not prototype with live fire or house wall modifications.
