# Authority Porch Discovery

Experiment 013 removes the last required hand-wired authority URL from the
normal remote-organ loop without turning LAN discovery into authority.

Core separation:

```text
ROAD != IDENTITY
DISCOVERY != TRUST
SIGNED ADVERT != ADMISSION
```

## Porch advert

The lease authority broadcasts a short-lived signed advert on a dedicated UDP
discovery port.

The signed identity-bearing fields include:

```text
authority_id
owner_node_id
world_id
particular
public_key
capability_ref
crossing_schema
receipt_schema
signing_profile
algorithm
lease_port
crossing_path
issued_at
ttl_seconds
```

The sender IP address is not included in the signed identity body.

A receiver derives:

```text
authority_url = http://<observed sender address>:<signed lease_port>
```

That URL is a road observation. The P-256 particular/public key is the authority
identity witness.

## Signed advert profile

Authority adverts use:

```text
ECDSA-P256-SHA256
ghot.authority-advert-signature/v0
```

with a domain-separated advert id and signature body.

An advert is rejected if:

- the signature fails;
- the advert id no longer derives;
- the particular no longer matches the public key under GHoT's convention;
- required protocol fields differ;
- the advert is stale.

Default advert TTL is 15 seconds.

A captured valid advert therefore remains historical evidence but is not a
permanent liveness claim.

## Trust store

Discovery never writes trust automatically.

Explicit operator admission:

```bash
python3 ghot/authority_discovery.py trust http://OWNER:7790
```

persists:

```text
.ghot/trust/authorities.json
```

A trust record binds:

```text
particular
public_key
authority_id
world_id
admitted_at
last_route
```

A later discovery is accepted only when the signed advert matches that identity
record exactly.

The remembered route is informational. It is not used as identity authority.

## Pinning

An operator may bypass the local trust store by supplying:

```bash
GHOT_AUTHORITY_PARTICULAR=<expected-particular>
```

A discovered advert with another particular is ignored.

Pinning is an external trust input. Discovery does not infer it.

## Remote organ flow

After one explicit introduction, normal operation becomes:

```text
REMOTE BODY BOOTS
  -> authority discovery broadcast
  -> signed porch adverts arrive
  -> verify cryptographic advert
  -> compare with local trust / pin
  -> derive current road
  -> POLL
  -> owner DISPATCH if any
  -> CLAIM / RENEW / COMPLETE
```

Command:

```bash
python3 ghot/lease_remote.py watch
```

No authority URL is required.

The older explicit form remains valid:

```bash
python3 ghot/lease_remote.py http://OWNER:7790 watch
```

That explicit route is treated as an operator-selected road, while the returned
authority advert and all receipts are still cryptographically verified.

## Road migration

If the same authority moves from one LAN address to another:

```text
10.0.0.5 -> 10.0.0.77
```

the remote organ may follow the new road without a new trust decision when:

```text
particular == remembered particular
public key == remembered public key
authority_id == remembered authority_id
world_id == remembered world_id
```

Thus:

```text
ROAD CHANGE != IDENTITY CHANGE
```

## Same-key boundary

GHoT's local trust record binds more than public key possession.

If the same key is presented under a different authority_id/world_id, the
remembered authority does not match.

This is owner-local trust policy, not a universal reLATTE identity rule.

## Forgetting

```bash
python3 ghot/authority_discovery.py forget <authority-particular>
```

removes local admission.

The next discovery of that authority remains visible to scan, but it is not
eligible for automatic polling unless separately pinned.

## Scope

013 does not provide:

- TLS;
- DNS identity;
- public PKI;
- human identity;
- global authority registries;
- automatic trust-on-first-use;
- WAN rendezvous;
- NAT traversal.

It proves a smaller statement:

> A body can discover where a previously admitted authority currently is
> without making location the authority.

## Laws

- ROAD != IDENTITY
- DISCOVERY != TRUST
- SIGNED ADVERT != ADMISSION
- FRESH != TRUSTED
- TRUSTED != HUMAN IDENTITY
- PREVIOUSLY ADMITTED != PERMANENTLY ONLINE
- ADDRESS CHANGE != AUTHORITY CHANGE
- FORGET != ERASE HISTORY
