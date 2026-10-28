# Rhythm pack preview contract

The preview CLI is plan-only. It never applies a plan, downloads or extracts
archives, launches a runtime, creates mount/unit files, or contacts a device,
NAS, or network service. JSON is emitted to stdout by default. `--output FILE`
may create a new plan metadata file outside both source and target trees; existing files and symlink components are refused. The output parent must already exist.

## Inputs and version pins

* Inventory input must follow the
  `Stepmania.Inventory.Cli` / `LibraryInventoryExporter` adapter contract
  pinned to StepManiaSongManager `072dcfb83e28fa3cd5b6754db668c006b01eeec7`, with
  `schemaVersion: 1`, `identityVersion: 1`, exact `installationRoot`, and the
  requested `packId`. This is an adapter source pin, not proof of the inventory's
  producer. Synthetic inventories are fixtures, not provider integrations.
* `--validator-source PATH` enables live validation from an already available,
  trusted Python package source root. The preview runs `sys.executable -I`,
  inserts only that supplied root into `sys.path`, verifies module version
  `0.1.0`, and invokes `cli.main([source, "--json"])`. It snapshots every
  regular source-tree file before and after validation and rejects symlinks,
  unsupported entries, read errors, or any change. READY records the verified
  module version, live source snapshot SHA-256, and report SHA-256.
* `--validator-report` is display-only. A valid supplied report is labeled
  `UNVERIFIED` and blocks readiness because the preview cannot establish it
  describes the current source. Its exact report fields are
  `library_path`, `songs_scanned`, `charts_scanned`, `error_count`,
  `warning_count`, `ok`, and `findings`; the adapter identifier is
  `stepmania-song-validator-0.1.0-report-v1`. Missing executable/source means
  `UNAVAILABLE`; wrong version, invalid report, exception, or source mutation
  means `UNKNOWN`; these block readiness. A live report with `ok: false` is a
  blocking `FAIL`.
* Chart canonical identities are retained as unresolved provider data. A
  source simfile hash plus relative locator is local file provenance only and
  is never promoted to global chart identity.

## Safety and determinism

Every listed source asset must exist, be a regular non-symlink file within the
source root, and match the provider SHA-256. Any symlink in the selected pack,
path escape, inventory diagnostic, missing/unreadable asset, unsupported
Group/Song layout, hash drift, target conflict, unavailable free-space check,
or insufficient space blocks the plan. Existing identical target files are
reported as `identical`; different files and non-file entries are conflicts.
The plan records every source hash, destination, byte count, target hash/state,
inventory/report provenance, estimated bytes to add, and available bytes.
Target state is inspected read-only. Destination paths preserve the pack directory under the explicit runtime Songs root (for example, `Group/Song/chart.sm`). Runtime is mandatory and selected from
`stepmania-flatpak` and `itgmania-portable`, each with a caller-supplied
profile and Songs root; no cross-runtime default is inferred.

Output schema: `batocera.rhythm-pack-preview.v1`. Repeated inputs produce
stable JSON apart from filesystem-derived free space and explicitly selected
runtime/target metadata. Plans are input to a later staged-apply issue; they are
not authorization to apply.

## Validation

Run `bash tests/test-pack-preview.sh`. The synthetic inventory and mutation
validator are explicitly test fixtures; the integration test invokes the actual
validator source checkout when available. Fixtures contain text only (no
private audio or song packs). The test checks report-only blocking, live READY,
stale-report rejection when the actual validator finds a current error, source
mutation detection, unchanged targets, deterministic mapping, and safety blockers.

The preview installs no packages and performs no network or shell invocation.
