# GHoT — Giant Heap of Things

> Any available processor may become an organ of the same computational organism.

GHoT is the hardware/runtime edge of Static-OS: a local-first, heterogeneous compute organism that can discover bodies, describe their capabilities, compose work across them, execute locally, issue receipts, survive disappearance, and continue without requiring identical binaries or hardware.

## Foundational laws

- **IDENTITY != BODY**
- **CAPABILITY != DEVICE**
- **PROCESSOR != AUTHORITY**
- **DISCOVERY != TRUST**
- **OFFER != ASSIGNMENT**
- **ASSIGNMENT != EXECUTION**
- **EXECUTION != RECEIPT**
- **NODE LOSS != ORGANISM LOSS**
- **A BODY MAY ARRIVE, SERVE, RECEIPT, AND DEPART**

## First loop

```text
PROBE
  -> DECLARE BODY
  -> ADVERTISE CAPABILITIES
  -> DISCOVER PEERS
  -> COMPOSE PLAN
  -> CROSS TASK
  -> LOCAL EXECUTION
  -> RECEIPT
  -> MERGE RESULT
  -> REMEMBER
```

The first milestone is not "distributed AGI." It is two ordinary machines on a LAN proving this loop end-to-end, offline.

## Try the body

```bash
python3 ghot/reference_node.py probe
python3 ghot/reference_node.py pantry
python3 ghot/reference_node.py echo "hello heap"
python3 ghot/reference_node.py hash "the heap remembers"
```

The pantry currently recognizes Python, Git, ffmpeg/ffprobe, llama.cpp, whisper.cpp, Piper and ImageMagick. Installed executors become bounded capability offers; missing executors do not.

If ffprobe is installed:

```bash
python3 ghot/reference_node.py run media.probe "/path/to/local/file.mp3"
```

## Try two bodies

Machine A:

```bash
python3 ghot/lan_node.py serve --port 7788
```

Machine B:

```bash
python3 ghot/lan_node.py scan
python3 ghot/lan_node.py task http://<A-IP>:7788 system.hash "hello other body"
```

No arbitrary remote shell is exposed.

## Read next

- `docs/THE-MANY-BODIED-MACHINE.md`
- `docs/BUILD-PLAN.md`
- `docs/EXECUTOR-PANTRY.md`
- `experiments/001-one-body.md`
- `experiments/002-two-bodies-lan.md`
- `experiments/003-executor-pantry.md`

## Compose by capability

Once one or more LAN bodies are serving, the requester no longer needs to name
an IP address:

```bash
python3 ghot/capability_composer.py runtime.ffmpeg.version --dry-run
python3 ghot/capability_composer.py runtime.ffmpeg.version
```

The composer discovers bodies, rejects those that do not offer the capability,
applies explicit constraints/preferences, persists a PLAN with
`why_selected`, and then executes locally or crosses the task automatically.

See `docs/CAPABILITY-COMPOSER.md` and
`experiments/004-capability-composer.md`.


## Survive a disappearing body

Failure-aware recomposition keeps one stable composition identity across
multiple plans and attempts:

```bash
python3 ghot/resilient_composer.py runtime.ffmpeg.version --max-attempts 3
```

A deterministic no-network proof is included:

```bash
python3 ghot/recomposition_sim.py
```

Expected: body A is selected and fails, A is excluded, a child plan selects
body B, B succeeds, and the final COMPOSITION preserves both attempts.

See `docs/FAILURE-AWARE-RECOMPOSITION.md` and
`experiments/005-failure-aware-recomposition.md`.


## Keep a living field of bodies

GHoT now remembers bodies beyond a single discovery sweep:

```bash
python3 ghot/liveness_field.py sweep
python3 ghot/liveness_field.py show
python3 ghot/liveness_field.py watch --interval 5
```

V0 states are `awake`, `stale`, `departed`, and `quarantined`.

A cached body/offer can remain visible as history without being eligible for new
work. Capability composition requires `awake` liveness, and resilient
execution feeds failures/successes back into the field's bounded circuit
breaker.

Deterministic proof:

```bash
python3 ghot/liveness_sim.py
```

See `docs/LIVENESS-FIELD.md` and `experiments/006-liveness-field.md`.


## Let bodies spend energy honestly

BODY declarations now include live power pressure and power-adjusted offers:

```bash
python3 ghot/power_field.py
python3 ghot/reference_node.py power
python3 ghot/reference_node.py probe
```

V0 willingness is `abundant`, `normal`, `conserve`, or `critical`.

For solar/experimental nodes:

```bash
GHOT_POWER_SOURCE=solar \
GHOT_RENEWABLE_SURPLUS=1 \
GHOT_BATTERY_PERCENT=90 \
GHOT_CHARGING=1 \
python3 ghot/reference_node.py probe
```

Under conserve pressure, heavy offers withdraw. Under critical pressure, only
essential offers remain. Execution rechecks the current offer before running,
so a body may refuse work that became unaffordable after planning without
changing identity or deleting the executor.

Deterministic proof:

```bash
python3 ghot/power_sim.py
```

See `docs/POWER-FIELD.md` and `experiments/007-power-field.md`.


## Schedule across power and time

Energy-aware scheduling can now choose `run_here`, `run_there`, or `hold`:

```bash
python3 ghot/energy_scheduler.py runtime.ffmpeg.version --urgency normal --dry-run
```

For deferrable heavy background work, GHoT may persist a HOLD instead of
spending battery immediately:

```bash
python3 ghot/energy_scheduler.py render.video job.json \
  --urgency background \
  --deferrable \
  --dry-run
```

Urgent work is not delayed merely for energy optimization. Data locality is an
explicit scheduling factor, and HOLD records preserve the original intent for
later re-evaluation.

Deterministic proof:

```bash
python3 ghot/energy_sim.py
```

See `docs/ENERGY-AWARE-SCHEDULING.md` and
`experiments/008-energy-aware-scheduling.md`.


## Wake held work

HOLDs now live in an active local queue as well as the append-only record trail:

```bash
python3 ghot/wake_composer.py list
python3 ghot/wake_composer.py wake
python3 ghot/wake_composer.py watch --interval 5
```

A hold may remain held, release into a child energy plan, be cancelled, or
expire. Cancelled/expired work is never started by the Wake Composer.

Optional expiry can be attached when a hold is created:

```bash
python3 ghot/energy_scheduler.py render.video job.json \
  --urgency background \
  --deferrable \
  --hold-for-seconds 3600
```

Cancellation:

```bash
python3 ghot/wake_composer.py cancel <hold-id> "no longer needed"
```

Deterministic proof:

```bash
python3 ghot/wake_sim.py
```

See `experiments/009-hold-queue-wake-composer.md`.


## Share one HOLD queue safely

Wake workers now acquire an exclusive expiring lease before execution.

```bash
python3 ghot/wake_composer.py watch \
  --worker-id worker-a \
  --lease-seconds 60
```

A second worker sharing the same `GHOT_HOME` cannot start the same HOLD while
the lease is live. Healthy workers renew their lease during execution; if a
worker dies, the lease expires and another worker can recover it.

Cancellation/expiry wins before claim. Once a live claim exists, V0 reports
that cancellation is blocked rather than pretending already-started work was
revoked.

Deterministic concurrency proof:

```bash
python3 ghot/lease_sim.py
```

See `docs/WORK-LEASES.md` and
`experiments/010-atomic-claim-work-lease.md`.


## Cross leases between bodies

010 made one shared queue safe for multiple workers. 011 keeps the queue owner
authoritative while allowing execution to move to remote bodies through
reLATTE-shaped crossing envelopes and receipts.

Owner authority:

```bash
export GHOT_LEASE_SHARED_SECRET='development-only-value'
python3 ghot/lease_authority.py serve --port 7790
```

The owner must explicitly dispatch a HOLD to a named worker before that worker
can claim it:

```bash
python3 ghot/lease_authority.py prepare \
  <hold-id> \
  <worker-id> \
  <child-energy-plan-id> \
  --ttl 120
```

Selected remote worker:

```bash
export GHOT_LEASE_SHARED_SECRET='development-only-value'
python3 ghot/lease_remote.py http://OWNER:7790 --worker-id <worker-id> work
```

The crossing objects use `relatte.crossing-envelope/v0`; authority responses
use `relatte.receipt/v0`.

Experiment 011 originally used a bounded shared-secret HMAC bridge. Experiment
012 supersedes that transport-auth profile with the current reLATTE P-256
identity/signature profile while preserving the same owner-local authority law.

Deterministic proof:

```bash
python3 ghot/portable_lease_sim.py
```

See `docs/PORTABLE-LEASE-AUTHORITY.md` and
`experiments/011-portable-lease-authority.md`.


## Sign bodies and dispatch automatically

012 upgrades portable work leases from the 011 shared-secret bridge to the
current reLATTE Identity + Signature Profile v0.

Each BODY now advertises a stable P-256 public identity generated from local
durable key material:

```bash
python3 ghot/reference_node.py probe
```

The BODY record includes:

```text
identity.profile = relatte.identity-signature/v0
identity.algorithm = ECDSA-P256-SHA256
identity.particular
identity.public_key
```

Wake Composer now automatically emits an owner DISPATCH when an energy plan
selects a remote body. The dispatch is bound to the selected body's node id,
particular, and public key.

Owner services:

```bash
python3 ghot/lease_authority.py serve --port 7790
python3 ghot/wake_composer.py watch
```

Remote organ:

```bash
python3 ghot/lan_node.py serve --port 7788
python3 ghot/lease_remote.py http://OWNER:7790 watch
```

For authority continuity on a network where the initial advert itself is not
implicitly trusted, pin the expected authority particular:

```bash
GHOT_AUTHORITY_PARTICULAR=<expected-particular> \
python3 ghot/lease_remote.py http://OWNER:7790 watch
```

Conformance and automatic-dispatch proofs:

```bash
python3 ghot/relatte_identity_sim.py
python3 ghot/portable_lease_sim.py
python3 ghot/auto_dispatch_sim.py
```

The reLATTE fixture test verifies the fixed genesis P-256 crossing and receipt,
not only GHoT-generated signatures.

See `docs/IDENTITY-AUTOMATIC-DISPATCH.md` and
`experiments/012-identity-automatic-dispatch.md`.


## Discover the authority porch

013 removes the last hand-wired owner URL from the normal remote-organ path.

The authority server now broadcasts a short-lived signed porch advert on the
LAN:

```bash
python3 ghot/lease_authority.py serve --port 7790
```

A remote body may inspect what is present:

```bash
python3 ghot/authority_discovery.py scan
```

Discovery alone grants nothing. Admit an intended authority explicitly once:

```bash
python3 ghot/authority_discovery.py trust http://OWNER:7790
```

That stores the authority particular, public key, authority id and world id as
a local trust record. Future network-address changes do not require a new
identity decision as long as the signed authority identity remains the same.

Then the remote organ can run with no owner address:

```bash
python3 ghot/lease_remote.py watch
```

It discovers current roads, rejects unsigned/stale adverts, and polls only
authorities that are either remembered locally or pinned with
`GHOT_AUTHORITY_PARTICULAR`.

Useful inspection commands:

```bash
python3 ghot/authority_discovery.py trusted
python3 ghot/authority_discovery.py resolve
python3 ghot/authority_discovery.py forget <authority-particular>
```

The authority IP address is deliberately not identity-bearing:

```text
ROAD != IDENTITY
DISCOVERY != TRUST
SIGNED ADVERT != ADMISSION
```

Deterministic proof:

```bash
python3 ghot/authority_discovery_sim.py
```

See `docs/AUTHORITY-PORCH-DISCOVERY.md` and
`experiments/013-authority-porch-discovery.md`.


## Become one organ process

014 composes the running body into one supervised process:

```bash
python3 ghot/organ.py
```

That single command now keeps the BODY HTTP service and BODY discovery responder
alive while repeatedly refreshing the local body/power/offers, maintaining the
liveness field, resolving trusted authority porches, and running the portable
lease worker.

Current composed state is written to:

```text
.ghot/organ/state.v0.json
```

Subsystem failure is local. A failed peer discovery, authority scan, or lease
worker cycle is recorded and retried without discarding the body's identity or
the rest of the daemon. BODY HTTP/discovery service death is supervised and
restart is attempted.

A no-port diagnostic cycle is available:

```bash
python3 ghot/organ.py --once --no-serve
```

The daemon remains a supervisor, not a new authority:

```text
DAEMON != AUTHORITY
SUPERVISION != ADMISSION
SERVICE FAILURE != BODY DEATH
```

Deterministic proof:

```bash
python3 ghot/organ_sim.py
```

See `docs/ORGAN-DAEMON.md` and `experiments/014-organ-daemon.md`.


## Wake as an organ

015 packages the organ daemon into reversible startup surfaces.

Linux user service:

```bash
python3 ghot/install_organ.py systemd-user --enable-now
```

This installs `~/.config/systemd/user/ghot-organ.service` and points it at a
stable explicit `GHOT_HOME`. It is rootless by default and starts only
`ghot/organ.py`.

A user unit starting before interactive login depends on the host's systemd user
manager / linger policy. GHoT does not change that OS policy automatically.

Termux / Android:

```bash
python3 ghot/install_organ.py termux
```

This installs `~/.termux/boot/ghot-organ`. Actual Android boot execution
requires Termux:Boot to be installed/configured on the device. The launcher has
a PID guard to avoid duplicate live daemon starts.

Live-USB/image bundle:

```bash
python3 ghot/install_organ.py live-usb \
  --output-dir build/ghot-live \
  --target-repo-root /opt/GHoT
```

That command only renders an image-integration bundle; it does not modify the
current host.

Uninstall the Linux or Termux startup hook:

```bash
python3 ghot/install_organ.py systemd-user --uninstall
python3 ghot/install_organ.py termux --uninstall
```

Uninstall preserves durable GHoT state and body identity.

```text
STARTUP != AUTHORITY
INSTALL != IDENTITY
UNINSTALL STARTUP != FORGET BODY
```

Deterministic proof:

```bash
python3 ghot/install_organ_sim.py
```

See `docs/BOOTABLE-ORGAN.md` and
`experiments/015-bootable-organ.md`.
