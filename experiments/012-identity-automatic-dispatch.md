# Experiment 012 — Identity + Automatic Remote Dispatch

## Question

Can Wake Composer select a remote body, automatically bind a dispatch to that body's P-256 identity, and complete the HOLD only through reLATTE-profile signed lease crossings?

## Trial A — reLATTE fixed-fixture conformance

```bash
python3 ghot/relatte_identity_sim.py
```

Expected proof:

- genesis crossing ID re-derives exactly;
- genesis receipt ID re-derives exactly;
- fixed crossing signature verifies;
- fixed receipt signature verifies;
- semantic mutation fails verification.

## Trial B — portable P-256 lease lifecycle

```bash
python3 ghot/portable_lease_sim.py
```

Expected:

- target body sees its dispatch;
- another body does not;
- wrong-key claim is refused;
- selected-key claim is admitted;
- replay returns the original receipt;
- renew extends lease;
- stale worker completion is refused;
- tampered crossing is refused;
- recovered selected worker can complete.

## Trial C — automatic owner dispatch

```bash
python3 ghot/auto_dispatch_sim.py
```

Expected:

1. Wake Composer selects remote BODY;
2. owner emits DISPATCH without manual `prepare`;
3. DISPATCH contains selected node id + P-256 particular + public key;
4. unchanged second wake does not create a duplicate active dispatch;
5. wrong key cannot claim even using the selected node id;
6. selected key can claim;
7. selected key can complete;
8. original HOLD becomes released;
9. an identityless remote body remains held rather than falling back to unsigned execution.

## Trial D — two real bodies

On owner:

```bash
python3 ghot/lease_authority.py serve --port 7790
python3 ghot/wake_composer.py watch
```

On remote body:

```bash
python3 ghot/lan_node.py serve --port 7788
python3 ghot/lease_remote.py http://OWNER:7790 watch
```

Create a deferrable HOLD whose capability/energy plan selects the remote body.

Expected:

```text
discovery
 -> remote BODY identity observed
 -> wake selects remote
 -> automatic owner dispatch
 -> remote poll
 -> signed claim
 -> remote task
 -> signed completion
 -> owner release
```

## Pass

012 passes when:

- GHoT verifies the existing reLATTE fixed P-256 fixtures;
- BODY identity is stable across probes;
- scheduler output carries the selected body identity;
- remote selection automatically creates one owner dispatch;
- dispatch is cryptographically bound to selected body identity;
- unsigned/identityless remote fallback does not occur;
- remote completion cannot release the HOLD without current owner lease;
- CI proves all earlier experiments plus the 012 witnesses.

## Mutation opened

013 should remove the remaining manually configured authority address.

Candidate seam:

```text
BODY discovery
  + authority advert
  + trusted/pinned introduction
  -> remote organ learns where its selected owner's porch is
  -> dispatch notification or discovery
  -> zero hand-wired authority URL
```

That is where arrival itself can become enough for an organ to discover both work and the authority boundary around that work.
