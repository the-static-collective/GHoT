# SOVEREIGN-PRINT-SHOP-002 — actual signed design, GHoT printer organ, native reLATTE owner lab

**Status:** cross-repository executable proof, *not* commissioned manufacturing or real owner admission. This stacks on [GHoT PR #102](https://github.com/the-static-collective/GHoT/pull/102), [Static OS PRINT-013 PR #66](https://github.com/the-static-collective/static-os/pull/66) and [reLATTE FABRICATION-013 PR #87](https://github.com/the-static-collective/reLATTE/pull/87). None of their source authority is replaced.

## The composition

1. Static OS owns a **real source-constrained OCCT solid, STEP/STL and a real PrusaSlicer FFF G-code file**. Its native signed reLATTE CAD crossing is verified from the **original source artifacts**, not trusted because a request hash looks correct.
2. Its original 012 fleet and explicit human 013 selection produce a verified proposal with exactly three selected printer identities (`example:machine-01`, `example:machine-02`, `virtual:fff-pla-180`). The FFF and resin example machines remain *unverified owner declarations*, while the virtual profile remains *virtual*.
3. GHoT's actual `external_adapters.execute_external_adapter` runs the existing printer-organ-001 subprocess twice: `printer.status.read` and `printer.fabrication.propose`. Fixture owner `example:machine-01` is selected, but reports **no connected printer**, no authenticated physical device, no profile and no actuation grant. GHoT's output is R3_HOLD **projection only**.
4. The separately pinned reLATTE FABRICATION-CROSSING-013 experiment runs its own **native signed Ed25519 LocalWorld owner histories** and issues three signed R3_HOLD decisions. The initially withdrawn third-world grant fails, and a genuinely new fourth local world can issue only a fresh propose-only grant for software review.
5. A separate process invokes reLATTE's native signature/history cold verifier with the lab's explicitly documented **ephemeral, self-generated simulation trust anchors**. They do not authenticate an actual printer owner. GHoT binds that verified output to exact Static OS request ID and GHoT owner's local held proposal, and writes a new **unsigned, non-authoritative composition receipt**.

**There is no remote reLATTE crossing to a printer, no printer discovery on a real network, no firmware communication, no machine start, no physical parts, and no currency/inventory issued.** A native signed *simulated owner decision* is not an independent real-world printer contract.

## Local unit tests

```sh
python3 ghot/printer_organ_sim.py
python3 ghot/sovereign_print_shop_002_sim.py
```

Those fixtures deliberately fabricate *unsignable* lab summaries to test the **GHoT binding function only**. They do not constitute Ed25519 or native CAD validation. The full cross-repo GitHub Actions job, not these fixtures, runs actual native verifiers.

## Full native CI integration

See `.github/workflows/sovereign-print-shop-002.yml`. Pinned sources:

- Static OS `7bc551610421bd60a8dbf624d93d7a6682ce3987` (PR #66)
- reLATTE native CAD donor `dcc8cdca84c440aa4294134f020fb7095bf87f24`
- reLATTE signed owner worlds `ded308b463df4eda2003000b4202d3c7aaa2dc84` (PR #87)
- GHoT current branch checkout for external printer-organ-001

The workflow installs CadQuery/OpenCASCADE, PrusaSlicer and reLATTE dependencies, rebuilds original CAD and actual FFF toolpath, creates a source-native 013 request, independently cold-verifies its original signatures/G-code, runs the real GHoT operator-provisioned adapter, executes reLATTE's *native signer*, and cold-verifies signed histories in another process. Artifact upload contains only public signed **lab** proofs, the source request and GHoT hold composition: **never private signing keys**.

The native owner lab has **self-generated ephemeral public trust pins** by design. These are separate pinned file *inputs* to its verifier, not independently established legal or physical machine identities. Its cryptographic receipts are genuine Ed25519 signatures in a simulated world.

## Manual operator invocation after an independently obtained source package

Only if you already have the original signed Static OS CAD directory, real print packet, unmodified fleet/selection, a genuine 013 request and local *exact* pinned repository checkouts:

```sh
export GHOT_ADAPTER_MANIFESTS="$PWD/adapters/printer-organ-001/adapter-manifest.json"
export GHOT_PRINTER_OWNER_FILE="$PWD/fixtures/sovereign-print-shop-002/fff-owner.json"
python3 ghot/sovereign_print_shop_002.py \
  --static-root /private/static-os \
  --relatte-root /private/relatte-013 \
  --original-source /private/static-os/dist/cad010-real-solid \
  --print-packet /private/static-os/dist/print011-held \
  --fleet /private/static-os/fixtures/printer-field-012/synthetic-fleet.json \
  --selection /private/static-os/fixtures/fabrication-013/three-node-selection.json \
  --request /private/static-os/dist/fabrication-request-013.json \
  --owner fixtures/sovereign-print-shop-002/fff-owner.json \
  --out /private/brand-new-shop-proof \
  --static-commit 7bc551610421bd60a8dbf624d93d7a6682ce3987 \
  --relatte-commit ded308b463df4eda2003000b4202d3c7aaa2dc84
```

All external commands are fixed program paths under repository checkouts with verified commit HEADs. No arbitrary command from a task or printer controls are executed. The output directory must be new, avoiding silent in-place replay. Use pinned, protected checkout directories and independently reviewed source. Current code does not authenticate installed hardware, operator identity, authorized safety profile or local physical custody.

## Hostile gate

- Tampered source request ID, unknown selected machine, changed printer technology, or forged GHoT admission is refused.
- Source-native verifier must say the exact selected request is recomputed from original signed CAD/G-code and remain zero authority.
- Signed reLATTE proof must refer to same exact selected request, three original HOLD decisions and one reborn **software-only propose** ticket, with historical revocation of the stale grant.
- Forged physical stock/print or modified decision topology fails; native verifier also detects forged signatures and source-changed histories.
- Any absent/failed native checker aborts the composition and cannot produce the final receipt.
- Real printing, material stock, Kinship publication, on-air rights, money or redeemable PENNY units remain out of scope.

## Next separate physical door

A future real-world PR should authenticate a **specific** printer owner and firmware, inspect the actual original toolpath against a verified printer/material profile, separately attest stock/safety/operator presence, issue a fresh single-use **owner-local** start grant, apply a durable machine-specific idempotency and abort protocol, and only then *optionally* perform a supervised hardware action. Status reads and producer/grant software signatures must not be used as proof of fabricated parts.

**Laws:** `SOURCE != MACHINE`, `CANDIDATE != PRINTER CONTROL`, `SIGNED SIMULATION != PHYSICAL AUTHENTICATION`, `PROPOSE GRANT != START GRANT`, `WITHDRAWN != REBORN AUTHORITY`, `HOLD IS NOT FAILURE`, `SLICED != PRINTED`.
