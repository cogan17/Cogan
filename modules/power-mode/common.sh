# Cogan Power Mode: shared paths, settings and the few system knobs it touches.
# POSIX sh (Android mksh, KernelSU busybox sh). It only writes CPU frequency limits, the top-app
# uclamp boost and the charging switch, and puts all of them back when it stops.
# The CP_* / CT_* paths can be overridden, which the offline tests use with a fake /sys.

MODDIR=${MODDIR:-${0%/*}}
CP_DATA=${CP_DATA:-/data/adb/cogan_power}
CP_SYS=${CP_SYS:-/sys}
CP_PROC=${CP_PROC:-/proc}
CP_CPUCTL=${CP_CPUCTL:-/dev/cpuctl}
CT_DATA=${CT_DATA:-/data/adb/cogan_thermal}           # Cogan Thermal Monitor's data
CT_MOD=${CT_MOD:-/data/adb/modules/cogan_thermal}     # and its module folder
CP_RUN=$CP_DATA/run
CONFIG=$CP_DATA/config
EVENTS=$CP_DATA/events.tsv
BATTERY=$CP_SYS/class/power_supply/battery

# Settings (the WebUI writes $CONFIG; only these keys and values within range are accepted).
KEYS="MODE TARGET_TEMP GAME_LIMIT SAVER_CAP GAME_BOOST CHARGE_CTRL CHARGE_STOP CHARGE_RESUME BATT_TEMP_STOP HEAT_PAUSE_CHARGE INTERVAL FORCE AUTOSTART"
MODE=seimbang          # hemat | seimbang | game
TARGET_TEMP=42         # Seimbang keeps the processor at or below this (°C); Hemat 3 °C lower
GAME_LIMIT=48          # Game only steps in at this temperature (°C)
SAVER_CAP=60           # Hemat: top speed of the big cores (% of their maximum)
GAME_BOOST=1           # Game: give the app on screen a minimum CPU share (uclamp)
CHARGE_CTRL=1          # auto cut charging on/off
CHARGE_STOP=95         # owner default, retained settings are not silently changed
CHARGE_RESUME=90
BATT_TEMP_STOP=42      # pause charging while the battery is this hot (°C), resume 3 °C lower
HEAT_PAUSE_CHARGE=1    # Seimbang: pause charging when charging is what heats the phone
INTERVAL=10            # seconds between checks
FORCE=0               # 1 = reapply supported controls on every check
AUTOSTART=1
. "$MODDIR/bridge.sh"

defaults() {
  MODE=seimbang; TARGET_TEMP=42; GAME_LIMIT=48; SAVER_CAP=60; GAME_BOOST=1
  CHARGE_CTRL=1; CHARGE_STOP=95; CHARGE_RESUME=90; BATT_TEMP_STOP=42
  HEAT_PAUSE_CHARGE=1; INTERVAL=10; FORCE=0; AUTOSTART=1
}

limits() {   # limits KEY -> "min max" of a numeric setting
  case "$1" in
    TARGET_TEMP) echo "35 55" ;;
    GAME_LIMIT) echo "40 60" ;;
    SAVER_CAP) echo "30 90" ;;
    GAME_BOOST|CHARGE_CTRL|HEAT_PAUSE_CHARGE|FORCE|AUTOSTART) echo "0 1" ;;
    CHARGE_STOP) echo "50 100" ;;
    CHARGE_RESUME) echo "40 99" ;;
    BATT_TEMP_STOP) echo "35 50" ;;
    INTERVAL) echo "5 60" ;;
    *) return 1 ;;
  esac
}

valid() {   # valid KEY VALUE
  if [ "$1" = MODE ]; then
    case "$2" in hemat|seimbang|game) return 0 ;; *) return 1 ;; esac
  fi
  uint "$2" || return 1
  case "$2" in 0|[1-9]*) ;; *) return 1 ;; esac
  set -- "$2" $(limits "$1")
  [ $# = 3 ] && [ "$1" -ge "$2" ] && [ "$1" -le "$3" ]
}

load_config() {
  defaults
  [ -f "$CONFIG" ] || return 0
  while IFS='=' read -r key value; do
    valid "$key" "$value" && eval "$key=\$value"   # key is one of the settings above
  done < "$CONFIG"
  [ "$CHARGE_RESUME" -lt "$CHARGE_STOP" ] || CHARGE_RESUME=$((CHARGE_STOP - 5))
}

write_config() {
  mkdir -p "$CP_DATA" || return 1
  [ ! -d "$CONFIG" ] && [ ! -L "$CONFIG" ] || return 1
  for key in $KEYS; do eval "echo \"$key=\$$key\""; done > "$CONFIG.tmp.$$" && mv "$CONFIG.tmp.$$" "$CONFIG" || return 1
  chmod 600 "$CONFIG"
}

event() {   # one line in the WebUI's activity log
  mkdir -p "$CP_DATA"
  printf '%s\t%s\n' "$(date +%s)" "$*" >> "$EVENTS"
}

deg() { echo "$(($1 / 10)).$(( ($1 < 0 ? -$1 : $1) % 10 ))"; }

# Hottest CPU/GPU sensor in tenths of °C.
read_main_temp() {
  for zone in "$CP_SYS"/class/thermal/thermal_zone*; do
    [ -r "$zone/temp" ] || continue
    echo "$(cat "$zone/type" 2>/dev/null) $(cat "$zone/temp" 2>/dev/null)"
  done | awk -f "$MODDIR/power.awk"
}

# Battery: "level status temp_tenths current_mA"; status is charging, full, discharging or idle.
read_battery() {
  level=$(cat "$BATTERY/capacity" 2>/dev/null)
  status=$(cat "$BATTERY/status" 2>/dev/null)
  temp=$(cat "$BATTERY/temp" 2>/dev/null)
  current=$(cat "$BATTERY/current_now" 2>/dev/null)
  design=$(cat "$BATTERY/charge_full_design" 2>/dev/null)
  case "$level" in ''|*[!0-9]*) level=-1 ;; esac
  case "$temp" in ''|*[!0-9-]*) temp=-999 ;; esac
  case "$current" in ''|*[!0-9-]*) current=0 ;; esac
  case "$design" in ''|*[!0-9]*) design=0 ;; esac
  current=${current#-}
  if [ "$current" -ge 20000 ] || [ "$design" -ge 100000 ]; then current=$((current / 1000)); fi   # microamps
  case "$status" in Charging) status=charging ;; Full) status=full ;; Discharging) status=discharging ;; *) status=idle ;; esac
  echo "$level $status $temp $current"
}

monitor_installed() { [ -f "$CT_MOD/module.prop" ] && [ ! -f "$CT_MOD/disable" ]; }

# Latest report of Cogan Thermal Monitor (see its sampler.sh) when it is at most 90 s old:
# sets M_MAIN, M_APP and M_CAUSE.
read_monitor() {
  M_MAIN=""; M_APP=""; M_CAUSE=""
  [ -f "$CT_MOD/disable" ] || [ -f "$CT_MOD/remove" ] && return 1
  IFS='	' read -r m_ts m_main _ _ m_app m_cause < "$CT_DATA/run/latest" 2>/dev/null || return 1
  case "$m_ts" in ''|*[!0-9]*) return 1 ;; esac
  m_age=$(($(date +%s) - m_ts))
  [ "$m_age" -ge 0 ] && [ "$m_age" -le 90 ] || return 1
  M_MAIN=$m_main; M_APP=$m_app; M_CAUSE=$m_cause
}

# Tell Cogan Thermal Monitor which mode is active from now on; its summaries report per mode.
log_mode() {
  [ -d "$CT_DATA" ] || return 0
  last=$(tail -n 1 "$CT_DATA/modes.tsv" 2>/dev/null | cut -f 2)
  [ "$last" = "$1" ] || printf '%s\t%s\n' "$(date +%s)" "$1" >> "$CT_DATA/modes.tsv"
}

# Charging switches known from many phones, as "node|on|off" (proc/... is under /proc, the rest
# under /sys). The first one that really stops and restarts charging is kept in $CP_DATA/switch.
SWITCHES="class/power_supply/battery/input_suspend|0|1
class/power_supply/battery/charging_enabled|1|0
class/power_supply/battery/battery_charging_enabled|1|0
class/power_supply/battery/charge_disable|0|1
class/qcom-battery/input_suspend|0|1
class/power_supply/usb/input_suspend|0|1
class/power_supply/main/input_suspend|0|1
class/power_supply/battery/batt_slate_mode|0|1
class/power_supply/battery/op_disable_charge|0|1
class/power_supply/battery/mmi_charging_enable|1|0"

switch_node() {
  case "$1" in proc/*) echo "$CP_PROC/${1#proc/}" ;; *) echo "$CP_SYS/$1" ;; esac
}

is_charging() { [ "$(cat "$BATTERY/status" 2>/dev/null)" = Charging ]; }

wait_charging() {   # wait_charging yes|no SECONDS
  i=0
  while :; do
    [ "${stop:-0}" = 1 ] && return 1
    cp_charge_status=$(cat "$BATTERY/status" 2>/dev/null)
    case "$cp_charge_status:$1" in Charging:yes|Not\ charging:no|Discharging:no) return 0 ;; esac
    [ "$i" -ge "$2" ] && return 1
    sleep 1
    i=$((i + 1))
  done
}

# Try each switch while the phone charges; print one "node result" line per switch tried.
detect_switch() {
  is_charging || return 2
  found=1
  while IFS='|' read -r rel on off; do
    node=$(switch_node "$rel")
    [ -f "$node" ] || continue
    [ "${stop:-0}" = 1 ] && break
    cp_probe_before=$(cat "$node" 2>/dev/null)
    if [ "$cp_probe_before" != "$on" ]; then echo "$rel sudah_dikontrol"; continue; fi
    printf '%s|%s|%s\n' "$rel" "$on" "$off" > "$CP_RUN/probe"
    if ! (echo "$off" > "$node") 2>/dev/null; then echo "$rel tidak_bisa_ditulis"; restore_probe; continue; fi
    if wait_charging no 6; then
      restore_probe || return 1
      if wait_charging yes 15; then
        echo "$rel|$on|$off" > "$CP_DATA/switch"
        echo "$rel ok"
        found=0
        break
      fi
      echo "$rel tidak_lanjut"
    else
      echo "$rel tidak_berpengaruh"
    fi
    restore_probe || return 1
    wait_charging yes 10
  done <<EOF
$SWITCHES
EOF
  return $found
}

# Only restore controls this module actually owns. Other controllers retain their limits.
restore() {
  restore_failed=0
  if bridge_available; then (echo '0 0 0' > "$CB_ROOT/limits") 2>/dev/null || restore_failed=1; fi
  restore_probe || restore_failed=1
  restore_cpu || restore_failed=1
  set_boost 0 || restore_failed=1
  restore_charge || restore_failed=1
  bridge_heartbeat power 0
  rm -f "$CP_RUN/charge_off" "$CP_RUN/level" "$CP_RUN/cool" "$CP_RUN/prev" "$CP_RUN/state.json" "$CP_RUN/apply.tsv" "$CP_RUN/apply.tsv.tmp" "$CP_RUN/backend"
  if [ "$restore_failed" = 1 ]; then
    : > "$CP_RUN/restore_pending"; event 'Ada kontrol yang belum pulih; periksa izin node lalu Henti lagi'; return 1
  fi
  rm -f "$CP_RUN/restore_pending"
}

# Discard snapshots from a previous boot; never replay stale sysfs values after reboot.
boot_session() {
  mkdir -p "$CP_RUN"
  cp_boot=$(cat "$CP_PROC/sys/kernel/random/boot_id" 2>/dev/null)
  [ -n "$cp_boot" ] || cp_boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
  if [ "$(cat "$CP_RUN/boot_id" 2>/dev/null)" != "$cp_boot" ]; then
    rm -rf "$CP_RUN/original" "$CP_RUN/written"
    rm -f "$CP_RUN/charge.owned" "$CP_RUN/uclamp.orig" "$CP_RUN/uclamp.written" "$CP_RUN/charge_off" "$CP_RUN/state.json" "$CP_RUN/probe" "$CP_RUN/restore_pending"
    printf '%s\n' "$cp_boot" > "$CP_RUN/boot_id"
  fi
}

record_control() { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" >> "$CP_RUN/apply.tsv.tmp"; }

controls_json() {
  [ -f "$CP_RUN/apply.tsv" ] || { printf '[]'; return; }
  awk -F '\t' 'BEGIN { printf "[" } NF == 4 {
    # Escape the regex delimiter even inside a character class (Android/BusyBox awk).
    for (i=1;i<=4;i++) gsub(/[^A-Za-z0-9_.:\/ -]/,"_",$i)
    printf "%s{\"node\":\"%s\",\"requested\":\"%s\",\"actual\":\"%s\",\"result\":\"%s\"}", n++ ? "," : "",$1,$2,$3,$4
  } END { printf "]" }' "$CP_RUN/apply.tsv" 2>/dev/null
}

restore_cpu() {
  cp_restore_failed=0
  for cp_orig in "$CP_RUN"/original/policy*; do
    [ -f "$cp_orig" ] || continue
    cp_name=${cp_orig##*/}; cp_node=$CP_SYS/devices/system/cpu/cpufreq/$cp_name/scaling_max_freq
    cp_old=$(cat "$cp_orig"); cp_last=$(cat "$CP_RUN/written/$cp_name" 2>/dev/null)
    cp_now=$(cat "$cp_node" 2>/dev/null)
    if [ "$cp_now" = "$cp_last" ] && uint "$cp_old"; then
      if ! (echo "$cp_old" > "$cp_node") 2>/dev/null; then
        event "Pemulihan CPU gagal: $cp_name"; cp_restore_failed=1; continue
      fi
      [ "$(cat "$cp_node" 2>/dev/null)" = "$cp_old" ] || { cp_restore_failed=1; continue; }
    fi
    rm -f "$cp_orig" "$CP_RUN/written/$cp_name"
  done
  [ "$cp_restore_failed" = 0 ]
}

# Override the original unverified sysfs writer. The bridge owns an independent
# CPU QoS request; fallback snapshots and readback are needed on older kernels.
set_cpu_cap() {
  cp_big=$1; cp_little=$2
  if bridge_available; then
    # Restore our old sysfs request before adding QoS, otherwise the aggregate
    # QoS cap can hide that request and prevent its correct restoration later.
    restore_cpu || { record_control cpu restore unknown write_failed; return 1; }
    cp_expected=0
    for cp_dir in "$CP_SYS"/devices/system/cpu/cpufreq/policy*; do
      [ -r "$cp_dir/cpuinfo_max_freq" ] && cp_expected=$((cp_expected + 1))
    done
    cp_ttl=$((INTERVAL * 3)); [ "$cp_ttl" -lt 30 ] && cp_ttl=30
    if (echo "$cp_big $cp_little $cp_ttl" > "$CB_ROOT/limits") 2>/dev/null; then
      read -r cp_rb cp_rl cp_rt cp_rn cp_re < "$CB_ROOT/limits"
      if [ "$cp_rb" = "$cp_big" ] && [ "$cp_rl" = "$cp_little" ] && uint "$cp_rt" && [ "$cp_rt" -gt 0 ] &&
          uint "$cp_rn" && [ "$cp_rn" -gt 0 ] && [ "$cp_rn" -ge "$cp_expected" ] && [ "$cp_re" = 0 ]; then
        record_control kernel/cogan/limits "$cp_big/$cp_little" "$cp_rb/$cp_rl" applied
        echo kernel_qos > "$CP_RUN/backend"
        return 0
      fi
    fi
    record_control kernel/cogan/limits "$cp_big/$cp_little" unknown write_failed
    (echo '0 0 0' > "$CB_ROOT/limits") 2>/dev/null
  fi
  echo sysfs > "$CP_RUN/backend"
  mkdir -p "$CP_RUN/original" "$CP_RUN/written"
  cp_lowest=$(cat "$CP_SYS"/devices/system/cpu/cpufreq/policy*/cpuinfo_max_freq 2>/dev/null | sort -n | head -n 1)
  cp_highest=$(cat "$CP_SYS"/devices/system/cpu/cpufreq/policy*/cpuinfo_max_freq 2>/dev/null | sort -n | tail -n 1)
  cp_count=0
  for cp_policy in "$CP_SYS"/devices/system/cpu/cpufreq/policy*; do
    cp_max=$(cat "$cp_policy/cpuinfo_max_freq" 2>/dev/null)
    cp_min=$(cat "$cp_policy/cpuinfo_min_freq" 2>/dev/null)
    uint "$cp_max" && uint "$cp_min" || continue
    cp_count=$((cp_count + 1)); cp_pct=$cp_big; cp_name=${cp_policy##*/}
    [ "$cp_max" = "$cp_lowest" ] && [ "$cp_lowest" != "$cp_highest" ] && cp_pct=$cp_little
    cp_want=$((cp_max * cp_pct / 100)); [ "$cp_want" -lt "$cp_min" ] && cp_want=$cp_min
    cp_node=$cp_policy/scaling_max_freq
    cp_now=$(cat "$cp_node" 2>/dev/null)
    if ! uint "$cp_now"; then record_control "$cp_name" "$cp_want" unknown unsupported; continue; fi
    cp_orig=$CP_RUN/original/$cp_name; cp_written=$CP_RUN/written/$cp_name
    [ -f "$cp_orig" ] || echo "$cp_now" > "$cp_orig"
    cp_ceiling=$(cat "$cp_orig"); cp_last=$(cat "$cp_written" 2>/dev/null)
    # Preserve a stricter external limit observed between our own writes.
    if [ -n "$cp_last" ] && [ "$cp_now" != "$cp_last" ] && [ "$cp_now" -lt "$cp_ceiling" ]; then
      cp_ceiling=$cp_now; echo "$cp_ceiling" > "$cp_orig"
    fi
    [ "$cp_want" -gt "$cp_ceiling" ] && cp_want=$cp_ceiling
    cp_freq=$(awk -v want="$cp_want" '{for(i=1;i<=NF;i++) if($i+0<=want && $i+0>best)best=$i+0} END{print best+0}' "$cp_policy/scaling_available_frequencies" 2>/dev/null)
    [ "${cp_freq:-0}" -gt 0 ] || cp_freq=$cp_want
    cp_result=applied
    if [ "$cp_now" != "$cp_freq" ]; then
      if [ "$FORCE" = 0 ] && [ "$cp_last" = "$cp_freq" ]; then cp_result=conflict
      elif (echo "$cp_freq" > "$cp_node") 2>/dev/null; then
        cp_actual=$(cat "$cp_node" 2>/dev/null)
        uint "$cp_actual" && echo "$cp_actual" > "$cp_written"
      else cp_result=write_failed; fi
    fi
    cp_actual=$(cat "$cp_node" 2>/dev/null)
    if [ "$cp_result" = applied ] && [ "$cp_actual" != "$cp_freq" ]; then
      if uint "$cp_actual" && [ "$cp_actual" -lt "$cp_freq" ]; then cp_result=limited; else cp_result=conflict; fi
    fi
    record_control "$cp_name" "$cp_freq" "${cp_actual:-unknown}" "$cp_result"
  done
  [ "$cp_count" -gt 0 ] || record_control cpu 0 unknown unsupported
}

native_cpu_cooling() {
  for cp_dev in "$CP_SYS"/class/thermal/cooling_device*; do
    [ -r "$cp_dev/type" ] && [ -r "$cp_dev/cur_state" ] || continue
    read -r cp_kind < "$cp_dev/type"
    case "$cp_kind" in *cpu*|*CPU*) ;; *) continue ;; esac
    read -r cp_cstate < "$cp_dev/cur_state"
    uint "$cp_cstate" && [ "$cp_cstate" -gt 0 ] && return 0
  done
  return 1
}

set_boost() {
  cp_node=$CP_CPUCTL/top-app/cpu.uclamp.min
  [ -f "$cp_node" ] || { [ "$1" = 1 ] && record_control uclamp 20 unknown unsupported; return 0; }
  cp_current=$(cat "$cp_node" 2>/dev/null)
  if [ "$1" = 1 ]; then
    if ! printf '%s\n' "$cp_current" | grep -Eq '^[0-9]+([.][0-9]+)?$'; then
      record_control uclamp 20 unknown unsupported; return 0
    fi
    if awk -v n="$cp_current" 'BEGIN {exit !(n > 20)}'; then
      record_control uclamp 20 "$cp_current" applied; return 0
    fi
    [ -f "$CP_RUN/uclamp.orig" ] || printf '%s\n' "$cp_current" > "$CP_RUN/uclamp.orig"
    cp_result=applied
    if [ "$cp_current" != 20 ] && [ "$cp_current" != 20.00 ]; then
      if [ -f "$CP_RUN/uclamp.written" ] && [ "$FORCE" = 0 ]; then cp_result=conflict
      elif (echo 20 > "$cp_node") 2>/dev/null; then : > "$CP_RUN/uclamp.written"
      else cp_result=write_failed; fi
    fi
    cp_actual=$(cat "$cp_node" 2>/dev/null)
    case "$cp_actual" in 20|20.00) ;; *) [ "$cp_result" = applied ] && cp_result=conflict ;; esac
    record_control uclamp 20 "${cp_actual:-unknown}" "$cp_result"
  elif [ -f "$CP_RUN/uclamp.orig" ]; then
    case "$cp_current" in
      20|20.00) (cat "$CP_RUN/uclamp.orig" > "$cp_node") 2>/dev/null || return 1 ;;
    esac
    rm -f "$CP_RUN/uclamp.orig" "$CP_RUN/uclamp.written"
  fi
}

# Refuse arbitrary paths from a damaged/edited switch file. No bypass/power-path nodes.
read_switch() {
  IFS='|' read -r sw_rel SW_ON SW_OFF < "$CP_DATA/switch" 2>/dev/null || return 1
  printf '%s\n' "$SWITCHES" | grep -Fxq "$sw_rel|$SW_ON|$SW_OFF" || return 1
  case "$sw_rel" in ''|*..*|/*|proc/*|*bypass*|*power_path*) return 1 ;; esac
  SW_NODE=$(switch_node "$sw_rel")
  [ -f "$SW_NODE" ]
}

charge_set() {
  read_switch || return 1
  if [ "$1" = on ]; then cp_value=$SW_ON; else cp_value=$SW_OFF; fi
  cp_before=$(cat "$SW_NODE" 2>/dev/null)
  if [ "$1" = off ] && [ ! -f "$CP_RUN/charge.owned" ]; then
    [ "$cp_before" = "$SW_ON" ] || return 1
    printf '%s|%s|%s\n' "$sw_rel" "$cp_before" "$SW_OFF" > "$CP_RUN/charge.owned"
  fi
  if ! (printf '%s\n' "$cp_value" > "$SW_NODE") 2>/dev/null; then
    [ -f "$CP_RUN/apply.tsv.tmp" ] && record_control charging "$cp_value" "$cp_before" write_failed
    return 1
  fi
  cp_after=$(cat "$SW_NODE" 2>/dev/null)
  if [ "$cp_after" != "$cp_value" ]; then
    [ -f "$CP_RUN/apply.tsv.tmp" ] && record_control charging "$cp_value" "$cp_after" conflict
    return 1
  fi
  [ -f "$CP_RUN/apply.tsv.tmp" ] && record_control charging "$cp_value" "$cp_after" applied
  [ "$1" = on ] && rm -f "$CP_RUN/charge.owned"
  return 0
}

restore_charge() {
  [ -f "$CP_RUN/charge.owned" ] || return 0
  IFS='|' read -r cp_rel cp_orig cp_off < "$CP_RUN/charge.owned"
  read_switch || return 1
  [ "$cp_rel" = "$sw_rel" ] || return 1
  if [ "$(cat "$SW_NODE" 2>/dev/null)" = "$cp_off" ]; then
    (printf '%s\n' "$cp_orig" > "$SW_NODE") 2>/dev/null || { event 'Pemulihan saklar cas gagal'; return 1; }
    [ "$(cat "$SW_NODE" 2>/dev/null)" = "$cp_orig" ] || return 1
  fi
  rm -f "$CP_RUN/charge.owned"
}

restore_probe() {
  [ -f "$CP_RUN/probe" ] || return 0
  IFS='|' read -r cp_pr cp_on cp_off < "$CP_RUN/probe"
  printf '%s\n' "$SWITCHES" | grep -Fxq "$cp_pr|$cp_on|$cp_off" || return 1
  cp_pnode=$(switch_node "$cp_pr")
  if [ "$(cat "$cp_pnode" 2>/dev/null)" = "$cp_off" ]; then
    (echo "$cp_on" > "$cp_pnode") 2>/dev/null || return 1
    [ "$(cat "$cp_pnode" 2>/dev/null)" = "$cp_on" ] || return 1
  fi
  rm -f "$CP_RUN/probe"
}
