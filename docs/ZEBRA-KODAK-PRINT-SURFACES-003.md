# PRINT-SURFACES-003 — Zebra and Kodak join GHoT

Stacked on [GHoT SOVEREIGN-PRINT-SHOP-002 PR #105](https://github.com/the-static-collective/GHoT/pull/105). This is a **device-family proposal and artifact-preparation layer**, NOT real-world printer connection, brand endorsement, machine owner identity or hardware actuation.

## First three surfaces

| Surface | Technology | What the new code really does | What it does NOT do |
|---|---|---|---|
| Zebra ZD421 example | Thermal label printing, ZPL II | Prepare a size-bounded, sanitized ASCII ZPL label source file **in memory**, bound to a source ref and digest | Connect to USB/TCP/serial or actually print a label |
| Kodak Mini 3 Retro P300R example | 4PASS 3-by-3-inch dye-sublimation photograph | Accept operator-supplied bounded PNG/JPEG bytes, verify header-level dimensions, require square/no autocrop, emit only hash and metadata | Decode pixels or implement unknown Bluetooth/USB/mobile protocol; no physical photo |
| Kodak Portrait 3D | FFF/FDM 3D filament printing | Hold model-specific printer candidate with published reference 200×200×235 mm envelope and 0.4 mm nominal nozzle; optionally check exact 3-node Static OS 013 request structure | Treat virtual PrusaSlicer G-code as Kodak-ready, authenticate model, start heaters or extruders |

**Official source references:**

- [Zebra ZPL II programming guide](https://docs.zebra.com/us/en/printers/software/zpl-pg/introduction.html) and [ZD421/ZD621 supported family](https://docs.zebra.com/us/en/printers/desktop/zd421-and-zd621-desktop-printers-user-guide/introduction/link-os-4-inch-desktop-thermal-printers.html). Zebra hardware and firmware vary; example ZPL cannot be asserted printable on every Zebra model or DPI.
- [Kodak's November 2018 Portrait 3D model announcement](https://www.kodak.com/en/company/press-release/3d-printer-availability/), describing FFF, 200×200×235 mm and dual extrusion. It is historical published product evidence, **not a current model support, availability, firmware, owner, or safety assertion**.
- [Kodak Mini 3 Retro P300R reference](https://kodakphotoprinter.com/products/best-photo-printer-kodak-mini-3-retro), describing 4PASS photo sublimation and 3×3-inch output. No reusable transport API established. Kodak 3D and Kodak 4PASS are **different physical technologies**.

## Native GHoT adapter

Existing [GHoT external adapters](../ghot/external_adapters.py) discover capabilities only after **the operator explicitly sets** `GHOT_ADAPTER_MANIFESTS`. The new source-owned manifest [adapters/zebra-kodak-surfaces-003/adapter-manifest.json](../adapters/zebra-kodak-surfaces-003/adapter-manifest.json) exposes three bounded stdin/stdout JSON processes:

1. `printer.surface.zebra.label.prepare` — produces ZPL text, source digest, fixed quantity implied only by one format, explicit width/height and DPI; rejects unsafe ^/~ characters and control bytes.
2. `printer.surface.kodak.photo.inspect` — only PNG/JPEG syntactic header inspection with bounded base64, human-reviewed source rights and square framing; hash only. **Not full image decode or trust in image content**.
3. `printer.surface.kodak.portrait3d.propose` — a descriptive model reference, with exact content-consistency check on an optional existing `static-os.fabrication-request/v0`, but it never cold-verifies signed original CAD on its own. Existing 002 native verification remains separate and mandatory before any actual future printer gate.

Every returned artifact has `transport_authorized=false`, no physical output, and either `HELD` or `HOLD`. The Zebra output **does contain printable ZPL instructions if somebody separately transports it to a matching printer**. It is deliberately not sent by this code; sending it must require a separate real printer-owner permission and runtime.

## Try offline

From GHoT repo root:

```sh
python3 ghot/print_surfaces_003_sim.py
export GHOT_ADAPTER_MANIFESTS="$PWD/adapters/zebra-kodak-surfaces-003/adapter-manifest.json"
python3 ghot/reference_node.py pantry
```

To exercise a label using GHoT's actual existing subprocess adapter, run from the repo root:

```python
import sys
sys.path.insert(0, "ghot")
from external_adapters import execute_external_adapter
result = execute_external_adapter("printer.surface.zebra.label.prepare", {
    "schema": "ghot.print-surface-command-003/v0",
    "action": "printer.surface.zebra.label.prepare",
    "input": {
        "text": "HAUNTED JUBILEE 003",
        "source_ref": "example:proof-label-003",
        "width_mm": 80, "height_mm": 50, "dpi": 203,
        "human_reviewed_source": True
    }
})
print(result["result"]["status"])
```

The Kodak photo adapter's command takes `image_base64`, `source_ref`, `rights_reviewed=true`, `crop_policy="NONE_REQUIRE_SQUARE"`. Never put private customer photos in committed fixtures or CI logs. Inputs are passed only to the operator-selected local GHoT process and **never embedded in the returned metadata**, but no authenticated encrypted transport or secure memory erasure is claimed.

Kodak Portrait action accepts `source_ref`, `requested_machine_id="reference:kodak-portrait-3d"`, and optional `source_request`. A signed-source **selection of a different printer is not transferable**: a source request without the exact Kodak machine ID returns `HOLD_KODAK_PORTRAIT_NOT_SELECTED_BY_SOURCE`. A self-consistent request mentioning the Kodak model remains `HOLD_KODAK_PRINTER_PROFILE_AND_OWNER_AUTH_REQUIRED` because self-consistency is not native signature verification.

## Lineage and authority

Static OS owns original CAD, slicer, exact model firmware/material/profile evidence. GHoT discovers and prepares different physical surface candidates. Native reLATTE owns independent source/owner crossing, new local grant, admission and signed receipt. A *label candidate* or *photo metadata candidate* does not become a reLATTE signed local crossing by changing its schema name. The unchanged 002 flow currently supports only its originally selected three **3D** machine IDs.

Future live printer runtime is separate: authenticate a specific Zebra printer and exact DPI/media/ribbon/ZPL dialect; or independently validate Kodak Portrait's actual firmware and material conditions; or establish a supported Kodak photo device driver and rights. Use operator-local durable job idempotency; print transport or printer ACK is not proof of a physical label, photograph or part. Kodak Portrait source G-code must be re-sliced/verified against its exact manufacturer/operator-approved profile, not the Static OS virtual 011 profile.

**Laws:** `BRAND != PROTOCOL`, `PRINTER != PRINTER FAMILY`, `ARTIFACT != HARD COPY`, `IMAGE HASH != RIGHTS`, `ZPL SOURCE != DEVICE TRANSPORT`, `VIRTUAL SLICER != KODAK PORTRAIT PROFILE`, `PROPOSE != PRINT`, `OWNER NAME != MACHINE AUTHORITY`.
