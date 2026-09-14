#!/usr/bin/env bash
set -euo pipefail

# This script is installed as a Batocera Port.  Keep it foregrounded while
# StepMania runs so Batocera performs its normal game input handoff instead of
# leaving EmulationStation to consume controller events alongside StepMania.
SERVICE_NAME="${STEPMANIA_FLATPAK_SERVICE_NAME:-stepmania-flatpak-launcher}"
SERVICE_PATH="${STEPMANIA_FLATPAK_SERVICE:-/userdata/system/services/$SERVICE_NAME}"
EXIT_DELAY="${STEPMANIA_FLATPAK_EXIT_DELAY:-1}"

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
