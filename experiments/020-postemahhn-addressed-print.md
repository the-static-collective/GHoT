# PostEmahh'n MAIL-001: Personal Address, Local Print Release

**Status:** test adapter in GHoT, not the source PostEmahh'n runtime. Source constitution: https://github.com/the-static-collective/Jubilee-Engine-VM/pull/12 . Preceding PDF boundary: https://github.com/the-static-collective/GHoT/pull/110 .

## Flow

PERSONAL KEY -> SHAREABLE ADDRESS CARD -> SIGNED PDF PARCEL -> RECEIVE -> HOLD -> OWNER RELEASE -> PRINT-READY PDF.

The address `pm1-...` is derived from the recipient's P-256 public key. A contact card is portable; it does not authorize use of the recipient's private key. A sender can create a source-signed reLATTE CrossingEnvelopeV0, addressed to that contact with the exact PDF SHA-256. The local host validates it and holds it. The recipient signs a station-bound, short-lived ReceiptV0 to authorize exporting the PDF there. The station verifies the recipient's locally registered key, signature, expiry and PDF bytes before export.

## CLI

Use Python 3 with OpenSSL; commands run from the repository root.

```bash
python3 ghot/postemahhn_mail.py register --owner-key .local/owner.pem --mail-root .local/mail --contact-out .local/address.json
python3 ghot/postemahhn_mail.py compose --sender-key .local/sender.pem --to .local/address.json --pdf sample.pdf --out .local/parcel
python3 ghot/postemahhn_mail.py receive --mail-root .local/mail --parcel .local/parcel
python3 ghot/postemahhn_mail.py inbox --mail-root .local/mail --owner-key .local/owner.pem
# Substitute the signed crossing ID from the inbox:
python3 ghot/postemahhn_mail.py release --mail-root .local/mail --owner-key .local/owner.pem --crossing-id 'relatte-crossing-v0:...' --station-id station-001 --out .local/release.json
python3 ghot/postemahhn_mail.py export --mail-root .local/mail --release .local/release.json --station-id station-001 --out-dir .local/print-ready
python3 -m unittest discover -s test -p test_postemahhn_mail.py -v
```

## What this does not do

- No public mail server, DNS, online routing, end-to-end encryption or automatic remote delivery.
- Raw PDFs exist inside a trusted local host's filesystem; not suitable for confidential documents yet.
- A signing key proves the cryptographic source, not verified real-world identity.
- Local export is not physical printing, payment, delivery or card ownership.
- This is a host adapter, not a grant of authority from PostEmahh'n's independent provenance system.

Next is encrypted mail transport and a separately authorized, site-local print organ. Postal arrival and printable effect remain different receipts.

**Laws:** ADDRESS != IDENTITY. RECEIVED != ADMITTED. RELEASE != PRINTED. PRINTED != DELIVERED. COPY != NEW OCCURRENCE.
