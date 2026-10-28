# Experiment 018 — Thermal Domino House (offline, no fire)

**Requested concept:** short, hot wood combustion -> thermal storage -> small heat-to-electric conversion -> optional GHoT compute scheduling -> consented evidence, in a Rube Goldberg-themed home.

**What we actually built:** `ghot/thermal_domino_sim.py`, zero dependencies, deterministic arithmetic, no imports from physical hardware adapters, no network, no GPIO, no actuator capabilities, no real sensors. It emits hypothetical assumptions instead of pretending that a real household or stove was measured.

**Pass criteria:**
- a modeled thermal bank has finite energy, with shorter duration under higher home heat loss;
- a TEG cannot claim more electric energy than the available model heat energy;
- battery storage and reserve are capped and priority loads consume budget;
- optional large tasks HOLD when there's inadequate surplus;
- source metadata explicitly refuses to classify wood heat as measured renewable/solar surplus;
- no code can change a heater, flue, pressure relief, or safety equipment;
- fire/smoke/CO protections remain independent of GHoT.

Run: `python3 ghot/thermal_domino_sim.py` and `python3 -m unittest discover -s ghot -p 'test_thermal_domino_sim.py'`.

**Next separate authorization gates:** building official and certified masonry heater designer; qualified electrician/TEG designer; university lab steward for a no-fire education bench; independent EAP steward for housing assistance; landowner and occupant consent; documented fire-code and chimney compliance. A proposal does not pass those gates.

Further physical development should measure **actual** household heat loss, verified masonry temperature profile, chimney draft and emission performance, fuel consumed, TEG DC net of parasitics, battery-controller current, and electrical loads. Refuse any actuator controls near a live fire until an appropriately certified safety engineer and code reviewer independently design/approve them.
