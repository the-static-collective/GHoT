# RADIO HOUSE 002 — one computer, two purposes, local ministry first

**Research specimen / not an installed station service.** A Linux machine operated by Rock Impact (if it agrees) can reserve its present resources for local media creation while doing optional, *explicitly approved* bounded compute during operator-observed idle periods. The owner and media project are never subordinate to GHoT.

002 extends [RADIO HOUSE 001](../ghot/radio_house_001.py), whose original synthetic recording can be transferred locally under review-only scope. In 002, one actual local SHA-256 computation advances in short durable 256-byte checkpoints and yields on the **next checkpoint** when local media status becomes RECORDING, STREAMING, or EDITING. It can resume later without recomputing already recorded chunks. This is useful proof of the scheduling law, not yet donated remote work.

### Existing GHoT/native seams

- Imports **real existing** \`ghot.power_field.probe_power\` and \`apply_power_policy\`; power willingness is a separate gate from the media recording status.
- Does NOT modify existing GHoT peer discovery, lease authority, \`reference_node.execute\` or GHoT \`energy_scheduler\`. Its \`compute.public-hash/v0\` is explicitly *not yet advertised externally*; do not infer native remote dispatch from a local offer.
- Uses owner-local SQLite with an opt-in switch, operator-observed media state, per-job explicit approval, finite text input quota, one-frame-per-call work, and hash-linked local event receipts.
- Uses [RADIO HOUSE 001](../ghot/radio_house_001.py) unchanged for synthetic held media handoff during a recording.
- No OBS probe/control is connected; the operator must explicitly mark when recording or streaming. An OBS watchdog and OS cgroup CPU and I/O protection are **necessary before trusting this for live production**.
- No remote network, untrusted task ingestion, arbitrary code, keys, minter, donations, job payouts, GHoT signed cross-machine leases, public radio rebroadcasting, editorial approval or Rock Impact organizational endorsement.

### Local run (Python 3.10+ from repo root)

\`\`\`sh
python3 -m unittest discover -s tests -p 'test_radio_house_002.py' -v
python3 -m ghot.radio_house_002 demo /tmp/ghot-radio-house-002-fresh
\`\`\`

For exploratory local-only use **with synthetic/nonprivate test text**:

\`\`\`sh
python3 -m ghot.radio_house_002 enable /tmp/my-radio-node
python3 -m ghot.radio_house_002 media /tmp/my-radio-node IDLE_CONFIRMED
python3 -m ghot.radio_house_002 submit /tmp/my-radio-node job-001 "public synthetic test input"
python3 -m ghot.radio_house_002 tick /tmp/my-radio-node job-001
python3 -m ghot.radio_house_002 media /tmp/my-radio-node RECORDING
python3 -m ghot.radio_house_002 tick /tmp/my-radio-node job-001
python3 -m ghot.radio_house_002 disable /tmp/my-radio-node
python3 -m ghot.radio_house_002 verify /tmp/my-radio-node
\`\`\`

The **tick command deliberately fails closed** when the physical GHoT power probe lacks temperature, load, confirmed external power or suitable willingness. It is acceptable for a desktop to HOLD until the real machine has adequate telemetry. The \`demo\` uses an explicitly synthetic power snapshot, so it never passes as a physical-field power test.

### Acceptance and known limits

- Default opt-in is off; enabling clears any previous idle observation.
- Fresh operator-observed IDLE_CONFIRMED (within 45 seconds) required. UNKNOWN or stale observations HOLD. An optimistic user-entered status is a claim, not a verified OBS sensor.
- External/mains/solar source, acceptable GHoT willingness, thermal reading ≤74°C and load per CPU ≤0.7 required; any unknown fails closed.
- One tick processes at most 256 local bytes and commits a checkpoint within one SQLite transaction. Concurrent attempts serialize; after a recording signal, the next tick holds. This **does not instantly preempt a hardware codec or native FFmpeg**.
- Only locally submitted, explicitly approved \`compute.public-hash/v0\` is possible. Input text is kept in the local database, not exported; **never use personal prayer/counseling, donor, unpublished ministry or licensed media data**.
- Strictly limited to 64KiB input and 256 jobs. Per-job cancel and global opt-out. Input, each processed chunk, and final computed digest are cold verified.
- Audit hashes prove local record *consistency* but NOT cryptographic authorship or resilience against complete local DB replacement. Need signed, durable external checkpoints and hardened Linux permissions for real machines.
- No actual resource donation, live remote compute dispatch or media broadcast has happened.

### World to aim for

Rock Impact operates one inexpensive Linux Static computer:

1. Records locally through OBS and preserves media, even if a stream fails (Static Live STREAM-001).
2. Produces its own podcasts and audio/video versions with the ministry's rights and review.
3. Provides GHoT with a **voluntary** bounded compute offer whenever not occupied, and automatically retracts it when live media is needed.
4. Eventually completes a source-approved remote job, cold-verifies a signed receipt through reLATTE and returns it without exposing any ministry media or giving up computer governance.
5. May optionally propose a rights-cleared segment to Kinship, which alone decides air/editorial outcome.

**LOCAL MEDIA > COMPUTE. OFFER != DISPATCH. CHECKPOINT != PROOF OF IDENTITY. NODE != CHURCH. SPARE COMPUTE != DONATED MONEY.**
