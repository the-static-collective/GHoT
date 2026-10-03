# Experiment 015 — Bootable Organ / Service Installation

## Question

Can GHoT install or render reversible startup surfaces for Linux, Termux/Android,
and live-USB images without requiring root by default, granting authority, or
destroying body state on uninstall?

## Trial A — deterministic installer simulation

```bash
python3 ghot/install_organ_sim.py
```

The simulation uses temporary directories only.

It proves:

1. the Linux user unit launches only `ghot/organ.py`;
2. the Linux unit does not install lease authority;
3. the unit carries rootless containment settings;
4. repeated install replaces one unit rather than creating duplicate hooks;
5. the Termux launcher is mode `0700`;
6. the Termux launcher guards against duplicate live PIDs;
7. the Termux launcher starts only `ghot/organ.py`;
8. the live-USB bundle targets explicit image paths;
9. rendering the live bundle does not modify the host;
10. uninstall removes startup hooks;
11. uninstall preserves the durable state directory.

Expected:

```json
{
  "simulation_passed": true
}
```

## Trial B — Linux user service

Render only:

```bash
python3 ghot/install_organ.py systemd-user
```

Inspect:

```bash
cat ~/.config/systemd/user/ghot-organ.service
```

Enable/start:

```bash
python3 ghot/install_organ.py systemd-user --enable-now
```

Then inspect:

```bash
systemctl --user status ghot-organ.service
```

Expected: the service runs `ghot/organ.py` and GHoT state appears under the
configured state home.

## Trial C — persistence across restart

Record:

```text
node_id
identity particular
```

Restart the service.

Expected: with the same `GHOT_HOME`, both remain stable.

## Trial D — uninstall without forgetting

Create a marker or observe real durable state under `GHOT_HOME`.

Then:

```bash
python3 ghot/install_organ.py systemd-user --uninstall
```

Expected:

- startup unit is gone;
- body state remains.

## Trial E — Termux render

Inside Termux:

```bash
python3 ghot/install_organ.py termux
```

Inspect:

```bash
ls -l ~/.termux/boot/ghot-organ
```

Expected:

- mode 0700;
- stable `GHOT_HOME`;
- PID guard;
- nohup organ launch;
- no lease-authority autostart.

Actual boot execution requires Termux:Boot to be installed/configured on the
Android device.

## Trial F — live image render

```bash
python3 ghot/install_organ.py live-usb \
  --output-dir build/ghot-live \
  --target-repo-root /opt/GHoT
```

Expected:

```text
build/ghot-live/ghot-organ.service
build/ghot-live/INSTALL.txt
```

No file is written to `/etc/systemd/system` on the current host.

## Pass

015 passes when the deterministic simulation and complete prior smoke suite are
green, and each platform path preserves:

```text
STARTUP != AUTHORITY
UNINSTALL STARTUP != FORGET BODY
```

## Mutation opened

016 can make the bootable organ self-describing at startup:

```text
boot manifest
+ startup receipt
+ version / git commit
+ state migration check
+ dependency readiness
+ local health endpoint
```

Then a machine can answer not only "I woke up" but:

```text
what code woke?
from which durable body state?
under which boot surface?
with which capabilities healthy?
what degraded?
```
