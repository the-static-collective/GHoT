# Experiment 019 — Pressure Work without pressure vessels

Hypothesis: one hot burn can produce **multiple kinds of useful work**, if an independent heat engine converts part of the hot heat into mechanical shaft work while its rejected heat is recovered into the thermal-mass building envelope.

This is an OFFLINE energy-ledger experiment, not a pressure system design. It contains no vessel pressure, gas volume, material, valve setting, steam generation, plumbing, heater modification or actuator command.

- `python3 ghot/thermal_cascade_sim.py`
- `python3 -m unittest discover -s ghot -p 'test_thermal_cascade_sim.py'`

Proof: every joule of electric or buffered mechanical work is debited from the single fuel-energy budget; the total plus modeled losses reconciles exactly. Taking work reduces thermal output in the conservative example. The engine's rejected heat is partially recovered, never counted twice. All data are hypothetical rather than observed.

Potential research real-world counterpart: appropriately supervised, **noncombustion** laboratory test of a commercially rated thermodynamic engine with a safe low-temperature test heat source; observe mechanical/electric/thermal budgets and compare them to the ledger. A domestic heater connection, steam/pneumatic reservoir, and automated combustion controls are explicitly OUT of scope.

Owner/steward: none enrolled. Permits, operating appliances, participants, measured heat/work, and partnerships: none established.
