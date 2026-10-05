# SPARSE ICE FIELD 001

## Question

Can one Field Commons Ice Field WANT become exact sparse work authority across
multiple sovereign workers, survive partial completion and reassignment, and
reconstruct one canonical verified Ice Cube without collapsing service
authority, region authority, compute capacity, or verification?

## Composition

```text
FIELD COMMONS service promise
        |
        | service authorization
        v
Ice Field WANT
        |
        v
exact pixel-region plan
        |
        v
GENESIS exact-missing set
(all root regions missing)
        |
        v
owner-local sparse region leases
        |
        +------------------+
        |                  |
        v                  v
Worker R              Worker S
local compute          local compute
capacity               capacity
        |                  |
        v                  |
22 exact regions           |
        |                  |
returns 14 exact IDs ------+
                           |
                           v
                    14 exact regions
                           |
                           v
                    complete coverage
                           |
                           v
              sparse execution evidence
                           |
                           v
                  Dogram adaptive probes
                           |
                           v
             canonical PGM reconstruction
                           |
                           v
                ordinary Ice Cube receipt
                           |
                           v
                 reLATTE return -> HOLD
                           |
             economic settlement may occur
                           |
                           v
              requester-local verification
                           |
                           v
                   owner-local ADMIT
                           |
                           v
                     pantry merge
                           |
                           v
                    Ice Field grows
```

## Three authorities

The specimen intentionally separates:

```text
1. Commons service authorization
   "this Guild may attempt this one promised service"

2. sparse region authority
   "this worker may work THESE exact root regions"

3. local compute capacity authority
   "this worker may spend THIS local compute measure"
```

None implies either of the others.

```text
SERVICE AUTHORITY != REGION AUTHORITY
REGION AUTHORITY != COMPUTE CAPACITY
COMPUTE CAPACITY != REGION AUTHORITY
```

## Genesis missing set

067 derives missing work after continuation/fork/salvage history.

Sparse Ice Field also needs a legitimate first state for a brand-new child.

For that case:

```text
accepted root regions = 0
missing root regions  = every exact pixel region
```

The resulting object preserves the exact 067 intrinsic missing-set contract and
grants no assignment or execution authority by itself.

## Partial execution

The proof uses a 6x6 child: 36 exact pixel regions.

R initially receives authority over all 36, but independently has local compute
capacity for only 22.

R computes exactly 22 and returns the exact remaining 14 IDs.

While R's lease is live, overlapping assignment is refused.

After closure, one of R's consumed regions is still refused for reassignment,
while the 14 returned regions may be leased to S.

S supplies its own local compute authority and computes exactly those 14.

The combined sparse witness requires:

```text
R regions ∩ S regions = empty
R regions ∪ S regions = exact root region set
total local compute consumed = 36 region-units
```

## Dogram adaptive verification

Dogram branch:

```text
impl/sparse-ice-probe-001
```

first verifies complete structural region identity and coverage.

It then deterministically probes four pixel values.

For a clean specimen:

```text
4 probes
-> bounded OK receipt
```

If a root probe disagrees:

```text
mismatch
-> expand to all 36 regions
-> REFUSED
```

A declared clean/dirty prior may alter the receipt's expected-cost calculation.
It may not change probe indices, evidence, branching, or status.

```text
PRIOR != EVIDENCE
COST ORDER != EVIDENCE ORDER
BOUNDED PROBES != UNIVERSAL PROOF
```

The reconstructed artifact also passes the ordinary Ice Cube Dogram receipt.

## Economic boundary

The artifact-access / compute-service exchange may settle after:

- exact sparse coverage;
- worker-side Dogram receipts;
- a signed return reaching requester HOLD.

It still does not ADMIT the cube.

Requester-local Dogram verification and owner-local ADMIT remain later,
separate actions.

## CI oracle

The production sparse artifact is constructed only from region claims.

The CI simulation additionally calls the ordinary full renderer once as a test
oracle and requires byte-for-byte equality with the sparse reconstruction.

The oracle is not the artifact production path.

## Proof

```bash
python3 ghot/sparse_ice_field_sim.py --dogram-repo _dogram_ice
```

The proof requires:

- exact Ice Field work identity survives decomposition;
- invalid Commons authorization refuses before sparse work;
- one-shot service authorization replay is refused;
- live sparse overlap is refused;
- R computes 22 and returns the exact 14 unfinished IDs;
- consumed R regions cannot be reassigned;
- returned IDs can be reassigned exactly to S;
- each worker proves independent local compute capacity;
- combined region authority has no duplication;
- sparse reconstruction equals the canonical render bytes;
- Dogram clean path uses only four adaptive probes;
- changing the prior changes expected-cost interpretation but not evidence;
- corrupting a root-probed claim triggers all-region expansion and refusal;
- the ordinary Ice Cube Dogram receipt also returns OK;
- result return reaches HOLD;
- bilateral economics may settle while the cube remains HOLD;
- requester independently verifies, ADMITs, and merges;
- the Ice Field WANT becomes satisfied.

## Laws

```text
SERVICE AUTHORITY != REGION AUTHORITY
REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY
QUANTITY != REGION AUTHORITY
PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS
REASSIGNMENT MAY NOT DUPLICATE LIVE REGION AUTHORITY
PRIOR != EVIDENCE
SETTLEMENT != ADMISSION
SPARSE RECONSTRUCTION != FULL RERENDER
```
