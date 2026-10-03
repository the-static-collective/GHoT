# Experiment 018 — Portable State Parcels

## Question

Can one body export a bounded piece of durable state, cryptographically bind
that exact fragment, cross it to another body, receive only HOLD over the
network, and preserve owner-local ADMIT / REJECT / SCAR decisions without
mutating canonical live state?

## Deterministic proof

```bash
python3 ghot/state_parcel_sim.py
```

The simulation creates separate source and receiver BODY roots.

It proves:

1. a v1 organ-state fragment exports as a bounded state parcel;
2. source state kind/version and current known version are retained;
3. target BODY particular is cryptographically bound;
4. parcel export receipt verifies;
5. reLATTE crossing verifies;
6. payload mutation invalidates the bundle;
7. an actual localhost HTTP crossing returns a signed `HELD` receipt;
8. receive creates exactly one inbox record;
9. canonical receiver state bytes remain unchanged;
10. duplicate crossing does not duplicate the inbox entry;
11. owner-local ADMIT returns a signed `ADMITTED` receipt;
12. ADMIT materializes only into the admitted parcel corpus;
13. a terminal parcel cannot later be REJECTED;
14. another parcel can be explicitly REJECTED;
15. another parcel can be SCARRED as an inactive witness;
16. scar materialization records `active = false`;
17. a parcel addressed to another particular receives signed `REFUSED`;
18. wrong-target parcel never enters the inbox;
19. every persisted receiver receipt verifies;
20. canonical live state remains byte-for-byte unchanged through all dispositions.

## Real two-body trial

On receiver:

```bash
python3 ghot/organ.py
```

Its BODY discovery response advertises a separate state parcel porch.

On sender, export a parcel targeted at the receiver BODY particular:

```bash
python3 ghot/state_parcel.py export \
  organ/state.v1.json \
  --selector /body/offers \
  --target-particular <receiver-particular> \
  --out offers.parcel.json
```

Then either:

```bash
python3 ghot/state_parcel.py send \
  offers.parcel.json \
  http://RECEIVER:7792
```

or after discovery:

```bash
python3 ghot/state_parcel.py send-node \
  offers.parcel.json \
  <receiver-node-id>
```

Expected sender receipt:

```text
HELD
semantic_effect = none
```

On receiver:

```bash
python3 ghot/state_parcel.py inbox
python3 ghot/state_parcel.py show <parcel-id>
```

Then explicitly:

```bash
python3 ghot/state_parcel.py decide <parcel-id> ADMIT
```

or:

```bash
python3 ghot/state_parcel.py decide <parcel-id> REJECT
python3 ghot/state_parcel.py decide <parcel-id> SCAR
```

## Pass

018 passes when the deterministic simulation and the complete earlier smoke
suite remain green.

## Mutation opened

019 can define schema-specific local merge contracts over **admitted** parcels:

```text
ADMITTED PARCEL
      ↓
local schema compatibility
      ↓
explicit merge proposal
      ↓
before local state address
+ foreign parcel address
      ↓
bounded merge function
      ↓
proposed after address
      ↓
owner decision
      ↓
atomic local write
      ↓
signed MERGE RECEIPT
```

That would make state composition possible without giving a foreign body direct
write authority over local durable state.
