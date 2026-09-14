#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$script_dir" <<'PY'
import importlib.util
import io
import os
import pathlib
import shutil
import tarfile
import tempfile

script_dir = pathlib.Path(os.sys.argv[1])
spec = importlib.util.spec_from_file_location("transaction", script_dir / "rhythm_release_transaction.py")
transaction = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(transaction)

root = pathlib.Path(tempfile.mkdtemp(prefix="rhythm-fd-ancestry-"))
try:
    archive = root / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        payload = b"#!/usr/bin/env bash\nexit 0\n"
        info = tarfile.TarInfo("install.sh")
        info.mode = 0o755
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))

    root_fd, root_path = transaction.open_directory_walk(str(root / "downloads"))
    stage_fd, stage_path = transaction.create_stage(root_fd, root_path)
    try:
        archive_fd = os.open(
            "bundle.tar.gz",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=stage_fd,
        )
        with os.fdopen(archive_fd, "wb") as output, archive.open("rb") as source:
            output.write(source.read())

        outside = root / "outside"
        outside.mkdir()
        os.symlink(outside, pathlib.Path(stage_path) / "extracted")
        try:
            transaction.extract_secure(stage_fd, "bundle.tar.gz", "stepmania-flatpak-launcher")
        except (OSError, RuntimeError):
            pass
        else:
            raise AssertionError("extract_secure accepted a symlinked extraction ancestry")
        if list(outside.iterdir()):
            raise AssertionError("extraction wrote through the symlinked ancestry")
    finally:
        os.close(stage_fd)
        os.close(root_fd)
finally:
    shutil.rmtree(root)
print("descriptor-pinned stage and extraction ancestry: ok")
PY
