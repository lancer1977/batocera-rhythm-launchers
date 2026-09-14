#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/userdata/system}"
BUNDLE_ROOT="${BUNDLE_ROOT:-$INSTALL_ROOT/share/itgmania-portable-launcher}"
CONFIG_FILE="${CONFIG_FILE:-$BUNDLE_ROOT/config.env}"
test -f "$CONFIG_FILE" && . "$CONFIG_FILE"
SERVICE_NAME="${SERVICE_NAME:-itgmania-portable-launcher}"
ACTION="${1:-}"
USERDATA_ROOT="${USERDATA_ROOT:-$(dirname "$INSTALL_ROOT")}"
PORTS_ROOT="${PORTS_ROOT:-$USERDATA_ROOT/roms/ports}"
PORTS_LAUNCHER_NAME="${PORTS_LAUNCHER_NAME:-ITGMania Portable.sh}"
ITGMANIA_RELEASE_VERSION="${ITGMANIA_RELEASE_VERSION:-1.3.0}"
# Every action that actually touches ITGmania needs a complete config.env.
# uninstall deliberately does not: a bundle that was never fully configured,
# or whose config.env was already deleted, must still be removable.
if [ "$ACTION" = uninstall ]; then
  ITGMANIA_ARTIFACT_PATH="${ITGMANIA_ARTIFACT_PATH:-}"
  ITGMANIA_ARTIFACT_SHA256="${ITGMANIA_ARTIFACT_SHA256:-}"
  ITGMANIA_RUNTIME_ROOT="${ITGMANIA_RUNTIME_ROOT:-$BUNDLE_ROOT/runtime}"
  ITGMANIA_EXECUTABLE="${ITGMANIA_EXECUTABLE:-}"
  ITGMANIA_SONGS_DIR="${ITGMANIA_SONGS_DIR:-$BUNDLE_ROOT/Songs}"
else
  ITGMANIA_ARTIFACT_PATH="${ITGMANIA_ARTIFACT_PATH:?ITGMANIA_ARTIFACT_PATH is required}"
  ITGMANIA_ARTIFACT_SHA256="${ITGMANIA_ARTIFACT_SHA256:?ITGMANIA_ARTIFACT_SHA256 is required}"
  ITGMANIA_RUNTIME_ROOT="${ITGMANIA_RUNTIME_ROOT:?ITGMANIA_RUNTIME_ROOT is required}"
  ITGMANIA_EXECUTABLE="${ITGMANIA_EXECUTABLE:?ITGMANIA_EXECUTABLE is required}"
  ITGMANIA_SONGS_DIR="${ITGMANIA_SONGS_DIR:?ITGMANIA_SONGS_DIR is required}"
fi
ITGMANIA_LOG_DIR="${ITGMANIA_LOG_DIR:-/userdata/system/logs}"
ITGMANIA_PIDFILE="${ITGMANIA_PIDFILE:-/var/run/$SERVICE_NAME.pid}"
SIDECAR_CAPABILITY_PROFILE="${SIDECAR_CAPABILITY_PROFILE:-itgmania-theme-lua}"
if [ "$ACTION" = uninstall ]; then
  SIDECAR_EVENT_DIR="${SIDECAR_EVENT_DIR:-$BUNDLE_ROOT/events}"
else
  SIDECAR_EVENT_DIR="${SIDECAR_EVENT_DIR:?SIDECAR_EVENT_DIR is required}"
fi
DISPLAY="${DISPLAY:-:0}"; XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/var/run}"; XAUTHORITY="${XAUTHORITY:-}"
LOGFILE="$ITGMANIA_LOG_DIR/$SERVICE_NAME.log"

log() { echo "$(date): $*" >> "$LOGFILE"; }
resolve_x_authority() {
  [ -n "$XAUTHORITY" ] && return 0
  local server auth
  server="$(ps -eo args 2>/dev/null | awk '/\/usr\/bin\/X[[:space:]]+:[0-9]+/ { print; exit }')"
  auth="$(printf '%s\n' "$server" | sed -n 's/.*[[:space:]]-auth[[:space:]]\([^[:space:]]*\).*/\1/p')"
  [ -n "$auth" ] && [ -r "$auth" ] && XAUTHORITY="$auth"
  return 0
}
pid_matches() { [ -f "$ITGMANIA_PIDFILE" ] && kill -0 "$(cat "$ITGMANIA_PIDFILE")" 2>/dev/null && ps -p "$(cat "$ITGMANIA_PIDFILE")" -o args= 2>/dev/null | grep -Fq "$ITGMANIA_EXECUTABLE"; }
stop_tree() { local pid="$1" child; while IFS= read -r child; do [ -n "$child" ] && stop_tree "$child"; done < <(pgrep -P "$pid" 2>/dev/null || true); kill "$pid" 2>/dev/null || true; }
verify_artifact() {
  [ "$SIDECAR_CAPABILITY_PROFILE" = itgmania-theme-lua ] || { log 'unsupported Sidecar profile'; return 1; }
  [ -f "$ITGMANIA_ARTIFACT_PATH" ] || { log 'artifact missing'; return 1; }
  printf '%s  %s\n' "$ITGMANIA_ARTIFACT_SHA256" "$ITGMANIA_ARTIFACT_PATH" | sha256sum -c - >/dev/null || { log 'artifact checksum mismatch'; return 1; }
  tar -tzf "$ITGMANIA_ARTIFACT_PATH" | grep -Fx "ITGmania-$ITGMANIA_RELEASE_VERSION-Linux-no-songs/itgmania/itgmania" >/dev/null || { log 'artifact layout mismatch'; return 1; }
}
ensure_runtime() {
  verify_artifact
  if [ ! -x "$ITGMANIA_EXECUTABLE" ]; then
    local stage="$BUNDLE_ROOT/runtime/.extract-$$"
    mkdir -p "$stage"
    tar -xzf "$ITGMANIA_ARTIFACT_PATH" -C "$stage"
    mkdir -p "$(dirname "$ITGMANIA_RUNTIME_ROOT")"
    mv "$stage/ITGmania-$ITGMANIA_RELEASE_VERSION-Linux-no-songs/itgmania" "$ITGMANIA_RUNTIME_ROOT"
    rmdir "$stage" 2>/dev/null || true
  fi
  touch "$ITGMANIA_RUNTIME_ROOT/Portable.ini"
}
configure_song_directory() {
  local preferences stage
  preferences="$ITGMANIA_RUNTIME_ROOT/Save/Preferences.ini"
  mkdir -p "$(dirname "$preferences")"
  stage="$preferences.$$.tmp"
  if [ -f "$preferences" ]; then
    awk -v songs_dir="$ITGMANIA_SONGS_DIR" '
      BEGIN { in_options = 0; saw_options = 0; wrote_song_dir = 0 }
      $0 == "[Options]" {
        in_options = 1
        saw_options = 1
        print
        next
      }
      in_options && /^\[/ {
        if (!wrote_song_dir) {
          print "AdditionalSongFoldersReadOnly=" songs_dir
          wrote_song_dir = 1
        }
        in_options = 0
      }
      in_options && /^AdditionalSongFoldersReadOnly=/ {
        if (!wrote_song_dir) {
          print "AdditionalSongFoldersReadOnly=" songs_dir
          wrote_song_dir = 1
        }
        next
      }
      { print }
      END {
        if (saw_options && in_options && !wrote_song_dir) {
          print "AdditionalSongFoldersReadOnly=" songs_dir
        }
        if (!saw_options) {
          print ""
          print "[Options]"
          print "AdditionalSongFoldersReadOnly=" songs_dir
        }
      }
    ' "$preferences" > "$stage"
  else
    printf '[Options]\nAdditionalSongFoldersReadOnly=%s\n' "$ITGMANIA_SONGS_DIR" > "$stage"
  fi
  mv "$stage" "$preferences"
}
start() {
  mkdir -p "$ITGMANIA_LOG_DIR" "$ITGMANIA_SONGS_DIR" "$SIDECAR_EVENT_DIR"
  pid_matches && return 0
  ensure_runtime
  configure_song_directory
  resolve_x_authority
  export DISPLAY XDG_RUNTIME_DIR ITGMANIA_SONGS_DIR SIDECAR_EVENT_DIR SIDECAR_CAPABILITY_PROFILE
  [ -n "$XAUTHORITY" ] && export XAUTHORITY
  (cd "$ITGMANIA_RUNTIME_ROOT" && exec "$ITGMANIA_EXECUTABLE") >> "$LOGFILE" 2>&1 &
  echo $! > "$ITGMANIA_PIDFILE"
  log "started stock ITGmania $ITGMANIA_RELEASE_VERSION"
}
stop() { pid_matches && stop_tree "$(cat "$ITGMANIA_PIDFILE")"; rm -f "$ITGMANIA_PIDFILE"; }
report_preserved() {
  # Drop the bundle root only when nothing survives, and name whatever does.
  if [ ! -d "$BUNDLE_ROOT" ]; then echo "$SERVICE_NAME uninstalled"; return 0; fi
  local remaining
  remaining="$(find "$BUNDLE_ROOT" -mindepth 1 -maxdepth 1 2>/dev/null | sort)"
  if [ -z "$remaining" ]; then
    rmdir "$BUNDLE_ROOT" 2>/dev/null || true
    echo "$SERVICE_NAME uninstalled"
  else
    echo "$SERVICE_NAME uninstalled; preserved under $BUNDLE_ROOT:"
    printf '%s\n' "$remaining" | sed 's|^|  |'
  fi
}
uninstall() {
  # Can't call pid_matches() unconditionally: ITGMANIA_EXECUTABLE may be
  # unset here (config missing/deleted), and an empty -F pattern would match
  # any process's command line. So only kill when the pidfile's PID is still
  # alive *and* its command line matches the known executable -- a stale
  # pidfile whose PID has been reused by an unrelated process must not be
  # signaled. When the executable is unknown, or the PID doesn't match, just
  # drop the unverifiable pidfile.
  if [ -f "$ITGMANIA_PIDFILE" ]; then
    itgmania_pid="$(cat "$ITGMANIA_PIDFILE" 2>/dev/null || true)"
    if [ -n "$itgmania_pid" ] && [ -n "$ITGMANIA_EXECUTABLE" ] \
      && kill -0 "$itgmania_pid" 2>/dev/null \
      && ps -p "$itgmania_pid" -o args= 2>/dev/null | grep -Fq "$ITGMANIA_EXECUTABLE"; then
      stop_tree "$itgmania_pid" 2>/dev/null || true
    fi
    rm -f "$ITGMANIA_PIDFILE"
  fi
  # Songs/, events/, artifacts/ and the extracted runtime/ are the operator's
  # library, telemetry and staged build. Removing them here would throw away a
  # song collection to uninstall a launcher, so they stay and are reported.
  rm -f "$INSTALL_ROOT/services/$SERVICE_NAME"
  rm -f "$PORTS_ROOT/$PORTS_LAUNCHER_NAME"
  rm -rf "$BUNDLE_ROOT/payload"
  rm -f "$CONFIG_FILE"
  report_preserved
}
case "${1:-}" in start) start;; stop) stop;; uninstall) uninstall;; restart) stop; start;; status) pid_matches && { echo "$SERVICE_NAME is running"; exit 0; }; echo "$SERVICE_NAME is stopped"; exit 1;; *) echo "Usage: $0 {start|stop|restart|status|uninstall}"; exit 2;; esac
