# GHoT 030 — owner-local branch worker

This experimental organ exposes one **read-only** locally permitted capability through GHoT's **existing** typed launch, destination preflight, and signed activation ticket machinery. It does **not** run donor code.

The first task is **hash-exact-source**: compute SHA-256 of a file at a pinned original Git commit, and compare it to a separately declared SHA-256. This is a real local task whose output can later be carried through reLATTE.

## Boundary

    branch candidate (repo, exact commit, path, SHA256, branch hint)
         ↓
    GHOT_HOME/branch-worker/sources.json (owner-curated local checkout + allowed read)
         ↓
    027 typed launch → exact read-only preflight → inert proposal identity
         ↓
    human reads preview, explicitly types ACT and the exact proposal address
         ↓
    028 BODY-signed one-job ticket (short TTL; not human identity)
         ↓
    028 atomic ticket claim → fresh preflight and original Git object/policy
         ↓
    owning worker performs one local Git source hash (no donor execution)
         ↓
    028 BODY-signed execution receipt and durable local result

Candidate discovery is not consent. The source allowlist is not consent. A synthetic CI ACT does not establish authorization for someone else's node.

## Candidate JSON

    {
      "schema": "ghot.branch-worker-candidate/v0",
      "context": {
        "repository": "the-static-collective/planZ",
        "branchHint": "experiment/fatherhand-grant-chain-residue-001",
        "commit": "e8111fdb64c5587b33aece0fed639ed3d03375ac",
        "path": "002/bin/sense-global.mjs",
        "sha256": "<64-hex-SHA256-of-original-blob-bytes>"
      }
    }

Save this as your local candidate.json, replacing the placeholder with the **actual original Git blob bytes SHA-256**. A failed comparison HOLDs.

An owner independently creates GHOT_HOME/branch-worker/sources.json:

    {
      "schema": "ghot.branch-worker-sources/v0",
      "entries": [{
        "context": {
          "repository": "the-static-collective/planZ",
          "branchHint": "experiment/fatherhand-grant-chain-residue-001",
          "commit": "e8111fdb64c5587b33aece0fed639ed3d03375ac",
          "path": "002/bin/sense-global.mjs",
          "sha256": "<same-64-hex-SHA256>"
        },
        "checkout_root": "/absolute/local/full/planZ/checkout",
        "reviewed_for_local_read": true
      }]
    }

Only the owner-local allowlist can name checkout paths; candidate JSON cannot. Both files are local inputs, not public records. A review flag does not authorize any execution.

A local original-Git-object check requires a source commit present and a Git remote origin matching the declared GitHub repository (a structural check, not owner authentication). No network fetch occurs. Bytes are limited to 1 MiB. No shell, donor import, URL or arbitrary subprocess arguments are permitted.

## Human-operated CLI

Read-only preview:

    GHOT_HOME=/your/home python3 ghot/branch_worker.py preview /your/candidate.json

The resulting exact proposal address is printed. After reviewing it, explicitly choose a single job:

    GHOT_HOME=/your/home python3 ghot/branch_worker.py act /your/candidate.json \
      --expected sha256:<proposal-address-from-preview> --confirm ACT

The operator must supply the expected proposal address from the preview. GHoT rechecks it before ticket creation and again at execution, then re-verifies the original bytes and local policy inside the job. The activation ticket may be spent only once; a failure is a signed failure, never a fabricated success. No session authorization is created.

The ticket, result, and verified signed receipt are stored in GHOT_HOME/activation-tickets/.

## First proof

The CI workflow clones the exact planZ experimental commit and runs a **synthetic** ACT inside a disposable GHoT home. It confirms a real local Git blob hash, one BODY-signed ticket, one signed execution receipt, rejection of ticket replay, and signed refusal when owner-local policy is revoked after ticket issue. Existing launch descriptor, activation and broker simulations run unchanged.

**BRANCH != BACKLOG. AVAILABLE != AUTHORIZED. POLICY != ACT. PREVIEW != PERMISSION. ONE TICKET != SESSION. BODY SIGNATURE != HUMAN IDENTITY. SOURCE HASH != DONOR EXECUTION.**

This implementation is not a daemon, remote worker, browser executor, release, generalized branch-code loader or reLATTE transport. CANNON 009 separately proves native reLATTE receipt crossing; an explicit bridge to this new *signed* owner-local result is a later, independent seam.
