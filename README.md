# Batocera Rhythm Launchers

MIT-licensed, checksum-verified launcher bundles for running stock StepMania
and stock ITGmania on Batocera. This project publishes launchers and setup
guidance only: it does not contain game engines, songs, media, controller
firmware, or a custom Batocera image.

## Install the current beta

Download `install-rhythm-from-release.sh`,
`rhythm_release_transaction.py`, and each matching `.sha256` file from the
same GitHub prerelease. Keep all four files in one directory. On the Batocera
host:

```bash
sha256sum -c install-rhythm-from-release.sh.sha256
sha256sum -c rhythm_release_transaction.py.sha256
chmod +x install-rhythm-from-release.sh
./install-rhythm-from-release.sh --tag v<version>
```

The checksum-verified shell entrypoint invokes the checksum-verified local
transaction helper. It downloads, verifies, and unpacks both launcher bundles before
it installs either one. Add `--dry-run` to inspect the release plan first.
When `--download-dir` is supplied, the installer pins that directory and its
private stage with Linux file descriptors for the entire metadata, download,
checksum, extraction, and install transaction; it does not reopen the stage
by its mutable pathname.

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

## Read-only song-pack preview

`rhythm_pack_preview.py` creates a deterministic plan from a real
`Stepmania.Inventory.Cli` inventory schema v1 export. Supply the exact inventory
pack ID, an explicit source root, a configured runtime Songs root and profile,
and live validation by `stepmania-song-validator` 0.1.0. A report-only input is
unverified and blocks the plan. This tool does not copy files,
download content, launch a game, or change either runtime.

Example (inventory and validator commands run against a synthetic/test root or
the operator's own local library):

```bash
dotnet run --project /path/to/Stepmania.Inventory.Cli -- inventory-id /path/to/library > inventory.json
python3 rhythm_pack_preview.py --source /path/to/library --inventory inventory.json \
  --pack 'pack:Group' --runtime stepmania-flatpak \
  --target /userdata/system/share/stepmania-flatpak-launcher/Songs \
  --profile stock-stepmania-flatpak \
  --validator-source /path/to/stepmania-song-validator/src
```

The other runtime is `itgmania-portable`; its default Songs root is
`/userdata/system/share/itgmania-portable-launcher/Songs` and profile is
`stock-itgmania-portable`. Never point one runtime at the other's target. JSON
goes to stdout by default; `--output plan.json` stores only plan metadata.
Preview schema is `batocera.rhythm-pack-preview.v1`. Inventory provenance records
adapter source pin `072dcfb83e28fa3cd5b6754db668c006b01eeec7` and
inventory schema v1. The validator adapter accepts only version 0.1.0's exact
report field set (`stepmania-song-validator-0.1.0-report-v1`). Chart identity
remains unresolved: source hashes and locators are provenance scoped to this
inventory, not global equivalence claims. See
[`docs/rhythm-pack-preview.md`](docs/rhythm-pack-preview.md) for full contract.
Checksum-verified Batocera launchers for stock StepMania and ITGmania.
