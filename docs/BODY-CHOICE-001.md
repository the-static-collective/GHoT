# BODY CHOICE 001 — OFFER != ASSIGNMENT

## Purpose

The capability composer can automatically rank bodies. That is useful for machine scheduling.

The House needs a different surface: **show the bodies first, then let an external human-facing layer name one explicitly.**

This slice adds that surface without changing the automatic composer.

```text
DISCOVER
   ↓
BODY/OFFER SNAPSHOT
   ↓
BODY-CHOICE OFFER
   ↓
human/external selection
   ↓
ASSIGNMENT
   ↓
revalidate selected body
   ↓
EXECUTION
   ↓
GHOT RECEIPT
```

## Laws

```text
DISCOVERY != TRUST
OFFER != ASSIGNMENT
CAPABILITY != AUTHORITY
ASSIGNMENT != EXECUTION
EXECUTION != RECEIPT
RECEIPT != TRUTH
```

## Offer

The offer contains every currently observed candidate and marks each as eligible or rejected for the requested capability.

There is deliberately no `selected` field.

The offer id is content-derived from the exact observed candidate set.

## Assignment

The caller returns:

- the exact offer;
- one `selected_node_id`;
- the bounded payload;
- an attributable `selection_source`.

GHoT refuses assignment when:

- the node was not present in the offer;
- the node was ineligible in the offer;
- the body is no longer discoverable;
- the body is no longer awake;
- the capability is no longer offered;
- a remote body has no execution route.

The chosen body is revalidated at assignment time.

## Execution

V0 uses the existing bounded reference-node execution surface.

Local choice calls `reference_node.execute()`.

Remote choice calls the existing LAN `request_task()` route.

No arbitrary shell capability is added.

## Human-facing composition

A user-facing system may truthfully render:

> Three bodies are awake and currently offer this capability. Choose one.

It may not truthfully render that sentence when only one body is observed.

It should not silently select the highest-scoring body when using this surface. Automatic scheduling remains a separate capability-composer behavior.
