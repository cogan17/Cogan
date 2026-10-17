# Shared companion ABI 1; kept byte-identical in both independently installable modules.
# Never infer an original kernel identity from uname alone.
CB_SYS=${CB_SYS:-${CP_SYS:-${CT_SYS:-/sys}}}
CB_PROC=${CB_PROC:-${CP_PROC:-${CT_PROC:-/proc}}}
CB_ROOT=$CB_SYS/kernel/cogan

json_string() {
  printf '%s' "$1" | awk 'BEGIN { printf "\"" } {
    if (NR > 1) printf "\\n";
    gsub(/\\/, "\\\\"); gsub(/\"/, "\\\""); gsub(/\t/, "\\t"); gsub(/\r/, "\\r");
    printf "%s", $0
  } END { printf "\"" }'
}

uint() {
  case "$1" in ''|*[!0-9]*) return 1 ;; esac
  case "$1" in 0|[1-9]*) ;; *) return 1 ;; esac
  [ "${#1}" -le 10 ]
}

bridge_available() { [ "$(cat "$CB_ROOT/abi" 2>/dev/null)" = 1 ] && [ -s "$CB_ROOT/release" ]; }

kernel_release() {
  if bridge_available; then cat "$CB_ROOT/release"; return; fi
  candidate=$(cat "$CB_PROC/sys/kernel/osrelease" 2>/dev/null)
  [ -n "$candidate" ] || candidate=$(uname -r)
  printf '%s\n' "$candidate"
}

kernel_json() {
  shown=$(uname -r); candidate=$(kernel_release)
  if bridge_available; then
    source=cogan_bridge; verified=1; original=$(json_string "$candidate")
    banner=$(cat "$CB_ROOT/banner" 2>/dev/null)
    features=$(cat "$CB_ROOT/features" 2>/dev/null)
  else
    source=proc_candidate; verified=0; original=null
    [ -r "$CB_PROC/sys/kernel/osrelease" ] || source=uname_only
    banner=$(cat "$CB_PROC/version" 2>/dev/null); features=""
  fi
  printf '{"bridge":%d,"abi":%d,"verified":%d,"source":"%s","original":%s,"release":' "$verified" "$verified" "$verified" "$source" "$original"
  json_string "$candidate"
  printf ',"uname":'; json_string "$shown"
  printf ',"different":%d,"banner":' "$([ "$candidate" != "$shown" ] && echo 1 || echo 0)"
  json_string "$banner"
  printf ',"features":'; json_string "$features"
  printf ',"limits":'; json_string "$(cat "$CB_ROOT/limits" 2>/dev/null)"
  printf ',"power_client":'; json_string "$(cat "$CB_ROOT/power_client" 2>/dev/null)"
  printf ',"thermal_client":'; json_string "$(cat "$CB_ROOT/thermal_client" 2>/dev/null)"
  printf '}'
}

bridge_heartbeat() { # power|thermal, versionCode (0 unregisters)
  bridge_available || return 0
  case "$1" in power|thermal) ;; *) return 1 ;; esac
  uint "$2" || return 1
  (printf '%s\n' "$2" > "$CB_ROOT/${1}_client") 2>/dev/null
}

module_code() { sed -n 's/^versionCode=//p' "$MODDIR/module.prop"; }

cooling_json() {
  printf '['; cb_sep=""
  for cb_dev in "$CB_SYS"/class/thermal/cooling_device*; do
    cb_cur=$(cat "$cb_dev/cur_state" 2>/dev/null)
    cb_max=$(cat "$cb_dev/max_state" 2>/dev/null)
    uint "$cb_cur" && uint "$cb_max" || continue
    printf '%s{"name":' "$cb_sep"; json_string "$(cat "$cb_dev/type" 2>/dev/null)"
    printf ',"state":%d,"max":%d}' "$cb_cur" "$cb_max"; cb_sep=,
  done
  printf ']'
}

safe_pid() { # PID_FILE SCRIPT_PATH: check the full script path, not a generic name.
  cb_pid=$(cat "$1" 2>/dev/null)
  uint "$cb_pid" && [ "$cb_pid" -gt 1 ] || return 1
  kill -0 "$cb_pid" 2>/dev/null || return 1
  (tr '\0' '\n' < "/proc/$cb_pid/cmdline") 2>/dev/null | grep -Fqx "$2" || return 1
  printf '%s\n' "$cb_pid"
}

peer_json() { # module directory, pid file, script
  cb_installed=0; cb_running=0
  [ -f "$1/module.prop" ] && [ ! -f "$1/disable" ] && [ ! -f "$1/remove" ] && cb_installed=1
  safe_pid "$2" "$1/$3" >/dev/null && cb_running=1
  printf '{"installed":%d,"running":%d,"version":' "$cb_installed" "$cb_running"
  json_string "$(sed -n 's/^version=//p' "$1/module.prop" 2>/dev/null)"
  printf '}'
}

# A PID-owned mkdir lock works with Android sh; no flock dependency or kill -9.
lock_take() { # directory; caller releases explicitly or through its EXIT trap.
  mkdir -p "${1%/*}"
  cb_boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
  cb_try=0
  while ! mkdir "$1" 2>/dev/null; do
    cb_owner=$(cat "$1/pid" 2>/dev/null)
    cb_old_boot=$(cat "$1/boot_id" 2>/dev/null)
    cb_stale=0
    [ -n "$cb_old_boot" ] && [ -n "$cb_boot" ] && [ "$cb_old_boot" != "$cb_boot" ] && cb_stale=1
    if uint "$cb_owner" && [ "$cb_owner" -gt 1 ]; then
      if ! kill -0 "$cb_owner" 2>/dev/null; then cb_stale=1
      elif ! safe_pid "$1/pid" "$MODDIR/report.sh" >/dev/null &&
           ! safe_pid "$1/pid" "$MODDIR/controller.sh" >/dev/null &&
           ! safe_pid "$1/pid" "$MODDIR/sampler.sh" >/dev/null; then cb_stale=1; fi
    elif [ "$cb_try" -ge 10 ]; then
      cb_stale=1
    fi
    if [ "$cb_stale" = 1 ]; then
      rm -f "$1/pid" "$1/boot_id"; rmdir "$1" 2>/dev/null || return 1
      continue
    fi
    [ "$cb_try" -ge 50 ] && return 1
    sleep 0.1; cb_try=$((cb_try + 1))
  done
  printf '%s\n' "$cb_boot" > "$1/boot_id"
  printf '%s\n' "$$" > "$1/pid"
}

lock_drop() {
  [ "$(cat "$1/pid" 2>/dev/null)" = "$$" ] || return 0
  rm -f "$1/pid" "$1/boot_id"; rmdir "$1" 2>/dev/null
}
