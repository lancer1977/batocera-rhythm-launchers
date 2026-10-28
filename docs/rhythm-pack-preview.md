# Rhythm pack preview contract

The preview CLI is plan-only. It never applies a plan, downloads or extracts
archives, launches a runtime, creates mount/unit files, or contacts a device,
NAS, or network service. JSON is emitted to stdout by default. `--output FILE`
may create a new plan metadata file outside both source and target trees; existing files and symlink components are refused. The output parent must already exist.

## Inputs and version pins

* Inventory input must be emitted by the actual
  `Stepmania.Inventory.Cli` / `LibraryInventoryExporter` contract at
  StepManiaSongManager `072dcfb83e28fa3cd5b6754db668c006b01eeec7`, with
  `schemaVersion: 1`, `identityVersion: 1`, exact `installationRoot`, and the
  requested `packId`. Synthetic tests retain this provenance and do not claim
  to be real provider integrations.
* Validator input must be the JSON report from
  `stepmania-song-validator` 0.1.0. Its exact report fields are
  `library_path`, `songs_scanned`, `charts_scanned`, `error_count`,
  `warning_count`, `ok`, and `findings`; the adapter identifier is
  `stepmania-song-validator-0.1.0-report-v1`. `library_path` must equal the
  explicit source root. Missing means `UNAVAILABLE`; unsupported version or
  field shape means `UNKNOWN`; either blocks readiness. A report with `ok: false`
  is a blocking `FAIL`.
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

Run `bash tests/test-pack-preview.sh`. Fixtures are synthetic text only (no
private audio or song packs). The test proves plan generation leaves the target
unchanged, checks deterministic mapping across the separate runtime roots,
and verifies unsupported validator and source symlink blockers.

Provider checkouts were available at the pinned commits when this adapter was
implemented. A real provider integration is run separately when `dotnet` and
the validator 0.1.0 executable are already available; this project installs no
provider packages as part of preview.
