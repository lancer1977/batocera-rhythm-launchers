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


def preview(args: argparse.Namespace) -> dict:
    source = Path(args.source).absolute()
    target = Path(args.target).absolute()
    inventory_path = Path(args.inventory).absolute()
    report_path = Path(args.validator_report).absolute() if args.validator_report else None
    blockers: list[str] = []
    entries: list[dict] = []
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        if inventory.get("schemaVersion") != INVENTORY_VERSION:
            blockers.append("unsupported-inventory-schema")
        if inventory.get("identityVersion") != 1:
            blockers.append("unsupported-inventory-identity-version")
        if inventory.get("installationRoot") != str(source):
            blockers.append("inventory-source-root-mismatch")
    except (OSError, ValueError, AttributeError):
        inventory = {}
        blockers.append("inventory-unavailable-or-invalid")

    pack = next((p for p in inventory.get("packs", []) if p.get("packId") == args.pack), None)
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
            for asset in pack.get("assets", []):
                rel = asset.get("relativeLocation", "")
                if not safe_relative(rel) or not rel.startswith(loc.rstrip("/") + "/"):
                    blockers.append("unsupported-pack-asset-layout")
                    continue
                path = source / rel
                if path.is_symlink() or not within(source, path.resolve(strict=False)):
                    blockers.append("source-symlink-unsupported")
                    continue
                if asset.get("status") != "present" or not path.is_file():
                    blockers.append("missing-or-unreadable-asset")
                    continue
                actual = digest(path)
                if not asset.get("sha256") or actual != asset["sha256"]:
                    blockers.append("source-hash-mismatch")
                    continue
                entries.append({"source": rel, "destination": str(PurePosixPath(rel).relative_to(PurePosixPath(loc))),
                                "sha256": actual, "bytes": path.stat().st_size,
                                "targetState": "absent", "targetSha256": None})
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
                    if not safe_relative(rel):
                        blockers.append("source-path-escape-or-unsupported-path")
                        continue
                    path = source / rel
                    if not within(source, path.resolve(strict=False)):
                        blockers.append("source-path-escape-or-symlink")
                        continue
                    if asset.get("status") != "present" or not path.is_file():
                        blockers.append("missing-or-unreadable-asset")
                        continue
                    if path.is_symlink() or not within(source, path.resolve()):
                        blockers.append("source-symlink-unsupported")
                        continue
                    actual = digest(path)
                    if not asset.get("sha256") or actual != asset["sha256"]:
                        blockers.append("source-hash-mismatch")
                        continue
                    destination = PurePosixPath(songloc).relative_to(PurePosixPath(loc)) / Path(rel).name
                    dest_rel = str(destination)
                    dest = target.joinpath(*destination.parts)
                    state = "absent"
                    existing_hash = None
                    if dest.exists() or dest.is_symlink():
                        if dest.is_symlink() or not dest.is_file():
                            blockers.append("target-conflict-unsupported-entry")
                            state = "conflict"
                        else:
                            existing_hash = digest(dest)
                            if existing_hash != actual:
                                blockers.append("target-file-conflict")
                                state = "conflict"
                            else:
                                state = "identical"
                    entries.append({"source": rel, "destination": dest_rel, "sha256": actual,
                                    "bytes": path.stat().st_size, "targetState": state,
                                    "targetSha256": existing_hash})

    validator = {"status": "UNAVAILABLE", "version": None, "reportSchema": "stepmania-song-validator-0.1.0-report-v1"}
    if report_path and args.validator_version == VALIDATOR_VERSION:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if set(report) != {"library_path", "songs_scanned", "charts_scanned", "error_count", "warning_count", "ok", "findings"}:
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
