# Rhythm Support Beta: song library guide

The Rhythm Support Beta installs launchers. It does not provide songs, song
packs, audio, video, or other copyrighted content. Add only content that you
created, licensed, purchased for this use, or otherwise have permission to
store and play. Do not commit or redistribute a song pack through this
repository or a release asset.

## Keep the runtimes separate

Each runtime has its own library. Copying a pack into one directory does not
make it available to the other runtime.

| Runtime | Songs directory | Batocera Ports entry |
| --- | --- | --- |
| StepMania Flatpak | `/userdata/system/share/stepmania-flatpak-launcher/Songs/` | **StepMania** |
| ITGmania portable | `/userdata/system/share/itgmania-portable-launcher/Songs/` | **ITGMania Portable** |

The installers create these directories. If you use a non-default
`STEPMANIA_SONGS_DIR` or `ITGMANIA_SONGS_DIR` in `config.env`, use that
configured directory instead and keep the two values different.

## Expected layout

Both runtimes expect the standard Group/Song structure. A song folder contains
its simfile and the assets referenced by that simfile:

```text
Songs/
└── My Group/
    └── My Song/
        ├── My Song.sm       # or My Song.ssc
        ├── music.ogg        # as referenced by the simfile
        ├── banner.png       # optional, if referenced
        └── jacket.png       # optional, if referenced
```

Copy the complete `Group/Song` tree, not just an isolated audio file or
simfile. Avoid nesting an extra pack directory above the group directory (for
example, `Songs/Pack/My Group/My Song`) unless that pack's own documentation
explicitly requires it; the game should be able to find the group directly
under `Songs/`.

For example, after copying a pack, these are valid discovery locations:

```text
/userdata/system/share/stepmania-flatpak-launcher/Songs/My Group/My Song/My Song.sm
/userdata/system/share/itgmania-portable-launcher/Songs/My Group/My Song/My Song.ssc
```

The ITGmania launcher configures its stock portable runtime with
`AdditionalSongFoldersReadOnly` pointing at its isolated `Songs/` directory.
The StepMania launcher passes its isolated directory as
`STEPMANIA_SONGS_DIR`. This keeps libraries and runtime data from crossing
between games.

## Copy safely

Install the launcher bundle first, then copy an owner-supplied pack into the
chosen runtime directory. A local computer can use `rsync` over SSH; replace
`<batocera>` with the operator's current Batocera host name or address:

```bash
rsync -a --progress "My Group/" \
  "<batocera>:/userdata/system/share/stepmania-flatpak-launcher/Songs/My Group/"
```

To make the same pack available to ITGmania, copy it separately to the
ITGmania path. Do not use a move, a wildcard aimed at `/userdata`, or a command
that removes the destination first. If a destination song folder already
exists, stop and inspect it before choosing whether to merge or preserve it.

After copying, launch the corresponding game from Batocera **Ports** and look
for the group and song in the song select screen. The Ports wrapper owns the
gameplay lifecycle and controller focus; direct service commands are for
diagnostics, not normal play.

## Remove or roll back without losing songs

Uninstalling a launcher is separate from managing its library. Roll back only
the launcher/service and its Ports entry using the bundle's documented
uninstall action. Preserve both `Songs/` directories, runtime user data,
staged ITGmania artifacts, and event data unless you intentionally archive or
remove those owner-controlled files yourself.

If a newly copied pack is the problem, remove or restore only that specific
`Group/Song` directory after closing the game and taking a backup. Never remove
the entire `Songs/` root to repair a launcher. The release-level installation
and rollback boundaries are in
[Rhythm Support Beta](releases/rhythm-support-beta.md), and the repeatable
operator steps are in the [LEN1 install checklist](rhythm-beta-len1-install-checklist.md).

## What this project can publish

The useful public artifact is the reproducible launcher and guidance: verified
checksums for runtime inputs, isolated paths, clear legal boundaries, and
rollback-safe Ports launchers. Song creation, chart authoring, and compatibility
testing belong in the content/tooling workflow; users supply the resulting
content under its own license.
