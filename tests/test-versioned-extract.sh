#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

mkdir -p "$work_dir/assets" "$work_dir/fixtures" "$work_dir/bin" "$work_dir/downloads"

python3 - "$work_dir/assets" "$work_dir/fixtures" <<'PY'
import hashlib
import json
import pathlib
import sys
import tarfile

assets = pathlib.Path(sys.argv[1])
fixtures = pathlib.Path(sys.argv[2])
for version in ("0.1.0-rhythm-beta.1", "0.1.0-rhythm-beta.2"):
    release_assets = []
    for bundle in ("stepmania-flatpak-launcher", "itgmania-portable-launcher"):
        archive_name = f"{bundle}-{version}.tar.gz"
        archive = assets / archive_name
        install = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"mkdir -p \"$INSTALL_ROOT\"\n"
            f"printf '%s\\n' '{version}' > \"$INSTALL_ROOT/{bundle}.installed\"\n"
        )
        temp = assets / f"{bundle}-{version}.install.sh"
        temp.write_text(install, encoding="utf-8")
        temp.chmod(0o755)
        with tarfile.open(archive, "w:gz") as handle:
            handle.add(temp, arcname="install.sh")
        temp.unlink()
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksum_name = f"{archive_name}.sha256"
        (assets / checksum_name).write_text(f"{digest}  {archive_name}\n", encoding="utf-8")
        for name in (archive_name, checksum_name):
            release_assets.append({
                "name": name,
                "browser_download_url": f"file://{assets / name}",
            })
    (fixtures / f"{version}.json").write_text(json.dumps({"assets": release_assets}), encoding="utf-8")
PY

cat > "$work_dir/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
output=''
url=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) output="$2"; shift 2 ;;
    *) url="$1"; shift ;;
  esac
done
cp "$ASSET_SOURCE/$(basename "$url")" "$output"
SH
chmod +x "$work_dir/bin/curl"

run_install() {
  local version="$1"
  INSTALL_ROOT="$work_dir/install" \
    ASSET_SOURCE="$work_dir/assets" \
    PATH="$work_dir/bin:$PATH" \
    "$script_dir/install-rhythm-from-release.sh" \
      --tag "v$version" \
      --release-json "$work_dir/fixtures/$version.json" \
      --download-dir "$work_dir/downloads"
}

run_install 0.1.0-rhythm-beta.1
run_install 0.1.0-rhythm-beta.2

stage_count="$(find "$work_dir/downloads" -maxdepth 1 -type d -name '.rhythm-stage.*' | wc -l)"
[ "$stage_count" -eq 2 ]
find "$work_dir/downloads" -type f -name 'stepmania-flatpak-launcher-0.1.0-rhythm-beta.1.tar.gz' | grep -q .
find "$work_dir/downloads" -type f -name 'stepmania-flatpak-launcher-0.1.0-rhythm-beta.2.tar.gz' | grep -q .

nested_downloads="$work_dir/missing/retained/downloads"
INSTALL_ROOT="$work_dir/install" \
  ASSET_SOURCE="$work_dir/assets" \
  PATH="$work_dir/bin:$PATH" \
  "$script_dir/install-rhythm-from-release.sh" \
    --tag v0.1.0-rhythm-beta.1 \
    --release-json "$work_dir/fixtures/0.1.0-rhythm-beta.1.json" \
    --download-dir "$nested_downloads" >/dev/null
[ -d "$nested_downloads" ]
find "$nested_downloads" -type f -name 'itgmania-portable-launcher-0.1.0-rhythm-beta.1.tar.gz' | grep -q .

outside_parent="$work_dir/outside-parent"
mkdir -p "$outside_parent"
ln -s "$outside_parent" "$work_dir/symlinked-download-parent"
if INSTALL_ROOT="$work_dir/install" \
  ASSET_SOURCE="$work_dir/assets" \
  PATH="$work_dir/bin:$PATH" \
  "$script_dir/install-rhythm-from-release.sh" \
    --tag v0.1.0-rhythm-beta.2 \
    --release-json "$work_dir/fixtures/0.1.0-rhythm-beta.2.json" \
    --download-dir "$work_dir/symlinked-download-parent/downloads" > "$work_dir/parent-output" 2>&1; then
  echo "installer unexpectedly accepted a symlinked download directory parent" >&2
  exit 1
fi
grep -Fq 'unsafe download directory ancestry' "$work_dir/parent-output"

archive_sentinel="$work_dir/archive-sentinel.txt"
printf 'must-survive-archive\n' > "$archive_sentinel"
ln -s "$archive_sentinel" "$work_dir/downloads/stepmania-flatpak-launcher-0.1.0-rhythm-beta.2.tar.gz"
run_install 0.1.0-rhythm-beta.2
[ "$(cat "$archive_sentinel")" = 'must-survive-archive' ]

echo "private staging and retained downloads: ok"
