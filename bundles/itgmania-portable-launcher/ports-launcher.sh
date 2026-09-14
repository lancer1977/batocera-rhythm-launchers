#!/usr/bin/env bash
set -euo pipefail

# This script is installed as a Batocera Port.  Keep it foregrounded while
# ITGmania runs so Batocera performs its normal game input handoff instead of
# leaving EmulationStation to consume controller events alongside ITGmania.
SERVICE_NAME="${ITGMANIA_PORTABLE_SERVICE_NAME:-itgmania-portable-launcher}"
SERVICE_PATH="${ITGMANIA_PORTABLE_SERVICE:-/userdata/system/services/$SERVICE_NAME}"
EXIT_DELAY="${ITGMANIA_PORTABLE_EXIT_DELAY:-1}"

stop_service() {
  "$SERVICE_PATH" stop >/dev/null 2>&1 || true
}

cleanup() {
  stop_service
  # Do not let the release/repeat event used to leave the Port trigger the
  # currently selected EmulationStation entry.
  sleep "$EXIT_DELAY"
}

trap cleanup EXIT INT TERM

"$SERVICE_PATH" start
while "$SERVICE_PATH" status >/dev/null 2>&1; do
  sleep 1
done
