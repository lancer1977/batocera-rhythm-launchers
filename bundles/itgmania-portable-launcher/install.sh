#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_ROOT="${INSTALL_ROOT:-/userdata/system}"
SERVICE_NAME="${SERVICE_NAME:-itgmania-portable-launcher}"
BUNDLE_ROOT="${BUNDLE_ROOT:-$INSTALL_ROOT/share/$SERVICE_NAME}"
if [ -z "${USERDATA_ROOT:-}" ]; then
  USERDATA_ROOT="$(dirname "$INSTALL_ROOT")"
fi
PORTS_ROOT="${PORTS_ROOT:-$USERDATA_ROOT/roms/ports}"
PORTS_LAUNCHER_NAME="${PORTS_LAUNCHER_NAME:-ITGMania Portable.sh}"

mkdir -p "$INSTALL_ROOT/services" "$BUNDLE_ROOT/artifacts" "$BUNDLE_ROOT/runtime" "$BUNDLE_ROOT/Songs" "$BUNDLE_ROOT/events" "$PORTS_ROOT"
install -m 0755 "$SOURCE_DIR/service.sh" "$INSTALL_ROOT/services/$SERVICE_NAME"
install -m 0755 "$SOURCE_DIR/ports-launcher.sh" "$PORTS_ROOT/$PORTS_LAUNCHER_NAME"
cp "$SOURCE_DIR/config.example" "$BUNDLE_ROOT/config.env"
cp -R "$SOURCE_DIR/payload" "$BUNDLE_ROOT/"
printf 'Install complete. Stage the qualified archive at %s/artifacts/, verify its SHA-256, then launch %s from Batocera Ports.\n' "$BUNDLE_ROOT" "$PORTS_LAUNCHER_NAME"
