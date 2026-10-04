# Experiment 032 — The Cube Comes Home

032 makes verified Ice Cube results portable without teaching reLATTE any Ice Cube mathematics.

## Flow

```text
worker mines
→ worker Dogram receipt
→ compact result manifest
→ render split into content-addressed chunks
→ signed reLATTE State Parcel commits to manifest + chunk addresses
→ network POST /ice-cube-return
→ receiver HOLD
→ receiver-local Dogram replay
→ signed receiver verification receipt
→ still HOLD
→ owner-local ADMIT
→ materialize frozen render on requester
→ explicit existing pantry merge
```

## Why chunking

Normal State Parcels intentionally cap JSON payloads at 512 KiB. The Ice Cube return keeps the signed State Parcel small and moves render bytes as separately hashed chunks named by the signed manifest.

The v0 HTTP porch is still bounded, but the object model no longer assumes the render itself fits inside one State Parcel.

## Authority laws

```text
WORKER VERIFIED != RECEIVER VERIFIED
NETWORK ARRIVAL != VERIFICATION
VERIFICATION != ADMISSION
ADMISSION != MERGE
CHUNK HASH != MATHEMATICAL TRUTH
TRANSPORT != AUTHORITY
```

The network endpoint can only produce HOLD.

The receiver cannot use `admit_verified` until its own Dogram run produces OK and the receiver signs a local verification receipt.

After ADMIT, 030's existing `ghot.plugin.verified-ice-cube` merge grammar is reused unchanged.

## Proof

CI runs:

```bash
python3 ghot/ice_cube_return_sim.py --dogram-repo _dogram_ice
```

The simulation mines a real small cube, sends it over a real loopback HTTP porch, proves a modified chunk is refused, proves ADMIT is blocked before local verification, independently verifies on the receiving body, ADMITs, materializes the render, and merges the ordinary admitted State Parcel into the verified Ice Cube pantry.
