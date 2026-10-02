# GHoT Build Plan

This plan keeps every recovered idea that is practical to test while ordering them by dependency.

## 0 — Prove the organism on one machine

Build a zero-cloud reference node in Python.

It must:

- probe host architecture, CPU count, RAM, disk and power information where available;
- emit a BODY document;
- detect installed executors such as Python, ffmpeg and llama.cpp;
- derive OFFER records;
- accept one local TASK;
- execute a safe built-in capability;
- emit a RECEIPT;
- persist BODY, OFFER, TASK and RECEIPT records locally.

First capabilities:

- `system.echo`
- `system.hash`
- `system.info`

Why: prove contracts and lifecycle before networking.

**Exit test:** one command produces a complete task + receipt round trip with no network.

---

## 1 — Two bodies on an offline LAN

Add peer discovery and task crossing.

Start with boring transports:

- UDP broadcast for discovery;
- HTTP on the LAN for task submission and result retrieval.

No cloud broker, account or central coordinator.

Experiments:

1. laptop discovers desktop;
2. desktop discovers laptop;
3. each advertises different offers;
4. laptop requests work only desktop offers;
5. desktop executes;
6. laptop stores the receipt;
7. disconnect desktop;
8. laptop remains alive and marks the offer unavailable.

**Exit test:** pull the Ethernet cable / disable Wi-Fi on one node while the other continues.

---

## 2 — Capability adapters

Wrap real tools without making them core dependencies.

Adapters to try:

- ffmpeg: `audio.transcode`, `video.transcode`, `media.probe`;
- llama.cpp: `llm.infer.local`;
- Whisper / whisper.cpp: `speech.transcribe.local`;
- Piper: `speech.synthesize.local`;
- ImageMagick: image transforms;
- git: repository inspection / bounded local operations;
- shell adapter with a strict allowlist, never arbitrary remote shell by default.

Each adapter declares:

- executable/version;
- input schema;
- output schema;
- estimated resource cost;
- privacy policy;
- timeout;
- concurrency.

**Exit test:** scheduler chooses a node because it actually owns the required executable.

---

## 3 — Scheduler: “what body should do this?”

Start deterministic.

Selection dimensions:

- capability match;
- online status;
- free RAM;
- accelerator presence;
- battery / power state;
- queue depth;
- data locality;
- trust policy;
- declared energy cost.

Do not start with AI scheduling. Make every choice inspectable.

Add `why_selected` to the plan/receipt trail.

**Exit test:** the same task routes differently when available bodies or power states change.

---

## 4 — Android body

Use Termux first; do not begin by writing a custom phone OS.

Try:

- Python reference node under Termux;
- camera/microphone/GPS exposure through Termux APIs where practical;
- local llama.cpp build if hardware allows;
- Wi-Fi peer discovery;
- battery-aware offers;
- wake/sleep behavior.

Phone-specific offers can include:

- `camera.capture`
- `microphone.record`
- `location.read`
- `display.notify`
- `llm.infer.mobile`

**Exit test:** workstation asks phone for a sensor capability; phone asks workstation for a heavy compute capability.

This directly tests the old “phone as JARVIS body” idea without requiring firmware work yet.

---

## 5 — Raspberry Pi / SBC body

Role: cheap always-on house organ.

Try:

- reference node as a systemd service;
- local discovery coordinator that is useful but non-authoritative;
- USB storage;
- GPIO adapters;
- Bluetooth / Wi-Fi;
- local SQLite state mirror;
- optional small LLM.

**Exit test:** laptops can disappear and return while the Pi preserves local continuity and peer knowledge.

---

## 6 — Microcontroller organ

Do **not** port the full node runtime to ESP32.

Instead define a constrained organ protocol.

ESP32 can advertise tiny offers:

- sensor read;
- relay set;
- LED/display output;
- wake event;
- low-bandwidth telemetry.

Use one of:

- HTTP;
- MQTT on a local broker;
- serial/USB;
- BLE;
- ESP-NOW;
- LoRa later.

A gateway body translates constrained organ messages into normal GHoT TASK/RECEIPT records.

**Exit test:** ordinary GHoT intent triggers a real sensor/actuator and produces a receipt.

---

## 7 — Power-aware organism

Recover the 2024 solar-compute idea explicitly.

BODY/OFFER additions:

- power source;
- battery percent;
- charging status;
- estimated watts;
- thermal state;
- energy policy;
- willingness state.

Policies to try:

- surplus solar => permit expensive background compute;
- battery below threshold => withdraw heavy offers;
- heat threshold => down-rank or withdraw accelerator;
- critical battery => retain only wake/safety capabilities.

**Exit test:** a task migrates or waits because energy state changed.

---

## 8 — Removable / borrowed bodies

Test the “arrive, serve, receipt, depart” law.

Examples:

- USB-booted laptop;
- friend's machine running a temporary GHoT node;
- rented GPU box;
- ephemeral VM;
- old desktop switched on only for renders.

Requirements:

- no assumption of permanence;
- scoped trust;
- scoped task data;
- explicit expiry;
- result hash;
- departure does not corrupt organism state.

**Exit test:** temporary node executes exactly one permitted capability, returns a receipt, then is forgotten or retained only as historical provenance.

---

## 9 — Durable identity and state

Only after task crossing works.

Separate:

- node identity;
- organism identity;
- user identity;
- project identity;
- data ownership.

Try:

- append-only local event log;
- content-addressed blobs;
- SQLite index;
- signed receipts;
- CRDT or DAG replication where multi-writer state is genuinely required.

Do not make “shared memory” a magical global database.

**Exit test:** two nodes diverge offline, reconnect, reconcile allowed shared state and preserve conflicting owner-local state rather than silently overwriting it.

---

## 10 — reLATTE crossing

Replace ad-hoc task envelopes with reLATTE-compatible crossings once the physical loop is stable.

Map:

- BODY/OFFER -> available organ contract;
- TASK -> crossing payload;
- execution -> owner-local disposition;
- RECEIPT -> reLATTE receipt;
- scheduler decision -> recommendation/selection evidence, not authority.

**Exit test:** a GHoT task can be reconstructed entirely from portable crossing + receipt records.

---

## 11 — Static-OS inhabitability

The user should eventually see:

- “bodies currently awake”;
- what each can do;
- what the organism can do collectively;
- current jobs;
- why a job went where it did;
- energy state;
- arrivals/departures;
- receipts;
- degraded capabilities.

Then hide most of this under ordinary intent.

Example:

> “Transcribe this recording.”

Static-OS composes:

```text
phone owns file
workstation has whisper GPU
local policy permits crossing
-> send/stream bounded input
-> workstation transcribes
-> receipt returns
-> phone retains result
```

The user asks for an outcome, not a cluster operation.

---

# Experiment backlog

Keep these even if they are not immediate milestones.

### Compute aggregation
- split embarrassingly parallel jobs across old laptops;
- distributed media transcode;
- map/reduce-style hashing/indexing;
- distributed embeddings;
- parallel image batch generation when models/runtime allow.

### Data-local scheduling
- prefer processing on the body already holding private data;
- send model/code to data instead of data to model where practical.

### Store-and-forward
- USB “sneakernet” task bundles;
- QR transfer for tiny crossings;
- Bluetooth transfer;
- intermittent mesh.

### Network transports
- mDNS/zeroconf;
- UDP discovery;
- HTTP;
- WebSocket;
- QUIC;
- BLE;
- LoRa;
- serial;
- local MQTT;
- Wi-Fi Direct.

Transport must remain replaceable.

### Offline knowledge
- portable local document corpus;
- embeddings index;
- local encyclopedia;
- local manuals and repair knowledge;
- task-specific knowledge capsules.

### Local voice
- wake word;
- whisper.cpp;
- Piper;
- streaming audio;
- hands-free command/result loop.

### Local vision
- phone camera as an organ;
- local OCR;
- object detection;
- image generation;
- visual inspection tasks.

### Hardware pantry
- old Android devices;
- old x86 laptops/desktops;
- Raspberry Pi-class SBCs;
- routers capable of OpenWrt;
- ESP32;
- USB accelerators;
- webcams;
- microphones;
- SDR/radio hardware;
- sensors and relays.

### Fault experiments
- kill executor mid-task;
- power off scheduler;
- duplicate task;
- delayed receipt;
- stale offer;
- network partition;
- rejoin after hours/days;
- corrupted local state;
- clock disagreement.

### Trust experiments
- unknown node may advertise but not receive tasks;
- capability-specific trust;
- task-specific approval;
- data sensitivity labels;
- one-time borrowed node;
- revocation;
- signed manifests/receipts.

### Future boot media
- bootable USB GHoT body;
- live Linux image;
- preloaded local models;
- auto-probe on boot;
- local web UI;
- “plug machine in, organism gains a body.”

This is the cleanest modern realization of the old flash-drive JARVIS idea.

# Non-goals for the first implementation

Do not block progress on:

- custom kernel;
- custom phone ROM;
- universal binary format;
- decentralized consensus;
- blockchain;
- autonomous self-modifying code;
- global P2P discovery;
- arbitrary remote shell;
- distributed large-model tensor parallelism across random hardware.

Those may be investigated later. None are required to prove the organism.
