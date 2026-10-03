# The Many-Bodied Machine

## Recovered architecture, 2024–2026

GHoT treats hardware as temporary embodiment, not identity.

The recurring design thread is simple:

1. computation may exist across arbitrary available machines;
2. each machine should contribute what it can actually do;
3. local ownership and authority remain local;
4. work may cross between bodies;
5. results return with receipts;
6. any body may disappear without destroying the organism.

The original dream was often phrased as an offline JARVIS capable of using any connected processor. The buildable translation is stronger:

> **Any available processor may become an organ of the same persistent computational organism.**

This does **not** require one binary to run on every architecture. It requires a portable contract for describing bodies, offers, tasks, results, receipts, state and authority.

## Laws

- IDENTITY != BODY
- CAPABILITY != DEVICE
- PROCESSOR != AUTHORITY
- DISCOVERY != TRUST
- OFFER != ASSIGNMENT
- ASSIGNMENT != EXECUTION
- EXECUTION != RECEIPT
- RECEIPT != TRUTH
- NODE LOSS != ORGANISM LOSS
- SHARED WORK != SHARED OWNERSHIP
- REMOTE CAPABILITY != REMOTE AUTHORITY
- TEMPORARY ACCESS != PERMANENT MEMBERSHIP
- A BODY MAY ARRIVE, SERVE, RECEIPT, AND DEPART

## Organism loop

```text
PROBE
  -> DECLARE BODY
  -> ADVERTISE CAPABILITIES
  -> DISCOVER PEERS
  -> NEGOTIATE / SELECT
  -> CROSS TASK
  -> LOCAL EXECUTION
  -> RECEIPT
  -> MERGE RESULT
  -> REMEMBER
```

## Bodies

A body is any device that can expose one or more bounded capabilities.

Examples:

- x86 workstation: large-model inference, compilation, storage, rendering;
- laptop: CPU, display, microphone, storage, battery-backed continuity;
- Android phone: camera, microphone, GPS, NPU/GPU, display, radios, battery;
- Raspberry Pi / SBC: always-on coordination, sensors, local services;
- ESP32 / microcontroller: sensing, actuation, low-power wake/sleep;
- old router: networking, relay, storage;
- temporary cloud/borrowed machine: bounded compute that may appear and vanish.

A body does not become the organism. It becomes an organ for as long as it participates.

## Contract surface

### BODY
What am I?

- architecture
- operating system / runtime
- memory
- storage
- accelerators
- power source and current power state
- network transports
- attached sensors / actuators
- installed executors
- stable local node identity

### OFFER
What can I do right now?

Examples:

- `llm.infer.small`
- `llm.infer.large`
- `speech.transcribe`
- `speech.synthesize`
- `vision.capture`
- `vision.describe`
- `audio.play`
- `render.video`
- `compile.rust`
- `storage.hold`
- `sensor.temperature.read`
- `actuator.relay.set`

Offers may carry limits: RAM, queue depth, energy cost, latency, privacy boundary, executable version and expiry.

### TASK
What bounded work is requested?

A task should say:

- requested capability;
- input references or inline payload;
- constraints;
- requester;
- deadline / expiry if applicable;
- expected output shape;
- authority boundary.

### RECEIPT
What happened?

A receipt should say:

- task id;
- executor node;
- capability used;
- start/end times;
- status;
- output hash/reference;
- execution metadata;
- errors;
- optional signature.

The receipt proves that a node reports an execution event. It does not automatically prove correctness.

## Relationship to reLATTE

GHoT owns physical/runtime embodiment.

reLATTE owns portable crossing semantics and receipts.

Static-OS owns the inhabitable user-facing environment.

TranchNode / durable state systems may own persistence and synchronization.

These should compose without collapsing authority:

```text
Static-OS intention
       |
       v
reLATTE crossing
       |
       v
GHoT capability routing
       |
       v
local body execution
       |
       v
receipt
       |
       v
owner-local disposition + durable memory
```

## Constraint: offline first

The minimum useful organism must function on an isolated LAN with no internet connection.

Internet access, cloud models and external services may be optional organs. They are never required for organism continuity.

## Constraint: graceful degradation

If the strongest node disappears, the organism should become less capable rather than become nonexistent.

Example:

```text
GPU workstation disappears
-> large LLM offer disappears
-> laptop small-model offer remains
-> Pi coordination remains
-> ESP32 sensing remains
-> shared state continues
```

## Constraint: power awareness

A solar/battery node should be able to advertise both capability and current willingness.

Examples:

- high battery: accept inference;
- medium battery: accept sensing + light transforms;
- low battery: sensing only;
- critical battery: sleep, retain wake trigger.

Scheduling eventually considers not only speed but energy, heat, battery reserve and renewable surplus.

## Success condition

GHoT is real when two unrelated devices can meet on an offline network, discover one another, exchange a bounded task, execute it on the better-suited body, return a verifiable receipt, disconnect one device, and continue operating in degraded form.
