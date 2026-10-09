# THE WORLD THAT ASKS BACK — 001

Status: **fixture-only executable experiment**, not a physical-work controller or a deployed distributed system.

## Question

Can three separately signed local views be composed into a proposal for useful work that **nobody submitted as a task**, while preserving every owner's distinct decision?

In the toy world:
- **household** declares a hinge missing from a simulated greenhouse.
- **fabricator** declares an idle virtual printer, a matching design and energy.
- **stockist** declares spare PLA stock and an agreed local route.

No individual node declares a repair task. A discovery engine *infers* that a replacement hinge could be made. Three nodes have different P-256 identities and distinct scopes of permission.

## Eleven instruments and eleven responses

The instruments are **read-only projections of owner-signed fixture data**, not eleven real sensors:

| Instrument | Owner | Reads |
|---|---|---|
| condition | household | asset condition |
| fit | household | replacement geometry code |
| priority | household | urgency |
| privacy | household | disclosure policy |
| acceptance | household | fixture acceptance method |
| printer | fabricator | idle capability |
| energy | fabricator | available virtual energy |
| designs | fabricator | catalogued part design |
| material | stockist | virtual stock quantity |
| source | stockist | material provenance label |
| route | stockist | transfer method |

The composer evaluates **print / reuse / borrow / buy / weld / cut / glue / mill / cast / wait / report**. In the supplied fixture, only print has complete declared support; all other options remain unadmitted rather than having missing capabilities invented.

It issues a **PROPOSED / semantic_effect=none** record, bound to the hash of the complete observation cut. It cannot actuate hardware.

## Crossing and sovereign consent

Three owners must **separately** sign an exact (proposal_id, cut, epoch, scope) simulation grant:

1. household: simulate-repair-my-hinge
2. fabricator: simulate-printer-and-design-use
3. stockist: simulate-material-consumption

Partial grants cause **HOLD**, with a fabricator-signed HELD receipt. The household signs a genuine P-256 relatte.crossing-envelope/v0 carrying the proposal digest, and the fabricator signs a RECEIVED receipt with no effect. With all exact simulation grants, only the **virtual** part is produced, with a fabricator-signed EXECUTED / artifact-created receipt whose post-state address matches the virtual artifact.

The native signing equations come from ghot/relatte_identity.py. This is **not an invocation of a live reLATTE source verifier or LocalReceiver**; schema-shaped locally signed artifacts cannot establish external admission. A pinned public key is a fixture trust assumption, not human identity or physical property ownership. The packet carries a **self-declared** public roster for reproducible self-consistency checks. For signer trust beyond that packet, the verifier must receive a separate **out-of-band, independently established** pinset with --pins. Merely copying the roster out of the untrusted packet does not establish identity.

## Reproduce

Requires Python 3.10+ and the OpenSSL CLI, no PyPI dependencies, no network:

~~~sh
python3 -m unittest discover -s tests -p test_world_asks_back.py -v
python3 -m ghot.world_asks_back demo > /tmp/world-asks-back-packet.json
python3 -m ghot.world_asks_back verify /tmp/world-asks-back-packet.json
# With a separately trusted roster (same JSON shape as packet.pinned):
python3 -m ghot.world_asks_back verify /tmp/world-asks-back-packet.json --pins /secure/trusted-public-roster.json
python3 -m ghot.world_asks_back demo --hold > /tmp/world-asks-back-held.json
python3 -m ghot.world_asks_back verify /tmp/world-asks-back-held.json
~~~

Demo keys live in a disposable temporary directory and are gone before the packet is inspected. The verifier rebuilds the eleven readings, options, proposal and virtual consequence, then checks signed grants and both signed reLATTE-profile receipts. Without --pins, it reports **packet-pinned-only**: a valid signature is attributable only to an identity asserted inside that packet. With --pins it reports **externally-pinned** and denies otherwise valid packages from a rogue replacement three-key roster. The caller must independently establish which public keys belong to the owners.

Use --hold to inspect the absence of admission. With 30 virtual grams of PLA, the green simulation creates an artifact recording 12 virtually consumed grams and 18 virtual grams remaining, a geometry fixture PASS and zero economic credit.

## Negative controls

The dedicated test suite checks false measurements, changed epochs and cuts, wrong roles, rogue replacement roster against external pins, tampered grants, expanded scope, fabricated physical completion, forgery of post-state, an unauthorized success flag, partial consent, inadequate inventory, withdrawn privacy and public-only subprocess verification after the signing keys are deleted.

## Laws retained

- DISCOVERY ≠ TASK
- OBSERVATION ≠ WORLD TRUTH
- SIGNATURE ≠ SOURCE TRUTH
- POSSIBILITY ≠ PERMISSION
- PROPOSAL ≠ ADMISSION
- CROSSING ≠ OWNER CONSENT
- RECEIVED ≠ EXECUTED
- SIMULATED ARTIFACT ≠ PHYSICAL OBJECT
- RECEIPT ≠ VERIFIED HUMAN BENEFIT
- COMPUTED POTENTIAL ≠ ECONOMIC CREDIT
- ANY OWNER MAY WITHDRAW BEFORE A NEW CUT

## Hard frontier

This exercise makes **no physical hinge, no actual printer movement, no real inventory update, no real energy expenditure, no meaningful safety assessment, and no donation/treasury/money credit**. The fixed fixture clock is not evidence of real time. EXECUTED labels a **synthetic-local** consequence only. Three test keys aren't three independent human participants, and no distributed network or native GHoT scheduler is exercised.

Next admission requires a separately designed adapter for live GHoT capability offers and a real local receiver; replay protection, authenticated human grants, physical inspection, owner-backed material custody, equipment safety interlocks, and an independent service-acceptance receipt must be addressed **before** hardware, external consequences, or accounting are introduced.
