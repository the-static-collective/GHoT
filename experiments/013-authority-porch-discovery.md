# Experiment 013 — Authority Porch Discovery

## Question

Can a remote GHoT body discover the current road to a lease authority without a
hand-written URL while still refusing unknown, stale, or identity-mismatched
authorities?

## Trial A — deterministic trust/discovery model

```bash
python3 ghot/authority_discovery_sim.py
```

The simulation proves:

1. a valid P-256 authority advert verifies;
2. mutation of the signed lease port invalidates it;
3. valid discovery before trust is not eligible;
4. explicit admission makes the authority eligible;
5. the same authority may move to a new observed IP without changing identity;
6. the same key under a different authority_id is not the remembered authority;
7. a pinned authority particular may be accepted without the trust store;
8. a stale signed advert is rejected as current presence;
9. forgetting removes automatic admission.

Expected:

```json
{
  "simulation_passed": true
}
```

## Trial B — real LAN introduction

On the owner:

```bash
python3 ghot/lease_authority.py serve --port 7790
```

On the remote body:

```bash
python3 ghot/authority_discovery.py scan
```

The authority should appear with a valid signed advert and an observed
`authority_url`.

Admit it once:

```bash
python3 ghot/authority_discovery.py trust http://OWNER:7790
```

Inspect:

```bash
python3 ghot/authority_discovery.py trusted
python3 ghot/authority_discovery.py resolve
```

## Trial C — zero-URL organ

With the authority admitted, run:

```bash
python3 ghot/lease_remote.py watch
```

Expected:

```text
discover trusted authority
 -> derive current road
 -> poll
 -> claim selected dispatch
 -> renew
 -> execute
 -> complete
```

No owner URL is passed to the worker.

## Trial D — unknown authority

Run another valid authority with another key that has not been admitted.

Expected:

- `scan` may show it;
- `resolve` does not include it;
- `lease_remote.py watch` does not poll it.

## Trial E — road change

Move/restart the admitted authority at another LAN address while retaining its
authority key and authority id.

Expected: the remote body resolves the new road and continues without a new
trust decision.

## Trial F — forget

```bash
python3 ghot/authority_discovery.py forget <authority-particular>
```

Expected: subsequent discovery remains observable but is no longer eligible for
automatic polling.

## Pass

013 passes when:

- authority adverts are signed and freshness-bounded;
- sender address is transport evidence, not identity;
- discovery does not mutate trust;
- automatic polling requires a local trust record or explicit pin;
- a trusted authority can move roads;
- unknown/mismatched authorities remain unpolled;
- the remote worker can run with no hand-written authority URL;
- the complete pre-013 smoke suite remains green.

## Mutation opened

014 can collapse the two always-on remote processes into one organ daemon:

```text
BODY discovery responder
+ authority discovery
+ trusted porch resolution
+ lease worker
+ liveness heartbeat
+ power offer refresh
= one GHoT organ process
```

That would make joining the organism a single command rather than a small
service choreography.
