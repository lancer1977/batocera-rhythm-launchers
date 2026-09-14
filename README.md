# Batocera Rhythm Launchers

MIT-licensed, checksum-verified launcher bundles for running stock StepMania
and stock ITGmania on Batocera. This project publishes launchers and setup
guidance only: it does not contain game engines, songs, media, controller
firmware, or a custom Batocera image.

## Install the current beta

Download `install-rhythm-from-release.sh` and its matching `.sha256` file from
the latest GitHub prerelease. On the Batocera host:

```bash
sha256sum -c install-rhythm-from-release.sh.sha256
chmod +x install-rhythm-from-release.sh
./install-rhythm-from-release.sh --tag v0.1.0-rhythm-beta.5
```

The installer downloads, verifies, and unpacks both launcher bundles before
it installs either one. Add `--dry-run` to inspect the release plan first.

## What you provide

1. StepMania Flatpak `com.stepmania.StepMania` for the StepMania launcher.
2. The verified upstream ITGmania no-songs archive for ITGmania Portable.
3. Your own legal song content, placed separately for each runtime. See the
   [song-library guide](docs/rhythm-song-library-guide.md).

Launch both games from Batocera **Ports**, not from the diagnostic service
commands. That preserves controller focus and returns cleanly to
EmulationStation.

## Source and boundaries

The `bundles/` directory contains the two launcher sources. The beta release
assets are built from those sources and are accompanied by SHA-256 files. See
[release notes](docs/rhythm-support-beta.md) for runtime paths, input archive
verification, and rollback boundaries.
Checksum-verified Batocera launchers for stock StepMania and ITGmania.
