# PRINT-WORLD-005 — GHoT × Full Measure × PENNY

## What this executable cross-repo boundary does

**GHoT** owns the local PDF and venue-specific held packet from [PUBLIC-PRINT-VENUES-004](https://github.com/the-static-collective/GHoT/pull/108). **Full Measure** owns an opt-in Garden **quest proposal**. **PENNY-014** owns a separately signed work/custody ledger. This project composes the three with strict non-escalation and **no live print, Garden Deed, money or penny minted**.

```text
local operator-provisioned real PDF
    -> GHoT native pypdf page preflight and hashed PUBLIC_PRINT_004 receipt
    -> pinned original Python canonical source receipt verification
    -> Full Measure native Field Quest inbox verify + opt-in HOLD choice
    -> Full Measure Garden draft (never an accepted Pledge or a Deed)
    -> PENNY-014 native role policy zero-event genesis inspection
    -> held cross-organ proof with 0 certified work, 0 physical pennies, 0 issued units
```

## Native donors

- Full Measure: [FIELD-QUEST-ENGINE-001 PR #54](https://github.com/the-static-collective/full-measure-world-layer/pull/54), pinned commit `c9206d5055ad574a23acb2eceb5f8785a4ad64fe`. Import and **execute** its `verifyFieldTestInbox`, `drawQuestCards`, `decideQuest`, and `projectGardenDraft` methods. It does not write the Garden's canonical event ledger.
- Jubilee Treasury: [PENNY-014 PR #17](https://github.com/the-static-collective/Jubilee-treasury/pull/17), pinned commit `a36777cb87bcfb6b7706b910ba18c4c4b24c73a3`. Import and **execute** its own `newKeys`, `createWorld` and `inspectWorld` on ephemeral synthetic zero-event signers. Five signing identities are never exported. It is a real native policy check on an *empty simulator*, not native validation of any paid human work.
- GHoT source: [PUBLIC-PRINT-VENUES-004 PR #108](https://github.com/the-static-collective/GHoT/pull/108), original source commit `f62d8f2ae9a9077430bc1ef6fc4a17ea00f2affd`. The bridge checks that original GHoT 004 Python-canonical `packet_id` hash from raw JSON **before JavaScript parsing**, since JS and Python may serialize `612.0` differently. It also requires exact documented no-submission/no-effect original fields.

## Run native cross-repo demo

```sh
python3 -m pip install pypdf==5.9.0
node --test tests/print-world-005.test.mjs
# Obtain exact local, trusted donor checkouts at the pinned commit SHA above.
cd external/full-measure && npm ci --ignore-scripts --no-audit --no-fund && cd ../..
node external/full-measure/node_modules/tsx/dist/cli.mjs \
  ghot/public_print_world_005.mjs \
  "$PWD/external/full-measure" \
  "$PWD/external/penny-014" \
  "$PWD/dist/print-world-005/ghot-public-source.json" \
  "$PWD/dist/print-world-005/held-cross.json"
```

To create a first **real PDF source** reproducibly (without printing), run the workflow `.github/workflows/print-world-005.yml`. It creates a blank, synthetic one-page PDF using `pypdf`, passes its actual bytes through GHoT 004's `compile_handoff`, verifies the canonical source receipt and then executes the native Full Measure and PENNY donor modules. All external donor checkouts must match the recorded source SHA; any mismatch refuses. Output path must not already exist.

The exported result includes `full_measure_quest` and `full_measure_garden_draft` under **proposal/NOT_PLEDGED/NOT_AWARDED**, plus `penny_work_candidate` with **0** work witness, **0** allocation, **0** custody and **0** active units. A user may later *manually* choose to create a real Garden quest through its ordinary separate admission. The helper does **not** do so itself.

## What completing a real print could mean later

A human voluntarily chooses an actual venue (e.g. local Xerox MFP, library PrinterOn-style release, FedEx Office), knowingly submits the public-safe document, and obtains an external provider claim. An independent authorized human records the actual physical delivery or refusal in Full Measure's standard Pledge → Report → Confirm workflow. This is distinct from GHoT's PDF hash or a vendor's order acknowledgment. It must never automatically create Full Measure event, Deed or Harvest.

**PENNY work isn't payment for a print.** Even human-confirmed Garden participation does **not** become PENNY backing or a transferable balance. PENNY-014 needs independent, signed, role-pinned work proof, agreed work terms, holder consent and genuinely separate physical copper-penny custody with three independent depositor/custodian/counter attestations, then additional matched release; in the existing code all such examples are synthetic and not authorized as a live financial system. This 005 writes no canonical PENNY event at all. No real coins, token, profit, fee, discount, wage or redemption right is conferred.

## Known boundaries

- No vendor upload, email, print dialog, wireless discovery, library portal, payment, release code or paper. No invoice, print confirmation or receipt from a human.
- No source-private PDF bytes go into the Full Measure quest. For PRIVATE files, public Garden projection is denied outright. Output still contains hashes and a venue ref; handle as personal metadata.
- No original native reLATTE crossing is attempted. The result is a GHoT-local **cross-organ proposal receipt**, not an authoritative Full Measure deed or PENNY signed journal.
- No donor source implementation is vendored or changed; each pinned donor keeps its own decision surface and ledger. Native tests in CI check its real implementation.
- SHA-256 fingerprint pins bytes or local model output; it does not establish real-world delivery, identity, source copyright ownership or venue permission.

**Laws:** `PRINT CANDIDATE != HARD COPY`, `QUEST != PLEDGE`, `REPORT != WITNESS`, `DEED != PENNY WORK WITNESS`, `PENDING != SPENDABLE`, `WORK != COIN CUSTODY`, `COIN CUSTODY != LEGAL TITLE`, `PRINT COST != TREASURY ISSUANCE`.
