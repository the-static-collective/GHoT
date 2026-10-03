> **017 note:** 014 originally introduced organ state v0. Experiment 017 makes v1 canonical and preserves v0 through the signed migration path; the behavioral lifecycle test now writes v1.

# Experiment 014 — Organ Daemon

## Question

Can one GHoT process keep a body present, refresh its offers/power, maintain the
liveness field, resolve trusted authority porches, and execute addressed work
without collapsing when one subsystem fails?

## Trial A — deterministic lifecycle

```bash
python3 ghot/organ_sim.py
```

The simulation runs three cycles.

Cycle 1:

```text
local body normal
peer arrives
trusted authority resolves
no dispatch
```

Cycle 2 injects simultaneous failures in:

```text
peer discovery
authority discovery
lease worker
```

Expected: the daemon records all three errors and remains alive with the same
local body identity.

Cycle 3 recovers:

```text
local power -> critical
peer absent long enough -> departed
authority resolves again
work -> completed
```

The current state file must contain cycle 3 and the event trail must remain
durable.

## Trial B — one real organ command

On a machine that has already admitted an authority porch:

```bash
python3 ghot/organ.py
```

Expected services:

```text
BODY HTTP       :7788
BODY discovery  :47888/udp
organ cycle     every 5s
authority scan  every cycle
lease worker    every cycle
```

Another LAN machine should be able to discover the BODY while this process is
running.

## Trial C — power mutation

Start the organ with one power state, then change the probe inputs or physical
power condition.

Expected: a later organ cycle records the new willingness/offers without
changing node identity.

## Trial D — service failure

Force the BODY discovery service or BODY HTTP loop to die while the daemon
process remains alive.

Expected: supervisor marks the service failed and attempts to recreate it.

## Trial E — unknown authority

Present an unknown but valid signed authority porch.

Expected: the organ may observe it through explicit scan tooling, but its
automatic lease-worker path does not poll it.

## Trial F — diagnostic cycle

```bash
python3 ghot/organ.py --once --no-serve
```

Expected: BODY/power/liveness/authority/work composition runs once and writes:

```text
.ghot/organ/state.v1.json
```

without binding BODY service ports.

## Pass

014 passes when the deterministic simulation demonstrates failure locality,
recovery, durable current state, liveness aging, power mutation, and eventual
work completion while the complete earlier smoke suite remains green.

## Mutation opened

015 can make this process installable as an actual machine service:

```text
Linux/systemd
Termux/Android
portable user service
optional live-USB autostart
```

Then a body can boot directly into:

```text
wake
 -> declare
 -> discover
 -> recognize
 -> serve
 -> work
```

without a terminal command at all.
