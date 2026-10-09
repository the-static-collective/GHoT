# THE WORLD THAT ASKS BACK — 002

This experiment is a separate stacked draft on WORLD-ASKS-BACK-001 (#93).

## Proven distinction

001 was an eleven-instrument, three-identity, strictly simulated discovery
that inferred a missing hinge repair from declared conditions. 002 does not
silently promote the virtual 3D printer to hardware or reuse 001 permissions.

Instead, 002 makes an authentic native GHoT system.hash execution of the
exact canonical inferred-work proposal. It requires:

1. Revalidate GHoT's current local system.hash offer.
2. Bind that offer, proposal, observation cut, and unique nonce into a new
   source-owner P-256 reLATTE crossing.
3. Require THREE new native-work grants, signed by the fixture's sovereign
   owner keys, each binding role, proposal, cut, crossing, offer, capability,
   scope, and expiry. 001 APPROVE_SIMULATION grants cannot authorize 002.
4. Submit crossing to a separately provisioned, independently policy-pinned,
   actual reLATTE LocalReceiver via the partner script in reLATTE #88.
5. Native RECEIVE / R3_HOLD with no consent, or native RECEIVE / R3_ADMIT
   with full native-work grants.
6. Pin receiver signing public key from initial local bootstrap; verify exact
   native receiver P-256 receipts against that key.
7. Recheck actual GHoT native offer, then invoke existing GHoT
   reference_node.execute(system.hash), whose current-offer gate runs again.
8. Verify the SHA-256 output and produce a separate GHoT-local signed
   EXECUTED witness linking crossing, native R3_ADMIT and native task/receipt.

The R3_ADMIT grants only local hashing. No claim of actual physical hinge
printing is possible. Any person claiming a printed part, real inventory
consumption or economic production from this experiment contradicts evidence.

## Integration commands

Prepare this GHoT branch (experiment/world-asks-back-002) alongside
reLATTE branch (experiment/wab-native-receiver-002), with Node 24 and
dependencies installed via npm install in reLATTE.

    cd GHoT
    python3 ghot/world_asks_back_native.py demo ../reLATTE
    python3 ghot/world_asks_back_native.py hold ../reLATTE

For hostile tests:

    export RELATTE_ROOT="$(realpath ../reLATTE)"
    python3 -m unittest discover -s tests -p 'test_world_asks_back.py' -v
    python3 -m unittest discover -s tests -p 'test_world_asks_back_native.py' -v

Both demonstrations use disposable fixture owner P-256 keys and native
receiver state. The actual SHA operation runs locally in the first;
the HOLD world intentionally never invokes GHoT execute.

## Boundaries

Discovery does not assert world completeness. Local BODY is not a remotely
authenticated independent offer. A simulation-approved resource cannot grant
another capability. A packet self-declared signing key is not actual human
identity. A native RECEIVE and R3_ADMIT are not physical work. The 002
EXECUTED witness reports only actual local hashing, not external work.

This is a real cross-process and cross-language seam, not a three-machine LAN
test, 3D-print adapter, manufacturing certification, or receipt for human
benefit. Physical work remains a separate experiment requiring authenticated
humans, mechanical safety interlocks, independent stock custody, and witnessed
inspection and delivery.

## Branches and review

- https://github.com/the-static-collective/GHoT/pull/93 — prerequisite
- https://github.com/the-static-collective/GHoT/pull/94 — this integration
- https://github.com/the-static-collective/reLATTE/pull/88 — native policy bridge

Merge parent-first only after both independently reviewable branches and
their integration CI are green.
