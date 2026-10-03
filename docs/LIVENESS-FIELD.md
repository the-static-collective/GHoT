# Liveness Field

Discovery answers:

> Who answered just now?

The Liveness Field answers:

> Who have we known, when were they last seen, what state are they in now, and are they presently eligible to receive work?

Those are different questions.

## V0 body states

```text
                 heartbeat
 UNKNOWN ------------------------> AWAKE
                                      |
                           silence > awake TTL
                                      v
                                    STALE
                                      |
                          silence > depart TTL
                                      v
                                  DEPARTED
                                      |
                                  heartbeat
                                      v
                                    AWAKE
```

Repeated crossing/execution failures add a circuit-breaker path:

```text
AWAKE
  |
  | N consecutive failures
  v
QUARANTINED
  |
  | bounded quarantine expires
  | + body has recent heartbeat
  v
AWAKE
```

A state change does not delete the body.

## Default policy

- awake TTL: 15 seconds
- departed after: 60 seconds without observation
- quarantine threshold: 3 consecutive failures
- quarantine duration: 30 seconds

These are visible V0 policy values, not universal truths.

## Heartbeats

V0 uses active discovery sweeps as heartbeat probes.

```bash
python3 ghot/liveness_field.py sweep
```

Continuous local watcher:

```bash
python3 ghot/liveness_field.py watch --interval 5
```

Each responding body refreshes `last_seen`.

Bodies that stop responding remain in `.ghot/field.v0.json` and age through
`awake -> stale -> departed`.

## Offer TTL

In V0, an offer inherits the freshness of the BODY observation that carried it.

That means a cached `llm.infer.local` offer from a departed workstation
remains historical evidence, but it is not routable.

Future versions can give individual offers independent TTLs.

## Events

Transitions produce durable `ghot.field.event` records:

- `body.arrived`
- `body.stale`
- `body.departed`
- `body.returned`
- `body.failure`
- `body.quarantined`
- `body.quarantine_expired`
- `body.recovered`

The field snapshot is current belief. Events are the trail of how that belief changed.

## Circuit breaker

A node is not permanently condemned for failure.

After the threshold is reached:

1. it becomes `quarantined`;
2. composers must not route new work to it;
3. heartbeat observations may continue;
4. after the bounded quarantine expires, recent liveness may restore eligibility;
5. success clears its consecutive failure count.

This prevents one broken body from being selected on every new composition while preserving its identity and history.

## Laws

- MEMORY OF BODY != ELIGIBILITY OF BODY
- LAST OFFER != CURRENT OFFER
- SILENCE != DELETION
- STALE != DEPARTED
- DEPARTED != FORGOTTEN
- FAILURE != PERMANENT EXILE
- HEARTBEAT != TRUST
- LIVENESS != AUTHORITY
