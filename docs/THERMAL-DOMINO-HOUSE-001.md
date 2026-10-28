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


## 002 / The pressure-work insight: more useful functions from the same burn

**New insight:** a high-temperature fire can drive a heat engine, whose working fluid changes pressure and volume, producing **shaft work**. That work may be used immediately or stored in a separate appropriately engineered mechanical/electrical buffer. The engine's rejected heat can subsequently warm masonry or a room. This is **combined heat and power**, not pressure energy created in addition to the heat already supplied.

```
single measured fuel input
        |
  high-grade heat
        +---> professionally engineered heat engine
        |             |
        |             +---> expanding working fluid / shaft work
        |             |                       |
        |             |                +------+------+
        |             |                |             |
        |             |          generator        approved, sealed
        |             |                |          work buffer (concept)
        |             |          charged battery     |
        |             |                |          recovered work
        |             |           GHoT observes       |
        |             |           and schedules       |
        |             |
        |             +---> rejected heat ----+
        |                                      |
        +------------> bypass heat ------------> masonry bank / occupied room
        |
        +------------> unrecoverable losses
```

**Thermodynamic accounting:** pressure is a state variable, not an independent fuel. Useful mechanical energy from expansion is work drawn from the heat supplied to the engine, subject to the temperature difference and real efficiencies. A pressure/work accumulator would store some of the already extracted mechanical energy, and round-trip losses reduce the recoverable fraction. Higher pressure by itself does not guarantee more net work; temperature, working fluid, full thermodynamic cycle, heat rejection, and safety all matter.

Pressure-bearing equipment **is not a proposed DIY addition** to the woodstove. Steam generation, improvised heated vessels, relief-valve manipulation, flue/combustion controls, and safety-device dependence on GHoT are explicitly prohibited. Where it is suitable, a commercially engineered/certified heat-engine module with independently qualified installation could theoretically perform the conversion; the heater itself must remain approved and independent.

### Model 002: accounting for heat + electricity + buffered work

```bash
python3 ghot/thermal_cascade_sim.py
python3 -m unittest discover -s ghot -p 'test_thermal_cascade_sim.py'
```

A **hypothetical energy ledger**, not an equipment prediction, starts with 40 kWh fuel energy, of which 30 kWh is modeled as potentially useful heating energy. An illustrative 8-kWh high-temperature stage yields 0.8 kWh shaft work at a 10% **assumed** shaft conversion fraction. It splits that 0.8 kWh into:

- 0.2 kWh abstract mechanical-buffer input, 0.13 kWh delivered after a hypothetical 65% round trip.
- 0.6 kWh shaft toward an electric generator, leaving 0.432 kWh stored electricity after assumed 80% generator and 90% charge conversion.
- 7.2 kWh rejected heat from the engine; if 90% is recovered, that adds 6.48 kWh back to the home.
- 22 kWh direct bypass thermal flow, yielding 28.48 kWh total delivered thermal energy.
- 10.958 kWh total modeled energy losses, so the ledger closes: **28.48 + 0.13 + 0.432 + 10.958 = 40 kWh**.

Compared with the no-engine 30 kWh heat scenario (same 75% baseline), the heat-engine path offers **more useful forms of work but less heat**. Whether the trade is worthwhile must be established by a real measured device and site-specific goals. The abstract pressure-buffer output cannot be interpreted as a pressure vessel specification.

### Independent evidence

- US DOE combined heat and power: https://www.energy.gov/cmei/ito/combined-heat-and-power-basics
- DOE industrial waste heat and exergy: https://www1.eere.energy.gov/manufacturing/intensiveprocesses/pdfs/waste_heat_recovery.pdf
- 2026 research prototype using biomass gasifier + Stirling engine: 210 W electric and 3.74 kW heating, at an experimental 3-kg pellet burn over >2 hours; **not transferable as performance or authorization of this house concept**. https://www.sciencedirect.com/science/article/pii/S1359431126007994
- Consumer Product Safety Commission's fireplace water-heater pressure-explosion warning: https://www.cpsc.gov/Recalls/1982/cpsc-warns-of-explosion-hazard-with-fireplace-powered-water-heaters

**Scientific goal:** maximize valuable useful output under `energy_conservation`, `independently_safe_installation`, `physical_measurement`, and `free_human_consent`. We should optimize *forms of work* and preserve hot-to-cold temperature usefulness, not add up multiple readings of the same heat as though they were separate energy sources.

**New law:** `PRESSURE_WORK = CONVERTED_HEAT_WORK`, not `ADDITIONAL_FUEL`. `HEAT_ENGINE_REJECTED_HEAT MAY BE RECOVERED`. `GHOT ADVISES COMPUTE; GHoT NEVER CONTROLS HEATER SAFETY`.


## 003 / Thermal flow feedback — make the room a resource graph, not a perpetual-motion machine

### Four different meanings of "loop"

1. **Heat cascade / reuse**: fire -> high-grade heat engine -> useful mechanical/electric work -> lower-temperature rejected heat -> masonry storage -> space heat -> outdoor loss. The returned engine waste heat is not a second fuel; it uses a heat stream previously headed toward waste. DOE CHP documents concurrent electrical/mechanical and thermal use: https://www.energy.gov/cmei/ito/combined-heat-and-power-basics
2. **Thermal storage charge/discharge**: an approved appliance charges masonry during a burn, masonry discharges passively afterwards. This is a cycle through time, **not** heat circulating to create energy.
3. **Electrical reuse inside a heated building**: electricity -> GHoT optional compute -> heat dissipated by electronics -> occupied-room warmth. The computation serves a useful purpose before becoming low-grade heat. It cannot regenerate enough electricity to power itself. Recovery depends on where the equipment dissipates heat, heating load, noise and ventilation.
4. **Information feedback (actual GHoT role)**: validated battery and temperature telemetry -> advisory schedule -> optional computing task or HOLD -> updated battery/temperature telemetry. A negative-feedback controller can make resource consumption stable and bounded. This **does not control a wood heater**, or promise that sensors and software can enforce human safety.

```text
                         SINGLE VERIFIED FUEL INPUT
                                     |
                             INDEPENDENT HEATER
                                     |
                       +-------------+---------------+
                       |                             |
                     HIGH HEAT                 bypass heating
                       |                             |
                PROFESSIONAL ENGINE                  |
                 |          |                        |
             SHAFT WORK   REJECT HEAT ---------------+
                 |                                   |
         GENERATOR / BATTERY                     MASONRY MASS
                 |                                   |
           GHoT OPTIONAL TASK                    SPACE HEAT
                 |                                   |
           ELECTRONICS HEAT ---------------------+    |
                (only if indoors)                    |
                  +----------- OUTDOOR HEAT LOSS ----+
                 |
          STATE MEASUREMENT
                 |
          GHoT ADVISORY HOLD / RUN
                 |
          OPTIONAL LOAD ONLY
```

There are **two different arrows**: (a) material/energy-flow arrows and (b) sensor/decision feedback arrows. Don't equate a recirculating working fluid, pressure reservoir, or a control signal with a net energy gain. The laws of thermodynamics require an energy gradient and losses; to lift low-temperature heat back to higher temperature requires external work and an appropriately engineered heat pump. IEA explains heat pump energy comes partly from an **external environment**, not merely the battery: https://www.iea.org/reports/the-future-of-heat-pumps/how-a-heat-pump-works .

### Honest, reproducible time-series model

The 002 cascade ends with a finite packet of mass heat, one period of direct room heat, battery electricity, unspent abstract mechanical-buffer work and irrecoverable losses. The 003 model consumes that exact packet **once** and runs a 24-step observation/advisory experiment. It never invents recurring burns or an energy source from a loop.

```bash
python3 ghot/flow_feedback_sim.py
python3 -m unittest discover -s ghot -p 'test_flow_feedback_sim.py'
```

Parameters **are synthetic**: every hour a fixed fraction of the remaining masonry energy passively releases; a set percentage enters the room while the remainder escapes; the house has hypothetical hourly heat demand. GHoT *advises* an optional computing task only when (a) enough modeled battery charge exists above reserve, and (b) the room has a heat deficit after passive delivery. The small electricity spent on useful computing then dissipates as room heat (or outdoor loss); this is counted once and cannot be reharvested as a new electric supply.

Outputs include the hour-by-hour energy remaining, GHoT advice, thermal comfort shortfall/excess, and full conservation across **fuel = cumulative room heat + outside losses + remaining heat bank + battery + unspent mechanical buffer + upstream losses**. The initial burn-period direct heat is separate from later hourly demand to avoid claiming a house's thermal response is solved.

**Interpretation limits:** A real room has heat capacity, weather-dependent losses and temperature dynamics. A masonry heater discharges according to its actual thermal properties; GHoT cannot command how quickly it radiates. The model does not represent a stable control-loop implementation, heat-exchanger design, Carnot/exergy calculations, steam/pressure/vessel sizing, a listed appliance, or qualified installation. There is **no** permitted pressure system or domestic heater pilot in this code.

### Validated research direction

The useful next empirical question is *which waste heat can be recovered without creating more system losses or maintenance than it saves?* On a professionally supervised, noncombustion laboratory bench, measure energy at each boundary, both hot and cold side, battery electrical Wh, electronics dissipation, and rejected heat. Expose measured, timestamped, provenance-labeled readings to GHoT, but treat missing sensors as UNKNOWN -> HOLD.

No physical prototype, partner, approval, test heating data or installed energy feedback loop is claimed.

**New laws:** `ENERGY LOOP != ENERGY SOURCE`, `FEEDBACK SIGNAL != POWER FLOW`, `REUSE HEAT ONCE`, `QUALITY OF ENERGY DEGRADES`, `PASSIVE HEATER != GHOT ACTUATOR`, `NO MEASUREMENT -> NO POWER CLAIM`.


## 004 / Wall panels as thermal routing surfaces (2026-10-28)

Three materially different devices might be described as "thermal transfer panels":

| Panel family | Input | What it actually accomplishes | Where it belongs |
|---|---|---|---|
| **Hydronic/radiant wall panel** | Properly controlled warm water or electric heat | Distributes thermal energy across a large indoor surface with radiation and convection. **Not an additional heat source.** | Interior conditioned-side walls, properly insulated exterior wall assembly and code-compliant HVAC. |
| **Phase-change material (PCM) wallboard/panel** | Heat crossing its phase-change temperature | **Buffers heat across time**, slowing temperature swings. It must subsequently discharge and re-solidify/reset to be effective. | Fire-rated, moisture-reviewed interior thermal-storage layers rather than bare thermal bridges through insulation. |
| **Thermoelectric generator (TEG) wall tiles** | Sustained hot-to-cold temperature difference | **Converts a small fraction of traversing heat into electricity**. For normal indoor-outdoor gradients, practical output may be tiny, and penetrating wall insulation to create a gradient can *increase building heat loss*. | Research only until independent energy-balance/installation assessment proves usefulness. |

Conventional radiant hydronic walls do not themselves harvest electricity; TEG wall tiles don't store much heat; PCM panels don't create energy. They are complementary but cannot be conflated.

**Most important architectural decision:** Put safe heat-sharing surfaces *inside* the insulated building envelope. Otherwise adding a thermally conductive panel can short-circuit the insulation and dump valuable stored heat outdoors. In summer, reverse cooling design must consider condensation and dew point. Do **not** connect a wood heater directly to unapproved wall tubing or install a pressurized steam loop. Any hydronic equipment uses code-compliant, independently engineered HVAC circulation, expansion, protection, and freeze safeguards, not GHoT-controlled life safety.

### Context and evidence

- ASHRAE, wall/floor/ceiling hydronic radiant panel definition: https://handbook.ashrae.org/Handbooks/S24/IP/S24_Ch36/S24_Ch36_ip.aspx
- ASHRAE, thermal bridging increases losses and condensation risk: https://handbook.ashrae.org/Handbooks/F25/SI/f25_Ch25/f25_Ch25_si.aspx
- 2026 review of building thermoelectric envelopes, including wall TEGs and PCM hybrids, concludes more validation needed: https://www.sciencedirect.com/science/article/pii/S0378778826004706
- 2026 review on real building TEG power: smaller and fluctuating indoor-outdoor gradients limit generation: https://doi.org/10.1016/j.enbuild.2026.117697
- Minnesota Department of Commerce/LHB study of commercial PCM building panels found **inconclusive measured energy savings**, despite modeling promise: https://lhbcorp.com/insights/field-study-of-phase-change-material-use-for-passive-thermal-regulation-in-mn-buildings/
- 2024 California Energy Commission PCM retrofits found climate, behavior and installation-dependent results and mixed heating outcomes: https://www.energy.ca.gov/publications/2024/phase-change-material-enhanced-insulation-residential-exterior-wall-retrofits

### New offline demonstration: an energy-accountable wall skin

```bash
python3 ghot/wall_skin_sim.py
python3 -m unittest discover -s ghot -p 'test_wall_skin_sim.py'
```

Experiment 004 uses the finite existing `thermal_cascade_sim.py` *same* 40-kWh fuel budget. It partitions the existing thermal-mass bank into four shares: 60% conventional mass, 20% radiant wall distribution, 15% PCM wall storage, 5% research-only TEG wall branch. All of the wall panel heating energy is **subtracted from the same original thermal bank** rather than conjured as a separate source. A 24-hour illustrative passive release flows to indoors or outdoors. TEG electrical generation is debited from heat leaving the building. GHoT may report simulated optional compute `RUN_ELIGIBLE`/`HOLD` based on battery budget; it does not operate any panel or heater.

**Warning about the illustration:** The model's TEG wall share is intentionally a counterexample: using the indoor-outdoor gradient for generation could lose **far more heat** through the envelope than the electricity it produces. It is not a recommended residential retrofit. Transfer coefficients are invented assumptions and not weather, fluid, temperature, PCM latent heat or building-shell engineering. No hardware, approval, partners, actual installed wall performance or real measurements are claimed.

Future study: choose *interior* radiant-wall/PCM panelization first. Compare seasonal heat loss, heat comfort, moisture/fire safety and parasitic pump power against an ordinary well-insulated house; reject modifications that cost more power/heat than they yield.

**New laws:** `WALL_PANEL != FUEL`; `DISTRIBUTION != GENERATION`; `PCM STORAGE != NEW ENERGY`; `TEG POWER MUST PAY FOR WALL HEAT LOSS`; `ENVELOPE INSULATION FIRST`.
