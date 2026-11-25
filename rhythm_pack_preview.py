#!/usr/bin/env python3
"""Read-only deterministic preview for an inventory-backed rhythm pack."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import stat

SCHEMA = "batocera.rhythm-pack-preview.v1"
INVENTORY_VERSION = 1
VALIDATOR_VERSION = "0.1.0"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_snapshot(root: Path) -> str:
    """Hash the complete regular-file tree; reject links and unreadable entries."""
    root = root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise OSError("source root is not a regular directory")
    tree = hashlib.sha256()
    for parent, dirs, files in os.walk(root, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        dirs.sort()
        files.sort()
        for name in dirs + files:
            path = Path(parent) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise OSError("unsupported source tree entry")
            if stat.S_ISREG(info.st_mode):
                relative = path.relative_to(root).as_posix().encode("utf-8")
                content_hash = digest(path)
                tree.update(len(relative).to_bytes(8, "big"))
                tree.update(relative)
                tree.update(info.st_size.to_bytes(8, "big"))
                tree.update(bytes.fromhex(content_hash))
    return tree.hexdigest()


def validate_report(report: object, source: Path) -> bool:
    return (isinstance(report, dict)
            and set(report) == {"library_path", "songs_scanned", "charts_scanned", "error_count", "warning_count", "ok", "findings"}
            and report.get("library_path") == str(source)
            and type(report.get("ok")) is bool and isinstance(report.get("findings"), list)
            and all(isinstance(f, dict) and set(f) == {"category", "severity", "code", "message", "path"}
                    and f.get("severity") in ("error", "warning") for f in report["findings"])
            and all(type(report.get(k)) is int and report[k] >= 0 for k in
                    ("songs_scanned", "charts_scanned", "error_count", "warning_count"))
            and report["error_count"] == sum(f["severity"] == "error" for f in report["findings"])
            and report["warning_count"] == sum(f["severity"] == "warning" for f in report["findings"])
            and report["ok"] == (report["error_count"] == 0))


def run_live_validator(source: Path, package_source: Path) -> tuple[dict | None, str | None, str | None]:
    """Import the explicitly supplied trusted source in a clean isolated interpreter."""
    try:
        if not (package_source / "stepmania_song_validator" / "__init__.py").is_file():
            return None, None, None
        before = source_snapshot(source)
        code = ("import json, sys; "
                "sys.path.insert(0, sys.argv[1]); "
                "import stepmania_song_validator; "
                "from stepmania_song_validator.cli import main; "
                "print(json.dumps({'version': stepmania_song_validator.__version__})); "
                "raise SystemExit(main([sys.argv[2], '--json']))")
        result = subprocess.run([sys.executable, "-I", "-c", code, str(package_source), str(source)],
                                capture_output=True, text=True, check=False)
        lines = result.stdout.splitlines()
        if not lines:
            return None, None, before
        version_info = json.loads(lines[0])
        version = version_info.get("version") if isinstance(version_info, dict) else None
        if version != VALIDATOR_VERSION:
            return None, version, before
        report = json.loads("\n".join(lines[1:]))
        after = source_snapshot(source)
        if before != after:
            return None, version, None
        if not validate_report(report, source) or result.returncode not in (0, 1) or result.returncode != (0 if report["ok"] else 1):
            return None, version, before
        return report, version, before
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        return None, None, None


def within(base: Path, path: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def has_symlink_component(path: Path, *, include_leaf: bool = True) -> bool:
    """Check every existing component without resolving away symlinks."""
    parts = path.parts if include_leaf else path.parts[:-1]
    current = Path(path.anchor) if path.is_absolute() else Path()
    for part in parts[1:] if path.is_absolute() else parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def valid_inventory_shape(inventory: object) -> bool:
    if not isinstance(inventory, dict):
        return False
    if any(key in inventory and type(inventory[key]) is not int for key in ("schemaVersion", "identityVersion")):
        return False
    if "installationRoot" in inventory and not isinstance(inventory["installationRoot"], str):
        return False
    if not isinstance(inventory.get("diagnostics", []), list) or not isinstance(inventory.get("packs", []), list):
        return False
    for pack in inventory.get("packs", []):
        if not isinstance(pack, dict) or not isinstance(pack.get("packId"), str):
            return False
        if not isinstance(pack.get("relativeLocation"), str):
            return False
        if not isinstance(pack.get("diagnostics", []), list):
            return False
        if not isinstance(pack.get("assets", []), list) or not isinstance(pack.get("songs", []), list):
            return False
        for asset in pack.get("assets", []):
            if not valid_asset_shape(asset):
                return False
        for song in pack.get("songs", []):
            if not isinstance(song, dict) or not isinstance(song.get("relativeLocation"), str):
                return False
            if not isinstance(song.get("diagnostics", []), list) or not isinstance(song.get("assets", []), list):
                return False
            if not isinstance(song.get("charts", []), list):
                return False
            if any(not valid_asset_shape(asset) for asset in song.get("assets", [])):
                return False
            for chart in song.get("charts", []):
                if not isinstance(chart, dict):
                    return False
                if "sourceRelativeLocation" in chart and not isinstance(chart["sourceRelativeLocation"], str):
                    return False
                if "sourceRevision" in chart and not isinstance(chart["sourceRevision"], str):
                    return False
    return True


def valid_asset_shape(asset: object) -> bool:
    return (isinstance(asset, dict) and isinstance(asset.get("relativeLocation"), str)
            and isinstance(asset.get("status"), str)
            and isinstance(asset.get("sha256"), str))


def inspect_target(target: Path, destination: PurePosixPath, actual: str, blockers: list[str]) -> tuple[str, str | None]:
    dest = target.joinpath(*destination.parts)
    if has_symlink_component(dest):
        blockers.append("target-symlink-unsupported")
        return "conflict", None
    try:
        if not dest.exists():
            return "absent", None
        if not dest.is_file():
            blockers.append("target-conflict-unsupported-entry")
            return "conflict", None
        existing_hash = digest(dest)
    except OSError:
        blockers.append("target-conflict-unreadable")
        return "conflict", None
    if existing_hash != actual:
        blockers.append("target-file-conflict")
        return "conflict", existing_hash
    return "identical", existing_hash


def preview(args: argparse.Namespace) -> dict:
    source = Path(args.source).absolute()
    target = Path(args.target).absolute()
    inventory_path = Path(args.inventory).absolute()
    report_path = Path(args.validator_report).absolute() if args.validator_report else None
    validator_source = Path(args.validator_source).absolute() if args.validator_source else None
    blockers: list[str] = []
    entries: list[dict] = []
    inventory_shape_ok = False
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory_shape_ok = valid_inventory_shape(inventory)
        if not inventory_shape_ok:
            blockers.append("inventory-unavailable-or-invalid")
            inventory = {}
        if inventory.get("schemaVersion") != INVENTORY_VERSION:
            blockers.append("unsupported-inventory-schema")
        if inventory.get("identityVersion") != 1:
            blockers.append("unsupported-inventory-identity-version")
        if inventory.get("installationRoot") != str(source):
            blockers.append("inventory-source-root-mismatch")
    except (OSError, ValueError, AttributeError):
        inventory = {}
        blockers.append("inventory-unavailable-or-invalid")

    pack = next((p for p in inventory.get("packs", []) if p.get("packId") == args.pack), None) if inventory_shape_ok else None
    destinations: dict[str, str] = {}
    if pack is None:
        blockers.append("pack-not-found-in-inventory")
    else:
        if inventory.get("diagnostics") or pack.get("diagnostics"):
            blockers.append("inventory-has-diagnostics")
        loc = pack.get("relativeLocation", "")
        if not safe_relative(loc):
            blockers.append("unsupported-pack-layout")
        else:
            pack_source = source / loc
            if has_symlink_component(pack_source):
                blockers.append("source-symlink-unsupported")
            for asset in pack.get("assets", []):
                rel = asset.get("relativeLocation", "")
                if not safe_relative(rel) or not rel.startswith(loc.rstrip("/") + "/"):
                    blockers.append("unsupported-pack-asset-layout")
                    continue
                path = source / rel
                if has_symlink_component(path):
                    blockers.append("source-symlink-unsupported")
                    continue
                try:
                    if not within(source.resolve(), path.resolve(strict=False)):
                        blockers.append("source-symlink-unsupported")
                        continue
                except OSError:
                    blockers.append("missing-or-unreadable-asset")
                    continue
                if asset.get("status") != "present" or not path.is_file():
                    blockers.append("missing-or-unreadable-asset")
                    continue
                try:
                    actual = digest(path)
                    size = path.stat().st_size
                except OSError:
                    blockers.append("missing-or-unreadable-asset")
                    continue
                if not asset.get("sha256") or actual != asset["sha256"]:
                    blockers.append("source-hash-mismatch")
                    continue
                destination = PurePosixPath(rel)
                dest_rel = str(destination)
                previous = destinations.get(dest_rel)
                if previous is not None and previous != actual:
                    blockers.append("destination-hash-collision")
                destinations[dest_rel] = actual
                state, existing_hash = inspect_target(target, destination, actual, blockers)
                entries.append({"source": rel, "destination": dest_rel,
                                "sha256": actual, "bytes": size,
                                "targetState": state, "targetSha256": existing_hash})
            for song in pack.get("songs", []):
                songloc = song.get("relativeLocation", "")
                if not safe_relative(songloc) or not songloc.startswith(loc.rstrip("/") + "/"):
                    blockers.append("unsupported-song-layout")
                    continue
                files = list(song.get("assets", []))
                # Simfiles are represented by chart source locators; inventory asset lists omit them.
                seen_simfiles: set[str] = set()
                for chart in song.get("charts", []):
                    simfile = chart.get("sourceRelativeLocation", "")
                    if simfile and simfile not in seen_simfiles:
                        seen_simfiles.add(simfile)
                        files.append({"relativeLocation": simfile, "sha256": chart.get("sourceRevision"), "status": "present"})
                if not song.get("charts"):
                    blockers.append("song-has-no-supported-charts")
                if song.get("diagnostics"):
                    blockers.append("inventory-song-has-diagnostics")
                for asset in files:
                    rel = asset.get("relativeLocation", "")
                    if not safe_relative(rel) or not rel.startswith(songloc.rstrip("/") + "/"):
                        blockers.append("source-path-escape-or-unsupported-path")
                        continue
                    path = source / rel
                    if has_symlink_component(path):
                        blockers.append("source-path-escape-or-symlink")
                        continue
                    try:
                        if not within(source.resolve(), path.resolve(strict=False)):
                            blockers.append("source-path-escape-or-symlink")
                            continue
                    except OSError:
                        blockers.append("missing-or-unreadable-asset")
                        continue
                    if asset.get("status") != "present" or not path.is_file():
                        blockers.append("missing-or-unreadable-asset")
                        continue
                    try:
                        actual = digest(path)
                        size = path.stat().st_size
                    except OSError:
                        blockers.append("missing-or-unreadable-asset")
                        continue
                    if not asset.get("sha256") or actual != asset["sha256"]:
                        blockers.append("source-hash-mismatch")
                        continue
                    destination = PurePosixPath(rel)
                    dest_rel = str(destination)
                    collision_key = dest_rel
                    previous = destinations.get(collision_key)
                    if previous is not None and previous != actual:
                        blockers.append("destination-hash-collision")
                    destinations[collision_key] = actual
                    state, existing_hash = inspect_target(target, destination, actual, blockers)
                    entries.append({"source": rel, "destination": str(destination), "sha256": actual,
                                    "bytes": size, "targetState": state,
                                    "targetSha256": existing_hash})

    validator = {"status": "UNAVAILABLE", "version": None, "reportSchema": "stepmania-song-validator-0.1.0-report-v1"}
    source_before = None
    if validator_source:
        try:
            live_report, live_version, source_before = run_live_validator(source, validator_source)
            validator["version"] = live_version
            if live_version != VALIDATOR_VERSION:
                validator["status"] = "UNKNOWN"
                blockers.append("unsupported-validator-version")
            elif live_report is None or source_before is None:
                validator["status"] = "UNKNOWN"
                blockers.append("live-validator-invalid-or-source-changed")
            else:
                validator.update(status="PASS" if live_report["ok"] else "FAIL", ok=live_report["ok"],
                                 errorCount=live_report["error_count"], warningCount=live_report["warning_count"],
                                 reportSha256=hashlib.sha256(json.dumps(live_report, sort_keys=True).encode()).hexdigest(),
                                 verifiedModuleVersion=live_version, liveSourceSnapshotSha256=source_before)
                if not live_report["ok"]:
                    blockers.append("validator-failed")
        except OSError:
            validator["status"] = "UNAVAILABLE"
            blockers.append("validator-unavailable")
    elif report_path and args.validator_version == VALIDATOR_VERSION:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not validate_report(report, source):
                validator["status"] = "UNKNOWN"
                blockers.append("invalid-validator-report")
            else:
                validator.update(status="UNVERIFIED", version=VALIDATOR_VERSION,
                                 ok=report["ok"], errorCount=report["error_count"],
                                 warningCount=report["warning_count"], reportSha256=digest(report_path))
                blockers.append("validator-report-unverified")
        except (OSError, ValueError):
            validator["status"] = "UNKNOWN"
            blockers.append("validator-report-unavailable-or-invalid")
    elif args.validator_version and args.validator_version != VALIDATOR_VERSION:
        validator["status"] = "UNKNOWN"
        blockers.append("unsupported-validator-version")
    else:
        blockers.append("validator-unavailable")

    # Reject source symlinks anywhere in the selected pack, including unlisted files.
    if pack is not None and safe_relative(pack.get("relativeLocation", "")):
        root = source / pack["relativeLocation"]
        if root.exists():
            for parent, dirs, files in os.walk(root, followlinks=False):
                for name in dirs + files:
                    if (Path(parent) / name).is_symlink():
                        blockers.append("source-symlink-unsupported")
                        dirs[:] = []
                        break
    if validator.get("status") == "PASS":
        try:
            if any(digest(source / item["source"]) != item["sha256"] for item in entries):
                raise OSError("selected inventory files changed before validation")
            if source_snapshot(source) != source_before:
                raise OSError("source changed after validation")
        except OSError:
            validator["status"] = "UNKNOWN"
            validator.pop("ok", None)
            validator.pop("errorCount", None)
            validator.pop("warningCount", None)
            validator.pop("reportSha256", None)
            validator.pop("verifiedModuleVersion", None)
            validator.pop("liveSourceSnapshotSha256", None)
            blockers.append("live-validator-invalid-or-source-changed")
    total = sum(x["bytes"] for x in entries if x["targetState"] == "absent")
    try:
        free = shutil.disk_usage(target if target.exists() else target.parent).free
        if total > free:
            blockers.append("insufficient-target-space")
    except OSError:
        free = None
        blockers.append("target-space-unknown")
    return {
        "schema": SCHEMA,
        "status": "BLOCKED" if blockers else "READY",
        "runtime": args.runtime,
        "profile": args.profile,
        "sourceRoot": str(source),
        "targetSongsRoot": str(target),
        "packId": args.pack,
        "provenance": {"inventory": {"schemaVersion": INVENTORY_VERSION,
                         "provider": "StepmaniaSongManager Stepmania.Inventory.Cli",
                         "adapterSourceCommit": "072dcfb83e28fa3cd5b6754db668c006b01eeec7",
                         "sha256": digest(inventory_path) if inventory_path.is_file() else None},
                       "validator": validator},
        "files": sorted(entries, key=lambda item: item["destination"]),
        "estimatedBytes": total,
        "availableBytes": free,
        "blockers": sorted(set(blockers)),
        "canonicalIdentity": "unresolved; source hash and locator are local provenance only",
        "targetMutation": "none; preview only",
    }


def safe_relative(value: str) -> bool:
    p = PurePosixPath(value)
    return bool(value) and not p.is_absolute() and ".." not in p.parts and "\\" not in value and "\x00" not in value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="root used by Inventory.Cli and validator")
    parser.add_argument("--inventory", required=True, help="Inventory.Cli JSON schema v1")
    parser.add_argument("--pack", required=True, help="exact inventory packId")
    parser.add_argument("--runtime", choices=("stepmania-flatpak", "itgmania-portable"), required=True)
    parser.add_argument("--target", required=True, help="explicit runtime Songs root")
    parser.add_argument("--profile", required=True, help="configured runtime profile identifier")
    parser.add_argument("--validator-report", help="validator 0.1.0 JSON report; absent means unavailable")
    parser.add_argument("--validator-version", help="must be exactly 0.1.0")
    parser.add_argument("--validator-source", help="trusted Python package src root for isolated live validation")
    parser.add_argument("--output", help="write plan JSON metadata here; otherwise stdout")
    args = parser.parse_args()
    plan = preview(args)
    rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output).absolute()
        resolved = output.resolve(strict=False)
        protected = [Path(args.source).resolve(), Path(args.target).resolve()]
        if any(within(root, resolved) for root in protected):
            parser.error("--output must be outside source and target trees")
        if has_symlink_component(output) or output.exists():
            parser.error("--output must be a new non-symlink metadata file")
        if not output.parent.is_dir():
            parser.error("--output parent must already exist")
        try:
            with output.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        except OSError:
            parser.error("--output could not be created exclusively")
        print(render_human(plan))
    else:
        print(render_human(plan), file=sys.stderr)
        sys.stdout.write(rendered)
    return 0 if plan["status"] == "READY" else 2


def render_human(plan: dict) -> str:
    lines = [f"Rhythm pack preview: {plan['status']}", f"Runtime: {plan['runtime']} ({plan['profile']})",
             f"Source pack: {plan['packId']}", f"Target Songs root: {plan['targetSongsRoot']}",
             f"Files: {len(plan['files'])}; bytes to add: {plan['estimatedBytes']}",
             f"Validator: {plan['provenance']['validator']['status']}"]
    for item in plan["files"]:
        lines.append(f"  {item['targetState']:9} {item['source']} -> {item['destination']} sha256:{item['sha256']}")
    for blocker in plan["blockers"]:
        lines.append(f"BLOCKER: {blocker}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
