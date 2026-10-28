# Fuel Commons 006 — multiple resource banks, separate material and energy distribution

**Research prototype only — 2026-10-28.** GHoT now includes a small deterministic, read-only register of ten routes for nine categories: edible food, inedible scraps, manure, used cooking oil, dry wood, crop residue, plastics, used petroleum oils, and solar surplus.

The actual, browser-based public exploration desk lives in webZ at `https://apps.abundent.org/jubilee/wood/fuels/` (separate repository). No synchronization, remote fetch, API key, enrollment, storage, processor, physical pickup, permit, or known fuel inventory exists.

```text
RESOURCE BANK (owned feedstock)
 -> priority gate (edible food feeds people; reuse comes before fuel)
 -> authorized independent PROCESSOR
 -> graded/specification-verified OUTPUT BANK (food, compost, certified fuel, biogas, recycled material)
 -> independently approved RECEIVER / appliance
 -> measured electricity, thermal energy, or nutrient recovery
 -> optional GHoT load accounting and simulation
```

**Resource ≠ fuel ≠ energy.** Unrefined fryer oil cannot be poured into a burner as if it were biodiesel. Biogas from food and manure exists only after managed anaerobic digestion and appropriate conditioning. Plastic bags are handled as recyclable material, **not home fuel**; neither home burning nor DIY pyrolysis is part of a permitted pathway. Motor oil is regulated waste and should not mix with restaurant oil. Edible food should be donated rather than diverted to fuel production. Dry firewood needs legal ownership, moisture/quality and movement checks. Solar surplus is measured energy, not a fuel.

Independent processing can have emissions, corrosive or toxic components, and storage hazards; consult qualified operators and Minnesota MPCA / fire and utility authorities before any physical work. GHoT is prohibited from running a process, heater, digester, pressure device, fuel supply, or combustion safety control. reLATTE may in the future transport independently authorized, signed offers and receipts, but no such integration is implemented here. Even a plan with all claimed approvals remains HOLD until verified outside the proposal model.

Run `python3 ghot/fuel_commons_006.py` and `python3 -m unittest discover -s ghot -p 'test_fuel_commons_006.py'`.

Sources:
- EPA food priority https://www.epa.gov/sustainable-management-food/wasted-food-scale
- EPA AD and biogas https://www.epa.gov/anaerobic-digestion/basic-information-about-anaerobic-digestion
- DOE biodiesel processing https://afdc.energy.gov/fuels/biodiesel-production
- EPA advanced industrial plastics processing https://www.epa.gov/plastics/advanced-recycling-plastics
- Minnesota plastics burning restrictions https://www.revisor.mn.gov/statutes/cite/88.171
- MPCA AD requirements https://www.pca.state.mn.us/sites/default/files/wq-f8-54.pdf

**First useful crossing:** ask a real community grocery or restaurant how it *already* recovers edible food and sends inedible organics and fryer grease to qualified independent processors. Measure actual collection or avoided disposal costs only with permission; propose a receiver agreement only after discovering unmet needs. No resident or family information is needed.
