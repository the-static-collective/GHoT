# Capability Composer

The Capability Composer is the first layer where the heap chooses a body by capability rather than requiring a human to name a machine.

The user asks:

> I need `runtime.ffmpeg.version`.

The composer asks:

1. what bodies are currently visible?
2. which truthfully offer the capability?
3. which violate hard constraints?
4. how do the remaining candidates score under explicit preferences?
5. which body is deterministically selected?
6. why?

Only after that does execution occur.

## Law

**RECOMMENDATION != SELECTION != EXECUTION**

The plan is persisted independently of the task and receipt.

That gives the later system something inspectable to disagree with.

## V0 policy

Hard filter:

- exact capability offer must exist;
- known battery must satisfy `--min-battery` when supplied.

Optional preferences:

- local body: +100;
- powered/charging: +30;
- memory: +1 per GiB, capped at +64.

Default policy prefers local execution because it minimizes unnecessary crossing. Disable this with `--no-prefer-local`.

Equal scores resolve lexically by `node_id`, making the same candidate set reproducible.

These numbers are not claims about universal optimality. They are deliberately visible V0 policy constants.

## Examples

Inspect a plan without executing:

```bash
python3 ghot/capability_composer.py runtime.ffmpeg.version --dry-run
```

Require known batteries not to be below 25%:

```bash
python3 ghot/capability_composer.py runtime.ffmpeg.version \
  --min-battery 25 \
  --dry-run
```

Prefer stronger memory and powered nodes:

```bash
python3 ghot/capability_composer.py runtime.ffmpeg.version \
  --prefer-memory \
  --prefer-plugged-in
```

If the required capability only exists on another body, the composer selects its advertised route and crosses the bounded task automatically.

## Provenance repair

Experiment 004 also corrects an earlier V0 simplification: remote execution now preserves the original `requester_node_id` and plan constraints rather than recording the executor as though it requested its own task.

The resulting trail becomes:

```text
requester
  -> PLAN
      -> selected executor
          -> TASK carrying requester + plan_id
              -> local execution
                  -> RECEIPT carrying requester + executor
```

This matters for later reLATTE integration.

## Intentional limits

V0 does not yet:

- measure queue depth;
- benchmark executors;
- infer GPU capability;
- move files between bodies;
- know whether unknown battery state should be disqualifying;
- optimize cost/latency;
- retry on selected-body failure;
- select multiple bodies for one job.

Those are experiments, not hidden behavior.
