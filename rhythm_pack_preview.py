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

SCHEMA = "batocera.rhythm-pack-preview.v1"
INVENTORY_VERSION = 1
VALIDATOR_VERSION = "0.1.0"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


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
                destination = PurePosixPath(rel).relative_to(PurePosixPath(loc))
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
                    destination = PurePosixPath(songloc).relative_to(PurePosixPath(loc)) / PurePosixPath(rel).relative_to(PurePosixPath(songloc))
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
    if report_path and args.validator_version == VALIDATOR_VERSION:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or set(report) != {"library_path", "songs_scanned", "charts_scanned", "error_count", "warning_count", "ok", "findings"}:
                validator["status"] = "UNKNOWN"
                blockers.append("unsupported-validator-report-schema")
            elif report.get("library_path") != str(source):
                validator["status"] = "UNKNOWN"
                blockers.append("validator-report-source-mismatch")
            elif (type(report.get("ok")) is not bool or not isinstance(report.get("findings"), list)
                  or type(report.get("error_count")) is not int or type(report.get("warning_count")) is not int
                  or type(report.get("songs_scanned")) is not int or type(report.get("charts_scanned")) is not int
                  or report["error_count"] < 0 or report["warning_count"] < 0
                  or report["songs_scanned"] < 0 or report["charts_scanned"] < 0
                  or any(not isinstance(f, dict) or set(f) != {"category", "severity", "code", "message", "path"}
                         or f.get("severity") not in ("error", "warning") for f in report["findings"])
                  or report["error_count"] != sum(f["severity"] == "error" for f in report["findings"])
                  or report["warning_count"] != sum(f["severity"] == "warning" for f in report["findings"])
                  or report["ok"] != (report["error_count"] == 0)):
                validator["status"] = "UNKNOWN"
                blockers.append("invalid-validator-report")
            else:
                validator.update(status="PASS" if report["ok"] else "FAIL", version=VALIDATOR_VERSION,
                                 ok=report["ok"], errorCount=report["error_count"],
                                 warningCount=report["warning_count"], reportSha256=digest(report_path))
                if not report["ok"]:
                    blockers.append("validator-failed")
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
                         "commit": "072dcfb83e28fa3cd5b6754db668c006b01eeec7",
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
    parser.add_argument("--output", help="write plan JSON metadata here; otherwise stdout")
    args = parser.parse_args()
    plan = preview(args)
    rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output).absolute()
        if output.exists() and output.is_dir():
            parser.error("--output must name a metadata file")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
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
