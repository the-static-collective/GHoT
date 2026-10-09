# UNHEARD CHOIR 011 — THE VANISHING WITNESS

**GHoT experiment stacked on 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.**
All source observations, participants, chronology, log histories, trust roots and fork cases remain **simulation-only**. This is **not a network service**, physical-custody proof, native reLATTE crossing or grant to act.

## Problem

010 discovers a fork only when two independently signed observations cross paths. But suppose the observer who has a valid checkpoint loses the transport connection, receives no acknowledgement, restarts, or vanishes before the signed proof reaches the other party.

011 separates the **evidence**, **delivery attempt**, **receiver-local receipt**, **acknowledgement**, and **anti-entropy hint**. They are different objects with different authority boundaries.

## Executable world

```text
WEST has locally verified 009 log A: A B C D E F
EAST has locally verified 009 log B: A B C D F E
Both are validly co-witnessed, yet incompatible.

1. WEST signs one-hop scoped envelope:
   010 public package + exact recipient EAST + 010 roster/policy digest
   Envelope ID = SHA-256 of complete signed envelope.

2. WEST writes signed envelope to its own SQLite outbox, COMMIT.
   Simulated network drops first message.
   WEST's outbox remains PENDING.

3. WEST opens the outbox in a new session and resends bytes already durably staged.
   EAST recomputes all 001–010 inherited P-256 evidence.
   EAST compares its own 010 package with the incoming WEST package.
   → HOLD_GOSSIP_REVEALS_UNSEEN_FORK.

4. EAST signs an acknowledgement bound to:
   exact envelope digest, roles, EAST's own full signed 010 package,
   exact fork-comparison digest, monotonically numbered inbox receipt
   and previous local signed ACK digest.
   EAST commits both the incoming envelope and signed ACK in its own SQLite inbox.

5. Simulated network drops the ACK.
   WEST remains PENDING. Durable evidence is not destroyed or overwritten.

6. EAST signs bounded inbox inventory of delivery IDs and ACK digests.
   WEST recognizes "ACK_RECOVERY_NEEDED" but does NOT mark delivery confirmed.
   Inventory is a signed *hint*, not authenticated receipt transfer.

7. WEST resends the same signed envelope.
   EAST returns the **identical persisted signed ACK**.
   EAST makes no duplicate receipt or native effect.

8. WEST verifies the ACK P-256 signer, exact envelope ID and matching
   EAST-owned 010 signed package; it independently recomputes the fork.
   WEST records the actual valid ACK durably before showing ACKNOWLEDGED.
```

## New boundaries

- `ghot/unheard_choir_vanishing.py` imports, rather than replaces, the exact 010 authority checks. It verifies that the sender's package is a genuine 010 signed isolated review result, and that the recipient's own independently signed view contradicts it under the same 009 policy, epoch and log size.
- Only the pinned sender-site P-256 key can sign a `SIGNED_FORK_EVIDENCE_NOT_PERMISSION` envelope for the other specific observer site. No foreign sender, recycled key, unauthorized hop limit or role spoofing.
- Only the pinned recipient-site P-256 key can sign the `SIGNED_OWNER_LOCAL_DELIVERY_RECEIPT_NO_EFFECT` ACK. Its payload includes the full recipient signed 010 package and calculated 010 fork assessment digest; the sender **cold-recomputes** that comparison before accepting it.
- `stage_once` and `receive_once` use SQLite `BEGIN IMMEDIATE` transactions, `synchronous=FULL`, unique ID constraints and bounded 64-entry local storage. Duplicates return the exact existing record. Writes validate local signed history before mutation.
- `confirm_once` retains an authenticated signed ACK, refuses missing staged deliveries, forged or equivocated ACKs, and cannot turn an inventory hint into a receipt.
- `make_inventory` signs a bounded, sorted list of locally received envelope IDs and signed ACK digests. `reconcile` distinguishes `pending_resend`, `ack_recovery_needed` (still pending!) and `acknowledged` (verified receipt recorded).
- Read-only verification can occur in a new Python interpreter **with only public JSON evidence and pinned public keys**, not the private key files or sender's database.
- 010's local observation journals remain unchanged by the 011 transfer. The recipient controls the recipient inbox, and gossip from a peer cannot overwrite it or the sender's SQLite outbox.

## Epistemic and operational limitations

There is **no actual network transport** in 011. Message drops, restart/resumption, lost ACKs and gossip are deterministic local simulations. The sample program instantiates two SQLite databases and explicitly passes signed evidence between Python functions. Production networking, authentication at transport ingress, NAT, routing, packet throttling, offline peers and consent gates need separate implementations.

SQLite is *not* an append-only tamperproof remote ledger. A privileged operator can delete, roll back or replace a file. Signature-linked receipts detect mutations relative to a verifier's existing trusted signed tip, but do not alone prevent full rollback. Existing cryptographic receipt hashes are **not native reLATTE signed RECEIVEs**.

An ACK cryptographically authenticates a **recipient's claimed receipt** of a specific package in the bounded protocol and demonstrates independently recomputable disagreement between two simulated signed views. It does not prove external physical receipt, independent ownership, actual human contact, real transport delivery, or truth of the original measurements.

A signed inventory can lie, omit entries, or be stale. It is **never final acknowledgement**. Lack of an inventory entry is not proof that a packet was lost.

### Laws

```text
STAGED != SENT
SENT != DELIVERED
INVENTORY HINT != SIGNED ACK
RETRIED PACKET != NEW WORK
ACK SIGNATURE != REAL HUMAN RECEIPT
SQLITE PERSISTENCE != EXTERNAL IMMUTABILITY
TRANSPORT FAILURE != EVIDENCE DEATH
GOSSIP != OWNER AUTHORITY
DETECTED FORK != SELECTED TRUTH
LOCAL SHA DIGEST != NATIVE reLATTE RECEIPT
LOST ACK != PROVEN NONDELIVERY
NO MESSAGE != NO WORLD
```

## Execute

From GHoT root (Python 3 standard library and OpenSSL):

```bash
python3 ghot/unheard_choir_vanishing.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_vanishing.py' -v
```

The demo generates ephemeral P-256 keys, one full 010 split-history fixture, two 010 SQLite observation journals, and two separate 011 SQLite outbox/inbox databases. Keys are held only within temporary fixture storage, then discarded.

The read-only `verify` CLI takes all seventeen public 008 source artifacts, `--log-policy`, `--log-root`, `--gossip-roster`, `--gossip-root`, `--envelope`, `--ack` and `--now`. It rejects a forged ACK and cold-replays the entire original source and 010 comparison without any private keys.

CI runs inherited 001–010 hostile tests, then the 011 drop/retry/forgery/inventory/recovery matrix, and finally the standalone demo assertions.

## 012 frontier — THE DEAD LETTER THAT CAME HOME

011 stores one durable transfer and delivers it through direct local method calls. To prove a real cross-vessel transport handoff, add a bounded, offline file-based mailbag with import/export custody receipts, TTL/epoch/reconstitution handling, destination owner-local rejection and explicit 010/011 evidence availability after either node permanently disappears. Reuse real reLATTE portable crossing/RECEIVE/HOLD formats only when the native source/receiver integrations and grants are actually available. Preserve the distinction between **portable transport** and **owner-local admission**.
