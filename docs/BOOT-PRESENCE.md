> **017 note:** Experiment 017 makes `ghot.organ.state/v1` canonical and adds an exact v0→v1 migration with backup + BODY-signed migration receipt. Normal startup applies registered migrations before the 016 boot manifest is signed; unknown versions still block. See `docs/STATE-MIGRATIONS.md`.

# Morning Presence / Boot Manifest / Startup Receipt

Experiment 016 gives a booted GHoT body a bounded answer to:

> Who woke, from what durable state, under what code, through what startup
> surface, and what is degraded right now?

This is observation, not authority.

## Startup artifacts

Every normal `ghot/organ.py` start writes:

```text
GHOT_HOME/startup/manifest.v0.json
GHOT_HOME/startup/receipt.v0.json
GHOT_HOME/startup/receipts/<receipt-id>.json
```

The current manifest describes the wake. The receipt is append-only evidence
that the current body key witnessed that manifest.

## Boot manifest

`ghot.boot.manifest/v0` includes:

```text
boot_id
created_at
node_id

body:
  identity
  power
  offers

code:
  repo_root
  entrypoint
  python
  python_version
  platform
  revision:
    git commit
    dirty state

boot_surface:
  surface
  instance
  pid
  parent_pid

state_home
state compatibility / migration requirement
dependency readiness
manifest_address
```

The manifest is normalized into GHoT's bounded identity-safe JSON family before
hashing.

## Startup receipt

The body P-256 key signs a startup receipt over the manifest address.

```text
ghot.startup.receipt/v0
```

The receipt binds:

```text
boot_id
manifest_address
node_id
body particular
created_at
initial health
```

with domain:

```text
ghot.startup-receipt-signature/v0
```

The persisted manifest is re-hashed whenever health is read. A valid old receipt
cannot bless a manifest that was edited afterward.

```text
SIGNED ADDRESS + REHASHED MANIFEST
```

is the integrity pair.

## What the receipt does not mean

A valid startup receipt proves that possession of the current GHoT body key was
used to sign the wake description.

It does not prove:

- that the code is safe;
- that the git commit is trusted;
- that the machine is uncompromised;
- that the body remains healthy later;
- that lease authority was granted;
- that any task executed.

Therefore:

```text
STARTUP RECEIPT != EXECUTION RECEIPT
CODE REVISION != TRUST
HEALTH != AUTHORITY
```

## State compatibility

016 inspects known durable current-state records before the new daemon cycle
starts.

Current known compatible state:

```text
ghot.organ.state / 1
ghot.field / 0
```

If a known state file contains an unsupported version or invalid structure,
the manifest records:

```text
migration_required: true
```

and health becomes:

```text
blocked
```

016 does not automatically mutate unknown old state.

```text
UNKNOWN STATE != SAFE TO REWRITE
```

Later migration tooling can make that transition explicit and receipted.

## Dependency readiness

Required startup dependencies currently include:

- Python;
- OpenSSL, required for the P-256 body/signature profile.

Optional executor presence is also recorded, including examples such as:

- git;
- ffmpeg / ffprobe;
- llama.cpp;
- whisper.cpp;
- Piper;
- ImageMagick.

Missing optional tools do not make the organ globally unhealthy; their
capabilities simply remain absent from BODY offers.

## Health states

The local health surface uses:

```text
healthy
degraded
blocked
```

`blocked` currently covers conditions such as:

- required dependency unavailable;
- body P-256 identity unavailable;
- durable state requires migration/repair;
- boot manifest integrity failure;
- startup receipt missing/invalid/mismatched.

`degraded` covers runtime-local failures such as a supervised service being
down or a cycle reporting an error.

A degraded body still remains the same identity.

## Local endpoints

The organ daemon starts a separate loopback-first presence server by default:

```text
http://127.0.0.1:7791/health
http://127.0.0.1:7791/presence
```

The BODY LAN service remains on its own port.

This separation is deliberate: the richer presence record contains local code
and state provenance that does not need to be advertised to every LAN peer.

Override when explicitly needed:

```bash
python3 ghot/organ.py \
  --health-host 127.0.0.1 \
  --health-port 7791
```

Disable:

```bash
python3 ghot/organ.py --no-health
```

The existing no-port diagnostic mode remains no-port:

```bash
python3 ghot/organ.py --once --no-serve
```

because `--no-serve` also suppresses the local presence HTTP service.

## Boot-surface provenance

015 launchers now stamp:

```text
GHOT_BOOT_SURFACE
GHOT_BOOT_INSTANCE
```

Known examples:

```text
direct
systemd-user
termux-boot
live-usb-systemd
```

The manifest records those values rather than inferring them from process-tree
guesswork.

```text
BOOT SURFACE != BODY IDENTITY
```

## Presence query

`/presence` returns:

```text
manifest
startup_receipt
current health
```

That is the morning presence check.

A concise human reading is:

```text
I am this body.
I woke through this surface.
This code revision woke me.
This durable state was compatible / not compatible.
This body key signed the wake.
These services are healthy or degraded now.
```

## Laws

- PRESENCE != AUTHORITY
- HEALTH != AUTHORITY
- STARTUP RECEIPT != EXECUTION RECEIPT
- CODE REVISION != TRUST
- BOOT SURFACE != BODY IDENTITY
- PROCESS ID != BODY IDENTITY
- UNKNOWN STATE != SAFE TO REWRITE
- HEALTHY NOW != AVAILABLE FOREVER
- DEGRADED != IDENTITY LOSS
