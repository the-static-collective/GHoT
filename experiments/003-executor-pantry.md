# Experiment 003 — Executor Pantry

## Question

Can GHoT wake up on an unfamiliar computer, inspect the software already present, and convert real installed executables into truthful bounded capability offers?

## Probe the pantry

```bash
python3 ghot/executor_pantry.py
```

or, through the reference node:

```bash
python3 ghot/reference_node.py pantry
```

Compare output on two different computers.

Expected differences may include:

- ffmpeg / ffprobe on one but not the other;
- llama.cpp only on the stronger AI machine;
- Piper / Whisper on a voice machine;
- ImageMagick only on an art machine.

A missing executor must create **no false capability offer**.

## Inspect a real media file

If ffprobe is present:

```bash
python3 ghot/reference_node.py run media.probe "/path/to/local/file.mp3"
```

Expected:

- TASK record;
- execution through the explicit ffprobe adapter;
- structured media metadata;
- RECEIPT record;
- output hash.

## Cross it over the LAN

Start Machine A:

```bash
python3 ghot/lan_node.py serve --port 7788
```

From Machine B:

```bash
python3 ghot/lan_node.py scan
```

The BODY returned by A should now contain its pantry-derived offers.

A remote `media.probe` request is only meaningful for a file already local to A. File crossing is intentionally deferred to a later experiment so data movement remains explicit.

## Pass

Experiment passes when:

1. different machines truthfully advertise different capability sets;
2. installing/removing an executable changes the next BODY probe;
3. `media.probe` executes only when ffprobe exists;
4. the operation produces a normal TASK/RECEIPT trail;
5. no arbitrary command string can be supplied by the requester.

## Why it matters

This is the first literal implementation of:

> **What body did I wake up in?**

GHoT no longer has to be preconfigured around one ideal machine. It can inspect an accidental pile of hardware/software and begin composing from what is actually there.
