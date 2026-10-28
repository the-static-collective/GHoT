# THERMAL DOMINO HOUSE 001 — Wood heat × heat bank × GHoT power field

**Status: theoretical architecture and offline energy-budget simulation. No hardware installed, wired, validated, approved, or connected.**

## What is the device?

A **rocket mass heater** (RMH) is an insulated efficient wood-burning chamber and long thermal mass, often a sculpted cob bench. A **masonry heater** is the more-established related, standards-addressable category: burn a charge of dry wood quickly, transfer energy through masonry, and release it gradually for roughly 12–24+ hours, depending on the build and heat load.

Sources:
- Masonry Heater Association: https://www.masonryheaterassociation.org/about
- Masonry construction / 2024 IRC R1002.2 and ASTM E1602: https://www.masonryheaterassociation.org/about-masonry-heaters-for-architects-and-builders
- Rocket mass heater research (Schumack 2016): https://www.sciencedirect.com/science/article/pii/S1359431115010820
- EPA wood appliance types: https://www.epa.gov/burnwise/choosing-wood-burning-appliances

The claim **one small fire heats any home for two days** is unjustified. Heating duration depends on fuel energy, usable thermal mass, insulation, size and outdoor weather. A 10 kg dry-wood charge modeled at 4 kWh/kg and 75% useful heat gives 30 kWh of heat. If ~70% reaches the mass, that's ~21 kWh stored. At 1 kW net demand, the bank alone represents ~21 hours of heat. At 2 kW, ~10.5 hours. These are deliberately simplified energy figures, NOT estimates of a specific home or equipment. Heat output is a time-varying curve, not a constant. To get two days you need a correspondingly low heat-loss building, enough properly designed storage and fuel energy, and verified performance.

## The real cascade

```text
AUTHORIZED, CODE-COMPLIANT WOOD HEATING APPLIANCE
          |
          +--> direct heat to home / thermal mass
          |          |
          |          +--> passive radiant heating, independent of GHoT
          |          +--> OBSERVE surface temperature only (optional)
          |
          +--> optional professionally engineered, certified/approved
          |    stove thermoelectric device (TEG) on an appropriate surface,
          |    preserving draft, clearances and appliance listing
          |          |
          |          +--> approved charge controller -> rated battery
          |                                      |
          |                                      +--> GHoT battery telemetry
          |                                      +--> small optional DC loads
          |                                      +--> HOLD background workloads
          |
          +--> independent, unmodified flue to chimney
          +--> independent smoke/CO alarms and fire protection
```

GHoT is **a load scheduler and sensor witness**, not the controller of combustion, dampers, pressure-relief devices or life-safety equipment. It can reason about available battery energy and defer nonessential work, but it cannot create electricity, operate a wood stove on sensor inference, or make wood combustion automatically renewable. Source category `experimental_wood_heat_teg` is distinct from `solar`; no false `GHOT_RENEWABLE_SURPLUS=1` just because wood is burning.

Important thermodynamic distinction: the thermal mass **stores** energy; a temperature difference + generator **converts some** into electricity. Valves neither generate new energy nor create safe electricity by default. A TEG normally makes small power, and requires a hot and a cold side and thermal protection. Measured research examples:
- Stove TEG (2018): 8.25 W measured, 2.31% efficiency. https://pubmed.ncbi.nlm.nih.gov/29880758/
- Accumulating fireplace TEG study: max ~30 W electric, poor economic case. https://www.sciencedirect.com/science/article/abs/pii/S019689041630471X
- Larger experimental stove TEG: >200 W with carefully engineered generator and thermal system; not a normal DIY household expectation. https://www.sciencedirect.com/science/article/pii/S0960148120304626
- A hypothetical 20 W for 2 h yields just **40 Wh gross**, enough for sensors / short small electronics, not a household electric supply.

## Rube Goldberg: safe / unsafe branches

**Safe, separate showmanship concept:** a mechanically isolated decorative indicator, heat visualization, or software sequence that uses measured changes to start a lights/display/audio event. The visual trigger is optional and cannot impair the heater; if failed it should simply fail silent. A tiny thermal strip/museum device may be possible **only as a suitable rated accessory installed with approved clearances**.

**Stop lines:** DO NOT fabricate an enclosed steam loop or pressure vessel on a firebox, pressurize an improvised heat exchanger, automate the stove's combustion air or flue draft through GHoT, rely on a pump/network relay to stop boiling, or take over smoke/CO alarms. Heated water can boil after a pump outage, frozen pipe or stuck valve and rupture violently. CPSC records exploded fireplace-powered water heaters: https://www.cpsc.gov/id/Recalls/1982/cpsc-warns-of-explosion-hazard-with-fireplace-powered-water-heaters . Any real hydronic or mechanical expansion system requires professionally engineered listed equipment, appropriate relief, freeze protection, inspection and permits.

## Wiring the idea to existing GHoT

- **GHoT Power Field 007:** observes measured charging, battery SOC, thermal pressure and host conditions; source hint must be traceable. Refer `docs/POWER-FIELD.md`.
- **GHoT Energy Scheduler 008:** existing `run_here / run_there / hold` logic schedules *optional compute* based on real, independently collected electrical data. Refer `docs/ENERGY-AWARE-SCHEDULING.md`.
- **reLATTE:** future explicit owner-controlled signed crossing and independently admitted observational receipt: `observed` != `approved` != `installed` != `measured benefit`. No actual crossing or measured performance is asserted here.
- **Winter Warmth 001:** first prove safe fuel sourcing, energy assistance, wood moisture and legal movement before any experimental appliance installation. Never install an unapproved heater in a beneficiary's house as an aid experiment.
- **Bridge / colleges:** propose a bench-mounted, low-temperature, *noncombustion* demonstration with an appropriate educational lab, qualified supervisors and no connection to an occupied house. Test watts, heat flows, battery charge and sensor failures.
- **House experiment later:** professional code-compliant appliance and safe instrumentation only after fire/building officials and qualified heating designers approve.

## First reproducible no-hardware proof

```bash
python3 ghot/thermal_domino_sim.py
python3 -m unittest discover -s ghot -p 'test_thermal_domino_sim.py'
```

Simulated input: 10 kg dry wood × 4 kWh/kg × 75% delivered-heat fraction = 30 kWh useful. Hypothetical TEG 20 W × 2 h = 40 Wh electric gross. Assumed charge path 90%. Battery start 30 Wh, capacity 100 Wh, reserve 30 Wh, essential **demo monitoring only** 3 W for 8 h. Report: approximately 20.97 kWh bank, **20.97 hours at assumed 1 kW net heat loss**, 36 Wh harvested after path loss, 12 Wh above reserve after 24 Wh assumed monitoring, background 60 Wh task HOLD. This is *not* house-safe power, not an HVAC design tool, not a certified electrical system. Independent CO/fire alarms and essential heating safety are outside this compute budget.

A hotter fire, a bigger bench or an AI scheduler **cannot multiply the fuel energy**. The key question is **how to spend and store each joule better while preserving independent human safety controls.**

**New laws:** `STORED_HEAT != FREE_ELECTRICITY`; `SENSOR != SAFETY_AUTHORITY`; `RUBE_GOLDBERG_SHOW != HEATER_CONTROL`; `PRESSURE_RELIEF != ENERGY_HARVEST`; `DEMO_OUTPUT != PERMITTED_INSTALLATION`; `MEASURED_POWER != RENEWABLE_CLAIM`.
