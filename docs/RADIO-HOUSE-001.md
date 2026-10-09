# RADIO HOUSE 001 — The First Nigerian Static Radio Node

## Origin

Apostle Tunji Ayodele-Babs leads Rock Impact Makers International Believers Ministry (Impact Makers Global) in Nigeria. The user has an existing personal conversation about the ministry improving livestreaming and podcast work, and is exploring a **separate** Minnesota church branch. Kinship Radio in Minnesota operates its own editorial and app infrastructure. None of these human institutions is yet a party to this experiment.

- Rock Impact site: https://rockimpactmakersglobal.org/
- Kinship: https://kinshipradio.org/main/
- Static Live STREAM-001: https://github.com/the-static-collective/static-live
- GHoT: https://github.com/the-static-collective/GHoT
- CANNON 007 (Africa readiness, unranked markets, aggregate finance): https://github.com/the-static-collective/CANNON/pull/11
- reLATTE receipts: https://github.com/the-static-collective/reLATTE

**This code neither starts a church nor executes radio.** It proves only a bounded, local-disk media transfer model with independent sender/receiver roles and distinct review/air states.

## Proposed first hardware topology

One Linux laptop/mini-PC at a consenting Nigerian ministry site, operated by its own media steward:
- Existing camera/phone, USB microphone (or audio interface), headphones, reliable external storage.
- OBS from Static Live's STREAM-001 for *record before live*. Its existing localhost control assumes separately installed/configured OBS.
- ffmpeg available as GHoT media capability (probe first, do not assume present).
- A local recording, then a locally produced podcast draft, then a deliberately authorized media sharing route.
- Stable GHoT node identity and low-power budgets; never send cloud credentials or unattended remote shell.
- A separate Kinship intake *review endpoint only if Kinship separately invites this*, never direct replacement of its vendor stream.

Future transport may use tested reLATTE native receivers and GHoT peer auth. This 001 does NOT cross real machines, verify actual operator identity, claim remote key custody, call OBS, modify a stream, syndicate licensed music, or collect personally sensitive prayer/counseling data.

## Run one bounded local proof

From repo root with Python 3.10+:

\`\`\`sh
python3 -m unittest discover -s tests -p "test_radio_house_001.py" -v
python3 -m ghot.radio_house_001 demo /tmp/ghot-radio-house-001
\`\`\`

The demo:
1. Creates synthetic (noncopyright) media bytes and a closed metadata envelope.
2. First refuses delivery because no source-owner selection or receiving-editor invitation is present.
3. With deliberately simulated both-side selections, starts writing 32-byte frames to a local test directory, deliberately interrupts after two frames, then resumes.
4. Reopens all frames and verifies the full SHA-256 against the exact source.
5. Returns \`HELD_FOR_RECIPIENT_LOCAL_REVIEW\`, **not** an actual editorial admission, broadcast receipt, station authorization or podcast publication.
6. Refuses malformed and unauthorized metadata, partial corruption and forged files.

Rights reference \`LAB-NO-REAL-RIGHTS\` is just a marker, NOT a right to use any real audio. Even if both operator boolean flags are true, the program explicitly says both identities are **not authenticated**.

## What we could pilot if invited

1. The Nigerian operator records a real 5-minute teaching or reflection into *his own* local files. Use a recording made with appropriate speaker/media consents and without identifying confidential counseling details.
2. Test voice intelligibility, local data cost, intermittent connectivity, export as a modest audio-only file. Separate broadcast live from preserve-local recording.
3. Operator makes one podcast draft under Rock Impact's own name, choosing a publisher with local consent and appropriate rights.
4. Only if Kinship agrees, request that its editor privately review a separate cleared sample (not a public rebroadcast of station music).
5. Measure operational failures and human time. Do not equate playback events with individual listeners or donations.
6. Make a reciprocal Kinship-to-Nigeria media test **only if** Kinship holds the precise distribution permissions; a public streaming app is not an automatic license to mirror copyrighted music.

## Constitutional authority
- Nigeria's ministry owns its own local node, ministry content, speakers' permissions and decisions.
- Minnesota's Kinship station owns broadcasting and its existing publisher/media stack.
- CANNON is a composition/source witness, not a rights agency.
- reLATTE can hold/carry verified descriptions only through independently admitted receiver authority.
- GHoT can advertise and process bounded compute work, not assume governance of a church.
- A proposed US church branch needs separate authorization, entity identity, leadership appointment rules and local legal compliance; this repo does none of that.

**NODE != CHURCH. TECHNICAL ROUTE != LEGAL BRANCH. INVITATION != PUBLICATION. CONTENT HASH != COPYRIGHT LICENSE. PACKET COMPLETED != AIRED. POWER LOSS != SOURCE LOSS.**
