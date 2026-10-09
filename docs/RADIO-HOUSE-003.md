# RADIO HOUSE 003 — First signed work gift (offline courier, sovereign receiver)

**Research only; not deployed.** This branch composes RADIO HOUSE 001 (media review packet) + 002 (operator-opted-in, media-first SQLite hash work) + GHoT's native reLATTE P-256 \`relatte.crossing-envelope/v0\` and \`relatte.receipt/v0\` signatures.

## First proof, precise
Two separately stored local identities and SQLite state directories simulate independent participants. One requester creates a native source-signed crossing for **public synthetic ASCII text only**, bound to an exact JSON payload SHA-256, one recipient identity and an expiry. The request is manually couriered by a file inside the same CI runner; no socket connects the participants.

The recipient explicitly supplies a pinned requester P-256 public key **from outside the bundle** and its own locally held P-256 private key. Signature verification is not sufficient: a fresh receiver-local operator opt-in, per-job approval, idle observation, favorable GHoT power and a capability-specific queue check must succeed before any task is admitted. The signing key's possession is not proof of being a legitimate ministry or station operator.

A native signed \`HELD\` receipt records receiver-local admission without claiming broadcast or release. A genuine 002 bounded SHA-256 job advances in checked chunks. During simulated recording, the next chunk HOLDS with zero progress. After a fresh idle observation, work resumes. On completion and cold validation, the receiver issues a native signed \`EXECUTED\` receipt; sender independently verifies both source-specific and recipient-specific signatures, original input binding and recomputes the result.

A duplicate courier can retrieve the already-durable admission receipt without duplicating the job. Final signed receipt is sealed and replayable from the receiver-owned SQLite ledger. No arbitrary remote executable or shell.

## Bounded constitutional claims
- REAL: two distinct keys, separate local directories, actual GHoT 002 hash computation and checkpoints, OpenSSL P-256 signing, reLATTE v0 signing/verification, recipient-local SQL admission and final receipt, exact hash replay.
- NOT REAL: a long-distance network, two powered physical machines, a reLATTE R3 receiver endpoint, authenticated ministry/organizational identities, fresh physical sensor evidence, OBS priority or Linux cgroup resource enforcement, third-party work donation, actual radio signal, revenue or payouts.
- The local operator signs *a lab role claim*, not institutional authorization. The P-256 pin must be provisioned out of band. No publishing/broadcast permission.
- All job inputs are nonsecret synthetic ASCII; do not send church counseling, donor or copyrighted media content to compute organ.
- One non-adversarial local SQL writer per identity root. No cross-process hardware power watchdog. SQLite transaction ensures admission and job creation are atomic; staged work is receiver-owned and cannot be forced by the courier.
- The protocol uses the actual reLATTE cryptographic profile; it does **not** claim the existing canonical reLATTE source/receiver semantic authority or live \`R3_HOLD\` integration.
- The current crossing expires; true long-running remote resumability and cancellation after expiry require a separate sovereign protocol. Final sealed receipts are a local truth, not remotely queryable after expiry.

## Run
Python 3.10+, OpenSSL on PATH:

\`\`\`sh
python3 -m unittest discover -s tests -p 'test_radio_house_003.py' -v
python3 -m ghot.radio_house_003 demo /tmp/unique-ghot-radio-house-003
\`\`\`

No packages are installed. New demo directory must not already exist. All identities generated during demo are lab-only and must not be copied to real organizations.

## Next border
Real physical Linux hosts, independent pin exchange, authenticated transport, network retry, cancellation/revocation after admission, OBS state verification, OS-level compute throttling, cgroup limits, real signed owner-local grants, and a separate invitation from any participating real organizations.

**SIGNATURE != PERMISSION. MANUAL COURIER != INTERNATIONAL LINK. HELD != AIRED. OFFER != DISPATCH. LOCAL CHECKPOINT != REAL-TIME PREEMPTION. NODE != CHURCH. WORK != FINANCIAL DONATION.**
