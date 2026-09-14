#!/usr/bin/env bash
set -euo pipefail

# Install the two launcher bundles from one verified Rhythm Support Beta
# release. This script is intended to be downloaded as a release asset and run
# locally on a Batocera host; it never installs engines or song content.

usage() {
  cat <<'USAGE'
Usage: install-rhythm-from-release.sh --tag vX.Y.Z-rhythm-beta.N [options]

Download, checksum-verify, and install the StepMania and ITGmania launcher
bundles from one GitHub prerelease.

Options:
  --tag TAG              Required Rhythm Support Beta release tag.
  --repo OWNER/REPO      Release repository (default: lancer1977/batocera-rhythm-launchers).
  --release-json PATH   Local GitHub-release JSON fixture (tests/offline only).
  --download-dir PATH   Retain verified downloads here instead of a temporary directory.
  --dry-run              Resolve and print the verified install plan without writing.
  --help                 Show this help.

After installation, Stage the separately obtained, checksum-qualified stock
ITGmania archive before launching ITGMania Portable from Batocera Ports.
USAGE
}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

repo='lancer1977/batocera-rhythm-launchers'
tag=''
release_json=''
download_dir=''
dry_run=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --tag) tag="${2:-}"; shift 2 ;;
    --repo) repo="${2:-}"; shift 2 ;;
    --release-json) release_json="${2:-}"; shift 2 ;;
    --download-dir) download_dir="${2:-}"; shift 2 ;;
    --dry-run) dry_run=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[ -n "$tag" ] || die '--tag is required'
[ -n "$repo" ] || die '--repo is required'
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rhythm-beta\.[0-9]+$ ]] || die 'tag must use vX.Y.Z-rhythm-beta.N'

version="${tag#v}"
bundles=(stepmania-flatpak-launcher itgmania-portable-launcher)

validate_directory_ancestry() {
  python3 - "$1" <<'PY'
import os
import pathlib
import stat
import sys

path = pathlib.Path(os.path.abspath(sys.argv[1]))
current = pathlib.Path(path.anchor)
for component in path.parts[1:]:
    current /= component
    try:
        mode = os.lstat(current).st_mode
    except FileNotFoundError:
        break
    if stat.S_ISLNK(mode):
        raise SystemExit(f"refusing symlink in download directory ancestry: {current}")
    if not stat.S_ISDIR(mode):
        raise SystemExit(f"refusing non-directory in download directory ancestry: {current}")
PY
}

validate_regular_destination() {
  python3 - "$1" <<'PY'
import os
import stat
import sys

path = sys.argv[1]
try:
    mode = os.lstat(path).st_mode
except FileNotFoundError:
    raise SystemExit(0)
if stat.S_ISLNK(mode):
    raise SystemExit(f"refusing symlinked download destination: {path}")
if not stat.S_ISREG(mode):
    raise SystemExit(f"refusing non-regular download destination: {path}")
PY
}

if [ -z "$download_dir" ]; then
  download_dir="$(mktemp -d)"
  cleanup_download_dir=true
else
  cleanup_download_dir=false
  validate_directory_ancestry "$download_dir" || die "unsafe download directory ancestry: $download_dir"
  mkdir -p "$download_dir"
fi
cleanup() {
  if [ "$cleanup_download_dir" = true ]; then
    rm -rf -- "$download_dir"
  fi
}
trap cleanup EXIT

release_metadata="$download_dir/release.json"
validate_regular_destination "$release_metadata" || die "unsafe release metadata destination: $release_metadata"
if [ -n "$release_json" ]; then
  cp "$release_json" "$release_metadata"
else
  command -v curl >/dev/null 2>&1 || die 'curl is required'
  curl --fail --silent --show-error --location \
    -H 'Accept: application/vnd.github+json' \
    -H 'User-Agent: rhythm-support-installer' \
    "https://api.github.com/repos/$repo/releases/tags/$tag" > "$release_metadata"
fi

command -v python3 >/dev/null 2>&1 || die 'python3 is required'
if [ "$dry_run" = false ]; then
  command -v curl >/dev/null 2>&1 || die 'curl is required'
  command -v sha256sum >/dev/null 2>&1 || die 'sha256sum is required'
  command -v tar >/dev/null 2>&1 || die 'tar is required'
fi

asset_url() {
  local asset_name="$1"
  python3 - "$release_metadata" "$asset_name" <<'PY'
import json
import sys

with open(sys.argv[1], encoding='utf-8') as handle:
    payload = json.load(handle)
for asset in payload.get('assets', []):
    if asset.get('name') == sys.argv[2] and asset.get('browser_download_url'):
        print(asset['browser_download_url'])
        break
else:
    raise SystemExit(1)
PY
}

validate_bundle_archive() {
  local archive_path="$1"
  python3 - "$archive_path" <<'PY'
import tarfile
import sys

archive = sys.argv[1]
allowed_files = {
    "README.md",
    "service.sh",
    "install.sh",
    "config.example",
    "apply-controller-map.sh",
    "ports-launcher.sh",
}

try:
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            name = member.name.rstrip("/")
            if member.isdir() and name == "payload":
                continue
            if member.isfile() and (name in allowed_files or name.startswith("payload/")):
                continue
            raise SystemExit(f"unexpected or unsafe archive entry: {member.name}")
except (OSError, tarfile.TarError) as error:
    raise SystemExit(f"unable to inspect archive: {error}")
PY
}

validate_extraction_ancestry() {
  local extraction_dir="$1"
  python3 - "$download_dir" "$extraction_dir" <<'PY'
import os
import pathlib
import sys

root = pathlib.Path(os.path.abspath(sys.argv[1]))
target = pathlib.Path(os.path.abspath(sys.argv[2]))
try:
    relative = target.relative_to(root)
except ValueError:
    raise SystemExit("extraction directory is outside the download directory")

current = root
paths = [current]
for component in relative.parts:
    current /= component
    paths.append(current)

for path in paths:
    if path.is_symlink():
        raise SystemExit(f"refusing symlink in extraction ancestry: {path}")
    if path.exists() and not path.is_dir():
        raise SystemExit(f"refusing non-directory in extraction ancestry: {path}")
PY
}

for bundle in "${bundles[@]}"; do
  archive="${bundle}-${version}.tar.gz"
  checksum="${archive}.sha256"
  archive_url="$(asset_url "$archive")" || die "release $tag is missing $archive"
  checksum_url="$(asset_url "$checksum")" || die "release $tag is missing $checksum"
  [[ "$archive_url" == https://* && "$checksum_url" == https://* ]] || die 'release asset URL must use HTTPS'
  validate_regular_destination "$download_dir/$archive" || die "unsafe archive destination: $archive"
  validate_regular_destination "$download_dir/$checksum" || die "unsafe checksum destination: $checksum"
  printf 'Verified install plan: %s\n' "$archive"
  if [ "$dry_run" = true ]; then
    printf '  archive: %s\n  checksum: %s\n' "$archive_url" "$checksum_url"
    continue
  fi

  curl --fail --silent --show-error --location "$archive_url" -o "$download_dir/$archive"
  curl --fail --silent --show-error --location "$checksum_url" -o "$download_dir/$checksum"
  (
    cd "$download_dir"
    sha256sum -c "$checksum"
  )
  validate_bundle_archive "$download_dir/$archive"
  # Keep extracted files isolated by release. A retained download directory can
  # contain multiple releases, and extracting over a prior directory would
  # leave files that no longer exist in the current archive.
  extract_dir="$download_dir/extracted/$bundle/$version"
  # Only remove this exact release's staging directory. Archives and extracted
  # files for other releases remain available in a retained download dir.
  validate_extraction_ancestry "$extract_dir" || die "unsafe extraction ancestry for $extract_dir"
  rm -rf -- "$extract_dir"
  mkdir -p "$extract_dir"
  tar -xzf "$download_dir/$archive" -C "$extract_dir"
  [ -x "$extract_dir/install.sh" ] || die "$archive does not contain an executable install.sh"
done

if [ "$dry_run" = false ]; then
  for bundle in "${bundles[@]}"; do
    extract_dir="$download_dir/extracted/$bundle/$version"
    (
      cd "$extract_dir"
      ./install.sh
    )
  done
fi

if [ "$dry_run" = true ]; then
  printf 'DRY-RUN: no release assets were downloaded or installed.\n'
else
  printf 'Installed verified Rhythm Support Beta %s launcher bundles.\n' "$version"
fi
