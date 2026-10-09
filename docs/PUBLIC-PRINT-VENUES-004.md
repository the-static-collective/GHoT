# PUBLIC-PRINT-VENUES-004 — Xerox, libraries and FedEx Office

## What is actually implemented

**A GHoT-native, operator-enabled, read-only print handoff composer** for real, locally owned PDF bytes. This is not a connection to an institution or a printer and does not simulate external authorization. A local `pypdf==5.9.0` parser validates PDF structure, number of pages (1-250), media boxes, and encrypted document HOLD; checks requested paper size without silently scaling or cropping; then binds the actual local file SHA-256 to a venue-specific manual print-intent receipt.

Input lives in an operator-selected `GHOT_PUBLIC_PRINT_INBOX` absolute filesystem directory, strictly local (no remote paths, symlinks, parent traversal, hidden files, arbitrary hostnames or background watchers). No private filename or bytes appear in the returned receipt. Max file size is 12 MB. An operator-approved copy count is limited to 1-20.

## Why three routes are not the same as three printers

| Route | Real-world situation | Software output now | Separate venue responsibility |
| --- | --- | --- | --- |
| `printer.venue.xerox.mfp.prepare` | Xerox-branded multifunction printer in an institution or business | Source-hash-bound PDF handoff for local print dialog or an operator-carried USB | Real printer administrator must establish model, permissions, IPP/AirPrint/CUPS driver, paper, release and policy |
| `printer.venue.library.public.prepare` | Any library with public printing, including one physically using Xerox hardware | Local PDF page/size receipt with manual web release, USB or staffed-counter preference | Library's *actual* service (PrinterOn or other) decides portal, account, release-code issuer, fees, privacy and timing |
| `printer.venue.fedex-office.prepare` | Retail print service, not one known printer model | Local PDF handoff intent for USB, cloud kiosk, Print & Go email or staffed counter | FedEx Office's kiosk/staff decides file acceptance, retrieval code, service availability, payment and physical output |

A **library Xerox** means a Xerox hardware implementation *behind the library's own customer interface*. We route through the library only when printing as a library patron. A directly managed Xerox printer is a distinct, administrator-controlled route. FedEx is a retail service brand, not a universal IPP or Xerox machine interface.

## Verified external protocols and sources

- Xerox [AltaLink B8200 specifications](https://www.xerox.com/en-ng/office/multifunction-printers/altalink-b8200-series/specifications) list IPP, AirPrint, Microsoft Universal Print and other protocols. This is a **specific Xerox model family**, not proof a particular library device is configured or reachable.
- [PrinterOn's Hosted Printing guide](https://www.printeron.com/wp-content/uploads/2022/04/PrinterOnHostedPrintingGuideandFAQ_2022-min.pdf) documents library-style web/email workflow and separately issued secure release code. An actual library might use a different platform or require identification.
- [FedEx Office Print & Go](https://www.office.fedex.com/default/print-and-go): email file to `printandgo@fedex.com` to receive a retrieval code (FedEx says retrieval codes last 10 days), then self-service kiosk; alternatively USB/cloud account. Venue handles payment; store prices vary. **This code never sends email**.
- [FedEx Office self-service copy/print page](https://www.office.fedex.com/default/copy-and-print-services) lists letter, legal, tabloid and larger *separate* machines. Print & Go email is for self-service small-format, not arbitrary posters or architectural output.

## Run locally

Requirements: Python 3.11+, `pypdf==5.9.0`. From GHoT checkout:

```sh
python3 -m pip install 'pypdf==5.9.0'
python3 ghot/public_print_venues_004_sim.py

# Explicitly enable only this local, bounded capability manifest.
export GHOT_ADAPTER_MANIFESTS="$PWD/adapters/public-print-venues-004/adapter-manifest.json"
export GHOT_PUBLIC_PRINT_INBOX="$HOME/private-print-inbox"
mkdir -p "$GHOT_PUBLIC_PRINT_INBOX/reviewed"

# Place a real human-approved, rights-cleared local PDF at
# $GHOT_PUBLIC_PRINT_INBOX/reviewed/document.pdf
python3 ghot/reference_node.py pantry
```

Example: manually prepare a **library** public document with the existing GHoT subprocess interface:

```python
import sys
sys.path.insert(0, 'ghot')
from external_adapters import execute_external_adapter
cap='printer.venue.library.public.prepare'
result=execute_external_adapter(cap, {
    'schema':'ghot.public-print-input-004/v0',
    'action':cap,
    'input':{
        'relative_pdf':'reviewed/document.pdf',
        'source_ref':'local:document-approved-004',
        'venue_ref':'local:chosen-library-004',
        'method':'MANUAL_WEB_RELEASE',
        'copies':1,
        'color':'MONOCHROME',
        'duplex':'DUPLEX_LONG_EDGE',
        'paper':'LETTER',
        'sensitivity':'PUBLIC',
        'operator_review':True
    }
})
print(result['result']['state'])
```

Change the capability to `printer.venue.xerox.mfp.prepare` with `MANUAL_LOCAL_PRINT_DIALOG` or `MANUAL_USB`. FedEx is `printer.venue.fedex-office.prepare`, with `MANUAL_USB`, `MANUAL_CLOUD_KIOSK`, `MANUAL_EMAIL_PRINT_AND_GO`, or `MANUAL_STAFF_COUNTER`.

**None of those methods trigger any external action**. The chosen method is only a *human next-step intention*. The operator separately visits the real portal/store/driver and must confirm current availability, policy and exact cost. All packets remain `PREPARED_LOCAL_HANDOFF_R3_HOLD`, with no venue receipt or signed reLATTE owner grant.

## Privacy, rights, and physical boundaries

- `RESTRICTED` documents are explicitly refused for public-print handoff. A `PRIVATE` document is refused for public third-party email/web/cloud routes; manual USB remains a candidate with explicit notice of no assumed confidentiality. The user should inspect the venue's retention and privacy policies before releasing any sensitive document.
- The code does not inspect or retain text, images, embedded font licenses, malware behavior, content rights, actual color behavior, trim, margins, ink coverage or physical output. An `operator_review=true` field is an operator assertion, not third-party attestation.
- Native structural inspection provides a real page count and PDF MediaBox geometry, but does **not** render the PDF, prove font fidelity, confirm printable area, negotiate printer properties or prove a finished print.
- It neither connects to a Xerox machine nor calls a library's PrinterOn endpoint. It does not scrape FedEx Office, create retrieval codes, create accounts, pay, submit an order, purchase paper or produce financial receipts.
- The PDF hash is useful for local provenance but is not a signature or evidence of external printer custody. Keep the receipt private for sensitive inputs; a hash may disclose document equality.
- Physical outcome requires the actual vendor's receipt and an independent operator observation; vendor order acknowledgement is not proof that pages were collected.

## Architectural note for reLATTE

Run a later signed **operator-mediated public-print crossing** only after a real venue and permission has been selected: source-owned artifact PDF fingerprint → GHoT's local private intent → separately granted external submission (not present) → external provider acceptance → separate staff/operator physical-observation receipt. `LIBRARY` is a *venue context*, `XEROX` a *manufacturer*. A single physical copier may be both.

**Laws:** `PRINTER BRAND != VENUE`, `LOCAL PREFLIGHT != PDF/A CERTIFICATION`, `PREPARED != UPLOADED`, `RELEASE CODE != INVENTED TOKEN`, `PAYMENT NOT EXECUTED`, `VENDOR ACCEPTANCE != PAGES COLLECTED`, `GHoT CANDIDATE != NATIVE reLATTE RECEIPT`.
