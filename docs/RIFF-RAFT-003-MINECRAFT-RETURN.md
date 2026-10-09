# RIFF-RAFT-003 — Signed Minecraft return inbox

GHoT can now **read a portable reLATTE evidence bundle** produced by two separately provisioned official Minecraft worlds. The design deliberately makes the **return crossing** richer in evidence but poorer in authority.

## Source / ownership

- GHoT [RIFF-RAFT-002](https://github.com/the-static-collective/GHoT/pull/113) provides the original nine-cue synthetic ecology rehearsal. Exact source commit: `a63624f1be6a533f5ab927b1e4e8b1a629f1ba53`.
- reLATTE [Minecraft-001](https://github.com/the-static-collective/reLATTE/pull/96) proved independently observed voxel stage stations; [Minecraft-002](https://github.com/the-static-collective/reLATTE/pull/97) proved actual vanilla redstone causality and a fault/repair sequence.
- reLATTE Minecraft-003 orchestrates two **distinct GitHub CI jobs**, each booting its own localhost-only Mojang 26.1.1 server with a distinct seed, signing its own instance and held candidate, then a replay coordinator reads both evidence artifacts and issues a **third** signed, held return crossing addressed to GHoT.
- GHoT's `ghot/riff_raft_minecraft_return.py` verifies the portable crossing and receipt with its pre-existing independent **OpenSSL-backed P-256 reLATTE verifier**; verifies every source instance launch and candidate crossing and receipt; validates the actual evidence bytes, witness separation, material ancestry, game-state hashes, and the 0/3/0/9 lamp sequence.

The intake can be called against an externally supplied bundle:

```bash
python3 ghot/riff_raft_minecraft_return.py /path/to/riff-raft-return-bundle.json
```

Successful verification returns **HOLD**, never ADMIT. It does **not** update the work scheduler, boot an organ, send a command, seed plants, spend electrical power, affect permissions, start a public Minecraft realm, or write to an authoritative node.

```text
two official vanilla runtime instances (A, B; separate runner, seed, world)
         ↓
two distinct operator/observer world traces
         ↓
two reLATTE signed R3_ADMIT instance launches
         ↓
two independently signed R3_HOLD Minecraft results
         ↓
world-specific redstone off/broken/reset/repaired witness histories
         ↓
reLATTE pair comparison and signed R3_HOLD portable packet
         ↓
GHoT independent ECDSA P-256 verification + byte/ancestry checks
         ↓
GHoT HOLD; owner-local review necessary for any later admission
```

## What is compared

It is incorrect to demand that two different Minecraft worlds have an identical complete voxel state. Instead, the verifier requires:

- Distinct world seeds and distinct source instance, launch and candidate identities.
- Different measured voxel state hashes.
- The same pinned Minecraft server binary/version.
- Two independently observed `redstone_lamp[lit=true]` causality traces.
- Exactly `000000000 → 111000000 → 000000000 → 111111111` for the nine redstone stations.
- Each trace's final non-operator Minecraft client reported all lamps lit.
- Exact resulting redstone-state hash included in the observed-state hash and signed result.
- Source documents and GHoT ancestry bound to the signed packet.
- No source candidate auto-admitted, no resource movement, no physical effect.

The GHoT receiver also checks raw source evidence bytes against the signed packet's hashes and verifies the **source** signatures rather than merely trusting a summary of earlier signature checks.

## Crucial trust distinction

A **self-signed** ephemeral reLATTE crossing is cryptographically verifiable and tamper-evident; it does **not** by itself prove the signer owns a GitHub organization, a Minecraft server, physical land, a budget, or a GHoT organ. GitHub Actions logs supply a separate, inspectable run identity. No trust root for project-level authorization is created by this experimental adapter.

Current read-side cryptographic validation also does not independently query a Minecraft server. It validates a signed composition of two GitHub CI results, which must remain externally auditable; this is stronger than blind trust in a textual summary but weaker than two live receivers each querying the world.

**GHoT RECEIVES A VERIFIED GAME-OBSERVATION CANDIDATE. NOT A DIRECT INSTRUCTION.**

## Noncollapse laws

```text
TWO WORLD RUNS != TWO PHYSICAL SITES
TWO DISTINCT SEEDS != INDEPENDENT SOCIAL AUTHORITY
MATCHING GAME TRACES != ECOSYSTEM RECOVERY
SIGNATURE INTEGRITY != OWNER IDENTITY
SIGNED GHoT RETURN != GHoT ADMISSION
A SOURCE R3_HOLD != PERMISSION TO EXECUTE
OBSERVED LAMP != LAND FERTILITY
REPLAY SUCCESS != REMOTE ACTUATION
```

## Next step

After a successful first paired replay, integrate a *local human-review display* in GHoT that shows the two external traces side by side and offers only a non-authoritative **inspected candidate** for the next ecological simulation. A future physical bench is a separate engineering process.
