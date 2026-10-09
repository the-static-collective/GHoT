# RIFF-RAFT-007 — TWO-REPOSITORY POST OFFICE / SINGLE-CUSTODIAN-PARTITION TRIAL

**Implemented and exercised with real signed source bytes.** Two GitHub repositories now contain a full copy of the exact original reLATTE 005 held return, including both actual independently observed vanilla Minecraft results and the nested original signed 004 return. The GHoT copy at `fixtures/riff-raft-007/signed-005-return.bundle.json` is byte-for-byte identical to reLATTE's original `fixtures/riff-raft-minecraft-006/signed-005-return.bundle.json`. Full bundle SHA-256:

`da6c556051f197e1d07578b5e435ae3b7132538c7c098a4add9e4acfd4572d42`.

## What the test did

1. Read the Git-committed source material from **two separate repositories** in independent checkout directories (not expiring Actions artifacts).
2. Recompute exact file SHA-256 and run GHoT's OpenSSL-backed P-256 verifier on the entire original 004 + 005 crossing/receipt and both native Minecraft evidence sets.
3. Issue **two distinct local P-256 ephemeral custody receipts** carrying the same source-file SHA, each bound to a different repository label and `HOLD`. Neither key is an identity root or owner.
4. **Partition rehearsal A:** remove reLATTE's temporary local checkout copy from the trial and independently reverify *all* original source signatures, game observations and GHoT local receipt using GHoT's surviving bytes. No missing-source inference.
5. **Partition rehearsal B:** remove GHoT's temporary trial copy and independently reopen the *same* source from reLATTE alone. A separate cold CI runner can verify reLATTE source without checking out GHoT's evidence files.
6. Reject tampered local signature / custody label, truncated source and promotion to `admission=true`.

The tests are executable:

```bash
python3 ghot/riff_raft_custody_007.py check fixtures/riff-raft-007/signed-005-return.bundle.json --store GHoT
python3 ghot/riff_raft_partition_007.py /path/to/reLATTE/fixtures/riff-raft-minecraft-006/signed-005-return.bundle.json fixtures/riff-raft-007/signed-005-return.bundle.json /tmp/riff-raft-007-proof.json
python3 ghot/riff_raft_custody_007_sim.py
```

Run `.github/workflows/riff-raft-007.yml` for **three jobs**: direct two-repo comparison plus local disconnect trials; GHoT-only cold reopen; reLATTE-only cold reopen using only GHoT verification *code* without GHoT peer *data*.

**Boundary:** The actual GitHub repositories were **not remotely taken offline**. The deliberate missing-store exercise deleted/isolated disposable local fixture copies in CI. Distinct repos are two custody *locations*, but both live in the same `the-static-collective` GitHub organization. They do **not** establish independently administered storage, jurisdiction, power supply, network link, or trust. The two P-256 receipts use ephemeral keys without established real-world identities. Retained Git repository copies can still be modified or deleted by a common administrator. No automatic re-replication or remote sender authority is created.

```text
TWO LOCATIONS != TWO ADMINISTRATORS
TWO SIGNATURES != TWO TRUST ROOTS
LOSS OF ONE TEMPORARY COPY != VERIFIED REMOTE OUTAGE
REOPENED SIGNED 004+005 GAME EVIDENCE != NEW MINECRAFT RUN
HOLD IS PRESERVED; NO DISPATCH OR LAND RIGHTS
```

**Next real-world test (not claimed here):** a second genuinely independently controlled account/provider/storage medium, ideally with an offline removable backup, independently selecting the crossing and returning a separately authorized receipt. That would be a distinct human and infrastructure crossing.
