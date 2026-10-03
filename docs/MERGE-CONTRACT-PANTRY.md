# Merge-Contract Pantry

Experiment 020 makes local merge grammars discoverable without turning
discovery into recommendation, selection, proposal, or apply authority.

The full sequence is:

```text
ADMITTED PARCEL
  -> INSPECT installed contracts
  -> explain compatibility
  -> SELECT one contract
  -> persist selection
  -> revalidate selection + contract
  -> create 019 merge plan
  -> persist selection-to-plan link
  -> owner APPLY / REJECT
  -> signed merge receipt
```

## Pantry

List installed grammars:

```bash
python3 ghot/merge_contract_pantry.py list
```

020 introduces two installed contracts:

```text
ghot.organ.offers->foreign-offer-catalog/v0
ghot.organ.presence->foreign-presence-catalog/v0
```

Each descriptor declares:

- source state kind/version;
- required parcel selector;
- required payload type;
- local target path/kind/version;
- category and human-readable description;
- authority effect;
- freshness effect;
- whether explicit selection is required.

Descriptor content is itself content-addressed.

## Inspection

Inspect one locally ADMITTED parcel:

```bash
python3 ghot/merge_contract_pantry.py inspect <parcel-id>
```

Inspection compares every installed grammar against:

```text
source state kind
source state version
selector
payload type
local target readiness
already-merged state
```

Non-matches carry reason codes such as:

```text
state-kind-mismatch
state-version-mismatch
selector-mismatch
payload-type-mismatch
already-merged
local-target-blocked:<error>
```

Compatibility is descriptive only.

```text
COMPATIBLE != RECOMMENDED
```

## Explicit selection

Select one compatible grammar:

```bash
python3 ghot/merge_contract_pantry.py select \
  <parcel-id> \
  <contract-id>
```

This persists:

```text
ghot.merge-contract.selection/v0
```

binding:

```text
parcel id/address
payload address
admitted materialization address
contract id/address
selection time/source
```

Selection creates neither a merge plan nor target state.

```text
SELECTION != PROPOSAL
```

## Proposal

Create a 019 merge proposal from the persisted selection:

```bash
python3 ghot/merge_contract_pantry.py propose <selection-id>
```

Before producing the plan, 020 revalidates:

- selected contract is still installed;
- contract descriptor address is unchanged;
- parcel address is unchanged;
- payload address is unchanged;
- admitted materialization address is unchanged;
- contract remains compatible.

A valid proposal produces:

```text
ghot.merge-contract.proposal/v0
├── selection
├── 019 merge plan
└── content-addressed selection-to-plan link
```

The link is stored under:

```text
GHOT_HOME/state-merges/proposal-links/
```

This preserves traceability without changing the 019 merge-plan hash format.

## Two pantry shelves

### Reported offers

```text
ghot.organ.state/v1
selector /body/offers
payload array
  ->
ghot.foreign-offer-catalog/v0
```

This remains observational capability memory:

```text
REMEMBERED CAPABILITY != CURRENT CAPABILITY
```

### Foreign presence

```text
ghot.organ.state/v1
selector /presence
payload object
  ->
ghot.foreign-presence-catalog/v0
```

The catalog records foreign boot/provenance snapshots:

```text
source particular
source node id
boot id
manifest address
startup receipt id
parcel id
payload address
```

It is historical presence memory only.

```text
FOREIGN PRESENCE CATALOG != LIVENESS
```

It does not change peer liveness, authority, trust, or scheduling eligibility.

## No generic fallback

If no exact contract matches:

```text
compatible_contract_ids = []
```

020 does not invent a transformation.

```text
NO CONTRACT != GUESS A MERGE
```

## Shared compatibility primitive

Pantry inspection and the lower-level 019 merge engine use the same payload
shape rules. A parcel that pantry rejects for payload shape is also ineligible
to the merge engine.

## Drift handling

Selections are intentionally stale-able.

If the admitted materialization changes after SELECT:

```text
PROPOSE -> REFUSE
```

If the installed contract descriptor changes after SELECT:

```text
PROPOSE -> REFUSE
```

The user can inspect and select again against the new facts.

## Operator flow

```bash
python3 ghot/merge_contract_pantry.py list
python3 ghot/merge_contract_pantry.py inspect <parcel-id>
python3 ghot/merge_contract_pantry.py select <parcel-id> <contract-id>
python3 ghot/merge_contract_pantry.py selections
python3 ghot/merge_contract_pantry.py propose <selection-id>

python3 ghot/state_merge.py plans
python3 ghot/state_merge.py apply <plan-id>
python3 ghot/state_merge.py reject <plan-id>
```

## Laws

- DISCOVERY != SELECTION
- COMPATIBLE != RECOMMENDED
- SELECTION != PROPOSAL
- PROPOSAL != APPLY
- CONTRACT DESCRIPTOR != AUTHORITY
- FOREIGN PRESENCE CATALOG != LIVENESS
- FOREIGN OFFER CATALOG != LIVE OFFER SET
- NO CONTRACT != GUESS A MERGE
- PROPOSAL LINK != APPLY AUTHORITY
