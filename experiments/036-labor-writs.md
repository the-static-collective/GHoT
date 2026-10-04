# Experiment 036 — Labor Writs

## Question

Can the old Lightwalker **Labor Writ** become an actual portable future-work
instrument while preserving sovereignty, bounded scope, expiry, delegation
limits, one-time redemption, and replay refusal?

## Object

A Labor Writ is an issuer-signed promise:

~~~text
issuer
  promises
one bounded scope of future work
  to
current holder
  before
expiry cut
~~~

It is deliberately not money, a balance, a human-worth score, proof of completed
work, or blanket execution authority.

## Frozen lifecycle

~~~text
ISSUE
  |
  v
portable Labor Writ
  |
  +--> HOLD / ADMIT at receiver
  |
  v
optional bounded DELEGATION
  |
  v
REDEMPTION REQUEST
  |
  v
issuer-local atomic claim
  |
  v
REDEEMED / EXHAUSTED
  |
  v
actual bounded work
  |
  v
terminal PERFORMANCE RECEIPT
~~~

The original Writ never changes.

## Portability

The issuer may send the Writ in a signed reLATTE-shaped crossing.

The request explicitly says:

~~~text
automatic_redemption_requested = false
execution_authority_requested = false
~~~

The receiver still performs HOLD followed by explicit local ADMIT. Receiving a
Writ does not redeem it.

## Delegation

The experiment issues one Writ with bounded delegation and exactly one allowed
hop. Holder A may delegate it to Holder B. Holder B may not delegate it again.

The delegation carries the original writ ID and scope digest. It cannot expand
scope or extend expiry.

**DELEGATION MOVES A CLAIM; IT DOES NOT REWRITE THE PROMISE.**

## Redemption

Only the current holder may sign a redemption request.

The issuer-local store then performs an atomic exclusive claim keyed by the
Writ ID.

Successful redemption creates a signed receipt with:

~~~text
status = REDEEMED
writ_exhausted = true
performance_completed = false
~~~

**REDEMPTION CREATES THE ACTIVE OBLIGATION. IT DOES NOT PRETEND THE WORK IS
DONE.**

## Replay refusal

036 exercises both replay forms:

1. the exact same redemption request is replayed;
2. a fresh second redemption request is created for the same Writ.

Both must fail after the first successful redemption.

~~~text
ONE WRIT -> AT MOST ONE REDEMPTION
~~~

## Expiry

A separate short-lived Writ is redeemed after its expiry cut. The request is
refused before issuer-local activation.

Expiry limits the holder's right to exercise the promise; it does not rewrite
the old Writ.

## Performance

After redemption, the issuer performs the bounded work and issues a separately
signed terminal performance receipt.

The receipt may say FULFILLED or FAILED. Either way, the already-redeemed Writ
remains exhausted.

This avoids a semantic collapse where failed performance silently regenerates a
redeemable claim.

## Composition with Experiment 035

036 turns the Writ back into a typed heterogeneous-exchange obligation:

~~~text
hosting-service
      <->
future-labor-writ
~~~

The exchange references the writ ID, scope digest, expiry, and delegation
policy, but does not turn the Writ into currency.

## Laws

~~~text
WRIT != MONEY
WRIT != PERFORMANCE
PORTABILITY != AUTHORITY
DELEGATION != REWRITING
REDEMPTION != PERFORMANCE
ONE WRIT -> AT MOST ONE REDEMPTION
EXHAUSTION DOES NOT PROVE PERFORMANCE
PERFORMANCE FAILURE DOES NOT UNSPEND A REDEEMED WRIT
~~~

## Next aperture

The next old-Lightwalker object ready to become machinery is the **Guild
Treasury**.

The interesting version is not one balance. It is a sovereign inventory of
heterogeneous claims: active Labor Writs, settlement receipts, compute capacity,
storage commitments, artifact rights, local credits, and ordinary money
references.

A Guild could then publish a local resource/solvency view without pretending
everything collapses into one universal number.
