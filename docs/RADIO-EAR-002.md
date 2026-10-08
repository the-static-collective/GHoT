# RADIO-EAR-002 — Receive-only RTL-SDR Instrument Port

Status: draft experiment stacked on LISTENING-HEAP-001 (#71), which is
stacked on INSTRUMENT-RACK-001 (#69). No normative core edits.

## What is actually new?

The first real receiver *driver path*: one explicit, bounded invocation of
the existing open-source rtl_sdr CLI to capture an exact finite number of raw
8-bit interleaved IQ complex samples from a configured receiver index.

This does not claim a physical hardware event happened in CI. The included
hostile test uses a fake rtl_sdr executable and proves native GHoT dispatch
and Autodisco preparation, not antenna reception.

The driver can operate against a real receive-only RTL-SDR when a human
separately installs the CLI, connects suitable hardware/antenna, chooses
appropriate reception, and opts into the adapter manifest.

## Contract

Actual adapter capability: radio.rx.rtlsdr.capture

1. Opt-in the GHoT external adapter using GHOT_ADAPTER_MANIFESTS
   pointing at integrations/radio-ear-002/adapter-manifest.json.
2. Discover the proposal-only GHoT Instrument Rack card.
3. Pass an exact ghot.radio-ear-request/v0 to make_proposal().
4. Obtain a separate operator-explicit-radio-rx/v0 selection for that exact
   proposal/card/request, then call execute_selected_capture().
5. Native GHoT exact-card freshness revalidation and signed
   relatte.crossing-envelope/v0 local dispatch execute the donor exactly once.
6. The donor invokes rtl_sdr with a fixed argv array: -d, -f, -s, -n, -.
   No shell, no remote tuner, no transmit args.
7. Exact output length is 2 bytes per requested complex IQ sample. Any
   timeout, nonzero status, early EOF, extra output or unaligned data refuses.
8. The raw IQ bytes are SHA-256 bound and carried inline as base64 in the
   ghot.portable-seed-packet/v0 donor result. No automatic seed admission.
9. The eight derived scalar values are uncalibrated *time-window amplitude*
   summaries, not Fourier bins, spectrum, modulation, decoded message or
   RF signal identity.
10. native_autodisco_request() projects only the verified, explicitly
    uncalibrated summary into an exact SVG. LOOK-TWICE native prepare receives
    the artifact and returns two first-listen PACKETS. No Gemini calls or
    fabricated first-listen dialogue are part of this proof.

## Minimal operator request

    {
      "schema": "ghot.radio-ear-request/v0",
      "action": "capture_rx_iq",
      "device_index": 0,
      "frequency_hz": 162550000,
      "sample_rate_hz": 1024000,
      "complex_samples": 4096,
      "rx_scope": "public-or-otherwise-authorized"
    }

Example frequency is one NOAA weather-radio allocation; it does not
guarantee a receivable station at your location.

Bounded parameters:

- receive-only, mandatory exact request;
- device index 0–7 (an index, NOT authenticated device identity);
- center frequency 24 MHz–1.7 GHz, actual device-supported range may be narrower;
- sample rate 250 kHz–2.4 MHz, subject to driver/device limits;
- 4,096–65,536 complex samples, divisible by eight;
- at most 131,072 raw sample bytes held per capture;
- one rtl_sdr process, 12-second timeout;
- auto gain (no arbitrary gain/ppm option in this first cut).

Configuration:

    export GHOT_ADAPTER_MANIFESTS="$PWD/integrations/radio-ear-002/adapter-manifest.json"
    python3 ghot/reference_node.py pantry

The Rack card may be available because Python is installed even if a
physical RTL-SDR or rtl_sdr CLI is unavailable. Card availability is a
*software-adapter offer*, not proof of an antenna or driver device.

The default receiver executable is the local rtl_sdr found on PATH;
GHOT_RTLSDR_BIN is an OPERATOR-side override meant for explicit driver
selection and fake-driver test fixtures. It must not come from untrusted
radio messages or AI output.

No new CLI automatically authorizes a capture. The integration entrypoints
are make_proposal(), execute_selected_capture(), native_autodisco_request()
and prepare_autodisco(), all called by an explicitly configured host.

## Measurement limits

A successful process proves only that the configured host command emitted
the expected number of bytes. Signed GHoT receipts bind those bytes to a
local command execution; they do not prove on-air origin or receiver hardware.

The capture truth boundary therefore remains:

    status: HOST_REPORTED_RX_CAPTURE
    origin_assurance: host-driver-report-unverified-physical-origin
    hardware_identity_verified: false
    clock_uncertainty: unmeasured
    gap_status: unknown
    tx_enabled: false

Captured start/end timestamps are host UTC observations. There is no
calibration chain, hardware clock accuracy proof, missed sample/overrun proof,
device serial attestation, licensed operation assertion, recording privacy
guarantee or third-party transmitter authenticity claim.

## How to verify

    python3 ghot/radio_ear_sim.py

For the actual native Autodisco producer contract:

    AUTODISCO_LOOK_TWICE_SCRIPT=/path/to/Autodisco-v20/scripts/look-twice.mjs \
      python3 ghot/radio_ear_sim.py

CI runs both cases with a fake RTL-SDR executable and a pinned Autodisco v20
commit. It tests raw byte identities, truncated and oversized samples,
driver failure, request injection, false source confidence, changed evidence,
proposal/card staleness, absence of approval and exact GHoT replay.

## Outstanding actual physical proof

A real separate execution must provide actual device ownership, an eligible
receive-only frequency, explicit choice, an instrument observation, raw IQ
bytes, independent raw replay, driver metadata and proof that its event came
from a connected physical receiver. The present experiment cannot supply
that proof in hosted CI.

## Next

RADIO-ATTENTION-003 can add a bounded sweep planner over independent
receiver cards, making absence of observation distinct from observed silence.
RADIO-VOICE-004 remains a separately reviewed simulated-TX and legally
authorized hardware-controller problem. No transmitter is present here.

Laws:

    SOFTWARE CARD != VERIFIED RECEIVER
    DRIVER SUCCESS != RF ORIGIN PROOF
    RAW IQ != DECODED MESSAGE
    TIME WINDOWS != FREQUENCY SPECTRUM
    CAPTURE != CALIBRATED MEASUREMENT
    RECEIPT != PHYSICAL TRUTH
    RX != TX
    PROPOSAL != EXECUTION
    PACKET != ADMISSION
    FIRST-LISTEN PACKET != AI FIRST LISTEN
