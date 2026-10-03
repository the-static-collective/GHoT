# Bootable Organ / Service Installation

Experiment 015 turns the 014 organ daemon from "a command you run" into
"something the machine can wake up as."

The deployment rule is conservative:

```text
STARTUP != AUTHORITY
INSTALL != IDENTITY
ENABLE != ADMISSION
```

The installer starts only:

```text
ghot/organ.py
```

It does not install or enable a lease authority.

## Linux: systemd user service

Default installation:

```bash
python3 ghot/install_organ.py systemd-user
```

Install and start immediately:

```bash
python3 ghot/install_organ.py systemd-user --enable-now
```

The unit is written to:

```text
~/.config/systemd/user/ghot-organ.service
```

and state defaults to:

```text
~/.local/state/ghot
```

or `$XDG_STATE_HOME/ghot` when configured.

The generated unit includes:

- `Restart=on-failure`;
- `NoNewPrivileges=true`;
- `PrivateTmp=true`;
- `ProtectSystem=strict`;
- `ProtectHome=read-only`;
- an explicit writable GHoT state path.

This is intentionally user-scoped and rootless by default.

### Boot before login

A systemd user unit runs when the user's systemd manager exists.

On some Linux installations, starting a user service before interactive login
requires that systemd lingering already be enabled for that account.

015 does **not** change linger policy automatically.

If the machine owner wants a user unit to run before login, configure that at
the OS/account layer according to the distribution's policy, commonly with a
command such as:

```bash
loginctl enable-linger "$USER"
```

That is an operating-system privilege/lifecycle decision, not a GHoT authority
decision.

## Linux uninstall

Remove the hook:

```bash
python3 ghot/install_organ.py systemd-user --uninstall
```

If it was enabled and should be stopped as part of removal:

```bash
python3 ghot/install_organ.py systemd-user --uninstall --enable-now
```

The latter flag means "apply systemctl state now" during uninstall.

Uninstall removes the startup unit. It does not delete `GHOT_HOME`.

Therefore:

```text
UNINSTALL STARTUP != FORGET BODY
```

## Termux / Android

Install the Termux:Boot launcher:

```bash
python3 ghot/install_organ.py termux
```

This writes:

```text
~/.termux/boot/ghot-organ
```

with executable mode `0700`.

The launcher:

- exports stable `GHOT_HOME`;
- changes into the GHoT repo;
- checks the previous PID witness;
- avoids starting a duplicate live daemon;
- removes a stale PID witness;
- starts `ghot/organ.py` with `nohup`;
- writes logs under `GHOT_HOME/logs/organ.log`.

Actual Android boot invocation requires the separate **Termux:Boot** app and
its normal platform setup. GHoT cannot manufacture Android boot permission.

After installing Termux:Boot, launch that app once as required by Termux's
platform workflow.

Remove the launcher:

```bash
python3 ghot/install_organ.py termux --uninstall
```

Again, durable GHoT state is preserved.

## Live USB / image build

015 does not mutate the current machine into a boot image.

Instead it renders an explicit bundle for an image-building pipeline.

Example:

```bash
python3 ghot/install_organ.py live-usb \
  --output-dir build/ghot-live \
  --target-repo-root /opt/GHoT \
  --target-python /usr/bin/python3 \
  --target-state-home /var/lib/ghot \
  --user ghot
```

The bundle contains:

```text
ghot-organ.service
INSTALL.txt
```

The system unit is intended to be copied into the live image at:

```text
/etc/systemd/system/ghot-organ.service
```

and enabled **inside the image**.

The image builder remains responsible for:

- creating the runtime user;
- placing GHoT at the target path;
- installing Python;
- making the state directory writable by the runtime user;
- enabling the unit inside the image.

The render command reports:

```text
modified_host: false
```

because generating a boot bundle is not the same as changing the current host.

## State location

A service should not rely on the launch working directory for identity.

Every install surface sets an explicit `GHOT_HOME`.

That home carries the durable body state developed by prior experiments:

```text
node-id
identity/
trust/
holds/
claims/
records/
organ/
field.v0.json
...
```

A process restart or repo upgrade may therefore preserve body continuity when
the same `GHOT_HOME` is retained.

## Repository upgrades

Generated startup hooks point to a specific repository path.

If GHoT is updated in place at that path, the service usually does not need to
be reinstalled.

If the repository or Python executable moves, rerun the installer so the
startup surface points at the new path.

## Status

Inspect known local startup hooks:

```bash
python3 ghot/install_organ.py status
```

This reports installation presence. It does not claim the service is healthy or
that the body is currently online.

For runtime health, inspect:

```text
GHOT_HOME/organ/state.v0.json
```

and the service manager itself.

## Security boundary

015 deliberately avoids:

- root installation by default;
- automatic authority creation;
- automatic trust admission;
- automatic linger-policy mutation;
- automatic live-image modification;
- deleting state on uninstall.

The startup surface is a launcher, not an authority.

## Laws

- STARTUP != AUTHORITY
- INSTALL != IDENTITY
- ENABLE != ADMISSION
- PROCESS ID != BODY IDENTITY
- INSTALL PATH != BODY IDENTITY
- UNINSTALL STARTUP != FORGET BODY
- RENDER IMAGE HOOK != MODIFY HOST
- OS BOOT POLICY != GHoT TRUST POLICY
