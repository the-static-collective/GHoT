# FIELD COMMONS 001

## Question

Can a verified mathematical WANT obtain real compute through a voluntary
heterogeneous exchange, a sovereign Guild treasury, and bounded execution
authority without inventing a coin or letting economic settlement become
artifact admission?

## First exchange

```text
artifact owner
  offers:
    read-only access to one verified Ice Cube artifact

Guild
  offers:
    one bounded Ice Cube compute service
```

There is no common unit, exchange rate, universal price, or token balance.

## Path

```text
verified pantry
    |
    v
Ice Field WANT
    |
    v
heterogeneous offer
    |
    v
explicit Guild acceptance
    |
    v
Guild treasury shows compute capacity
    |
    | CAPACITY != AUTHORIZATION
    v
resource proposal for exact WANT
    |
    v
steward-signed one-shot authorization
    |
    v
Field Commons atomically claims authorization
    |
    v
ordinary GHoT energy/capability scheduling
    |
    v
selected compute body
    |
    v
Ice Cube mining
    |
    v
worker Dogram verification
    |
    v
032 verified return crossing
    |
    v
requester HOLD
    |
    +----------------------------+
    |                            |
    | economic performance       | artifact authority
    v                            v
Guild execution receipt       still HOLD
    |                            |
artifact access grant           |
    |                            |
two role-local attestations      |
    |                            |
bilateral settlement             |
                                 |
                         requester-local Dogram
                                 |
                                 v
                            owner ADMIT
                                 |
                                 v
                          explicit pantry merge
                                 |
                                 v
                           Ice Field grows
```

## Economic boundary

The heterogeneous settlement may complete while the returned cube remains only
a HOLD candidate.

That is intentional.

```text
SETTLEMENT != VERIFICATION
SETTLEMENT != ADMISSION
PAYMENT/PERFORMANCE != OWNERSHIP
```

The compute obligation for this specimen is fulfilled by:

- successful GHoT execution;
- worker-side Dogram status OK;
- a return result accepted only as receiver HOLD.

The destination must still independently verify and ADMIT the artifact.

## Guild boundary

The treasury carries two units of:

```text
ice-cube-job
```

The accepted exchange does not spend them.

The visible treasury does not spend them.

A proposer asks to apply exactly one job to the exact Ice Field WANT.

The Guild steward signs one bounded authorization.

Field Commons refuses dispatch when that authorization is absent or invalid.

Before scheduling, the Commons atomically claims the authorization ID so the
same permission cannot start two jobs.

After a successful job, the existing Guild execution receipt consumes one
native `ice-cube-job` unit and the next treasury snapshot exposes one remaining
job.

No financial equivalence is inferred.

## Artifact-access performance

The artifact owner fulfills the other side by signing a bounded read-only
access grant over the exact offered artifact.

The grant says:

```text
ACCESS != OWNERSHIP
ACCESS != ADMISSION
GRANT != UNIVERSAL LICENSE
```

The heterogeneous offer then receives two independent role-local performance
attestations and may settle as bilateral evidence.

## Power placement

Field Commons does not choose a machine.

It delegates the accepted, authorized WANT to the ordinary GHoT Ice Field
dispatch path:

```text
urgency = background
deferrable = true
prefer surplus = true
```

The integration proof presents:

```text
local body  = normal battery
remote body = abundant renewable surplus
```

and requires the ordinary energy scheduler to select the remote body.

## Proof

CI runs:

```bash
python3 ghot/field_commons_sim.py --dogram-repo _dogram_ice
```

The simulation proves:

1. one verified seed cube enters the pantry;
2. Ice Field opens a `lucas-next` WANT;
3. artifact access is offered for one compute service;
4. the Guild explicitly accepts;
5. the Guild treasury exposes two native `ice-cube-job` units;
6. missing authorization refuses before scheduling;
7. a steward signs one exact authorization for the WANT;
8. the ordinary GHoT scheduler selects the surplus remote body;
9. the remote body mines the child and Dogram returns OK;
10. the child returns to the requester as HOLD;
11. the Guild execution receipt consumes one native compute job;
12. artifact access + compute performance settle bilaterally;
13. settlement occurs while the child remains unverified HOLD locally;
14. replay of the same Guild authorization is refused;
15. requester-local Dogram then verifies the returned child;
16. owner-local ADMIT and explicit pantry merge occur separately;
17. the original WANT becomes satisfied;
18. a second Ice Field generation appears.

## Laws

```text
COMMONS != CURRENCY
WANT != OFFER
OFFER != ACCEPTANCE
ACCEPTANCE != TREASURY AUTHORITY
CAPACITY != AUTHORIZATION
AUTHORIZATION != EXECUTION
EXECUTION != SUCCESS
EXECUTION != VERIFIED RETURN
SETTLEMENT != VERIFICATION
SETTLEMENT != ADMISSION
WORKER VERIFICATION != RECEIVER VERIFICATION
ADMISSION != MERGE
RESOURCE USE != UNIVERSAL PRICE
```

FIELD COMMONS 001 therefore demonstrates a bounded self-funding exploration
loop whose economic coordination does not require a native coin.
