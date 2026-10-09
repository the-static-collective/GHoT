# PRINTER-ORGAN-001 — GHoT × reLATTE printer field

Opt-in read-only 3D-printer organ for existing GHoT external-adapter support. Not a slicer, a reLATTE authority kernel, or printer actuator.

## Source-owned boundaries

- Static OS PRINT-011: [real OCCT STEP/STL and virtual-profile PrusaSlicer G-code](https://github.com/the-static-collective/static-os/pull/61).
- Static OS PRINT-FIELD-012: [ten printer families, owner-declared envelopes and HOLD](https://github.com/the-static-collective/static-os/pull/64).
- Static OS FABRICATION-013: [source-cold-verified three-machine proposal](https://github.com/the-static-collective/static-os/pull/66).
- reLATTE FABRICATION-CROSSING-013: [independent signed printer-owner worlds and stale grant denial](https://github.com/the-static-collective/reLATTE/pull/87).
- GHoT: external adapter manifests are already supported by the executor pantry. This experiment installs no global, unsolicited LAN scanning.
- PENNY-017/018: independently owned physical printer and inspection witnesses, not invented here.

## Two native GHoT capabilities

1. **printer.status.read**: owner-explicit declaration of device identity, technology, bounded volume/materials, and optionally two **GET-only** observations from an already-running OctoPrint service on literal local-loopback host. Sanitized machine and job states; no file names, keys, URLs, heater changes or job starts in results. The statuses are software claims, not physical certification.
2. **printer.fabrication.propose**: accept the exact structural Static OS FABRICATION-013 proposal shape with three distinct machines, matching local explicit machine ID, self-consistent request ID and zero proposed hardware authority. Always produce an R3_HOLD *projection* with explicit reasons. Self-consistent JSON is NOT native Static OS source verification, a valid signer, or real reLATTE admission.

## Try offline

Run: python3 ghot/printer_organ_sim.py

Then set GHOT_PRINTER_OWNER_FILE to an operator-owned private JSON declaration and GHOT_ADAPTER_MANIFESTS to adapters/printer-organ-001/adapter-manifest.json; run python3 ghot/reference_node.py pantry. GHoT will discover two bounded capabilities, available through existing external_adapters.execute_external_adapter.

The committed fixture at fixtures/printer-organ-001/owner.json intentionally describes a synthetic nonconnected FFF owner. Do not treat that fixture as hardware evidence. The interpreter receives a bounded JSON request on stdin; action status with request=null or action propose with exact 013-shaped request. Owner configuration comes from environment, not untrusted task payload.

## Explicit source and authority sequence

CAD design / STL / G-code are verified by Static OS and its original signed native reLATTE CAD evidence. Static OS FABRICATION-013 selects three candidate owners. GHoT exposes one local declared printer's read-only status and proposal eligibility. reLATTE independently authenticates fresh signed owner history and local admission. Only a different, later, model-specific printer-owner instrument could contemplate any actual start or material act.

Discovery does not confer authority. Matching a machine name is not identity authentication. Source hash checks here are self-consistency only. R3_HOLD in this adapter is a descriptive proposal status, **not** a native signed reLATTE receipt. Real material inventory, transport, user rights, shop safety, admission and action remain unverified.

## Physical gate

No POST, PUT, DELETE, upload, G-code sending, heater/nozzle movement, queue scheduling or printer start exists in this module. Optional OctoPrint GET is limited to 127.0.0.1 or [::1], explicit port, no DNS, redirect, proxies, or credential URL. API key is read only from GHOT_PRINTER_OCTOPRINT_API_KEY and never exported. FFF toolpaths are not compatible with resin/laser/sinter/metal print mechanisms without process-specific adapters.

Future PRINTER-ORGAN-002 must independently verify native source, current printer identity, manufacturer-specific firmware/profile, power/material/workspace conditions, owner-local grant, separate operator supervision, physical safety and durable idempotency. A signed crossing alone cannot safely drive an actuator.

## Tests

GHoT smoke executes ghot/printer_organ_sim.py: actual subprocess capability discovery; local GET-only server observations; sensitive data redaction; forged 013 fields; stale/self-invented authority denial; mismatched technology and unknown hosts; all effects remain zero.

**Laws:** SLICED != PRINTED; HASH != SIGNATURE; PRINTER STATUS != PHYSICAL SAFETY; ROUTE != OWNER ACTION; R3_HOLD PROJECTION != NATIVE RECEIPT; WORK != PHYSICAL MATERIAL STOCK.
