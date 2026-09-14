#!/bin/bash
# Install helper for the StepMania Flatpak launcher publish bundle.

set -u

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_ROOT="${INSTALL_ROOT:-/userdata/system}"
SERVICE_DIR="${SERVICE_DIR:-${INSTALL_ROOT}/services}"
BUNDLE_ROOT="${BUNDLE_ROOT:-${INSTALL_ROOT}/share/stepmania-flatpak-launcher}"
SERVICE_NAME="${SERVICE_NAME:-stepmania-flatpak-launcher}"
STEPMANIA_APPLY_DEFAULT_CONTROLLER_MAP="${STEPMANIA_APPLY_DEFAULT_CONTROLLER_MAP:-}"
USERDATA_ROOT="${USERDATA_ROOT:-}"
if [ -z "$USERDATA_ROOT" ]; then
  USERDATA_ROOT="$(dirname "$INSTALL_ROOT")"
fi
PORTS_ROOT="${PORTS_ROOT:-$USERDATA_ROOT/roms/ports}"
PORTS_LAUNCHER_NAME="${PORTS_LAUNCHER_NAME:-StepMania.sh}"

mkdir -p "$SERVICE_DIR" "$BUNDLE_ROOT" "$BUNDLE_ROOT/Songs" "$PORTS_ROOT"

install -m 0755 "$SOURCE_DIR/service.sh" "$SERVICE_DIR/$SERVICE_NAME"
install -m 0755 "$SOURCE_DIR/ports-launcher.sh" "$PORTS_ROOT/$PORTS_LAUNCHER_NAME"
install -m 0755 "$SOURCE_DIR/apply-controller-map.sh" "$BUNDLE_ROOT/apply-controller-map.sh"
cp "$SOURCE_DIR/config.example" "$BUNDLE_ROOT/config.env"
cp -R "$SOURCE_DIR/payload" "$BUNDLE_ROOT/"

if [ -z "$STEPMANIA_APPLY_DEFAULT_CONTROLLER_MAP" ]; then
  if [ "$INSTALL_ROOT" = "/userdata/system" ]; then
    STEPMANIA_APPLY_DEFAULT_CONTROLLER_MAP=1
  else
    STEPMANIA_APPLY_DEFAULT_CONTROLLER_MAP=0
  fi
fi

if [ "$STEPMANIA_APPLY_DEFAULT_CONTROLLER_MAP" = "1" ]; then
  STEPMANIA_FLATPAK_HOME="${STEPMANIA_FLATPAK_HOME:-/userdata/saves/flatpak/data}" \
  KEYMAPS_PATH="${STEPMANIA_KEYMAPS_PATH:-/userdata/saves/flatpak/data/.var/app/com.stepmania.StepMania/.stepmania-5.1/Save/Keymaps.ini}" \
  BUNDLE_ROOT="$BUNDLE_ROOT" \
  "$BUNDLE_ROOT/apply-controller-map.sh" >/dev/null
fi

cat <<EOF
Installed ${SERVICE_NAME} to:
- ${SERVICE_DIR}/${SERVICE_NAME}
- ${PORTS_ROOT}/${PORTS_LAUNCHER_NAME}
- ${BUNDLE_ROOT}/config.env
- ${BUNDLE_ROOT}/apply-controller-map.sh
- ${BUNDLE_ROOT}/Songs/
- ${BUNDLE_ROOT}/payload/

Smoke next:
1. Confirm flatpak list --app includes com.stepmania.StepMania.
2. Confirm ${BUNDLE_ROOT}/stepmania-controller-map.json if default mapping was applied.
3. Edit ${BUNDLE_ROOT}/config.env if the display/session differs.
4. Launch "StepMania" from Batocera Ports. Do not start the service directly for
   gameplay: the Ports wrapper gives the game controller focus and returns
   cleanly to EmulationStation, matching the ITGmania Ports launcher pattern.
   Direct service start remains available for diagnostics only.
5. Confirm StepMania opens, sees the controller, and sees a known-good song pack.
EOF
