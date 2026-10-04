# Experiment 031 — Ice Cube Background Organ

031 turns Ice Cube 001 into ordinary GHoT work.

Flow:

```text
advertise ghot.ice-cube/v0
→ classify heavy
→ HOLD background work on ordinary battery
→ observe favorable power
→ normal OrganDaemon calls Wake Composer
→ normal reference-node execution
→ Dogram bounded verification
→ normal task receipt
→ release HOLD
```

Configure a body with:

```bash
export GHOT_DOGRAM_REPO=/path/to/Dogram
```

The offer exists only when that checkout contains `dogram/ice_cube.py`.

Submit:

```bash
python3 ghot/ice_cube_submit.py --lucas-index 5 --width 256 --height 256
```

The submitter uses background + deferrable scheduling and prefers surplus/external power.

CI proof:

```bash
python3 ghot/ice_cube_daemon_sim.py --dogram-repo _dogram_ice
```

It proves ordinary battery produces HOLD, renewable surplus wakes the same job through the ordinary organ cycle, a real small cube is mined, Dogram returns OK, and the HOLD releases against the normal GHoT task receipt.

Preserve:

```text
SCHEDULED != EXECUTED
HOLD != FAILURE
WAKE != VERIFICATION
EXECUTION RECEIPT != DOGRAM RECEIPT
RELEASED HOLD != ADMITTED ARTIFACT
LOCAL ARTIFACT != RETURNED ARTIFACT
```

032 can test signed return of the frozen artifact to the requesting body.
