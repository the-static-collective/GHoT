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

V0 signs those records with a shared-secret HMAC profile. It explicitly does
**not** claim public-key identity verification yet.

Deterministic proof:

```bash
python3 ghot/portable_lease_sim.py
```

See `docs/PORTABLE-LEASE-AUTHORITY.md` and
`experiments/011-portable-lease-authority.md`.
