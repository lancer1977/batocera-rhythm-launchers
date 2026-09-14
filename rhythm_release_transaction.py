#!/usr/bin/env python3
"""Descriptor-pinned transaction for the Rhythm Support launcher release."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import secrets
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request


BUNDLES = ("stepmania-flatpak-launcher", "itgmania-portable-launcher")
ALLOWED_FILES = {
    "README.md",
    "service.sh",
    "install.sh",
    "config.example",
    "apply-controller-map.sh",
    "ports-launcher.sh",
}


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="install-rhythm-from-release.sh",
        description=(
            "Download, checksum-verify, and install the StepMania and "
            "ITGmania launcher bundles from one GitHub prerelease."
        ),
        epilog=(
            "After installation, Stage the separately obtained, "
            "checksum-qualified stock ITGmania archive before launching "
            "ITGMania Portable from Batocera Ports."
        ),
    )
    parser.add_argument("--tag", required=True, help="Required Rhythm Support Beta release tag.")
    parser.add_argument(
        "--repo",
        default="lancer1977/batocera-rhythm-launchers",
        help="Release repository (default: lancer1977/batocera-rhythm-launchers).",
    )
    parser.add_argument("--release-json", help="Local GitHub-release JSON fixture (tests/offline only).")
    parser.add_argument("--download-dir", help="Retain verified downloads here instead of a temporary directory.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and print the verified install plan without writing.",
    )
    args = parser.parse_args(argv)
    if not args.repo:
        die("--repo is required")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+-rhythm-beta\.[0-9]+", args.tag):
        die("tag must use vX.Y.Z-rhythm-beta.N")
    return args


def open_directory_walk(path: str) -> tuple[int, str]:
    """Open/create a directory tree without following a symlink component."""

    requested = os.path.abspath(path)
    components = [part for part in requested.split(os.sep) if part]
    current_fd = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    current_path = os.sep
    try:
        for component in components:
            try:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=current_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            os.close(current_fd)
            current_fd = next_fd
            current_path = os.path.join(current_path, component)
        return current_fd, current_path
    except OSError as error:
        os.close(current_fd)
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise RuntimeError(
                f"unsafe download directory ancestry (symlink or non-directory): {requested}"
            ) from error
        raise RuntimeError(f"unable to create retained download directory: {error}") from error


def create_stage(root_fd: int, root_path: str) -> tuple[int, str]:
    for _ in range(100):
        name = f".rhythm-stage.{secrets.token_hex(6)}"
        try:
            os.mkdir(name, 0o700, dir_fd=root_fd)
        except FileExistsError:
            continue
        try:
            created_stat = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            stage_fd = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
            opened_stat = os.fstat(stage_fd)
            if (
                not stat.S_ISDIR(created_stat.st_mode)
                or (created_stat.st_dev, created_stat.st_ino)
                != (opened_stat.st_dev, opened_stat.st_ino)
            ):
                os.close(stage_fd)
                raise RuntimeError("release staging directory was replaced during creation")
        except Exception:
            try:
                os.rmdir(name, dir_fd=root_fd)
            except OSError:
                pass
            raise
        return stage_fd, os.path.join(root_path, name)
    raise RuntimeError("unable to choose a private release staging directory")


def fd_path(directory_fd: int, *parts: str) -> str:
    return os.path.join(f"/proc/self/fd/{directory_fd}", *parts)


def write_test_hook(name: str, stage_path: str) -> None:
    """Optional race-test pause; unused in normal release execution."""

    marker = os.environ.get(name)
    if not marker:
        return
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write(stage_path + "\n")
    while not os.path.exists(marker + ".continue"):
        time.sleep(0.01)


def fetch_to_stage(stage_fd: int, url: str, destination: str) -> None:
    file_fd: int | None = None
    try:
        file_fd = os.open(".", os.O_WRONLY | os.O_TMPFILE, 0o600, dir_fd=stage_fd)
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "rhythm-support-installer",
            },
        )
        with urllib.request.urlopen(request) as response:
            while chunk := response.read(1024 * 1024):
                view = memoryview(chunk)
                while view:
                    written = os.write(file_fd, view)
                    view = view[written:]
        os.fsync(file_fd)
        # Link the anonymous inode by descriptor. A pre-existing destination,
        # including a symlink, fails rather than being followed or overwritten.
        # follow_symlinks=True is needed for Linux's /proc/self/fd indirection:
        # it resolves to the anonymous inode, while link() still refuses an
        # existing destination and therefore cannot overwrite a raced path.
        os.link(f"/proc/self/fd/{file_fd}", destination, dst_dir_fd=stage_fd, follow_symlinks=True)
    except Exception as error:
        raise RuntimeError(f"unable to stage {destination}: {error}") from error
    finally:
        if file_fd is not None:
            os.close(file_fd)


def read_stage_file(stage_fd: int, name: str) -> bytes:
    file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=stage_fd)
    with os.fdopen(file_fd, "rb") as handle:
        return handle.read()


def asset_url(metadata: dict, name: str) -> str:
    for asset in metadata.get("assets", []):
        if asset.get("name") == name and asset.get("browser_download_url"):
            return asset["browser_download_url"]
    raise RuntimeError(f"release is missing {name}")


def validate_checksum(stage_fd: int, archive: str, checksum: str) -> None:
    raw = read_stage_file(stage_fd, checksum).decode("utf-8")
    expected: str | None = None
    for line in raw.splitlines():
        fields = line.split()
        # sha256sum emits either "digest  name" or "digest *name" (binary
        # mode); accept both forms supported by the original sha256sum -c
        # implementation.
        if len(fields) >= 2 and fields[-1].lstrip("*") == archive:
            expected = fields[0].lower()
            break
    if expected is None or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise RuntimeError(f"invalid checksum file for {archive}")
    archive_fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=stage_fd)
    digestor = hashlib.sha256()
    with os.fdopen(archive_fd, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digestor.update(block)
    if not secrets.compare_digest(digestor.hexdigest(), expected):
        raise RuntimeError(f"checksum mismatch for {archive}")


def member_parts(name: str) -> tuple[str, ...]:
    if not name or name.startswith("/"):
        raise RuntimeError(f"unexpected or unsafe archive entry: {name}")
    parts = tuple(PurePosixPath(name).parts)
    if not parts or any(part in ("", ".", "..") for part in parts) or "\\" in name:
        raise RuntimeError(f"unexpected or unsafe archive entry: {name}")
    return parts


def validate_member(member: tarfile.TarInfo) -> tuple[str, ...]:
    parts = member_parts(member.name.rstrip("/"))
    allowed = len(parts) == 1 and parts[0] in ALLOWED_FILES
    payload = parts[0] == "payload"
    if not (allowed or payload):
        raise RuntimeError(f"unexpected or unsafe archive entry: {member.name}")
    if member.isdir():
        if not payload:
            raise RuntimeError(f"unexpected or unsafe archive entry: {member.name}")
    elif not member.isfile():
        raise RuntimeError(f"unexpected or unsafe archive entry: {member.name}")
    return parts


def open_dir_beneath(parent_fd: int, name: str, *, create: bool = False) -> int:
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)


def ensure_directory(root_fd: int, parts: tuple[str, ...]) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = open_dir_beneath(current_fd, part, create=True)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def extract_secure(stage_fd: int, archive: str, bundle: str) -> None:
    extracted_fd = open_dir_beneath(stage_fd, "extracted", create=True)
    try:
        bundle_fd = open_dir_beneath(extracted_fd, bundle, create=True)
    finally:
        os.close(extracted_fd)
    try:
        archive_fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=stage_fd)
        with os.fdopen(archive_fd, "rb") as archive_handle, tarfile.open(
            fileobj=archive_handle, mode="r:gz"
        ) as tar:
            members = [(member, validate_member(member)) for member in tar.getmembers()]
            for member, parts in members:
                if member.isdir():
                    directory_fd = ensure_directory(bundle_fd, parts)
                    os.close(directory_fd)
                    continue
                parent_fd = ensure_directory(bundle_fd, parts[:-1])
                output_fd = -1
                try:
                    output_fd = os.open(
                        parts[-1],
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        member.mode & 0o777,
                        dir_fd=parent_fd,
                    )
                    source = tar.extractfile(member)
                    if source is None:
                        raise RuntimeError(f"unable to read archive entry: {member.name}")
                    with source, os.fdopen(output_fd, "wb") as output:
                        output_fd = -1
                        while chunk := source.read(1024 * 1024):
                            output.write(chunk)
                finally:
                    if output_fd >= 0:
                        os.close(output_fd)
                    os.close(parent_fd)
    except (OSError, tarfile.TarError) as error:
        raise RuntimeError(f"unable to securely extract {archive}: {error}") from error
    finally:
        os.close(bundle_fd)


def remove_tree_fd(directory_fd: int) -> None:
    """Remove only a dedicated stage's contents, without pathname recursion."""

    for entry in os.scandir(fd_path(directory_fd)):
        name = entry.name
        if entry.is_dir(follow_symlinks=False):
            child_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
            try:
                remove_tree_fd(child_fd)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        else:
            os.unlink(name, dir_fd=directory_fd)


def run_installers(stage_fd: int) -> None:
    for bundle in BUNDLES:
        install_dir = fd_path(stage_fd, "extracted", bundle)
        subprocess.run(
            [fd_path(stage_fd, "extracted", bundle, "install.sh")],
            cwd=install_dir,
            check=True,
            pass_fds=(stage_fd,),
        )


def run(args: argparse.Namespace) -> None:
    version = args.tag[1:]
    # Match the public shell behavior: an omitted or empty --download-dir
    # uses private temporary staging rather than treating the current working
    # directory as a retained root.
    temporary_root = not args.download_dir
    if temporary_root:
        root_path = tempfile.mkdtemp(prefix="rhythm-release-")
        root_fd = os.open(root_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    else:
        root_fd, root_path = open_directory_walk(args.download_dir)

    stage_fd: int | None = None
    try:
        stage_fd, stage_path = create_stage(root_fd, root_path)
        write_test_hook("RHYTHM_TEST_STAGE_READY", stage_path)
        release_url = (
            "file://" + os.path.abspath(args.release_json)
            if args.release_json
            else f"https://api.github.com/repos/{args.repo}/releases/tags/{args.tag}"
        )
        fetch_to_stage(stage_fd, release_url, "release.json")
        metadata = json.loads(read_stage_file(stage_fd, "release.json").decode("utf-8"))

        for bundle in BUNDLES:
            archive = f"{bundle}-{version}.tar.gz"
            checksum = archive + ".sha256"
            archive_url = asset_url(metadata, archive)
            checksum_url = asset_url(metadata, checksum)
            if not args.release_json and (
                not archive_url.startswith("https://") or not checksum_url.startswith("https://")
            ):
                raise RuntimeError("release asset URL must use HTTPS")
            print(f"Verified install plan: {archive}")
            if args.dry_run:
                print(f"  archive: {archive_url}\n  checksum: {checksum_url}")
                continue
            fetch_to_stage(stage_fd, archive_url, archive)
            fetch_to_stage(stage_fd, checksum_url, checksum)
            validate_checksum(stage_fd, archive, checksum)
            extract_secure(stage_fd, archive, bundle)
            write_test_hook("RHYTHM_TEST_BEFORE_INSTALL", stage_path)
            if not os.access(fd_path(stage_fd, "extracted", bundle, "install.sh"), os.X_OK):
                raise RuntimeError(f"{archive} does not contain an executable install.sh")

        if not args.dry_run:
            run_installers(stage_fd)

        if args.dry_run:
            # The retained root is user-owned; remove only this stage.
            remove_tree_fd(stage_fd)
            os.close(stage_fd)
            stage_fd = None
            os.rmdir(os.path.basename(stage_path), dir_fd=root_fd)
            print("DRY-RUN: no release assets were downloaded or installed.")
        else:
            print(f"Installed verified Rhythm Support Beta {version} launcher bundles.")
    finally:
        if stage_fd is not None:
            if temporary_root:
                try:
                    remove_tree_fd(stage_fd)
                    # The private stage is a direct child of the temporary
                    # root.  Remove its directory entry via the root handle
                    # before attempting to remove the root itself.
                    os.rmdir(os.path.basename(stage_path), dir_fd=root_fd)
                except OSError:
                    pass
            os.close(stage_fd)
        os.close(root_fd)
        if temporary_root:
            try:
                os.rmdir(root_path)
            except OSError:
                pass


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        run(args)
    except (RuntimeError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        die(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
