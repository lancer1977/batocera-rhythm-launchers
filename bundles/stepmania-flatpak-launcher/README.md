# StepMania Flatpak Launcher Publish

Bundle: `stepmania-flatpak-launcher`

This bundle makes StepMania a first-class Batocera publish target by giving the
already-installed Flatpak app a normal Batocera service wrapper, config file,
install helper, and smoke checklist.

## Current state

This is a host-gated launcher bundle. It assumes the target already has Flatpak
and `com.stepmania.StepMania` available, which was observed in target
diagnostics. The bundle does not own song generation or chart authoring; those
belong in the StepMania content/tooling repo. This repo owns the Batocera-side
install, launch, lifecycle, and recovery surface.

## Bundle contents

- `service.sh`: Batocera service entrypoint for starting, stopping, and checking
  StepMania through Flatpak.
- `ports-launcher.sh`: installed as a Batocera Port (`StepMania.sh`). Keeps the
  Port foregrounded while StepMania runs so Batocera performs its normal game
  input handoff, instead of leaving EmulationStation to share the controller
  event device with the service. This mirrors the ITGmania portable launcher's
  Ports wrapper. Launch StepMania from Batocera Ports for gameplay; starting
  `service.sh` directly is for diagnostics only and does not get a clean
  controller handoff.
- `install.sh`: staging helper that installs the service, Ports launcher,
  config, payload notes, and persistent song directory.
- `apply-controller-map.sh`: writes a backed-up StepMania `Keymaps.ini` default
  for Player 1 gamepad control.
- `config.example`: non-secret runtime defaults for the target host.
- `payload/`: operator notes staged with the bundle.

Re-running `install.sh` for a beta upgrade preserves an existing
`/userdata/system/share/stepmania-flatpak-launcher/config.env`, including
host-specific display and pipeline settings. To deliberately replace it with
the bundle defaults, run the installer with `RHYTHM_RESET_CONFIG=1`; this is an
explicit reset and should be followed by reviewing the resulting file.

## Runtime shape

The service defaults to:

- `FLATPAK_APP_ID=com.stepmania.StepMania`
- `STEPMANIA_DATA_ROOT=/userdata/system/share/stepmania-flatpak-launcher`
- `STEPMANIA_SONGS_DIR=/userdata/system/share/stepmania-flatpak-launcher/Songs`
- `STEPMANIA_EXTRA_ARGS=`
- `STEPMANIA_APPLY_DEFAULT_CONTROLLER_MAP=1`
- `STEPMANIA_KEYMAPS_PATH=/userdata/saves/flatpak/data/.var/app/com.stepmania.StepMania/.stepmania-5.1/Save/Keymaps.ini`

Optional pipeline/remote-launch controls:

- `STEPMANIA_PIPELINE_INITIAL_SCREEN=ScreenPolyhydraPipeline`
- `STEPMANIA_PIPELINE_SCREEN_CLASS=ScreenWithMenuElements`
- `STEPMANIA_PIPELINE_SCREEN_FALLBACK=ScreenWithMenuElementsBlank`
- `STEPMANIA_PIPELINE_SCREEN=`
- `STEPMANIA_PIPELINE_SONG=`
- `STEPMANIA_PIPELINE_SONG_DIR=`
- `STEPMANIA_PIPELINE_DIFFICULTY=`
- `STEPMANIA_PIPELINE_AUTOPLAY=`
- `STEPMANIA_PIPELINE_EMIT_SONG_CATALOG=`
- `STEPMANIA_PIPELINE_CATALOG_LIMIT=`
- `STEPMANIA_PIPELINE_EVENT_DIR=`

The service starts `flatpak run com.stepmania.StepMania` in the background and
records a pidfile under `/var/run/stepmania-flatpak-launcher.pid`.

On the standard Batocera X session, the service discovers the current X
server's per-boot `-auth` cookie before launching Flatpak. This avoids a stale
PID-specific `XAUTHORITY` setting across reboots. Set `XAUTHORITY` in
`config.env` only when the host uses a non-standard display session.

The default controller mapper targets the first detected joystick (`Joy1`),
which is how StepMania stores the Microsoft Xbox Controller on the current
Batocera target. It maps D-pad/left-stick axes to arrows/menu movement, `B9` to
Back/Select, and `B10` to Start. Existing `Keymaps.ini` is backed up under the
bundle directory before replacement.

## Smoke flow

1. Stage the bundle with `install.sh` or through the bundle catalog workflow.
2. Confirm `flatpak list --app` includes `com.stepmania.StepMania`.
3. Confirm `stepmania-controller-map.json` reports `status: applied`.
4. Launch "StepMania" from Batocera Ports (`/userdata/roms/ports/StepMania.sh`).
   Use `/userdata/system/services/stepmania-flatpak-launcher start` only for
   diagnostics; it leaves EmulationStation sharing the controller event device.
5. Confirm StepMania opens on the target display and controller navigation
   works, and that leaving the Port returns cleanly to EmulationStation.
6. Stop and restart the service to verify lifecycle control.
7. Copy a known-good song pack into `Songs/` and confirm StepMania sees it.

## Validation boundary

Local automation validates the bundle contract and shell syntax. Display,
controller, audio, and song-pack behavior require a physical Batocera smoke
test.
