# Experiment 040 — TenetGram

## Question

Can every attributable consequence leave at least one bounded future possibility
somewhere explicitly connected to the participant who carries it forward,
without turning that possibility into a notification, recommendation, request,
obligation, score, or execution command?

## Compression

A TenetGram has two faces:

~~~text
PAST  <-  [ TENETGRAM ]  ->  FUTURE

BACK
what actually happened

FRONT
what could become possible next
~~~

The back face is an attributable consequence reference.

The front face contains one or more **dormant possibility seeds** addressed only
through explicit actor-to-field links.

## Founding invariant

A valid TenetGram cannot exist without an explicit connected field.

~~~text
CONSEQUENCE
    |
    v
explicit actor -> field relation
    |
    v
DORMANT POSSIBILITY SEED
~~~

This is the bounded protocol meaning of:

> using TenetGram always seeds future possibility somewhere connected to you.

It does **not** mean every message wakes another person up, requests labor, or
predicts what should happen next.

## Frozen specimen

The first donor consequence comes from Warm Thread World 001:

~~~text
Alice released the fallen tree
Bob cut it into firewood
Cara declined the haul
David still needs heat tonight
~~~

That world state already has its own Warm Thread recomposition path.

TenetGram does something orthogonal.

Alice has two explicit possibility-routing relations:

~~~text
alice -> neighborhood-a  [local-neighbor]
alice -> garden-circle   [explicit-member]
~~~

Bob also has an unrelated link:

~~~text
bob -> tool-circle
~~~

When **Alice** emits the TenetGram, only Alice's two explicit relations are
eligible. Bob's relation does not become Alice's routing authority.

The result carries two dormant seeds:

~~~text
neighborhood-a:
  "What becomes possible next from this consequence?"

garden-circle:
  "What becomes possible next from this consequence?"
~~~

No specific new capability is inferred.

The protocol does not automatically claim:

- Alice now has garden space;
- Bob is available to cut another tree;
- Cara should haul next time;
- David should request more help;
- the neighborhood should be notified.

Specific composers may later derive narrower candidate possibilities from richer
evidence, but the base TenetGram never needs to invent one in order to satisfy
its founding invariant.

## Explicit field relation

The first field-link contract says only:

~~~text
actor
field
relation
allowed seed kinds
allows seed delivery = true
allows notification = false
allows request = false
allows execution = false
authority = routing-consent-only
~~~

Thus:

~~~text
RELATION != BROADCAST
FIELD MEMBERSHIP != LABOR CONSENT
SEED DELIVERY != NOTIFICATION
~~~

## Receiving a seed

The receiving field may project the seed as:

~~~text
status = visible-dormant
admitted = false
requested = false
notified = false
executed = false
authority = projection-only
~~~

A later owning subsystem may explicitly admit, inspect, enrich, request, or
discard it under its own rules.

## Laws

~~~text
CONSEQUENCE -> POSSIBILITY

POSSIBILITY != REQUEST
POSSIBILITY != RECOMMENDATION
POSSIBILITY != OBLIGATION

SEED != NOTIFICATION
RELATION != BROADCAST
TRANSPORT != ADMISSION

PAST RECEIPT != FUTURE COMMAND
ONE PERSON'S RELATION != ANOTHER PERSON'S ROUTING AUTHORITY
~~~

## Why this is not recursive soup

TenetGram does not recursively generate another TenetGram merely because a seed
exists.

A new generation requires another attributable consequence.

~~~text
possibility seed
    |
    | human/world crossing
    v
actual consequence
    |
    v
next TenetGram generation
~~~

Therefore:

> **TENETGRAM RECURSION REQUIRES CONSEQUENCE BETWEEN GENERATIONS.**

## CLI

~~~bash
python3 ghot/tenetgram.py specimen

cat full-measure-residue.json \
  | python3 ghot/tenetgram.py emit \
      --issuer alice \
      --field neighborhood-a \
      --relation local-neighbor
~~~

## Telegram re-entry

Telegram is a natural carrier for a TenetGram, but not its authority.

The next paired specimen should let the existing PORCH-001 design receive and
render a TenetGram as a read-only card.

It may show:

~~~text
Something happened.
A future door exists here.

[Inspect]
~~~

It may not turn receipt into notification pressure, infer a task, or mutate
gramfork merely because a TenetGram arrived.

~~~text
TELEGRAM = PORCH
TENETGRAM = PORTABLE POSSIBILITY
GRAMFORK = SPECIALIZED PROVISION AUTHORITY
GHOT = POSSIBILITY COMPOSITION
FULL MEASURE = INHABITED CONSEQUENCE
RELATTE = BOUNDED CROSSING
~~~
