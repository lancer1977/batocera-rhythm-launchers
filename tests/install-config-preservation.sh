#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

assert_same() {
  if ! cmp -s "$1" "$2"; then
    printf 'expected files to match: %s and %s\n' "$1" "$2" >&2
    exit 1
  fi
}

run_case() {
  local name="$1"
  local installer="$2"
  local bundle_root="$TEST_ROOT/$name/bundle"
  local install_root="$TEST_ROOT/$name/system"
  local config="$bundle_root/config.env"
  local expected="$REPO_ROOT/$installer/config.example"

  INSTALL_ROOT="$install_root" BUNDLE_ROOT="$bundle_root" \
    bash "$REPO_ROOT/$installer/install.sh" >/dev/null
  assert_same "$config" "$expected"

  printf 'operator override for %s\n' "$name" >"$config"
  INSTALL_ROOT="$install_root" BUNDLE_ROOT="$bundle_root" \
    bash "$REPO_ROOT/$installer/install.sh" >/dev/null
  grep -Fxq "operator override for $name" "$config"

  RHYTHM_RESET_CONFIG=1 INSTALL_ROOT="$install_root" BUNDLE_ROOT="$bundle_root" \
    bash "$REPO_ROOT/$installer/install.sh" >/dev/null
  assert_same "$config" "$expected"
}

run_case stepmania bundles/stepmania-flatpak-launcher
run_case itgmania bundles/itgmania-portable-launcher
printf 'config preservation/reset tests passed\n'
