# POSTAL-CORPS-003 — Two Phones, One Fictional Parcel

**Status:** field-test kit and cryptographic simulator, not deployed as a service. No actual two-phone hardware trial has been run. The parcel is fictional.

## Purpose and architecture

Use two independently controlled phones plus an operator workstation:

- Phone A holds the **origin** P-256 key. It signs a test route, imports carrier1's separate signed acceptance claim, and issues a short-lived pickup QR.
- Phone B holds the **carrier1** P-256 key. It may refuse freely, or inspect A's signed request and explicitly countersign one native custody-claim event.
- B shows the response QR. A verifies, stores the history, shows the signed-history QR. B scans and verifies the exact same 64-character SHA-256 history head.
- A trusted GHoT operator independently checks enrolled public-key pins, the signed native LemonPRESS dispatch, every native custody event, the issued QR nonce and TTL, and may admit **one synthetic event only** into a SQLite journal.

## First prepare the two devices

Page: web/carrier-pocket/two-phones.html

The page needs a controlled HTTPS origin on both phones. Load once with connectivity and confirm it survives an offline reload; the service worker pre-caches the HTML and all local scripts. QR generation is fully local, from a vendored MIT QR library. Optional QR camera decoding uses BarcodeDetector; raw JSON copy/paste or a manually transferred file remains the fallback.

1. Select **Phone A — origin** on A and **Phone B — first carrier** on B. Use Create / reopen key on each. Independently record only their **PUBLIC** JWK JSON; never export, share, or upload the private key.
2. Using a checked-out native LemonPRESS Dispatch Gate source, create a fictional un-postaged selected-only dispatch:

       python3 test/two_phone_dispatch_fixture.py --lemon /path/to/lemonPRESS --out .local/dispatch.json

3. The operator uses PUBLIC key JSON from Phone A/B to prepare the source manifest:

       python3 test/two_phone_prepare.py --dispatch .local/dispatch.json --origin-public .local/origin-public.json --carrier-public .local/carrier1-public.json --unused-fixture-keys .local/dormant-test-only --out .local/setup-unsigned.json

   Four other public role keys are created as **dormant local synthetic fixtures**. They are not independent people, paid couriers, witnesses, or verified identities.

4. Phone A pastes setup-unsigned.json into Setup JSON and selects **A: sign route**. Export the signed setup to Phone B via manually transferred file or copy/paste before going offline. Phone B pastes and chooses **B: verify signed route**. Both should independently compare the A-origin key fingerprint with the operator-enrolled public key record. A signed route is not self-proving human identity.

## Four QR transfers after switching off network connectivity

The setup files must already be on both phones, and the browser/PWA must already have been loaded successfully.

1. **B -> A ACCEPT:** B chooses B: sign leg acceptance. A scans B's QR and presses Verify and import incoming packet. This advances both synthetic histories to LEG1_ACCEPTED.
2. **A -> B OFFER:** A selects A: issue pickup QR. B scans, verifies, and reads the exact route, parcel hash, evidence hash, roles, and 5-minute expiration. B may refuse.
3. **B -> A RESPONSE:** B explicitly checks consent, signs one response, and shows its QR. A scans, verifies and chooses A: verify returned response. No passive confirmation occurs.
4. **A -> B SYNC:** A displays the signed native-event/history-head QR. B scans and verifies it. Both devices should show LEG1_MOVING_CLAIM and the same history-head SHA-256.

The QR contains no real street addresses, seed phrases, financial keys, physical deliveries, jobs or payments. A signed claim is not independent evidence that something moved.

## Station import after connectivity returns

Phone A chooses Save station reconciliation bundle. The operator obtains that JSON and separately provisions the same two PUBLIC key pins originally collected at enrollment. Do not trust an arbitrary pin embedded inside the fieldkit:

    python3 ghot/two_phone_station.py --fieldkit .local/phone-a-fieldkit.json --origin-pin .local/origin-public.json --carrier-pin .local/carrier1-public.json --journal .local/station.sqlite3 --out .local/station-review.json

Possible station results:

- **SYNTHETIC_HANDOFF_ADMITTED:** source, independently enrolled key pins, signatures, nonce and current native journal are consistent; one synthetic claim is admitted. No real physical or financial consequence.
- **HOLD_EXPIRED:** a correctly signed claim arrived too late, with no independent trusted co-signing timestamp. The station does NOT backdate it or write it to its journal.
- **REFUSAL/HOLD:** invalid signatures, wrong source, conflicting histories, replay, altered parcel or other violations never silently become a custody event.

The QR expires in five minutes. Import should be promptly completed. Longer offline journeys need a distinct witnessed-time protocol; this experiment does not override expired claims.

## Verify from source and CI

    node test/two_phones_webcrypto.cjs /path/to/native-dispatch.json /tmp/fieldkit.json
    python3 -m unittest discover -s test -p test_two_phone_station.py -v
    python3 -m unittest discover -s test -p test_carrier_pocket.py -v

The Actions workflow uses the actual pinned LemonPRESS Dispatch Gate, two independently generated WebCrypto keys, real offline QR encoding, and Python GHoT native signed-custody replay and SQLite nonce admission. Only a safe final review summary is archived; no private test keys are published.

**Still untested:** any real phone browser, HTTPS hosting, physical camera scan, IndexedDB/service worker persistence on Android, person enrollment, street addresses, carrier service, compensation, actual delivery, physical custody, real Full Measure Deed or PENNY tokens.

**Laws:** SCAN != ACCEPTANCE. SIGNATURE != PERSON. QR != HANDOFF. PHONES AGREE != STATION ADMITTED. LATE != BACKDATED. CLAIM != PHYSICAL CUSTODY. WORK != PAYOUT.

Sources: GHoT POSTAL-CORPS-002 PR #121, POSTAL-CORPS-001 PR #118, Full Measure PR #55, LemonPRESS Dispatch Gate PR #17, PENNY-014 PR #17. Bundled QR dependency Cyphrme QRGenJS / Project Nayuki under MIT license, with notice in web/carrier-pocket/vendor/QRGEN-LICENSE.md.
