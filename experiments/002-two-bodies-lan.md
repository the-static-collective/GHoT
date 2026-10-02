# Experiment 002 — Two Bodies on an Offline LAN

## Question

Can two ordinary machines discover one another on a LAN, cross a bounded task, execute on the remote body, return a receipt, and survive the remote body's disappearance?

## Requirements

- two computers on the same LAN;
- Python 3.10+;
- this repository copied/cloned to both;
- no internet required after the files are present.

For the cleanest test, disconnect the router's WAN link or use an isolated Wi-Fi access point.

## Machine A — expose a body

```bash
python3 ghot/lan_node.py serve --port 7788
```

The node listens for GHoT discovery on UDP port `47888` and bounded tasks over HTTP `7788`.

## Machine B — discover bodies

```bash
python3 ghot/lan_node.py scan
```

Expected: a `ghot.here.v0` response containing Machine A's node id, address, HTTP port and BODY declaration.

## Machine B — cross a task

Replace the URL with the one returned by scan:

```bash
python3 ghot/lan_node.py task http://192.168.1.10:7788 system.echo "hello other body"
```

Then:

```bash
python3 ghot/lan_node.py task http://192.168.1.10:7788 system.hash "the heap remembers"
```

Expected: a remote TASK and RECEIPT.

## Failure test

1. Stop Machine A.
2. Run `scan` again from Machine B.
3. Machine A should no longer appear.
4. Run local Phase 0 commands on Machine B.

Pass condition: loss of Machine A removes its capability surface but does not damage Machine B's local identity or records.

## Safety boundary in V0

Remote execution is deliberately limited to the built-in allowlist:

- `system.echo`
- `system.hash`
- `system.info`

There is no arbitrary remote shell.

## What this proves

If this passes, the oldest useful claim is no longer speculative:

> a processor can arrive as a body, describe itself, perform bounded work for another body, receipt the work, and disappear.

Experiment 003 should replace toy capabilities with real executor adapters such as ffmpeg and llama.cpp.
