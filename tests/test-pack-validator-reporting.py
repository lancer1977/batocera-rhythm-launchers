#!/usr/bin/env python3
"""Stdlib unittest coverage for validator reporting in rhythm_pack_preview.

Run from the repository root:  python3 tests/test-pack-validator-reporting.py

Every fixture is built inside a tempfile.TemporaryDirectory tree. The validator
under test is a two-file synthetic package (stepmania_song_validator/__init__.py
and cli.py) whose cli echoes a canned report, so the real validator library,
the network and the real home directory are never touched.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.dont_write_bytecode = True

import rhythm_pack_preview as preview_mod  # noqa: E402  (repo root inserted above)

PREVIEW_SCRIPT = REPO_ROOT / "rhythm_pack_preview.py"
SUBPROCESS_TIMEOUT_SECONDS = 120
PACK_ID = "pack:Group"
SIMFILE_REL = "Group/Song/chart.sm"
CHART_BYTES = (b"#TITLE:Fixture;\n#ARTIST:Fixture;\n#BPMS:0=120;\n"
               b"#NOTES:dance-single:Fixture:Beginner:1:\n0000\n,\n0000\n;\n")

# Two warnings on one chart; warning-only reports are policy PASS, not blockers.
WARNING_FINDINGS = [
    {"category": "timing", "severity": "warning", "code": "unsupported_timing_feature",
     "message": "WARPS is not supported by the validator policy", "path": SIMFILE_REL},
    {"category": "metadata", "severity": "warning", "code": "missing_music_tag",
     "message": 'Chart has no "#MUSIC" tag', "path": SIMFILE_REL},
]
ERROR_FINDINGS = [
    {"category": "notes", "severity": "error", "code": "invalid_note_characters",
     "message": "Invalid note token in chart data", "path": SIMFILE_REL},
]

# Template for the synthetic cli.py. The payload is embedded as a JSON string literal.
CLI_TEMPLATE = '''"""Synthetic stepmania_song_validator cli used only by launcher tests."""
import json

_PAYLOAD = json.loads(__PAYLOAD__)


def main(argv):
    if _PAYLOAD["raw"] is not None:
        print(_PAYLOAD["raw"])
    else:
        report = dict(_PAYLOAD["report"])
        report["library_path"] = argv[0]
        print(json.dumps(report))
    return _PAYLOAD["exit_code"]
'''


def sha256_hex(data: bytes) -> str:
    """Return the hex sha256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def make_report(library_path: str, findings: list) -> dict:
    """Build a schema-valid validator 0.1.0 report whose counters match its findings."""
    errors = sum(1 for item in findings if item["severity"] == "error")
    warnings = sum(1 for item in findings if item["severity"] == "warning")
    return {"library_path": library_path, "songs_scanned": 1, "charts_scanned": 1,
            "error_count": errors, "warning_count": warnings, "ok": errors == 0,
            "findings": copy.deepcopy(findings)}


def finding_line(finding: dict) -> str:
    """Return the exact human-output line expected for one finding."""
    return ("  FINDING {severity} {code} path={path} message={message}".format(
        severity=finding["severity"], code=finding["code"],
        path=json.dumps(finding["path"]), message=json.dumps(finding["message"])))


def snapshot_tree(root: Path) -> list:
    """Return sorted (relative posix path, kind, bytes-or-None) for every entry under root."""
    entries = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        for name in dirnames:
            entries.append(((base / name).relative_to(root).as_posix(), "dir", None))
        for name in filenames:
            full = base / name
            entries.append((full.relative_to(root).as_posix(), "file", full.read_bytes()))
    return sorted(entries)


def write_validator_package(src_root: Path, *, version: str = "0.1.0", report=None,
                            raw=None, exit_code=None) -> Path:
    """Write <src_root>/stepmania_song_validator with __init__.py and cli.py.

    The cli prints `raw` verbatim when given, otherwise the report with
    library_path set from argv[0], and returns exit_code.
    """
    package = src_root / "stepmania_song_validator"
    package.mkdir(parents=True, exist_ok=True)
    if exit_code is None:
        exit_code = 0 if isinstance(report, dict) and report.get("ok") is True else 1
    payload = {"report": report, "raw": raw, "exit_code": exit_code}
    (package / "__init__.py").write_text('__version__ = "%s"\n' % version, encoding="utf-8")
    (package / "cli.py").write_text(
        CLI_TEMPLATE.replace("__PAYLOAD__", repr(json.dumps(payload))), encoding="utf-8")
    return src_root


class PreviewCase(unittest.TestCase):
    """Shared synthetic source, empty target, real-hash inventory and read-only checks."""

    def setUp(self):
        """Create a temp root with source/Group/Song/chart.sm, an empty target and an inventory."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).absolute()
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.inventory = self.root / "inventory.json"
        (self.source / "Group" / "Song").mkdir(parents=True)
        self.target.mkdir()
        (self.source / SIMFILE_REL).write_bytes(CHART_BYTES)
        self.write_inventory()

    def write_inventory(self):
        """Write a schemaVersion 1 inventory whose chart sourceRevision is the true sha256."""
        chart_hash = sha256_hex((self.source / SIMFILE_REL).read_bytes())
        inventory = {
            "schemaVersion": 1, "identityVersion": 1, "installationId": "fixture",
            "installationRoot": str(self.source), "diagnostics": [],
            "packs": [{"packId": PACK_ID, "relativeLocation": "Group", "diagnostics": [],
                       "assets": [],
                       "songs": [{"relativeLocation": "Group/Song", "diagnostics": [],
                                  "assets": [],
                                  "charts": [{"sourceRelativeLocation": SIMFILE_REL,
                                              "sourceRevision": chart_hash}]}]}],
        }
        self.inventory.write_text(json.dumps(inventory), encoding="utf-8")

    def validator_src(self) -> Path:
        """Return the synthetic validator src root used by live-validation tests."""
        return self.root / "validator" / "src"

    def write_report(self, content, name: str = "report.json") -> Path:
        """Write a supplied validator report; str content is written verbatim, others as JSON."""
        path = self.root / name
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(json.dumps(content), encoding="utf-8")
        return path

    def make_args(self, **overrides) -> argparse.Namespace:
        """Build the Namespace that preview(args) expects, with optional overrides."""
        values = dict(source=str(self.source), target=str(self.target),
                      inventory=str(self.inventory), validator_report=None,
                      validator_source=None, validator_version=None, pack=PACK_ID,
                      runtime="stepmania-flatpak", profile="stock-stepmania-flatpak")
        values.update(overrides)
        return argparse.Namespace(**values)

    def assert_read_only(self, action):
        """Run action and assert source and target trees are unchanged and target has no files."""
        source_before = snapshot_tree(self.source)
        target_before = snapshot_tree(self.target)
        result = action()
        self.assertEqual(snapshot_tree(self.source), source_before, "source tree changed")
        target_after = snapshot_tree(self.target)
        self.assertEqual(target_after, target_before, "target tree changed")
        self.assertEqual([entry for entry in target_after if entry[1] == "file"], [],
                         "preview wrote files into target")
        return result

    def checked_preview(self, args: argparse.Namespace) -> dict:
        """Call preview(args) under the read-only snapshot assertions."""
        return self.assert_read_only(lambda: preview_mod.preview(args))

    def assert_fail_closed(self, plan: dict, blocker_options: set):
        """Assert BLOCKED, UNKNOWN validator, one expected blocker and no findings key."""
        validator = plan["provenance"]["validator"]
        self.assertEqual(plan["status"], "BLOCKED", plan["blockers"])
        self.assertEqual(validator["status"], "UNKNOWN")
        self.assertTrue(set(plan["blockers"]) & blocker_options, plan["blockers"])
        self.assertNotIn("findings", validator)


class WarningOnlyLiveTests(PreviewCase):
    """Warning-only live validation: READY, PASS, findings retained and shown."""

    def setUp(self):
        """Install a synthetic validator 0.1.0 that reports two warnings and no errors."""
        super().setUp()
        write_validator_package(self.validator_src(),
                                report=make_report(str(self.source), WARNING_FINDINGS))

    def test_warning_only_live_report_is_ready_with_findings_retained(self):
        """Warnings do not block: plan READY, PASS, counts and findings kept in order."""
        plan = self.checked_preview(self.make_args(validator_source=str(self.validator_src())))
        validator = plan["provenance"]["validator"]
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["blockers"], [])
        self.assertEqual(validator["status"], "PASS")
        self.assertEqual(validator["errorCount"], 0)
        self.assertEqual(validator["warningCount"], 2)
        self.assertEqual(validator["findings"], WARNING_FINDINGS)
        self.assertEqual(validator["verifiedModuleVersion"], "0.1.0")
        self.assertEqual([item["destination"] for item in plan["files"]], [SIMFILE_REL])

    def test_warning_only_human_output_shows_counts_and_every_finding(self):
        """render_human shows the validator counts line and one exact FINDING line per finding."""
        plan = self.checked_preview(self.make_args(validator_source=str(self.validator_src())))
        text = preview_mod.render_human(plan)
        lines = text.splitlines()
        self.assertIn("Rhythm pack preview: READY", lines)
        self.assertIn("Validator: PASS", lines)
        self.assertIn("Validator counts: errors=0 warnings=2", text)
        for finding in WARNING_FINDINGS:
            self.assertIn(finding_line(finding), lines)
        self.assertFalse(any(line.startswith("BLOCKER:") for line in lines))

    def test_warning_only_command_line_stdout_json_and_stderr_human(self):
        """The script exits 0, writes the plan JSON to stdout and human output to stderr."""
        args = ["--validator-source", str(self.validator_src())]
        result = self.assert_read_only(lambda: self.run_cli(*args))
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["provenance"]["validator"]["findings"], WARNING_FINDINGS)
        self.assertIn("Validator counts: errors=0 warnings=2", result.stderr)
        stderr_lines = result.stderr.splitlines()
        for finding in WARNING_FINDINGS:
            self.assertIn(finding_line(finding), stderr_lines)

    def test_warning_only_preview_is_deterministic(self):
        """Two previews on unchanged inputs are equal once availableBytes is removed."""
        args = self.make_args(validator_source=str(self.validator_src()))
        first = self.checked_preview(args)
        second = self.checked_preview(args)
        first.pop("availableBytes")
        second.pop("availableBytes")
        self.assertEqual(first, second)

    def test_plan_without_findings_differs_from_fresh_preview(self):
        """A pre-findings plan (findings deleted) no longer equals a fresh preview of the same inputs."""
        args = self.make_args(validator_source=str(self.validator_src()))
        stale = copy.deepcopy(self.checked_preview(args))
        del stale["provenance"]["validator"]["findings"]
        fresh = self.checked_preview(args)
        self.assertIn("findings", fresh["provenance"]["validator"])
        stale.pop("availableBytes")
        fresh.pop("availableBytes")
        self.assertNotEqual(stale, fresh)

    def run_cli(self, *extra: str) -> subprocess.CompletedProcess:
        """Run rhythm_pack_preview.py as a subprocess with a bounded timeout."""
        command = [sys.executable, str(PREVIEW_SCRIPT),
                   "--source", str(self.source), "--inventory", str(self.inventory),
                   "--pack", PACK_ID, "--runtime", "stepmania-flatpak",
                   "--target", str(self.target), "--profile", "stock-stepmania-flatpak",
                   *extra]
        return subprocess.run(command, capture_output=True, text=True, check=False,
                              timeout=SUBPROCESS_TIMEOUT_SECONDS, cwd=str(self.root))


class RealErrorLiveTests(PreviewCase):
    """Live validator error report: BLOCKED with validator-failed and the error code kept."""

    def setUp(self):
        """Install a synthetic validator 0.1.0 that reports one invalid_note_characters error."""
        super().setUp()
        write_validator_package(self.validator_src(),
                                report=make_report(str(self.source), ERROR_FINDINGS))

    def test_error_report_blocks_with_validator_failed_and_keeps_error_code(self):
        """An error finding blocks the plan; the error code survives in the plan findings."""
        plan = self.checked_preview(self.make_args(validator_source=str(self.validator_src())))
        validator = plan["provenance"]["validator"]
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["blockers"], ["validator-failed"])
        self.assertEqual(validator["status"], "FAIL")
        self.assertEqual(validator["errorCount"], 1)
        self.assertEqual(validator["findings"], ERROR_FINDINGS)
        self.assertIn("invalid_note_characters", [f["code"] for f in validator["findings"]])

    def test_error_report_human_output_shows_error_code(self):
        """render_human names the error finding and the blocker."""
        plan = self.checked_preview(self.make_args(validator_source=str(self.validator_src())))
        text = preview_mod.render_human(plan)
        self.assertIn("Validator: FAIL", text)
        self.assertIn("Validator counts: errors=1 warnings=0", text)
        self.assertIn(finding_line(ERROR_FINDINGS[0]), text.splitlines())
        self.assertIn("BLOCKER: validator-failed", text.splitlines())

    def test_error_report_command_line_exits_2_with_error_on_stderr(self):
        """The script exits 2 for a BLOCKED plan and prints the error finding on stderr."""
        result = self.assert_read_only(
            lambda: self.run_cli("--validator-source", str(self.validator_src())))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")
        self.assertIn(finding_line(ERROR_FINDINGS[0]), result.stderr.splitlines())

    def run_cli(self, *extra: str) -> subprocess.CompletedProcess:
        """Run rhythm_pack_preview.py as a subprocess with a bounded timeout."""
        command = [sys.executable, str(PREVIEW_SCRIPT),
                   "--source", str(self.source), "--inventory", str(self.inventory),
                   "--pack", PACK_ID, "--runtime", "stepmania-flatpak",
                   "--target", str(self.target), "--profile", "stock-stepmania-flatpak",
                   *extra]
        return subprocess.run(command, capture_output=True, text=True, check=False,
                              timeout=SUBPROCESS_TIMEOUT_SECONDS, cwd=str(self.root))


class UnavailableValidatorTests(PreviewCase):
    """Missing provider: UNAVAILABLE with validator-unavailable, not an unsupported version."""

    def assert_unavailable(self, plan: dict):
        """Assert the shared unavailable-provider shape."""
        validator = plan["provenance"]["validator"]
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(validator["status"], "UNAVAILABLE")
        self.assertIsNone(validator["version"])
        self.assertIn("validator-unavailable", plan["blockers"])
        self.assertNotIn("unsupported-validator-version", plan["blockers"])
        self.assertNotIn("findings", validator)

    def test_nonexistent_validator_source_is_unavailable_not_bad_version(self):
        """A nonexistent --validator-source is reported as unavailable and stays fail-closed."""
        plan = self.checked_preview(
            self.make_args(validator_source=str(self.root / "no-such-validator")))
        self.assert_unavailable(plan)

    def test_existing_dir_without_package_is_unavailable_not_bad_version(self):
        """An existing validator source directory lacking the package is also unavailable."""
        empty = self.root / "empty-validator"
        empty.mkdir()
        plan = self.checked_preview(self.make_args(validator_source=str(empty)))
        self.assert_unavailable(plan)


class IncompatibleValidatorVersionTests(PreviewCase):
    """Real incompatible package version: UNKNOWN with unsupported-validator-version."""

    def test_live_package_version_9_9_9_fails_closed_as_unsupported_version(self):
        """A package whose __version__ is 9.9.9 is UNKNOWN, blocked, with no findings."""
        write_validator_package(self.validator_src(), version="9.9.9",
                                report=make_report(str(self.source), WARNING_FINDINGS))
        plan = self.checked_preview(self.make_args(validator_source=str(self.validator_src())))
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["provenance"]["validator"]["status"], "UNKNOWN")
        self.assertIn("unsupported-validator-version", plan["blockers"])
        self.assertNotIn("findings", plan["provenance"]["validator"])


class SuppliedReportTests(PreviewCase):
    """Supplied --validator-report without a live source: UNVERIFIED, findings retained."""

    def test_supplied_report_with_findings_is_unverified_and_retains_findings(self):
        """A supplied report is UNVERIFIED, the plan is BLOCKED and findings are kept in order."""
        report = self.write_report(make_report(str(self.source), WARNING_FINDINGS))
        plan = self.checked_preview(self.make_args(validator_report=str(report),
                                                   validator_version="0.1.0"))
        validator = plan["provenance"]["validator"]
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(validator["status"], "UNVERIFIED")
        self.assertIn("validator-report-unverified", plan["blockers"])
        self.assertEqual(validator["findings"], WARNING_FINDINGS)
        self.assertEqual(validator["warningCount"], 2)

    def test_supplied_report_findings_shown_in_human_output(self):
        """render_human shows the UNVERIFIED status, the counts line and each finding."""
        report = self.write_report(make_report(str(self.source), ERROR_FINDINGS))
        plan = self.checked_preview(self.make_args(validator_report=str(report),
                                                   validator_version="0.1.0"))
        text = preview_mod.render_human(plan)
        self.assertIn("Validator: UNVERIFIED", text)
        self.assertIn("Validator counts: errors=1 warnings=0", text)
        self.assertIn(finding_line(ERROR_FINDINGS[0]), text.splitlines())
        self.assertIn("BLOCKER: validator-report-unverified", text.splitlines())

    def test_malformed_supplied_reports_fail_closed(self):
        """Each malformed supplied report is UNKNOWN, BLOCKED, with no findings key."""
        clean = make_report(str(self.source), WARNING_FINDINGS)
        error = make_report(str(self.source), ERROR_FINDINGS)
        cases = {
            "extra-top-level-key": dict(clean, extra=1),
            "missing-findings-key": {k: v for k, v in clean.items() if k != "findings"},
            "warning-count-mismatch": dict(clean, warning_count=5),
            "unknown-severity": dict(clean, findings=[dict(WARNING_FINDINGS[0], severity="fatal")],
                                     warning_count=0),
            "ok-inconsistent-with-errors": dict(error, ok=True),
            "wrong-library-path": dict(clean, library_path=str(self.root / "elsewhere")),
            "finding-extra-key": dict(clean, findings=[dict(WARNING_FINDINGS[0], line=3),
                                                       WARNING_FINDINGS[1]]),
            "non-json": "{not json",
        }
        options = {"invalid-validator-report", "validator-report-unavailable-or-invalid"}
        for name, content in cases.items():
            with self.subTest(case=name):
                report = self.write_report(content)
                plan = self.checked_preview(self.make_args(validator_report=str(report),
                                                           validator_version="0.1.0"))
                self.assert_fail_closed(plan, options)


class LiveProviderMalformedTests(PreviewCase):
    """Live provider emitting a malformed report or a mismatched exit code: fail closed."""

    def test_malformed_live_provider_output_fails_closed(self):
        """Malformed live output or exit/ok mismatch is UNKNOWN, BLOCKED, with no findings key."""
        clean = make_report(str(self.source), WARNING_FINDINGS)
        error = make_report(str(self.source), ERROR_FINDINGS)
        cases = {
            "non-json-stdout": {"raw": "not json {", "exit_code": 0},
            "missing-findings-key": {"report": {k: v for k, v in clean.items() if k != "findings"},
                                     "exit_code": 0},
            "warning-count-mismatch": {"report": dict(clean, warning_count=5), "exit_code": 0},
            "ok-inconsistent-with-errors": {"report": dict(error, ok=True), "exit_code": 0},
            "exit-0-for-error-report": {"report": error, "exit_code": 0},
            "exit-1-for-clean-report": {"report": clean, "exit_code": 1},
        }
        for name, spec in cases.items():
            with self.subTest(case=name):
                write_validator_package(self.validator_src(), **spec)
                plan = self.checked_preview(
                    self.make_args(validator_source=str(self.validator_src())))
                self.assert_fail_closed(plan, {"live-validator-invalid-or-source-changed"})


class ReadOnlyScenarioTests(PreviewCase):
    """Every reporting scenario in sequence leaves source and target trees unchanged."""

    def test_scenarios_in_sequence_leave_trees_unchanged_and_target_empty(self):
        """Warning, error, unavailable and supplied-report runs each keep the trees intact."""
        source_str = str(self.source)
        scenarios = []
        write_validator_package(self.validator_src(), report=make_report(source_str, WARNING_FINDINGS))
        scenarios.append(self.make_args(validator_source=str(self.validator_src())))
        write_validator_package(self.validator_src(), report=make_report(source_str, ERROR_FINDINGS))
        scenarios.append(self.make_args(validator_source=str(self.validator_src())))
        scenarios.append(self.make_args(validator_source=str(self.root / "missing-validator")))
        report = self.write_report(make_report(source_str, WARNING_FINDINGS))
        scenarios.append(self.make_args(validator_report=str(report), validator_version="0.1.0"))
        for args in scenarios:
            with self.subTest(validator=args.validator_source or args.validator_report):
                plan = self.checked_preview(args)
                self.assertIn(plan["status"], ("READY", "BLOCKED"))
        self.assertEqual(snapshot_tree(self.target), [])


if __name__ == "__main__":
    unittest.main()
