# Rhythm Support Beta

This prerelease packages the verified Batocera launchers for stock StepMania
and stock ITGmania. It is an operator beta, not a custom Batocera image, an
engine fork, a song pack, or a remote-scoring service.

## Supported matrix

| Area | Verified beta support |
| --- | --- |
| Batocera host | LEN1, x86_64, Batocera X11 session |
| StepMania | Flatpak `com.stepmania.StepMania` `5.1.0-b2` |
| ITGmania | Upstream `ITGmania-1.3.0-Linux-no-songs.tar.gz`, x86_64 |
| Controller | `8BitDo Ultimate Wireless / Pro 2 Wired Controller` |
| ITGmania launch path | Batocera **Ports** → `ITGMania Portable` |
| Audio | PipeWire playback verified with the test chart |
| Sidecar telemetry | Separate JSONL and `state.json` stores using `stepmania-5.x-theme-lua` and `itgmania-theme-lua` |

The ITGmania input archive must be verified before installation:

```text
SHA-256: 0f106842a3a1fb9adb6d23df27557b60b9d4be23d661f2b5b2ed477eb63a7c09
Asset: ITGmania-1.3.0-Linux-no-songs.tar.gz
```

## Install

Download `install-rhythm-from-release.sh`,
`rhythm_release_transaction.py`, and their `.sha256` files from this same
GitHub prerelease. Keep all four files in one directory. Verify both program
files before running the shell entrypoint, then use the release tag shown on
that prerelease:

```bash
sha256sum -c install-rhythm-from-release.sh.sha256
sha256sum -c rhythm_release_transaction.py.sha256
chmod +x install-rhythm-from-release.sh
./install-rhythm-from-release.sh --tag v<version>
```

The installer downloads the two launcher bundles and their release checksums,
verifies them before extraction, and runs their local `install.sh` files. It
does not install either engine or any songs. To inspect without retaining
release assets or changing launchers, append `--dry-run`. To retain the
verified downloads, append
`--download-dir /userdata/system/backups/rhythm-beta-downloads`.
When a download directory is retained, each invocation creates a private
`.rhythm-stage.*` directory beneath it. The metadata, archives, checksums, and
extraction all remain in that unique stage, so a newer beta cannot mix files
with a previous invocation or overwrite predictable retained filenames.

Confirm the StepMania Flatpak is installed, then launch **StepMania** from
Batocera **Ports**. Do not use the direct service command for gameplay: the
Ports wrapper gives the game controller focus and returns cleanly to
EmulationStation, same as the ITGmania Ports launch path below.
`/userdata/system/services/stepmania-flatpak-launcher start` remains
available for diagnostics only.

For ITGmania, extract the archive and run `./install.sh`. Stage the verified
upstream archive in `/userdata/system/share/itgmania-portable-launcher/artifacts/`,
configure the explicit archive/runtime paths in `config.env`, then launch
**ITGMania Portable** from Batocera **Ports**. Do not use the direct service
command for gameplay: the Ports wrapper gives the game controller focus and
returns cleanly to EmulationStation.

## Song libraries

Songs are owner-supplied content and are not release payloads. Keep the
runtimes' libraries separate:

- StepMania: `/userdata/system/share/stepmania-flatpak-launcher/Songs/`
- ITGmania: `/userdata/system/share/itgmania-portable-launcher/Songs/`

Copy a complete `Group/Song/` tree containing its `.sm` or `.ssc` simfile and
referenced media into the selected directory. Do not redistribute content
unless its license permits it. The [song library guide](https://github.com/lancer1977/batocera-rhythm-launchers/blob/main/docs/rhythm-song-library-guide.md)
has the expected layout, safe copy procedure, discovery check, and
non-destructive rollback guidance.

## Boundaries and rollback

- The release contains launchers only. It does not include ITGmania, StepMania,
  songs, copyrighted media, controller firmware, or a Batocera image.
- ITGmania remains stock upstream and portable; no fork, build, or engine patch
  is required.
- The short `Quick Proof` chart was used only for host validation and is not a
  release payload.
- Remove only the installed launcher/service/test-theme files to roll back.
  Do not delete either runtime's normal user data or unrelated song libraries.

The beta was physically smoke-tested on a LEN1 x86_64 Batocera X11 host. Run
the documented Ports launch, controller, audio, song discovery, and clean
return-to-EmulationStation checks on your own hardware before relying on it.
