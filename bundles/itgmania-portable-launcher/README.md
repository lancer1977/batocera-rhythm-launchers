# itgmania-portable-launcher

An isolated Batocera service for the qualified, unmodified upstream ITGmania
v1.3.0 Linux no-songs artifact. It never uses Flatpak paths or modifies the
`stepmania-flatpak-launcher` bundle.

The payload is produced outside this repository: stage the qualified upstream
archive at the configured artifact path. This bundle does not vendor, download,
compile, or patch ITGmania.

1. Stage the artifact named in `config.env` and verify its SHA-256.
2. Run `./install.sh`; configure only explicit artifact/runtime/executable paths.
3. Launch `ITGMania Portable.sh` from Batocera **Ports**.

The service rejects a missing or changed archive, validates the upstream layout,
creates `Portable.ini` only when absent, mounts only this bundle's `Songs/`
directory through ITGmania's `AdditionalSongFoldersReadOnly` preference, and accepts only
`SIDECAR_CAPABILITY_PROFILE=itgmania-theme-lua`. It does not download, compile,
or patch ITGmania. Physical validation still requires display, controller,
audio, known-good songs, Sidecar JSONL/state, lifecycle cleanup, and rollback.

The installer places the foreground wrapper at
`/userdata/roms/ports/ITGMania Portable.sh`. It starts the isolated service,
waits for ITGmania to exit, then stops it and briefly holds the Ports process
open. This lets Batocera hand controller focus to the game; starting the
service directly is for diagnostics only and leaves EmulationStation input
active.
