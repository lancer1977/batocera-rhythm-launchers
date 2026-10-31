#!/usr/bin/env python3
"""Safely apply, inspect, recover, or roll back one READY rhythm pack plan."""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import sys

import rhythm_pack_preview as preview

RECEIPT_SCHEMA = "batocera.rhythm-pack-transaction.v1"
STATE_DIR = ".rhythm-pack-transactions"
STAGE_PREFIX = ".rhythm-pack-stage-"
OWNER_MARKER = ".rhythm-pack-owner"
RENAME_NOREPLACE = 1


def fail(message: str) -> None:
    raise RuntimeError(message)


def validate_rel(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not preview.safe_relative(value):
        fail("unsafe transaction path")
    parts = tuple(PurePosixPath(value).parts)
    if not parts or any(p in ("", ".", "..") for p in parts):
        fail("unsafe transaction path")
    return parts


def open_directory_walk(path: str, *, create: bool = False) -> int:
    """Open an absolute directory without following any symlink component."""
    absolute = os.path.abspath(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in (p for p in absolute.split(os.sep) if p):
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except Exception:
        os.close(fd)
        raise


def open_child_dir(parent_fd: int, name: str, *, create: bool = False, mode: int = 0o755) -> int:
    if name in ("", ".", "..") or "/" in name:
        fail("unsafe directory component")
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        os.mkdir(name, mode, dir_fd=parent_fd)
        os.fsync(parent_fd)
        child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        os.fsync(child)
        return child


def ensure_dir(root_fd: int, parts: tuple[str, ...], *, create: bool) -> int:
    fd = os.dup(root_fd)
    try:
        for part in parts:
            child = open_child_dir(fd, part, create=create)
            os.close(fd)
            fd = child
        return fd
    except Exception:
        os.close(fd)
        raise


def hash_fd(fd: int) -> str:
    h = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while block := os.read(fd, 1024 * 1024):
        h.update(block)
    return h.hexdigest()


def read_regular(parent_fd: int, name: str) -> bytes:
    # O_NONBLOCK keeps a FIFO from hanging the open before the type check below.
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            fail("unsupported transaction entry")
        chunks = []
        while block := os.read(fd, 1024 * 1024):
            chunks.append(block)
        return b"".join(chunks)
    finally:
        os.close(fd)


def write_exclusive(parent_fd: int, name: str, data: bytes, mode: int = 0o600) -> None:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=parent_fd)
    try:
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def rename_noreplace(source: str, destination: str, source_fd: int, destination_fd: int) -> None:
    """Atomically activate only if the destination is still absent."""
    libc = ctypes.CDLL(None, use_errno=True)
    operation = getattr(libc, "renameat2", None)
    if operation is None:
        fail("atomic no-replace rename is unavailable on this platform")
    operation.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    operation.restype = ctypes.c_int
    if operation(source_fd, os.fsencode(source), destination_fd, os.fsencode(destination), RENAME_NOREPLACE) != 0:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            fail("destination pack appeared during activation; refusing overwrite")
        raise OSError(error, os.strerror(error), destination)


def atomic_receipt(state_fd: int, receipt: dict) -> None:
    temp = ".receipt-" + secrets.token_hex(8)
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    write_exclusive(state_fd, temp, payload)
    os.rename(temp, receipt["id"] + ".json", src_dir_fd=state_fd, dst_dir_fd=state_fd)
    os.fsync(state_fd)


def load_receipt(state_fd: int, txid: str) -> dict:
    if not txid.isalnum() or len(txid) != 32:
        fail("invalid transaction id")
    try:
        value = json.loads(read_regular(state_fd, txid + ".json"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("receipt unavailable or invalid") from exc
    if (not isinstance(value, dict) or value.get("schema") != RECEIPT_SCHEMA
            or value.get("id") != txid or not isinstance(value.get("files"), list)):
        fail("receipt unavailable or invalid")
    if (value.get("stageDirectory") != STAGE_PREFIX + txid
            or value.get("before") != {"packRoot": "absent"}
            or value.get("status") not in {"staging", "staging-ready", "activation-pending", "active", "conflict", "rollback-conflict", "rolled-back"}
            or value.get("runtime") not in {"stepmania-flatpak", "itgmania-portable"}
            or not isinstance(value.get("profile"), str) or not value["profile"]
            or not isinstance(value.get("packId"), str) or not value["packId"]
            or not isinstance(value.get("targetSongsRoot"), str)
            or not os.path.isabs(value["targetSongsRoot"])
            or os.path.normpath(value["targetSongsRoot"]) != value["targetSongsRoot"]
            or ("conflicts" in value and (not isinstance(value["conflicts"], list)
                 or any(not isinstance(entry, str) or not entry for entry in value["conflicts"])) )):
        fail("receipt unavailable or invalid")
    ownership = value.get("ownership")
    if ownership is not None and (not isinstance(ownership, dict)
            or set(ownership) != {"device", "inode", "nonce", "marker"}
            or type(ownership["device"]) is not int or ownership["device"] < 0
            or type(ownership["inode"]) is not int or ownership["inode"] < 1
            or not isinstance(ownership["nonce"], str) or len(ownership["nonce"]) != 64
            or any(c not in "0123456789abcdef" for c in ownership["nonce"])
            or ownership["marker"] != OWNER_MARKER):
        fail("receipt unavailable or invalid")
    pack_root = validate_rel(value.get("packRoot"))
    if len(pack_root) != 1:
        fail("receipt unavailable or invalid")
    seen = set()
    for item in value["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
            fail("receipt unavailable or invalid")
        validate_rel(item["path"])
        if validate_rel(item["path"])[0] == OWNER_MARKER:
            fail("receipt unavailable or invalid")
        if (not isinstance(item["sha256"], str) or len(item["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in item["sha256"])
                or type(item["bytes"]) is not int or item["bytes"] < 0
                or item["path"] in seen):
            fail("receipt unavailable or invalid")
        seen.add(item["path"])
    if not seen:
        fail("receipt unavailable or invalid")
    return value


def copy_verified(source_fd: int, stage_fd: int, item: dict, hook=None) -> None:
    src_parts = validate_rel(item["source"])
    dst_parts = validate_rel(item["destination"])
    sparent = ensure_dir(source_fd, src_parts[:-1], create=False)
    try:
        sfd = os.open(src_parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=sparent)
    finally:
        os.close(sparent)
    try:
        details = os.fstat(sfd)
        if not stat.S_ISREG(details.st_mode) or hash_fd(sfd) != item["sha256"] or details.st_size != item["bytes"]:
            fail("source changed after plan validation")
        dparent = ensure_dir(stage_fd, dst_parts[:-1], create=True)
        try:
            dfd = os.open(dst_parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=dparent)
            try:
                os.lseek(sfd, 0, os.SEEK_SET)
                while block := os.read(sfd, 1024 * 1024):
                    view = memoryview(block)
                    while view:
                        count = os.write(dfd, view)
                        view = view[count:]
                os.fsync(dfd)
                if hook:
                    hook("file-staged")
                check_fd = os.open(dst_parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dparent)
                try:
                    if hash_fd(check_fd) != item["sha256"]:
                        fail("staged file hash mismatch")
                finally:
                    os.close(check_fd)
            finally:
                os.close(dfd)
        finally:
            os.close(dparent)
    finally:
        os.close(sfd)


def stage_identity(fd: int) -> dict:
    info = os.fstat(fd)
    return {"device": info.st_dev, "inode": info.st_ino}


def path_matches_fd(parent_fd: int, name: str, fd: int) -> bool:
    try:
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        opened = os.fstat(fd)
    except OSError:
        return False
    return stat.S_ISDIR(entry.st_mode) and (entry.st_dev, entry.st_ino) == (opened.st_dev, opened.st_ino)


def verify_ownership(fd: int, receipt: dict) -> bool:
    ownership = receipt.get("ownership")
    if not isinstance(ownership, dict) or stage_identity(fd) != {
            "device": ownership.get("device"), "inode": ownership.get("inode")} :
        return False
    try:
        marker = read_regular(fd, OWNER_MARKER)
    except OSError:
        return False
    expected = (json.dumps({"id": receipt["id"], "nonce": ownership["nonce"]},
                           sort_keys=True, separators=(",", ":")) + "\n").encode()
    return marker == expected


def remove_marker(fd: int, receipt: dict) -> bool:
    if not verify_ownership(fd, receipt):
        return False
    os.unlink(OWNER_MARKER, dir_fd=fd)
    os.fsync(fd)
    return True


def verify_tree(root_fd: int, files: list[dict], *, owned_marker: bool = False) -> tuple[bool, list[str]]:
    conflicts = []
    expected = {item["path"] for item in files}
    if owned_marker:
        expected.add(OWNER_MARKER)
    observed: set[str] = set()

    def walk(directory_fd: int, prefix: str = "") -> None:
        for name in os.listdir(directory_fd):
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            relative = f"{prefix}/{name}" if prefix else name
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                try:
                    walk(child, relative)
                    os.fsync(child)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                observed.add(relative)
            else:
                conflicts.append(relative)

    try:
        walk(root_fd)
    except OSError:
        return False, ["unsupported-tree-entry"]
    conflicts.extend(sorted(observed - expected))
    conflicts.extend(sorted(expected - observed))
    for item in files:
        parts = validate_rel(item["path"])
        try:
            parent = ensure_dir(root_fd, parts[:-1], create=False)
            try:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                try:
                    details = os.fstat(fd)
                    if not stat.S_ISREG(details.st_mode) or details.st_size != item["bytes"] or hash_fd(fd) != item["sha256"]:
                        conflicts.append(item["path"])
                finally:
                    os.close(fd)
            finally:
                os.close(parent)
        except OSError:
            conflicts.append(item["path"])
    return not conflicts, conflicts


def remaining_entries(root_fd: int, *, ignore_marker: bool = False) -> list[str]:
    entries = []

    def walk(directory_fd: int, prefix: str = "") -> None:
        for name in os.listdir(directory_fd):
            if not prefix and ignore_marker and name == OWNER_MARKER:
                continue
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            relative = f"{prefix}/{name}" if prefix else name
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                try:
                    before = len(entries)
                    walk(child, relative)
                    # An empty directory is operator content too; report it so rollback keeps ownership evidence.
                    if len(entries) == before:
                        entries.append(relative)
                finally:
                    os.close(child)
            else:
                entries.append(relative)

    try:
        walk(root_fd)
    except OSError:
        return ["unsupported-tree-entry"]
    return entries


def remove_owned(root_fd: int, files: list[dict]) -> list[str]:
    conflicts = []
    for item in reversed(files):
        parts = validate_rel(item["path"])
        try:
            parent = ensure_dir(root_fd, parts[:-1], create=False)
            try:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_size != item["bytes"] or hash_fd(fd) != item["sha256"]:
                        conflicts.append(item["path"])
                        continue
                finally:
                    os.close(fd)
                os.unlink(parts[-1], dir_fd=parent)
            finally:
                os.close(parent)
        except FileNotFoundError:
            pass
        except OSError:
            conflicts.append(item["path"])
    # Prune only directories represented by owned paths; rmdir is empty-only.
    dirs = sorted({p for item in files for p in [validate_rel(item["path"])[:-1][:i]
                                                for i in range(1, len(validate_rel(item["path"])))]},
                  key=len, reverse=True)
    for parts in dirs:
        try:
            parent = ensure_dir(root_fd, parts[:-1], create=False)
            try:
                os.rmdir(parts[-1], dir_fd=parent)
            finally:
                os.close(parent)
        except OSError:
            pass
    conflicts.extend(remaining_entries(root_fd, ignore_marker=True))
    return sorted(set(conflicts))


def fresh_plan(args) -> tuple[dict, dict]:
    supplied = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    fresh_args = argparse.Namespace(source=args.source, target=args.target, inventory=args.inventory,
        validator_report=None, validator_source=args.validator_source, validator_version=None,
        pack=args.pack, runtime=args.runtime, profile=args.profile)
    fresh = preview.preview(fresh_args)
    if not isinstance(supplied, dict) or supplied.get("schema") != preview.SCHEMA or supplied.get("status") != "READY":
        fail("apply requires an explicit schema-1 READY plan")
    # All plan content except available-space telemetry must be identical to the fresh live preview.
    supplied_cmp, fresh_cmp = dict(supplied), dict(fresh)
    supplied_cmp.pop("availableBytes", None)
    fresh_cmp.pop("availableBytes", None)
    if supplied_cmp != fresh_cmp:
        fail("plan is stale, edited, or does not match fresh live validation")
    return supplied, fresh


def pack_destination(files: list[dict]) -> str:
    paths = [validate_rel(item["destination"]) for item in files]
    if not paths:
        fail("empty pack plan")
    root = paths[0][0]
    if any(path[0] != root for path in paths):
        fail("plan spans multiple pack roots")
    return root


def apply(args, hook=None) -> dict:
    plan, fresh = fresh_plan(args)
    if not args.game_stopped:
        fail("--game-stopped acknowledgement is required")
    if not args.profile:
        fail("runtime profile is required")
    target = Path(args.target).absolute()
    target_fd = open_directory_walk(str(target), create=True)
    source_fd = open_directory_walk(str(Path(args.source).absolute()), create=False)
    state_fd = None
    try:
        root_name = pack_destination(plan["files"])
        try:
            os.stat(root_name, dir_fd=target_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            fail("destination pack already exists; refusing overwrite or merge")
        need = sum(item["bytes"] for item in plan["files"])
        if shutil.disk_usage(target).free < need:
            fail("insufficient space at apply time")
        state_fd = open_child_dir(target_fd, STATE_DIR, create=True, mode=0o700)
        txid = secrets.token_hex(16)
        stage_name = STAGE_PREFIX + txid
        files = [{"path": "/".join(validate_rel(item["destination"])[1:]),
                  "sha256": item["sha256"], "bytes": item["bytes"]}
                 for item in plan["files"]]
        if any(validate_rel(item["destination"])[1:] == (OWNER_MARKER,) for item in plan["files"]):
            fail("source collides with reserved transaction ownership marker")
        receipt = {"schema": RECEIPT_SCHEMA, "id": txid, "status": "staging", "runtime": args.runtime,
                   "profile": args.profile, "packId": plan["packId"], "targetSongsRoot": str(target),
                   "packRoot": root_name, "stageDirectory": stage_name, "files": files,
                   "before": {"packRoot": "absent"}, "ownership": None}
        atomic_receipt(state_fd, receipt)
        os.mkdir(stage_name, 0o700, dir_fd=target_fd)
        os.fsync(target_fd)
        stage_fd = open_child_dir(target_fd, stage_name)
        try:
            nonce = secrets.token_hex(32)
            write_exclusive(stage_fd, OWNER_MARKER,
                (json.dumps({"id": txid, "nonce": nonce}, sort_keys=True, separators=(",", ":")) + "\n").encode())
            os.fsync(stage_fd)
            receipt["ownership"] = dict(stage_identity(stage_fd), nonce=nonce, marker=OWNER_MARKER)
            atomic_receipt(state_fd, receipt)
            for item in plan["files"]:
                staged_item = dict(item, destination="/".join(validate_rel(item["destination"])[1:]))
                copy_verified(source_fd, stage_fd, staged_item, hook)
            ok, conflicts = verify_tree(stage_fd, files, owned_marker=True)
            if not ok:
                fail("staged tree verification failed: " + ", ".join(conflicts))
            os.fsync(stage_fd)
            if hook:
                hook("before-activation")
            # Bind the activation boundary to the validator's complete source
            # snapshot and the exact selected files, including changes made
            # while the staging copy was in progress.
            live_report, live_version, live_snapshot = preview.run_live_validator(
                Path(args.source).absolute(), Path(args.validator_source).absolute())
            validator = plan["provenance"]["validator"]
            if (live_report is None or live_version != preview.VALIDATOR_VERSION
                    or live_snapshot != validator.get("liveSourceSnapshotSha256")
                    or hashlib.sha256(json.dumps(live_report, sort_keys=True).encode()).hexdigest()
                    != validator.get("reportSha256")):
                fail("live validator/source changed before activation")
            for item in plan["files"]:
                source_path = Path(args.source).absolute() / Path(*validate_rel(item["source"]))
                if (not source_path.is_file() or source_path.is_symlink()
                        or source_path.stat().st_size != item["bytes"]
                        or preview.digest(source_path) != item["sha256"]):
                    fail("source file changed before activation")
            # Rename works by pathname, so confirm the name still denotes the verified, owned stage first.
            if not path_matches_fd(target_fd, stage_name, stage_fd) or not verify_ownership(stage_fd, receipt):
                fail("staging directory was replaced before activation")
            rename_noreplace(stage_name, root_name, target_fd, target_fd)
            os.fsync(target_fd)
            if not path_matches_fd(target_fd, root_name, stage_fd) or not verify_ownership(stage_fd, receipt):
                fail("activated directory identity changed during rename")
            if hook:
                hook("after-activation")
            receipt["status"] = "active"
            atomic_receipt(state_fd, receipt)
            return receipt
        finally:
            try:
                os.close(stage_fd)
            except OSError:
                pass
    finally:
        if state_fd is not None:
            os.close(state_fd)
        os.close(source_fd)
        os.close(target_fd)


def recover(args, rollback=False) -> dict:
    target = Path(args.target).absolute()
    target_fd = open_directory_walk(str(target), create=False)
    state_fd = None
    try:
        state_fd = open_child_dir(target_fd, STATE_DIR)
        receipt = load_receipt(state_fd, args.transaction)
        if receipt.get("targetSongsRoot") != str(target):
            fail("receipt belongs to a different target")
        root = validate_rel(receipt.get("packRoot"))[0]
        status = receipt.get("status")
        if status == "rolled-back":
            if rollback:
                return receipt
            fail("transaction has already been rolled back")
        if receipt.get("ownership") is None:
            receipt["status"] = "conflict"
            receipt["conflicts"] = ["missing-ownership-evidence"]
            atomic_receipt(state_fd, receipt)
            fail("transaction has no durable ownership evidence; manual inspection required")

        # Pin both candidate directories by fd. A matching tree is never ownership proof.
        candidates = []
        for name in (receipt["stageDirectory"], root):
            try:
                fd = open_child_dir(target_fd, name)
            except FileNotFoundError:
                continue
            candidates.append((name, fd, path_matches_fd(target_fd, name, fd)
                               and verify_ownership(fd, receipt)))
        owned = [(name, fd) for name, fd, proof in candidates if proof]
        other = [(name, fd) for name, fd, proof in candidates if not proof]
        for name, fd in other:
            os.close(fd)
        if len(owned) > 1:
            for _, fd in owned: os.close(fd)
            receipt["status"] = "conflict"
            receipt["conflicts"] = ["multiple-ownership-identities"]
            atomic_receipt(state_fd, receipt)
            fail("multiple directories claim transaction ownership")
        if not owned:
            if candidates:
                receipt["status"] = "conflict"
                receipt["conflicts"] = ["ownership-mismatch"]
                atomic_receipt(state_fd, receipt)
                fail("candidate directory ownership mismatch; manual inspection required")
            if status in ("staging", "staging-ready") and not rollback:
                return receipt
            if status in ("staging", "staging-ready") and rollback:
                receipt["status"] = "rolled-back"
                atomic_receipt(state_fd, receipt)
                return receipt
            receipt["status"] = "conflict"
            receipt["conflicts"] = ["owned-directory-missing"]
            atomic_receipt(state_fd, receipt)
            fail("owned directory is missing; manual inspection required")

        name, owned_fd = owned[0]
        try:
            ok, conflicts = verify_tree(owned_fd, receipt["files"], owned_marker=True)
            if rollback:
                if not path_matches_fd(target_fd, name, owned_fd) or not verify_ownership(owned_fd, receipt):
                    fail("owned directory was replaced during rollback; manual inspection required")
                conflicts = remove_owned(owned_fd, receipt["files"])
                if not conflicts and remove_marker(owned_fd, receipt):
                    try:
                        if not path_matches_fd(target_fd, name, owned_fd):
                            conflicts.append("owned-directory-replaced")
                        else:
                            os.rmdir(name, dir_fd=target_fd)
                    except OSError: conflicts.append("directory-not-empty")
                elif not conflicts:
                    conflicts.append("ownership-marker-changed")
                receipt["status"] = "rolled-back" if not conflicts else "rollback-conflict"
                if conflicts: receipt["conflicts"] = conflicts
                atomic_receipt(state_fd, receipt)
            elif not ok:
                receipt["status"] = "conflict"
                receipt["conflicts"] = conflicts
                atomic_receipt(state_fd, receipt)
                fail("transaction tree changed; preserving files as conflict: " + ", ".join(conflicts))
            elif name == root:
                if not path_matches_fd(target_fd, name, owned_fd) or not verify_ownership(owned_fd, receipt):
                    fail("active directory was replaced during recovery")
                receipt["status"] = "active"
                atomic_receipt(state_fd, receipt)
            else:
                if status == "staging":
                    receipt["status"] = "staging-ready"
                    atomic_receipt(state_fd, receipt)
                else:
                    if not path_matches_fd(target_fd, name, owned_fd) or not verify_ownership(owned_fd, receipt):
                        fail("stage directory was replaced during activation")
                    rename_noreplace(name, root, target_fd, target_fd)
                    os.fsync(target_fd)
                    receipt["status"] = "activation-pending"
                    atomic_receipt(state_fd, receipt)
                    receipt["status"] = "active"
                    atomic_receipt(state_fd, receipt)
        finally:
            os.close(owned_fd)
        return receipt
    finally:
        if state_fd is not None:
            os.close(state_fd)
        os.close(target_fd)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    apply_p = sub.add_parser("apply", help="stage and atomically activate one fresh READY plan")
    apply_p.add_argument("--apply", action="store_true", required=True,
                         help="explicitly authorize this selected local apply operation")
    apply_p.add_argument("--plan", required=True)
    apply_p.add_argument("--source", required=True)
    apply_p.add_argument("--inventory", required=True)
    apply_p.add_argument("--validator-source", required=True)
    apply_p.add_argument("--pack", required=True)
    apply_p.add_argument("--runtime", choices=("stepmania-flatpak", "itgmania-portable"), required=True)
    apply_p.add_argument("--profile", required=True)
    apply_p.add_argument("--target", required=True)
    apply_p.add_argument("--game-stopped", action="store_true", required=True,
                         help="acknowledge the selected runtime is stopped")
    tx_p = sub.add_parser("recover", help="inspect/finish a durable transaction")
    tx_p.add_argument("--target", required=True)
    tx_p.add_argument("--transaction", required=True)
    rb_p = sub.add_parser("rollback", help="remove only unchanged transaction-owned files")
    rb_p.add_argument("--target", required=True)
    rb_p.add_argument("--transaction", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "apply":
            result = apply(args)
        else:
            result = recover(args, rollback=args.command == "rollback")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
