# POSTAL-CORPS-002 — The Carrier's Pocket

**Research-only signed custody-claim simulator.** No real parcels, carrier service, wages, postage, PENNY tokens, Full Measure Deeds, physical custody or delivery have been produced.

## Architecture

The existing POSTAL-CORPS-001 signers and role state machine remain authoritative. The new offline handoff has six steps:

1. The issuer has a signed route with six independent public role keys, a pinned LemonPRESS source dispatch and a valid current event history.
2. The issuer creates a short-lived challenge containing the exact native route event body, parcel hash, evidence hash, prior history hash, initiator/responder, sequence and random nonce. It signs both the challenge and the original custody-event body.
3. A recipient reviews that signed request on a mobile-friendly, offline-cacheable browser screen and manually signs it with a nonexportable WebCrypto P-256 key (or uses the local GHoT CLI).
4. The response contains a role signature on the exact original event body and a second signature acknowledging the exact QR challenge. The browser persists the response to IndexedDB before showing the result for transfer.
5. The issuing GHoT SQLite journal verifies both signatures, still-current route state, exact issued nonce and role pins. On success, it atomically appends one signed event under SQLite WAL. It refuses stale, forged, duplicate or conflicting inserts.
6. After losing connectivity, a participant can recover its own outbox response, and a different journal can import an ordered signed history only when it extends its exact existing prefix. Divergent histories generate HOLD_FORK.

A signed handoff is **a claim**, not independent proof the item physically moved.

## Device enrollment and QR support

The prototype browser lives at web/carrier-pocket/index.html. It has PWA manifest and offline-cache service worker, local P-256 keypair storage in IndexedDB, public-key export, source-route signature verification, signed QR inspection and optional camera BarcodeDetector with paste fallback, direct human acknowledgment, and offline response recovery.

A browser key must be enrolled into the origin-signed route **before use**. Run the optional native setup helper with a JSON object of six public P-256 JWKs, the LemonPRESS fixture, the origin's separate private P-256 key and a sample parcel digest:

    python3 test/carrier_pocket_setup.py sign-route --dispatch dispatch.json --public-roles roles-public.json --origin-key origin.pem --parcel-sha256 <64-hex-sha256> --out route.json

For QR PNG display, install the optional qrcode[pil] Python package:

    python3 test/carrier_pocket_setup.py qr-png --challenge offer.json --out offer.png

It encodes only the signed synthetic request. No private key or street address is transmitted in a QR.

## Offline GHoT CLI demonstration

With a source-enrolled route and valid preceding POSTAL-CORPS-001 signed event history:

    python3 ghot/carrier_pocket.py --route route.json --dispatch dispatch.json --db station.sqlite3 issue --action PICKUP_LEG1 --key origin.pem --evidence-sha256 <64-hex-sha256> --out offer.json

A second independent journal may return the QR response:

    python3 ghot/carrier_pocket.py --route route.json --dispatch dispatch.json --db carrier.sqlite3 respond --qr offer.json --key carrier1.pem --out reply.json

The source admits it (only if its issued nonce and latest history match):

    python3 ghot/carrier_pocket.py --route route.json --dispatch dispatch.json --db station.sqlite3 commit --response reply.json

After connectivity loss, return original response by nonce, not a new fabricated event:

    python3 ghot/carrier_pocket.py --route route.json --dispatch dispatch.json --db carrier.sqlite3 recover --nonce <32-hex-nonce> --out recovery.json

Exchange signed event history over a separately trusted/manual file channel:

    python3 ghot/carrier_pocket.py --route route.json --dispatch dispatch.json --db station.sqlite3 export-history --out history.json
    python3 ghot/carrier_pocket.py --route route.json --dispatch dispatch.json --db carrier.sqlite3 sync-history --from-file history.json

## Validation

    python3 -m unittest discover -s test -p test_carrier_pocket.py -v
    python3 test/carrier_pocket_cross_runtime.py

The cross-runtime proof uses a Node WebCrypto-generated P-256 relay key (test-only, exported only inside CI) to sign a legitimate QR and proves Python GHoT accepts it into the existing signed route. The browser's actual Android UI, IndexedDB persistence, camera scanning and PWA installation have not been tested on a physical phone.

## Limits

This is not an audited app or postal network. A true mobile trial needs a controlled HTTPS origin, signed enrollment ceremony and key revocation/recovery; a separate laptop's localhost does not work from a phone. Offline expiration uses local wall-clock time and refuses late newly submitted proof even if the person claims to have acted earlier. Mobile/browser service worker storage may be evicted, and this research prototype does not deliver a backup. SQLite is trustworthy only under local file permissions, not adversarial shared multiwriter storage. Durable physical custody, safe labor, insurance, delivery classification, legal letter-carriage restrictions and explicit compensation remain separate deployment gates.

Full Measure still receives local noncanonical proposals and PENNY remains separate work-candidate accounting without backing or money transfer.

**Laws:** QR != HANDOFF. SIGNED CLAIM != PHYSICAL PROOF. OUTBOX != DELIVERY. RECOVERY != RE-AUTHORIZATION. FORK != AUTOMATIC RESOLUTION. QUEST != JOB. PROPOSED WORK != PENNY PAYMENT.

Source PRs: GHoT POSTAL-CORPS-001 #118; Full Measure #55; LemonPRESS #17; Jubilee Treasury PENNY-014 #17.
