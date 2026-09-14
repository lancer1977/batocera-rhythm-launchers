#!/bin/bash
# Batocera service for launching StepMania through Flatpak.

set -u

INSTALL_ROOT="${INSTALL_ROOT:-/userdata/system}"
BUNDLE_ROOT="${BUNDLE_ROOT:-${INSTALL_ROOT}/share/stepmania-flatpak-launcher}"
CONFIG_FILE="${CONFIG_FILE:-${BUNDLE_ROOT}/config.env}"
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  . "$CONFIG_FILE"
fi

SERVICE_NAME="${SERVICE_NAME:-stepmania-flatpak-launcher}"
# Mirrors install.sh so uninstall can remove the Ports entry it created.
USERDATA_ROOT="${USERDATA_ROOT:-$(dirname "$INSTALL_ROOT")}"
PORTS_ROOT="${PORTS_ROOT:-${USERDATA_ROOT}/roms/ports}"
PORTS_LAUNCHER_NAME="${PORTS_LAUNCHER_NAME:-StepMania.sh}"
FLATPAK_APP_ID="${FLATPAK_APP_ID:-com.stepmania.StepMania}"
STEPMANIA_DATA_ROOT="${STEPMANIA_DATA_ROOT:-${BUNDLE_ROOT}}"
STEPMANIA_SONGS_DIR="${STEPMANIA_SONGS_DIR:-${STEPMANIA_DATA_ROOT}/Songs}"
STEPMANIA_EXTRA_ARGS="${STEPMANIA_EXTRA_ARGS:-}"
STEPMANIA_PIPELINE_INITIAL_SCREEN="${STEPMANIA_PIPELINE_INITIAL_SCREEN:-ScreenPolyhydraPipeline}"
STEPMANIA_PIPELINE_SCREEN_CLASS="${STEPMANIA_PIPELINE_SCREEN_CLASS:-ScreenWithMenuElements}"
STEPMANIA_PIPELINE_SCREEN_FALLBACK="${STEPMANIA_PIPELINE_SCREEN_FALLBACK:-ScreenWithMenuElementsBlank}"
STEPMANIA_PIPELINE_SCREEN="${STEPMANIA_PIPELINE_SCREEN:-}"
STEPMANIA_PIPELINE_SONG="${STEPMANIA_PIPELINE_SONG:-}"
STEPMANIA_PIPELINE_SONG_DIR="${STEPMANIA_PIPELINE_SONG_DIR:-}"
STEPMANIA_PIPELINE_DIFFICULTY="${STEPMANIA_PIPELINE_DIFFICULTY:-}"
STEPMANIA_PIPELINE_AUTOPLAY="${STEPMANIA_PIPELINE_AUTOPLAY:-}"
STEPMANIA_PIPELINE_EMIT_SONG_CATALOG="${STEPMANIA_PIPELINE_EMIT_SONG_CATALOG:-}"
STEPMANIA_PIPELINE_CATALOG_LIMIT="${STEPMANIA_PIPELINE_CATALOG_LIMIT:-}"
STEPMANIA_PIPELINE_EVENT_DIR="${STEPMANIA_PIPELINE_EVENT_DIR:-}"
LOGDIR="${LOGDIR:-/userdata/system/logs}"
LOGFILE="${LOGFILE:-${LOGDIR}/${SERVICE_NAME}.log}"
PIDFILE="${PIDFILE:-/var/run/${SERVICE_NAME}.pid}"
DISPLAY="${DISPLAY:-:0}"
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/0}"
XAUTHORITY="${XAUTHORITY:-}"

mkdir -p "$LOGDIR" "$STEPMANIA_SONGS_DIR"

log() {
  echo "$(date): $*" >> "$LOGFILE"
}

is_truthy() {
  case "${1,,}" in
    1|true|yes|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_x_authority() {
  if [ -n "$XAUTHORITY" ]; then
    return 0
  fi

  # Batocera's startx command supplies a per-boot cookie with `-auth`.  Discover
  # that path instead of hard-coding its PID-derived name.  Operators can still
  # set XAUTHORITY explicitly for non-standard display sessions.
  local x_server auth_path
  x_server="$(ps -eo args 2>/dev/null | awk '/\/usr\/bin\/X[[:space:]]+:[0-9]+/ { print; exit }')"
  auth_path="$(printf '%s\n' "$x_server" | sed -n 's/.*[[:space:]]-auth[[:space:]]\([^[:space:]]*\).*/\1/p')"
  if [ -n "$auth_path" ] && [ -r "$auth_path" ]; then
    XAUTHORITY="$auth_path"
  fi
}

is_running() {
  if command -v flatpak >/dev/null 2>&1 && flatpak ps --columns=application 2>/dev/null | grep -Fxq "$FLATPAK_APP_ID"; then
    return 0
  fi

  pid_matches_launcher
}

pid_matches_launcher() {
  if [ ! -f "$PIDFILE" ]; then
    return 1
  fi

  local pid command
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -z "$pid" ] || ! kill -0 "$pid" >/dev/null 2>&1; then
    return 1
  fi

  command="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  [[ "$command" == *"flatpak run ${FLATPAK_APP_ID}"* || "$command" == *"flatpak-bwrap"*"-- stepmania"* ]]
}

stop_process_tree() {
  local pid="$1" child
  while IFS= read -r child; do
    [ -n "$child" ] && stop_process_tree "$child"
  done < <(pgrep -P "$pid" 2>/dev/null || true)
  kill "$pid" >/dev/null 2>&1 || true
}

start_service() {
  local -i should_use_pipeline=0
  log "start requested for ${SERVICE_NAME}"

  if is_running; then
    log "StepMania Flatpak launcher is already running"
    return 0
  fi

  if ! command -v flatpak >/dev/null 2>&1; then
    log "flatpak command is not available"
    return 1
  fi

  if ! flatpak info "$FLATPAK_APP_ID" >/dev/null 2>&1; then
    log "Flatpak app is not installed: ${FLATPAK_APP_ID}"
    return 1
  fi

  export DISPLAY
  export XDG_RUNTIME_DIR
  resolve_x_authority
  if [ -n "$XAUTHORITY" ]; then
    export XAUTHORITY
  fi
  export STEPMANIA_DATA_ROOT
  export STEPMANIA_SONGS_DIR
  export STEPMANIA_PIPELINE_SCREEN
  export STEPMANIA_PIPELINE_SONG_DIR
  export STEPMANIA_PIPELINE_DIFFICULTY
  export STEPMANIA_PIPELINE_SONG
  export STEPMANIA_PIPELINE_AUTOPLAY
  export STEPMANIA_PIPELINE_INITIAL_SCREEN
  export STEPMANIA_PIPELINE_SCREEN_CLASS
  export STEPMANIA_PIPELINE_SCREEN_FALLBACK
  export STEPMANIA_PIPELINE_EVENT_DIR
  export STEPMANIA_PIPELINE_EMIT_SONG_CATALOG
  export STEPMANIA_PIPELINE_CATALOG_LIMIT

  local -a pipeline_args=()
  if [ -n "${STEPMANIA_PIPELINE_SCREEN}" ] || [ -n "${STEPMANIA_PIPELINE_SONG}" ] || [ -n "${STEPMANIA_PIPELINE_SONG_DIR}" ] || [ -n "${STEPMANIA_PIPELINE_DIFFICULTY}" ] || [ -n "${STEPMANIA_PIPELINE_EVENT_DIR}" ] || is_truthy "$STEPMANIA_PIPELINE_AUTOPLAY" || is_truthy "$STEPMANIA_PIPELINE_EMIT_SONG_CATALOG" || [ -n "${STEPMANIA_PIPELINE_CATALOG_LIMIT}" ]; then
    should_use_pipeline=1
  fi

  if [ "$should_use_pipeline" -eq 1 ]; then
    pipeline_args+=("--metric=Common::InitialScreen=\"${STEPMANIA_PIPELINE_INITIAL_SCREEN}\"")
    pipeline_args+=("--metric=ScreenPolyhydraPipeline::Class=\"${STEPMANIA_PIPELINE_SCREEN_CLASS}\"")
    pipeline_args+=("--metric=ScreenPolyhydraPipeline::Fallback=\"${STEPMANIA_PIPELINE_SCREEN_FALLBACK}\"")

    if [ -n "${STEPMANIA_PIPELINE_SONG}" ]; then
      pipeline_args+=("--pipeline-song=${STEPMANIA_PIPELINE_SONG}")
    fi
    if [ -n "${STEPMANIA_PIPELINE_SONG_DIR}" ]; then
      pipeline_args+=("--pipeline-song-dir=${STEPMANIA_PIPELINE_SONG_DIR}")
    fi
    if [ -n "${STEPMANIA_PIPELINE_SCREEN}" ]; then
      pipeline_args+=("--pipeline-screen=${STEPMANIA_PIPELINE_SCREEN}")
    fi
    if [ -n "${STEPMANIA_PIPELINE_DIFFICULTY}" ]; then
      pipeline_args+=("--pipeline-difficulty=${STEPMANIA_PIPELINE_DIFFICULTY}")
    fi
    if is_truthy "$STEPMANIA_PIPELINE_AUTOPLAY"; then
      pipeline_args+=(--pipeline-autoplay)
    fi
    if [ -n "${STEPMANIA_PIPELINE_EVENT_DIR}" ]; then
      pipeline_args+=("--pipeline-event-dir=${STEPMANIA_PIPELINE_EVENT_DIR}")
    fi
  fi

  # shellcheck disable=SC2086
  flatpak run "$FLATPAK_APP_ID" $STEPMANIA_EXTRA_ARGS "${pipeline_args[@]}" >> "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  log "started ${FLATPAK_APP_ID} with pid $(cat "$PIDFILE")"
}

stop_service() {
  log "stop requested for ${SERVICE_NAME}"

  if command -v flatpak >/dev/null 2>&1; then
    flatpak kill "$FLATPAK_APP_ID" >/dev/null 2>&1 || true
  fi

  if pid_matches_launcher; then
    stop_process_tree "$(cat "$PIDFILE")"
  fi

  if [ -f "$PIDFILE" ]; then
    rm -f "$PIDFILE"
  fi
}

status_service() {
  if is_running; then
    echo "${SERVICE_NAME} is running"
    return 0
  fi

  echo "${SERVICE_NAME} is stopped"
  return 1
}

report_preserved() {
  # Drop the bundle root only when nothing survives, and name whatever does.
  if [ ! -d "$BUNDLE_ROOT" ]; then
    echo "${SERVICE_NAME} uninstalled"
    return 0
  fi

  remaining="$(find "$BUNDLE_ROOT" -mindepth 1 -maxdepth 1 2>/dev/null | sort)"
  if [ -z "$remaining" ]; then
    rmdir "$BUNDLE_ROOT" 2>/dev/null || true
    echo "${SERVICE_NAME} uninstalled"
  else
    echo "${SERVICE_NAME} uninstalled; preserved under ${BUNDLE_ROOT}:"
    printf '%s\n' "$remaining" | sed 's|^|  |'
  fi
}

restore_controller_map() {
  # install.sh may have run apply-controller-map.sh, which overwrote the
  # Flatpak's Keymaps.ini with our default map and recorded what it did in
  # stepmania-controller-map.json (the prior file's backup path, or an empty
  # backup_path if no prior file existed). Undoing install.sh means undoing
  # that too: restore the backup if there was a prior file, or remove the
  # bundle-generated map entirely if there wasn't. No report (map was never
  # applied, e.g. a test install under a temp root) is a no-op.
  local report="${BUNDLE_ROOT}/stepmania-controller-map.json"
  [ -f "$report" ] || return 0
  local status keymaps_path backup_path generated_sha256 current_sha256
  status="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('status',''))" "$report" 2>/dev/null || true)"
  keymaps_path="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('keymaps_path',''))" "$report" 2>/dev/null || true)"
  backup_path="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('backup_path',''))" "$report" 2>/dev/null || true)"
  generated_sha256="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('generated_sha256',''))" "$report" 2>/dev/null || true)"
  if [ "$status" = "applied" ] && [ -n "$keymaps_path" ]; then
    # Only undo the exact map this bundle wrote.  The map lives in the
    # operator's Flatpak data, so a later edit is theirs and must win over a
    # pre-install backup or our no-prior-file cleanup.
    current_sha256="$(sha256sum "$keymaps_path" 2>/dev/null | awk '{print $1}')"
    if [ -n "$generated_sha256" ] && [ "$current_sha256" = "$generated_sha256" ]; then
      if [ -n "$backup_path" ] && [ -f "$backup_path" ]; then
        mv "$backup_path" "$keymaps_path"
        rmdir "$(dirname "$backup_path")" 2>/dev/null || true
      elif [ -z "$backup_path" ]; then
        rm -f "$keymaps_path"
      fi
    else
      echo "${SERVICE_NAME} uninstall preserved a controller map modified after installation: ${keymaps_path}"
    fi
  fi
  # A retained backup belongs solely to the bundle's map application.  It is
  # no longer needed once the current operator map has been left untouched.
  [ -n "$backup_path" ] && rm -f "$backup_path"
  [ -n "$backup_path" ] && rmdir "$(dirname "$backup_path")" 2>/dev/null || true
  rm -f "$report"
}

uninstall_service() {
  stop_service
  # Songs/ is the operator's library; uninstalling a launcher must not delete a
  # song collection, so it stays and is reported. The Flatpak app is not ours
  # to remove either — this bundle only ever installed a launcher for it.
  restore_controller_map
  rm -f "${SERVICE_DIR:-${INSTALL_ROOT}/services}/${SERVICE_NAME}"
  rm -f "${PORTS_ROOT}/${PORTS_LAUNCHER_NAME}"
  rm -f "${BUNDLE_ROOT}/apply-controller-map.sh"
  rm -rf "${BUNDLE_ROOT}/payload"
  rm -f "$CONFIG_FILE"
  report_preserved
}

case "${1:-}" in
  start)
    start_service
    ;;
  stop)
    stop_service
    ;;
  restart|reload)
    stop_service
    start_service
    ;;
  status)
    status_service
    ;;
  uninstall)
    uninstall_service
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|reload|status|uninstall}"
    exit 1
    ;;
esac

exit 0
