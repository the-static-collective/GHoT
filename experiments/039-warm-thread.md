# Experiment 039 — Warm Thread / Pocket-Sized Promise

## Question

Can GHoT compose a present human need with nearby stranded usefulness without
turning capacity into obligation, need into entitlement, or a candidate path
into execution authority?

## Frozen specimen

Four self-declared, unverified local particulars exist:

~~~text
Alice  HAVE  fallen ash tree / wants it removed today
Bob    CAN   cut wood / 45 minutes this afternoon
Cara   CAN   haul one pickup load / eight-mile radius this evening
David  NEED  firewood for home heat tonight
~~~

No one of them owns the solution.

The candidate composition is:

~~~text
fallen tree
   |
Alice RELEASE
   v
Bob CUT
   v
Cara HAUL
   v
David ACCEPT
   |
   v
one possible warm house
~~~

The proposal deliberately withholds the household's exact address and claims no
verification of physical existence, ownership, safety, or human identity.

## Composition before economics

The useful path does not require a common unit, price, score, rank, or token.

~~~text
tree != cutter time != truck trip != household need
~~~

Economics remains an optional later layer. A participant may gift, barter,
redeem a Labor Writ, accept ordinary money, or use a Guild subsidy in another
owned subsystem. Experiment 039 does not choose among those possibilities.

## Gap behavior

Remove Cara's hauling capacity.

The same records now produce:

~~~text
status = gap
missing_relations = ["haul-firewood"]
steps = []
~~~

The system does not silently assume transport, choose a substitute person, or
convert another resource into hauling authority.

## Stepwise authority

Each step names a different local actor and requires a distinct explicit ACT.

Alice may authorize release of the tree.

That creates no authority for Bob.

Bob may authorize one cutting attempt.

That creates no authority for Cara.

Cara may authorize one haul.

That creates no authority for David to accept delivery.

Only when all four exact step authorizations are present does the derived
readiness record say:

~~~text
status = READY
execution_performed = false
~~~

READY still does not execute physical work.

## Laws

~~~text
CAPACITY != OBLIGATION
CANDIDATE != AUTHORIZATION
AUTHORIZATION N != AUTHORIZATION N+1
NEED VISIBLE != ENTITLEMENT
PROPOSAL != EXECUTION
ECONOMIC LAYER != REQUIRED PATH
LOCATION KNOWN != LOCATION RELEASED
~~~

## Producer

~~~bash
python3 ghot/warm_thread.py specimen
python3 ghot/warm_thread.py proposal
python3 ghot/warm_thread_sim.py
~~~

The proposal command is the bounded cross-repo producer intended for the Full
Measure Warm Thread world receiver.

## Closed-loop world residue

The paired Full Measure branch `experiment/warm-thread-world-001` now consumes
the real proposal producer, executes only locally authorized world steps, and
exports honest residue.

The hostile return specimen is:

~~~text
Alice released tree
Bob cut wood
Cara refused haul
David still needs heat
~~~

GHoT consumes that residue as observation-only state and can compose a fresh
child path:

~~~text
completed: release-tree, cut-tree
preserved unchanged
        +
new Erin haul capability
        +
David remaining heat need
        ↓
Erin HAUL
David ACCEPT
~~~

Cara is not scored, blamed, silently reselected, or carried into the child as
an obligation.

~~~text
REFUSAL != DEFECT
COMPLETED STEP != REEXECUTE
RESIDUE != SCORE
RECOMPOSITION != RETROACTIVE AUTHORITY
NEW CANDIDATE != OLD ACTOR OBLIGATION
~~~

## Next aperture

The first composition/world pulse is now closed at the proposal/residue layer.

The next hard seam is real carriage and ordinary-human ingress:

1. carry the proposal and residue through an actual signed reLATTE crossing;
2. keep destination HOLD / explicit ADMIT;
3. admit HAVE / NEED / CAN declarations from a human-facing door such as SMS
   without promoting a message into truth or consent.

~~~text
MESSAGE != TRUTH
MATCH != CONSENT
PHONE NUMBER != HUMAN AUTHORITY
TRANSPORT != ADMISSION
SIGNED != TRUE
~~~
