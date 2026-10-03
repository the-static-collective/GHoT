# Power Field

The Liveness Field asks:

> Is this body awake?

The Power Field asks:

> What can this awake body afford to do right now?

Power pressure changes capability, not identity.

## V0 observations

Where the operating system exposes them, GHoT probes:

- battery percentage;
- charging state;
- external power source;
- Linux thermal zones;
- 1/5/15-minute system load;
- 1-minute load normalized by CPU count.

For solar/experimental hardware, explicit environment hints are also supported:

```bash
GHOT_POWER_SOURCE=solar \
GHOT_RENEWABLE_SURPLUS=1 \
GHOT_BATTERY_PERCENT=82 \
GHOT_CHARGING=1 \
python3 ghot/reference_node.py probe
```

Optional thermal hint:

```bash
GHOT_THERMAL_C=54
```

Manual hints are visible in the emitted probe metadata. They are not disguised as automatic measurements.

## Willingness

V0 derives one transparent willingness state:

- `abundant`
- `normal`
- `conserve`
- `critical`

Default thresholds:

- battery on battery power <= 25% => `conserve`;
- battery on battery power <= 10% => `critical`;
- temperature >= 85C => `conserve`;
- temperature >= 95C => `critical`;
- 1m load per CPU >= 2.0 => pressure toward `conserve`;
- 1m load per CPU >= 4.0 => `critical`;
- declared renewable surplus => `abundant` unless stronger pressure overrides it.

Every willingness result carries reasons.

## Capability power classes

V0 classifies offers as:

- `essential`
- `light`
- `medium`
- `heavy`

Examples:

- `system.*`, sensors and safety actuators: essential;
- runtime inspection and `media.probe`: light;
- small/local inference, speech and ordinary image transforms: medium;
- large inference, video rendering and image generation: heavy.

This classification is policy, not physics. It is explicit and replaceable.

## Withdrawal

`normal` and `abundant` expose all otherwise-valid offers.

Under `conserve`:

- heavy offers are withdrawn;
- medium/light/essential offers remain.

Under `critical`:

- only essential offers remain.

The BODY still records installed executors. The offer says whether GHoT is currently willing to expose them.

Example:

```text
battery 21%
source battery
willingness conserve

system.echo         available
llm.infer.small     available
llm.infer.large     withdrawn
render.video        withdrawn
```

At 8%:

```text
system.echo              available
sensor.temperature.read  available
llm.infer.small          withdrawn
render.video             withdrawn
```

## Solar surplus

A solar node can explicitly say that it currently has excess energy:

```bash
GHOT_POWER_SOURCE=solar GHOT_RENEWABLE_SURPLUS=1 ...
```

That raises willingness to `abundant` unless thermal/load/battery pressure requires a lower state.

Later hardware adapters can replace the manual hint with measured panel/controller data without changing the policy contract.

## Laws

- POWER STATE != IDENTITY
- INSTALLED CAPABILITY != CURRENT WILLINGNESS
- WITHDRAWN != DELETED
- RENEWABLE SURPLUS != UNBOUNDED COMPUTE
- POWER CLAIM != POWER PROOF
- THERMAL PRESSURE MAY OVERRIDE ENERGY ABUNDANCE
