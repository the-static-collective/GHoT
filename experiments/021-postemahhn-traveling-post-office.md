# PostEmahh'n MAIL-002 — The Traveling Post Office

**Status:** runnable GHoT adapter, NOT a public postal network and NOT a deployed Android kiosk.

## Mail is addressed to a person, not a printer

The existing MAIL-001 shareable contact card `pm1-...` is a stable recipient-key-bound address. MAIL-002 uses it to send an **encrypted** PDF. The separate relay can accept/store/forward the opaque sealed parcel but cannot decrypt it with its own keys.

Flow:

```
sender / ORSHOT PDF
  -> ephemeral P-256 ECDH + HKDF-SHA256 + AES-256-GCM
  -> reLATTE source-signed sealed-payload reference
  -> opaque store and HTTP transport (relay node)
  -> recipient-owned P-256 key opens locally
  -> owner-signed, short-lived, named-station release
  -> exact PDF bytes staged at local station as HELD
  -> (future) separate device admission / paper / delivery receipts
```

### What is cryptographically guaranteed

- Source-signed reLATTE CrossingEnvelopeV0 binds the opaque ciphertext envelope SHA-256 and recipient address. The sender's P-256 source signature verifies. Sender key is not a legal identity.
- Each send creates an ephemeral P-256 ECDH key; the recipient's existing private P-256 key and HKDF-SHA256 derive AES-256-GCM. Nonce/salt are independently random per parcel.
- AES-GCM authenticated data includes the recipient address, source particular, ephemeral key, salt, nonce, content type, and unique message id. Any altered ciphertext/header fails source verification and/or decryption.
- Recipient signs reLATTE ReceiptV0 specifying the PDF SHA-256, original crossing ID, exact named station and expiry.
- Station verifies the signed recipient public key against a **separately configured trusted recipient address** and stages only matching PDF bytes to HELD, not printing automatically.
- Relay contains no private recipient key or plaintext PDF in its parcel records.
- Duplicate relay intake is idempotent by crossing ID, and staged releases are idempotent by signed release ID.

### What is NOT proven

- Internet-facing transport is **not** secure: the sample HTTP relay has **no TLS, authentication, metadata privacy, access-control, deletion, abuse controls or comprehensive hardening**. It binds to loopback by default. It must NOT be publicly exposed.
- A forwarded contact card does not prove real-world identity or that the address holder consents to mail. Anyone can send to a public address.
- The station sees the plaintext when the recipient authorizes export; never give a station a private key. Treat that site as trusted for the released document.
- Sending proves signature and encrypted data movement, **not delivery to the human**.
- Key rotation, recovery, cryptographic forward secrecy after later private-key compromise, full private-station handoff, and a browser-native/Android signing app are not implemented. Phone authorization is a compatible signed-release protocol, **not a finished mobile UI**.
- No CUPS/Zebra print executor is invoked. HELD != PRINTED. No PostEmahh'n card/custody/asset receipt is issued.

### Local test

Dependencies: Python 3, OpenSSL, and the separately installed `cryptography` package.

```bash
python3 -m pip install 'cryptography>=43,<47'
python3 -m unittest discover -s test -p test_postemahhn_sealed_mail.py -v
```

Use MAIL-001 to create shareable contact:

```bash
python3 ghot/postemahhn_mail.py register --mail-root .local/mail --owner-key .local/owner.pem --contact-out .local/owner-address.json
```

Create encrypted parcel:

```bash
python3 ghot/postemahhn_sealed_mail.py seal --pdf original.pdf --to .local/owner-address.json --sender-key .local/sender.pem --out .local/sealed.json
```

Start loopback-only relay in a separate shell:

```bash
python3 ghot/postemahhn_sealed_mail.py serve --root .local/opaque-relay --port 7789
```

For a two-device **trusted LAN experiment only**, an operator may explicitly opt into accepting remote connections:

```bash
python3 ghot/postemahhn_sealed_mail.py serve --root .local/opaque-relay --port 7789 --bind 0.0.0.0 --allow-insecure-lan
```

The sending device then uses the relay device's LAN IP in its `--url`. This is plaintext HTTP for routing metadata and has NO login/TLS. The document remains encrypted to the recipient, but even test deployments must be kept behind a trusted LAN/firewall; do not forward this port or host confidential mail. Production needs TLS, authenticated recipient listing, abuse prevention and secure station access.

Move ciphertext through HTTP, then decrypt ONLY with recipient key:

```bash
python3 ghot/postemahhn_sealed_mail.py send --url http://127.0.0.1:7789 --parcel .local/sealed.json
python3 ghot/postemahhn_sealed_mail.py fetch --url http://127.0.0.1:7789 --address 'pm1-YOURADDRESS' --out-dir .local/inbox-opaque
python3 ghot/postemahhn_sealed_mail.py open --parcel .local/inbox-opaque/PARCEL-ID.json --recipient-key .local/owner.pem --out .local/clear.pdf
python3 ghot/postemahhn_sealed_mail.py authorize --parcel .local/inbox-opaque/PARCEL-ID.json --recipient-key .local/owner.pem --station local-station-001 --out .local/release.json
python3 ghot/postemahhn_sealed_mail.py stage --parcel .local/inbox-opaque/PARCEL-ID.json --pdf .local/clear.pdf --release .local/release.json --station local-station-001 --trusted-address 'pm1-YOURADDRESS' --spool .local/print-hold
```

The relay's list/fetch endpoints expose ciphertext and address metadata without authentication in this bounded test. Use only with intentionally non-sensitive test fixtures and within trusted development conditions.

**Source references:** [Jubilee PostEmahh'n v0.1 constitution](https://github.com/the-static-collective/Jubilee-Engine-VM/pull/12), [GHoT MAIL-001](https://github.com/the-static-collective/GHoT/pull/112), [GHoT ORSHOT-002](https://github.com/the-static-collective/GHoT/pull/110).

**Next seam:** mobile QR claim/approval as a durable capability, relay admission policies, encrypted local store, phone/browser-native key custody, and a real owner-authorized printer with separate queued, printed and paper-collected observations.
