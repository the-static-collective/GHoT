# Experiment 004 — Capability Composer

## Question

Can a requester name only a capability, allow GHoT to discover available bodies, select one deterministically, explain the selection, cross the task when necessary, and preserve requester/executor provenance?

## Setup

Use two computers on the same LAN.

Machine A:

```bash
python3 ghot/lan_node.py serve --port 7788
```

Machine B may also run a server if you want both bodies independently discoverable, but the composer always includes its own local body automatically.

## Trial A — inspect before acting

On Machine B:

```bash
python3 ghot/capability_composer.py runtime.ffmpeg.version --dry-run
```

Expected:

- local + discovered remote candidates;
- candidates without ffmpeg rejected;
- eligible candidates scored;
- selected node;
- `why_selected`;
- persisted `ghot.plan` record.

## Trial B — force capability locality to matter

Choose an executor available on A but absent on B, such as ffmpeg, llama.cpp, Piper or ImageMagick.

Then:

```bash
python3 ghot/capability_composer.py runtime.ffmpeg.version
```

Expected:

1. B discovers A;
2. B sees A's offer;
3. B selects A without being given A's IP;
4. the task crosses to A;
5. A executes its bounded adapter;
6. receipt names B as requester and A as executor;
7. B receives the result.

## Trial C — preference visibility

If multiple eligible bodies exist:

```bash
python3 ghot/capability_composer.py runtime.ffmpeg.version \
  --no-prefer-local \
  --prefer-memory \
  --prefer-plugged-in \
  --dry-run
```

Verify that each scoring contribution is visible.

## Trial D — capability disappears

1. stop the only node offering a chosen capability;
2. rerun the composer;
3. expect `no-eligible-body`, not an invented fallback.

## Pass

Experiment passes when a human no longer needs to specify the executor address for a capability request and can reconstruct exactly why the selected node was chosen.

## Mutation opened

005 should add **failure-aware recomposition**:

```text
SELECT A
  -> A disappears / rejects
  -> mark attempted result
  -> recompose from remaining live offers
  -> SELECT B
  -> receipt both the failed crossing and successful fallback
```

That turns composition from a one-shot routing decision into resilient organism behavior.
