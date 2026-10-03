# Identity + Automatic Remote Dispatch

Experiment 012 closes two seams at once:

1. portable lease crossings now use the current reLATTE Identity + Signature Profile v0;
2. Wake Composer automatically emits an owner DISPATCH when its energy plan selects a remote body.

The resulting loop is:

```text
HOLD
  -> WAKE
  -> ENERGY PLAN
  -> remote BODY selected
  -> owner verifies BODY has P-256 identity
  -> owner emits identity-bound DISPATCH
  -> remote worker polls
  -> signed CLAIM crossing
  -> owner ADMITTED receipt
  -> remote execution
  -> signed RENEW crossings while active
  -> signed COMPLETE crossing
  -> owner commits HOLD release
  -> EXECUTED receipt
```

## Body identity

A GHoT BODY now advertises:

```text
identity.available
identity.profile = relatte.identity-signature/v0
identity.algorithm = ECDSA-P256-SHA256
identity.particular
identity.public_key { kty, crv, x, y }
```

The body key is local durable state under:

```text
.ghot/identity/body-p256.pem
```

The private key is never advertised.

GHoT derives its body particular from the normalized public key. That is a GHoT identity convention, not a general reLATTE law.

## reLATTE conformance

`ghot/relatte_identity.py` implements the bounded protocol surface GHoT needs:

- P-256 ECDSA with SHA-256;
- reLATTE crossing/receipt domain separators;
- derive-ID-first/sign-ID-plus-body equations;
- canonical unpadded base64url 32-byte JWK coordinates;
- canonical unpadded base64url raw 64-byte ECDSA signatures;
- strict reLATTE timestamps;
- closed root/signing-field guards;
- normalized optional crossing/receipt fields.

Curve operations use the system `openssl` executable so no Python cryptography package is required.

The bounded Python canonicalizer accepts the JSON family GHoT emits in signed records. Runtime floats in signed extensions are converted to identity-safe integers or decimal strings instead of claiming a complete ECMAScript number serializer.

Conformance is tested against the fixed signed genesis crossing and receipt from the reLATTE repository.

## Identity-bound dispatch

Dispatch V1 records:

```text
target_worker_id
target_node_id
target_particular
target_public_key
```

The remote CLAIM must satisfy all of them.

Therefore a process that knows:

```text
hold_id
dispatch_id
worker_id
```

but signs with another P-256 key is refused.

```text
NODE NAME != CRYPTOGRAPHIC BODY
```

## Automatic dispatch

Before 012, the owner needed a manual command:

```text
lease_authority.py prepare ...
```

That command remains as a diagnostic surface, but normal wake flow no longer requires it.

When an ENERGY PLAN resolves to `run_there`:

1. Wake Composer reads the selected BODY identity carried through discovery and scheduling;
2. if the BODY has no usable P-256 identity, the HOLD remains held;
3. if an active dispatch already exists, Wake Composer does not duplicate it;
4. otherwise the owner creates the identity-bound DISPATCH automatically;
5. the HOLD stays active until the remote body completes under the granted lease.

Selection still does not grant authority.

```text
SELECTION != DISPATCH
DISPATCH != CLAIM
CLAIM != EXECUTION
REMOTE EXECUTION != OWNER RELEASE
```

## Remote organ loop

A selected remote body can run:

```bash
python3 ghot/lease_remote.py http://OWNER:7790 watch
```

Its default worker id is its stable GHoT `node_id`, matching automatic dispatch.

The worker signs with the same body P-256 key advertised during discovery.

## Authority identity

The queue owner has a separate durable authority key:

```text
.ghot/identity/authority-p256.pem
```

`GET /authority` advertises its public key and particular.

Remote workers verify every authority ReceiptV0 against that advertised key.

For a trusted-LAN prototype this provides cryptographic continuity after the advert is obtained. On a hostile network, fetching an advert over unauthenticated HTTP does not prove that it is the intended authority.

A deployment may pin:

```bash
GHOT_AUTHORITY_PARTICULAR=<expected-particular>
```

so a substituted authority advert is rejected.

```text
SIGNED ADVERT != TRUSTED INTRODUCTION
```

## Authority split

The owner remains the only component that may:

- create the dispatch;
- grant the lease;
- renew the authoritative lease;
- accept completion;
- commit HOLD release.

The remote body may execute, but cannot make its own execution authoritative.

> EXECUTION MAY ROAM; LEASE AUTHORITY DOES NOT.

## Laws

- SIGNATURE != HUMAN IDENTITY
- KEY POSSESSION != SEMANTIC TRUTH
- GHoT PARTICULAR CONVENTION != reLATTE UNIVERSAL LAW
- DISCOVERY != TRUST
- SELECTION != DISPATCH
- DISPATCH != CLAIM
- CLAIM != EXECUTION
- REMOTE RECEIPT != OWNER RELEASE
- SIGNED ADVERT != TRUSTED INTRODUCTION
- EXECUTION MAY ROAM; LEASE AUTHORITY DOES NOT
