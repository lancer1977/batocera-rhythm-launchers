#!/usr/bin/env python3
"""Transaction tests driven by the REAL stepmania-song-validator package.

Scope: rhythm_pack_preview.preview and rhythm_pack_transaction apply/recover/
rollback, exercised against the actual validator source named by the
RHYTHM_VALIDATOR_SOURCE environment variable (the ``src`` directory that
contains ``stepmania_song_validator/__init__.py``, validator version 0.1.0).

Failure policy: if the variable is unset, names a missing directory, lacks the
package, or the package is not version 0.1.0, setUpModule raises and the suite
errors. It never skips, and it never fabricates a validator provider.

Run from the repository root:

    RHYTHM_VALIDATOR_SOURCE=/path/to/stepmania-song-validator/src \
        python3 tests/test-real-validator-transaction.py

Every library, target Songs root, inventory, and plan lives under a fresh
tempfile directory. Audio is synthetic bytes (b"synthetic-audio"). The tests
do not read or write HOME, do not use the network, and do not touch the real
Songs roots. Audio validity is out of scope; the validator only needs the
#MUSIC file to exist.

SM syntax used here follows the validator's own parser and checks:
  - #TAG:value; directives, #BPMS with a positive value, #MUSIC naming an
    existing file, and the five #NOTES header fields followed by note data.
  - These fixtures use four-row measures; that is not an engine validity rule.
  - Warning-only chart: omit #MUSIC, which yields missing_music_tag (WARNING).
  - Invalid chart: one note row with 'Q', which yields invalid_note_characters
    (ERROR).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
from unittest import mock
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import rhythm_pack_preview as preview  # noqa: E402
tx = importlib.import_module("rhythm_pack_transaction")  # noqa: E402

ENV_VAR = "RHYTHM_VALIDATOR_SOURCE"
EXPECTED_VALIDATOR_VERSION = "0.1.0"
PACK = "pack:Group"
PROFILE = "synthetic-profile"
RUNTIMES = {
    "stepmania-flatpak": "Songs-stepmania-flatpak",
    "itgmania-portable": "Songs-itgmania-portable",
}
MUSIC_NAME = "synthetic.ogg"
AUDIO_BYTES = b"synthetic-audio"
FINDING_KEYS = {"category", "severity", "code", "message", "path"}

VALID_CHART = "\n".join([
    "#TITLE:Synthetic Fixture;",
    "#ARTIST:Synthetic Artist;",
    f"#MUSIC:{MUSIC_NAME};",
    "#BPMS:0.000=120.000;",
    "#NOTES:",
    "     dance-single:",
    "     Synthetic:",
    "     Easy:",
    "     1:",
    "     0.000,0.000,0.000,0.000,0.000:",
    "0000", "0100", "0010", "0001", ",",
    "0000", "1000", "0000", "0100", ";",
    "",
])
# Warning-only: no #MUSIC tag, so the validator reports missing_music_tag (WARNING).
WARNING_CHART = VALID_CHART.replace(f"#MUSIC:{MUSIC_NAME};\n", "")
# One note row with an invalid token 'Q' -> invalid_note_characters (ERROR).
INVALID_CHART = VALID_CHART.replace("\n1000\n", "\n1Q00\n")
assert WARNING_CHART != VALID_CHART and INVALID_CHART != VALID_CHART

VALIDATOR_SRC: str = ""


def setUpModule() -> None:
    """Fail loudly unless RHYTHM_VALIDATOR_SOURCE names the real validator src."""
    global VALIDATOR_SRC
    raw = os.environ.get(ENV_VAR, "")
    if not raw:
        raise RuntimeError(
            f"{ENV_VAR} is unset. Set it to the real stepmania-song-validator src "
            "directory (the one containing stepmania_song_validator/__init__.py). "
            "This suite does not skip and does not fabricate a validator.")
    src = Path(raw).absolute()
    if not src.is_dir():
        raise RuntimeError(f"{ENV_VAR}={raw!r} is not an existing directory")
    init = src / "stepmania_song_validator" / "__init__.py"
    if not init.is_file():
        raise RuntimeError(
            f"{ENV_VAR}={raw!r} lacks stepmania_song_validator/__init__.py; "
            "point it at the src directory, not the repository root")
    if not re.search(r"""__version__\s*=\s*['"]%s['"]""" % re.escape(EXPECTED_VALIDATOR_VERSION),
                     init.read_text(encoding="utf-8")):
        raise RuntimeError(
            f"{ENV_VAR}={raw!r} is not validator {EXPECTED_VALIDATOR_VERSION}; "
            "the transaction contract is pinned to that version")
    VALIDATOR_SRC = str(src.resolve())


# ---------------------------------------------------------------- helpers

class SimulatedInterruption(Exception):
    """Injected at a named transaction boundary to model a crash."""


def interrupt_at(point_name: str):
    """Return a transaction hook that raises at the named boundary only."""
    def hook(point: str) -> None:
        if point == point_name:
            raise SimulatedInterruption(point)
    return hook


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_hex64(test: unittest.TestCase, value: object) -> None:
    test.assertIsInstance(value, str)
    test.assertIsNotNone(re.fullmatch(r"[0-9a-f]{64}", value), value)


def tree_files(base: Path) -> dict[str, bytes]:
    """Map each regular file under base (posix relative path) to its bytes."""
    files: dict[str, bytes] = {}
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise AssertionError(f"unexpected symlink in fixture tree: {path}")
        if path.is_file():
            files[path.relative_to(base).as_posix()] = path.read_bytes()
    return files


def pack_files(target: Path) -> dict[str, bytes]:
    """Files under the activated pack, excluding the transaction owner marker."""
    return {k: v for k, v in tree_files(target / "Group").items() if k != tx.OWNER_MARKER}


def make_library(root: Path, *, target_name: str, chart: str = VALID_CHART,
                 with_audio: bool = True) -> dict:
    """Build source (Group/Song), empty target Songs root, and a matching inventory.

    root must already be a realpath (no symlink components).
    """
    source = root / "source"
    target = root / target_name
    song = source / "Group" / "Song"
    song.mkdir(parents=True)
    target.mkdir(parents=True)
    chart_path = song / "chart.sm"
    chart_path.write_text(chart, encoding="utf-8")
    assets = []
    if with_audio:
        (song / MUSIC_NAME).write_bytes(AUDIO_BYTES)
        assets.append({"relativeLocation": f"Group/Song/{MUSIC_NAME}", "status": "present",
                       "sha256": sha256_hex(AUDIO_BYTES)})
    inventory = {
        "schemaVersion": 1, "identityVersion": 1, "installationId": "synthetic-fixture",
        "installationRoot": str(source), "diagnostics": [],
        "packs": [{
            "packId": PACK, "relativeLocation": "Group", "diagnostics": [], "assets": [],
            "songs": [{
                "relativeLocation": "Group/Song", "diagnostics": [], "assets": assets,
                "charts": [{"sourceRelativeLocation": "Group/Song/chart.sm",
                            "sourceRevision": sha256_hex(chart_path.read_bytes())}],
            }],
        }],
    }
    inventory_path = root / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    return {"root": root, "source": source, "target": target, "inventory": inventory_path}


def write_json(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def preview_ns(lib: dict, runtime: str, validator_source: str) -> argparse.Namespace:
    return argparse.Namespace(
        source=str(lib["source"]), target=str(lib["target"]), inventory=str(lib["inventory"]),
        validator_report=None, validator_source=validator_source, validator_version=None,
        pack=PACK, runtime=runtime, profile=PROFILE)


def build_plan(lib: dict, runtime: str, validator_source: str) -> dict:
    return preview.preview(preview_ns(lib, runtime, validator_source))


def apply_ns(lib: dict, plan_path: Path, runtime: str, validator_source: str) -> argparse.Namespace:
    return argparse.Namespace(
        plan=str(plan_path), source=str(lib["source"]), inventory=str(lib["inventory"]),
        validator_source=validator_source, pack=PACK, runtime=runtime, profile=PROFILE,
        target=str(lib["target"]), game_stopped=True)


def recover_ns(lib: dict, txid: str, source: Path | None = None,
               validator_source: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        target=str(lib["target"]), transaction=txid,
        source=str(source) if source is not None else None,
        validator_source=validator_source)


def receipt_files(target: Path) -> list[Path]:
    state = target / tx.STATE_DIR
    return sorted(state.glob("*.json")) if state.is_dir() else []


def only_txid(target: Path) -> str:
    files = receipt_files(target)
    if len(files) != 1:
        raise AssertionError(f"expected exactly one receipt, found {len(files)}")
    return files[0].stem


def read_receipt(target: Path, txid: str) -> dict:
    return json.loads((target / tx.STATE_DIR / f"{txid}.json").read_text(encoding="utf-8"))


def stage_dir(target: Path, txid: str) -> Path:
    return target / (tx.STAGE_PREFIX + txid)


def validator_findings(validator_block: dict) -> list[dict]:
    """Return provenance.validator.findings, failing if the core change is absent."""
    if "findings" not in validator_block:
        raise AssertionError(
            "provenance.validator.findings is missing; this suite requires the core change "
            "that records validator findings (category, severity, code, message, path) in report order")
    return validator_block["findings"]


class RealValidatorCase(unittest.TestCase):
    """Base class: fresh realpath temp root per test, and shared helpers."""

    def new_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory(prefix="rhythm-real-validator-")
        self.addCleanup(tmp.cleanup)
        return Path(os.path.realpath(tmp.name))

    def assert_no_active_receipt(self, target: Path) -> None:
        for path in receipt_files(target):
            self.assertNotEqual(read_receipt(target, path.stem)["status"], "active", path)

    def ready_plan(self, lib: dict, runtime: str) -> tuple[dict, Path]:
        plan = build_plan(lib, runtime, VALIDATOR_SRC)
        self.assertEqual(plan["status"], "READY", plan["blockers"])
        return plan, write_json(Path(lib["root"]) / "plan.json", plan)

    def interrupted_apply(self, lib: dict, runtime: str) -> str:
        """Apply until the before-activation boundary; return the transaction id."""
        _, plan_path = self.ready_plan(lib, runtime)
        with self.assertRaises(SimulatedInterruption):
            tx.apply(apply_ns(lib, plan_path, runtime, VALIDATOR_SRC),
                     hook=interrupt_at("before-activation"))
        target = Path(lib["target"])
        txid = only_txid(target)
        self.assertEqual(read_receipt(target, txid)["status"], "staging")
        self.assertTrue(stage_dir(target, txid).is_dir())
        self.assertFalse((target / "Group").exists())
        return txid


# ---------------------------------------------------------------- scenario 1

class OwnershipCopyTests(RealValidatorCase):
    """Copied marker bytes cannot establish ownership after root inode reuse."""

    def test_copied_pack_with_reused_root_identity_is_not_adopted_or_deleted(self):
        for rollback in (False, True):
            with self.subTest(rollback=rollback):
                lib = make_library(self.new_root(), target_name='target')
                _, plan_path = self.ready_plan(lib, 'stepmania-flatpak')
                receipt = tx.apply(apply_ns(lib, plan_path, 'stepmania-flatpak', VALIDATOR_SRC))
                target = lib['target']; pack = target / 'Group'
                aside = lib['root'] / 'original-owned-pack'
                pack.rename(aside)
                shutil.copytree(aside, pack)
                before = tree_files(pack)
                identity = {k: receipt['ownership'][k] for k in ('device', 'inode')}
                # External filesystem metadata control: the real host reproduced
                # deletion/recreation with identical dev+ino. Keep the original
                # inode alive for deterministic copying, then emulate that exact
                # root stat observation; marker bytes remain an actual file copy.
                with mock.patch.object(tx, 'stage_identity', return_value=identity):
                    with self.assertRaises(RuntimeError):
                        tx.recover(recover_ns(lib, receipt['id']), rollback=rollback)
                self.assertEqual(tree_files(pack), before)
                failed = read_receipt(target, receipt['id'])
                self.assertIn('ownership-mismatch', failed['conflicts'])
                self.assertNotEqual(failed['status'], 'rolled-back')

    def test_missing_or_malformed_marker_identity_preserves_target(self):
        for bad in (None, {'device': True, 'inode': 1, 'bytes': 1, 'mtimeNs': 1, 'ctimeNs': 1}):
            with self.subTest(identity=bad):
                lib = make_library(self.new_root(), target_name='target')
                _, plan_path = self.ready_plan(lib, 'stepmania-flatpak')
                receipt = tx.apply(apply_ns(lib, plan_path, 'stepmania-flatpak', VALIDATOR_SRC))
                path = lib['target'] / tx.STATE_DIR / (receipt['id'] + '.json')
                if bad is None:
                    receipt['ownership'].pop('markerIdentity')
                else:
                    receipt['ownership']['markerIdentity'] = bad
                write_json(path, receipt)
                before = tree_files(lib['target'])
                with self.assertRaises(RuntimeError):
                    tx.recover(recover_ns(lib, receipt['id']), rollback=True)
                self.assertEqual(tree_files(lib['target']), before)

    def test_plan_without_findings_is_rejected_by_actual_apply(self):
        lib = make_library(self.new_root(), target_name='target')
        plan, plan_path = self.ready_plan(lib, 'stepmania-flatpak')
        del plan['provenance']['validator']['findings']
        write_json(plan_path, plan)
        before = tree_files(lib['target'])
        with self.assertRaises(RuntimeError):
            tx.apply(apply_ns(lib, plan_path, 'stepmania-flatpak', VALIDATOR_SRC))
        self.assertEqual(tree_files(lib['target']), before)

    def test_validator_source_checkout_is_not_written(self):
        lib = make_library(self.new_root(), target_name='target')
        copied = lib['root'] / 'provider-source'
        shutil.copytree(VALIDATOR_SRC, copied, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        before = tree_files(copied)
        plan = build_plan(lib, 'stepmania-flatpak', str(copied))
        self.assertEqual(plan['status'], 'READY', plan['blockers'])
        self.assertEqual(tree_files(copied), before)


class HappyPathTests(RealValidatorCase):
    """Real validator PASS, then apply, reload, recover, and rollback, per runtime."""

    def run_lifecycle(self, runtime: str) -> None:
        root = self.new_root()
        lib = make_library(root, target_name=RUNTIMES[runtime])
        source, target = lib["source"], lib["target"]

        # Unrelated operator content already in the Songs root must survive everything.
        (target / "OtherPack").mkdir()
        (target / "OtherPack" / "keep.txt").write_bytes(b"unrelated pack content")
        (target / "readme-operator.txt").write_bytes(b"operator note")
        unrelated_before = tree_files(target)

        source_before = preview.source_snapshot(source)
        plan, plan_path = self.ready_plan(lib, runtime)
        self.assertEqual(plan["runtime"], runtime)
        self.assertEqual(plan["blockers"], [])
        validator_block = plan["provenance"]["validator"]
        self.assertEqual(validator_block["status"], "PASS")
        self.assertEqual(validator_block["verifiedModuleVersion"], EXPECTED_VALIDATOR_VERSION)
        self.assertEqual(validator_block["version"], EXPECTED_VALIDATOR_VERSION)
        assert_hex64(self, validator_block["liveSourceSnapshotSha256"])
        assert_hex64(self, validator_block["reportSha256"])

        receipt = tx.apply(apply_ns(lib, plan_path, runtime, VALIDATOR_SRC))
        txid = receipt["id"]
        self.assertEqual(receipt["status"], "active")
        self.assertEqual(receipt["runtime"], runtime)
        self.assertEqual(receipt["profile"], PROFILE)
        self.assertEqual(receipt["packRoot"], "Group")
        self.assertEqual(receipt["targetSongsRoot"], str(target))
        self.assertEqual(receipt["activationValidation"], validator_block)

        # Activated files match the source bytes exactly; only the owner marker is added.
        self.assertEqual(pack_files(target), tree_files(source / "Group"))
        self.assertIn(tx.OWNER_MARKER, tree_files(target / "Group"))
        self.assertFalse([p for p in target.iterdir() if p.name.startswith(tx.STAGE_PREFIX)])
        self.assertEqual(preview.source_snapshot(source), source_before)

        # Receipt is reloadable from disk, both raw and through the fd-validated loader.
        self.assertEqual(read_receipt(target, txid)["status"], "active")
        state_fd = tx.open_directory_walk(str(target / tx.STATE_DIR))
        try:
            reloaded = tx.load_receipt(state_fd, txid)
        finally:
            os.close(state_fd)
        self.assertEqual(reloaded["status"], "active")
        self.assertEqual(reloaded["id"], txid)

        # Recovering an active receipt keeps it active.
        recover_args = recover_ns(lib, txid, source, VALIDATOR_SRC)
        self.assertEqual(tx.recover(recover_args)["status"], "active")

        # Rollback removes only transaction-owned files and the empty pack directory.
        rolled = tx.recover(recover_args, rollback=True)
        self.assertEqual(rolled["status"], "rolled-back")
        self.assertFalse((target / "Group").exists())
        self.assertEqual(read_receipt(target, txid)["status"], "rolled-back")
        after_rollback = tree_files(target)
        for rel, content in unrelated_before.items():
            self.assertEqual(after_rollback.get(rel), content, rel)
        self.assertFalse([k for k in after_rollback if k.startswith("Group/")])

    def test_stepmania_flatpak_lifecycle(self) -> None:
        self.run_lifecycle("stepmania-flatpak")

    def test_itgmania_portable_lifecycle(self) -> None:
        self.run_lifecycle("itgmania-portable")


# ---------------------------------------------------------------- scenario 2

class WarningOnlyChartTests(RealValidatorCase):
    """Real validator WARNING findings keep the plan READY and PASS, and still apply."""

    def test_warning_only_chart_is_ready_records_findings_and_applies(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs", chart=WARNING_CHART, with_audio=False)
        plan, plan_path = self.ready_plan(lib, "stepmania-flatpak")
        validator_block = plan["provenance"]["validator"]
        self.assertEqual(validator_block["status"], "PASS")
        self.assertEqual(validator_block["verifiedModuleVersion"], EXPECTED_VALIDATOR_VERSION)
        self.assertEqual(validator_block["errorCount"], 0)
        self.assertGreaterEqual(validator_block["warningCount"], 1)

        findings = validator_findings(validator_block)
        codes = [f["code"] for f in findings]
        self.assertIn("missing_music_tag", codes)
        for finding in findings:
            self.assertEqual(set(finding), FINDING_KEYS, finding)
            self.assertIn(finding["severity"], ("error", "warning"))
        self.assertEqual(validator_block["warningCount"],
                         sum(f["severity"] == "warning" for f in findings))

        # Findings must equal the real validator's report, in the same order.
        live_report, live_version, _ = preview.run_live_validator(
            lib["source"], Path(VALIDATOR_SRC))
        self.assertEqual(live_version, EXPECTED_VALIDATOR_VERSION)
        self.assertIsNotNone(live_report)
        self.assertEqual(findings, live_report["findings"])

        receipt = tx.apply(apply_ns(lib, plan_path, "stepmania-flatpak", VALIDATOR_SRC))
        self.assertEqual(receipt["status"], "active")
        self.assertEqual(pack_files(lib["target"]), tree_files(lib["source"] / "Group"))


# ---------------------------------------------------------------- scenario 3

class InvalidChartTests(RealValidatorCase):
    """Real invalid note token: preview BLOCKED, and apply refuses forged or blocked plans."""

    def test_invalid_note_token_blocks_and_apply_refuses(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs", chart=INVALID_CHART)
        plan = build_plan(lib, "stepmania-flatpak", VALIDATOR_SRC)
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIn("validator-failed", plan["blockers"])
        validator_block = plan["provenance"]["validator"]
        self.assertEqual(validator_block["status"], "FAIL")
        self.assertGreaterEqual(validator_block["errorCount"], 1)

        findings = validator_findings(validator_block)
        bad = [f for f in findings if f["code"] == "invalid_note_characters"]
        self.assertTrue(bad, [f["code"] for f in findings])
        for finding in findings:
            self.assertEqual(set(finding), FINDING_KEYS, finding)
        self.assertEqual(bad[0]["severity"], "error")
        live_report, _, _ = preview.run_live_validator(lib["source"], Path(VALIDATOR_SRC))
        self.assertIsNotNone(live_report)
        self.assertEqual(findings, live_report["findings"])

        # A hand-forged READY plan is refused by the fresh live comparison.
        forged = json.loads(json.dumps(plan))
        forged["status"] = "READY"
        forged["blockers"] = []
        forged_path = write_json(Path(lib["root"]) / "forged-plan.json", forged)
        with self.assertRaises(RuntimeError):
            tx.apply(apply_ns(lib, forged_path, "stepmania-flatpak", VALIDATOR_SRC))

        # The BLOCKED plan itself is refused because apply requires READY.
        blocked_path = write_json(Path(lib["root"]) / "blocked-plan.json", plan)
        with self.assertRaises(RuntimeError):
            tx.apply(apply_ns(lib, blocked_path, "stepmania-flatpak", VALIDATOR_SRC))

        target = lib["target"]
        self.assertFalse((target / "Group").exists())
        self.assert_no_active_receipt(target)


# ---------------------------------------------------------------- scenario 4

class InterruptedActivationTests(RealValidatorCase):
    """Crash at before-activation leaves a staging receipt and an owned stage directory."""

    def test_unchanged_source_completes_recovery(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs")
        txid = self.interrupted_apply(lib, "stepmania-flatpak")
        target, source = lib["target"], lib["source"]
        stage = stage_dir(target, txid)

        # Without validator inputs the stage only advances to staging-ready.
        staged = tx.recover(recover_ns(lib, txid))
        self.assertEqual(staged["status"], "staging-ready")
        self.assertTrue(stage.is_dir())
        self.assertFalse((target / "Group").exists())

        # Same source plus the real validator completes activation.
        recovered = tx.recover(recover_ns(lib, txid, source, VALIDATOR_SRC))
        self.assertEqual(recovered["status"], "active")
        self.assertEqual(read_receipt(target, txid)["status"], "active")
        self.assertFalse(stage.exists())
        self.assertEqual(pack_files(target), tree_files(source / "Group"))

    def test_mutated_source_refuses_recovery_and_preserves_stage(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs")
        txid = self.interrupted_apply(lib, "stepmania-flatpak")
        target, source = lib["target"], lib["source"]
        stage = stage_dir(target, txid)
        self.assertEqual(tx.recover(recover_ns(lib, txid))["status"], "staging-ready")

        # Change the source tree after the interruption; the snapshot no longer matches.
        chart = source / "Group" / "Song" / "chart.sm"
        chart.write_text(VALID_CHART + "// mutated after interruption\n", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            tx.recover(recover_ns(lib, txid, source, VALIDATOR_SRC))

        self.assertTrue(stage.is_dir())
        self.assertFalse((target / "Group").exists())
        self.assertEqual(read_receipt(target, txid)["status"], "staging-ready")

    def test_unusable_validator_source_refuses_recovery_and_preserves_stage(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs")
        txid = self.interrupted_apply(lib, "stepmania-flatpak")
        target, source = lib["target"], lib["source"]
        stage = stage_dir(target, txid)
        self.assertEqual(tx.recover(recover_ns(lib, txid))["status"], "staging-ready")

        empty_validator = root / "empty-validator-src"
        empty_validator.mkdir()
        with self.assertRaises(RuntimeError):
            tx.recover(recover_ns(lib, txid, source, str(empty_validator)))

        self.assertTrue(stage.is_dir())
        self.assertFalse((target / "Group").exists())
        self.assertEqual(read_receipt(target, txid)["status"], "staging-ready")


# ---------------------------------------------------------------- scenario 5

class AbsentProviderTests(RealValidatorCase):
    """Without a validator package, preview is not READY and apply/recover refuse."""

    def test_preview_without_provider_is_not_ready(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs")
        empty_validator = root / "no-provider"
        empty_validator.mkdir()
        plan = build_plan(lib, "stepmania-flatpak", str(empty_validator))
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["provenance"]["validator"]["status"], "UNAVAILABLE")
        self.assertIn("validator-unavailable", plan["blockers"])

    def test_apply_refuses_without_provider(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs")
        _, plan_path = self.ready_plan(lib, "stepmania-flatpak")
        empty_validator = root / "no-provider"
        empty_validator.mkdir()
        with self.assertRaises(RuntimeError):
            tx.apply(apply_ns(lib, plan_path, "stepmania-flatpak", str(empty_validator)))
        self.assertFalse((lib["target"] / "Group").exists())
        self.assert_no_active_receipt(lib["target"])

    def test_staged_recovery_requires_validator_source(self) -> None:
        root = self.new_root()
        lib = make_library(root, target_name="Songs")
        txid = self.interrupted_apply(lib, "stepmania-flatpak")
        target, source = lib["target"], lib["source"]
        stage = stage_dir(target, txid)
        self.assertEqual(tx.recover(recover_ns(lib, txid))["status"], "staging-ready")

        with self.assertRaisesRegex(RuntimeError, r"--validator-source"):
            tx.recover(recover_ns(lib, txid, source, None))
        self.assertTrue(stage.is_dir())
        self.assertFalse((target / "Group").exists())


if __name__ == "__main__":
    unittest.main()
