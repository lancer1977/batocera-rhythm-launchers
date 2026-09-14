#!/usr/bin/env bash
set -euo pipefail

# Keep the public release-asset entrypoint small. The transaction lives in a
# Python helper because shell pathname operations cannot retain the directory
# descriptors needed to pin a user-supplied --download-dir.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null 2>&1 || {
  printf 'error: python3 is required\n' >&2
  exit 1
}
exec python3 "$script_dir/rhythm_release_transaction.py" "$@"
