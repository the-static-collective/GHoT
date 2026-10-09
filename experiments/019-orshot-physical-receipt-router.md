# ORSHOT-002 — Signed Physical Receipt / Print Staging

**Status:** bounded runnable experiment, not a physical printer driver, custody system, or PENNY issuance authority.

Orshot renders an inert artifact. GHoT stages PDF bytes only after verifying a signed reLATTE CrossingEnvelopeV0 and ReceiptV0 bound to the exact SHA-256 PDF digest. Two signer identities must match separately pinned keys. A signature does not prove physical deposit, print completion, or authorized money issuance.

The [ORSHOT-001 Orshot template](https://orshot.com/workspace/github-827/templates/studio/23751) contains a separate Ed25519 experimental signature, not a reLATTE P-256 crossing. ORSHOT-002 wraps the previously rendered PDF in a NEW test P-256 crossing and receipt, using GHoT's existing reLATTE identity implementation.

## Run against the existing render

Download [ORSHOT-001 PDF](https://storage.orshot.com/cloud/w-11442/renders/images/orshot-001-signed-test-receipt-6bu9B4ng54q.pdf), or supply any local PDF.

    python3 ghot/physical_receipt_router.py demo-stage ./orshot-001-signed-test-receipt.pdf --spool .ghot/print-spool --keys .ghot/print-test-keys

This creates two local TEST P-256 identities, signs a print-projection crossing/receipt bound to the PDF SHA-256, and stages a content-addressed HELD bundle:

- artifact.pdf — exact Orshot bytes;
- crossing.json — signed source proposal;
- receipt.json — receiver-signed receipt with extensions.ghot_print.artifact_sha256;
- manifest.json — unsigned owner-local routing status;
- source-pin.json and receiver-pin.json — demo trust keys; production trust must be provisioned independently.

Verify:

    python3 ghot/physical_receipt_router.py verify .ghot/print-spool/JOB-ID --source-pin .ghot/print-spool/JOB-ID/source-pin.json --receiver-pin .ghot/print-spool/JOB-ID/receiver-pin.json

The stage subcommand supports externally supplied signed crossings and receipts and requires source and receiver trust pins.

Run cryptographic tests:

    python3 -m unittest discover -s test -p test_physical_receipt_router.py -v

## Boundary and next experiment

This module creates HELD proposals only. It does not call lp, lpr, Zebra ZPL, hardware buses, or token/treasury systems. No print or deposit is claimed.

Next: owner selects a locally observed printer capability, authorizes a bounded job, and hands it to an executor with idempotence across crashes. Distinguish spool-accepted, device-completed, paper-observed, and delivered receipts. No autonomous physical print effect until owner-local admission and durable deduplication exist.

**Laws:** RENDERING != AUTHORITY. SIGNED != TRUE. HELD != PRINTED. QUEUED != PRINTED. PRINTED != DELIVERED. DEPOSIT != TOKEN ISSUANCE.
