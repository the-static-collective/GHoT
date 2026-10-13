# RELAY-001 — LOADOUT → GHoT media-probe crossing

**Status:** Proposed review branch. This does not modify LOADOUT, reLATTE, any
source media, or GHoT main. It creates neither signed receipts nor publication.

## Why this slice

A human-supplied song ("Blue Night Morning Bloom") is the current intended
particular. Its locally measured MP3 SHA-256 is
`6ae3a6916c6214f7582da048246596d36a6cf355effe1dd68c47d685fef3acc6`.
The original audio is **not copied into this repository**. CI instead builds
an innocuous 0.25 s WAV fixture in the runner and destroys it after the job.

The two source-owned operators stay distinct:

1. **LOADOUT:** native `loadout.bind.evaluate_binding` and
   `validate_execution_attempt`, from a source checkout, evaluate
   `media.probe` with exact source parameters and the declared
   `filesystem.read` / `process.spawn.ffprobe` effect fence.
2. **GHoT:** native `reference_node._current_offer` discovers whether this
   body actually offers the `ffprobe` capability; native
   `reference_node.execute("media.probe", source_path, constraints=...)`
   invokes GHoT's existing executor pantry and emits a task/receipt pair.
3. **RELAY-001:** verifies the input hash before and after, verifies GHoT's
   own output hash, and saves a bounded unsigned *observation* linked to the
   LOADOUT parameter digest. This is a third-party report, not adoption.

Native project checkouts are required. The bridge intentionally has **no
substitute executor** when either is missing.

## Native local command

Use the unmodified local GHoT and LOADOUT checkouts:

```sh
SHA="$(sha256sum '/path/to/Blue Night Morning Bloom.mp3' | awk '{print $1}')"
GHOT_HOME=/tmp/relay001-ghot python3 ghot/relay001_loadout_probe.py \
  '/path/to/Blue Night Morning Bloom.mp3' \
  --sha256 "$SHA" \
  --loadout-src /path/to/LOADOUT/src \
  --ghot-root /path/to/GHoT \
  --out /tmp/relay001-native-receipt
```

To insist on an exact identity (rather than asking the tool to trust current
bytes), pass the pinned source SHA shown above instead of recomputing it.

Requires `ffprobe` installed and GHoT's normal runtime requirements.
The local GHoT node records its native task and receipt under `GHOT_HOME`.

### Expected files

- `loadout-parameters.json`: exact source path/hash, named capability
- `loadout-binding.json`: native LOADOUT `BIND` / `REFUSE` decision
- `ghot-task.json`: actual GHoT task with binding digest in constraints
- `ghot-receipt.json`: actual GHoT status and output digest
- `relay-crossing.json`: unsigned local joining witness, refusal on changed
  source or invalid native output hash

Negative tests refuse a mismatched source SHA and a fence lacking the
process-spawn effect **before invoking GHoT**.

## Evidentiary limits

- BIND is a local effect-fence decision, **not a signed owner capability**.
- A task/receipt pair shows what GHoT reports. It does **not** prove the
  semantic truth of metadata returned by ffprobe.
- Local outputs depend on exact runtime code and tools. This prototype records
  input bytes and LOADOUT parameter identity, but is not a full hermetic build
  attestation; it is not a reLATTE-signed crossing.
- The command reads the input media locally. It does not publish the song,
  contact Suno, authorize descendants or transfer rights.
- The CI artifact uses a synthetic WAV, not the human song, and by itself does
  not prove the song was probed by native GHoT.

The next crossing should attach **native executed task/receipt evidence for the
pinned MP3** using a machine with both source checkouts. Only then can the
song-specific project invitation advance from BOUND to EXECUTED.
