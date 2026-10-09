# MAIL-004 — PostEmahh'n Passkey Door

**Experimental WebAuthn co-factor, not a production relying party.**

This branch composes four independent facts:

1. MAIL-002: an encrypted document can be opened by the PostEmahh'n recipient, who signs a local release to a chosen station.
2. MAIL-003: a station presents a signed, nonce-bound, typed wallet-door request for one PDF and accepts separate owner/guardian signatures.
3. MAIL-004: a real WebAuthn ES256 passkey assertion verifies *that exact wallet-door request* using approved RP, origin, user verification and its local one-time record.
4. The only downstream effect is **HELD** PDF staging; printing, funds, tokens, and custody are outside this scope.

## What exists

- ghot/postemahhn_passkey_door.py — WebAuthn none-attestation enrollment authorized by the mail-owner key; COSE ES256 key parsing; authenticator RP hash/UP/UV verification; origin-bound assertion verification; credential counter and one-use challenge store; added passkey gate for GHoT.
- ghot/passkey_ceremony_cli.py — local operator commands for enrollment and assertion ceremonies.
- web/postemahhn-passkey-lab.html — static HTML page that invokes browser navigator.credentials.create/get, and produces copyable ceremony JSON. It does not transmit credentials to a remote service.
- test/test_postemahhn_passkey_door.py — positive plus hostile synthetic-authenticator proof, including actual P-256 signatures, replay, wrong origin, false credential and missing authorizations.
- .github/workflows/postemahhn-passkey-004.yml — dedicated regression tests plus MAIL-003 and MAIL-002 tests.

**Do not treat synthetic test credentials as proof of physical phone ownership.** The code can validate real browser WebAuthn response formats, but no real phone/browser credential registration has yet been demonstrated.

## Local demo

Install: Python 3, OpenSSL, cryptography, cbor2.

    python3 -m pip install 'cryptography>=43,<47' 'cbor2>=5.6,<6'
    python3 -m unittest discover -s test -p test_postemahhn_passkey_door.py -v
    python3 -m http.server 8000 --bind 127.0.0.1

Open http://localhost:8000/web/postemahhn-passkey-lab.html on the **same** development machine. Use RP localhost and origin http://localhost:8000 for its locally issued challenges.

Starting from the MAIL-001 recipient contact card, extract public_key to owner-public.json. Do not give the browser or print station the recipient private key.

Register a credential:

    python3 ghot/passkey_ceremony_cli.py begin-register owner-public.json localhost http://localhost:8000 .local/passkeys .local/enrollment.json

Paste enrollment ticket into the local browser demo; choose Create Passkey, and save browser JSON to .local/registration.json. Then issue the independent owner authorization and finish registration:

    python3 ghot/passkey_ceremony_cli.py owner-approve-register .local/enrollment.json .local/owner.pem .local/owner-proof.txt
    python3 ghot/passkey_ceremony_cli.py finish-register .local/enrollment.json .local/owner-proof.txt .local/registration.json .local/passkeys .local/credential.json

After the signed MAIL-003 wallet request, policy and trusted station key are available, issue the browser challenge:

    python3 ghot/passkey_ceremony_cli.py begin-print-check .local/wallet-request.json .local/wallet-policy.json .local/station-public.json .local/credential.json .local/passkeys .local/assertion-ticket.json

Paste assertion-ticket.json into the browser. Save the resulting WebAuthn response as .local/assertion.json. Verify:

    python3 ghot/passkey_ceremony_cli.py verify-print-check .local/assertion-ticket.json .local/wallet-request.json .local/wallet-policy.json .local/station-public.json .local/assertion.json .local/passkeys

Verification consumes the challenge and witnesses user-verified credential control; it does NOT stage or print. For integrated HELD staging, use stage_with_passkey with a **fresh unconsumed** assertion, the MAIL-003 owner/guardian approvals and MAIL-002 recipient print release. The full integration is tested in test_postemahhn_passkey_door.py.

## Boundaries

The browser helper is not yet hosted under a deployable HTTPS domain. A phone cannot access another machine's localhost. For real phone testing, serve a verified HTTPS RP and implement authenticated backend ceremony endpoints. This is NOT a finished Android application.

None attestation proves no trusted hardware provenance. The prototype supports ES256 P-256 only, rejects unsupported attestation/extensions, and requires exact verified origin and RP. Production needs lifecycle/revocation/recovery, robust counter synchronization, secure account binding, rate limiting, secure station UI, and additional authentication hardening.

External wallets (EVM, Bitcoin BIP-322, Solana Ed25519) require separate verification profiles. No financial wallet, funds, seed phrase or blockchain transaction is connected here. Wallet authentication never becomes spending or printing authorization.

WALLET != BANK. PASSKEY != DECRYPTION KEY. VERIFIED != PRINTED. COPY != NEW OCCURRENCE.

Source: GHoT PR #115 (MAIL-003), PR #114 (MAIL-002), Jubilee-Engine-VM PR #12.
Specification: https://www.w3.org/TR/webauthn/
