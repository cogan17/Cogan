#!/system/bin/sh
# Cogan Power Mode: everything the WebUI and the Action button ask for. Output is JSON.
#
#   report.sh status              mode, temperatures, CPU limits, charging and settings
#   report.sh mode NAME           switch to hemat | seimbang | game
#   report.sh set KEY VALUE ...   change settings (only known keys, values within range)
#   report.sh detect              find the charging switch (the phone must be charging)
#   report.sh events [N]          the last N lines of the activity log, newest first
#   report.sh start | stop | restart

MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.   # started as "sh report.sh"
. "$MODDIR/common.sh"
load_config

persist_config() { write_config || { echo '{"ok":0,"error":"Gagal menyimpan setelan"}'; exit 0; }; }

controller_pid() { safe_pid "$CP_RUN/pid" "$MODDIR/controller.sh"; }

wake() { pid=$(controller_pid) && kill -HUP "$pid" 2>/dev/null; return 0; }

start_controller() {
  [ -n "$(controller_pid)" ] && return 0
  boot_session
  if command -v setsid > /dev/null 2>&1; then
    setsid sh "$MODDIR/controller.sh" < /dev/null > /dev/null 2>&1 &
  else
    nohup sh "$MODDIR/controller.sh" < /dev/null > /dev/null 2>&1 &
  fi
  i=0
  while [ $i -lt 30 ] && [ -z "$(controller_pid)" ]; do sleep 0.1; i=$((i + 1)); done
  [ -n "$(controller_pid)" ]
}

stop_controller() {
  if pid=$(controller_pid); then
    kill "$pid" 2>/dev/null || return 1
    i=0
    while [ $i -lt 60 ] && controller_pid >/dev/null; do sleep 0.1; i=$((i + 1)); done
    controller_pid >/dev/null && return 1
  fi
  lock_take "$CP_RUN/step.lock" || return 1
  boot_session
  cp_restored=0; restore || cp_restored=1
  log_mode none
  rm -f "$CP_RUN/pid" "$CP_RUN/mode"
  lock_drop "$CP_RUN/step.lock"
  [ "$cp_restored" = 0 ]
}

validate_values() {
  [ $(( $# % 2 )) = 0 ] || return 1
  [ $# -gt 0 ] || return 1
  while [ $# -ge 2 ]; do
    case " $KEYS " in *" $1 "*) ;; *) return 1 ;; esac
    valid "$1" "$2" || return 1
    eval "$1=\$2"
    shift 2
  done
  [ "$CHARGE_RESUME" -lt "$CHARGE_STOP" ]
}

set_values() {
  if ! validate_values "$@"; then
    echo '{"ok":0,"error":"Nilai tidak valid atau resume tidak lebih rendah dari stop; tidak ada setelan disimpan"}'
    return 0
  fi
  if write_config; then
    echo '{"ok":1}'
  else
    echo '{"ok":0,"error":"Gagal menyimpan setelan"}'
  fi
}

apply_now() {
  if [ $# -gt 0 ] && ! validate_values "$@"; then
    echo '{"ok":0,"error":"Nilai tidak valid; tidak ada perubahan"}'; return
  fi
  FORCE=1; AUTOSTART=1
  write_config || { echo '{"ok":0,"error":"Gagal menyimpan"}'; return; }
  mkdir -p "$CP_RUN"
  cp_request="$(date +%s)-$$"
  printf '%s\n' "$cp_request" > "$CP_RUN/apply.request"
  if controller_pid >/dev/null; then wake
  else start_controller || { echo '{"ok":0,"error":"Pengendali gagal mulai"}'; return; }; fi
  cp_wait=0
  while [ "$(cat "$CP_RUN/applied.request" 2>/dev/null)" != "$cp_request" ]; do
    [ "$cp_wait" -ge 60 ] && { echo '{"ok":0,"error":"Penerapan masih berjalan; periksa status kontrol"}'; return; }
    sleep 0.1; cp_wait=$((cp_wait + 1))
  done
  printf '{"ok":1,"status":'; status_json brief; printf '}\n'
}

json_config() {
  printf '{"mode":"%s"' "$MODE"
  for key in $KEYS; do [ "$key" = MODE ] || eval "printf ',\"%s\":%d' $key \"\$$key\""; done
  printf '}'
}

json_policies() {
  sep=""
  printf '['
  for policy in "$CP_SYS"/devices/system/cpu/cpufreq/policy*; do
    max=$(cat "$policy/cpuinfo_max_freq" 2>/dev/null) || continue
    printf '%s{"name":"%s","max":%d,"limit":%d,"cur":%d}' "$sep" "${policy##*/}" "$max" \
      "$(cat "$policy/scaling_max_freq" 2>/dev/null || echo 0)" "$(cat "$policy/scaling_cur_freq" 2>/dev/null || echo 0)"
    sep=","
  done
  printf ']'
}

status_json() {
  cp_status_detail=$1
  pid=$(controller_pid) || pid=0
  set -- $(read_battery)
  monitor=0; monitor_installed && monitor=1
  fresh=0; read_monitor && fresh=1
  switch=$(cut -d '|' -f 1 "$CP_DATA/switch" 2>/dev/null)
  state=$(cat "$CP_RUN/state.json" 2>/dev/null)
  version=$(sed -n 's/^version=//p' "$MODDIR/module.prop" 2>/dev/null)
  printf '{"running":%d,"version":"%s","main":%d,"battery":{"level":%d,"status":"%s","temp":%d,"current":%d},' \
    "$([ "$pid" -gt 0 ] && echo 1 || echo 0)" "$version" "$(read_main_temp)" "$1" "$2" "$3" "$4"
  printf '"monitor":{"installed":%d,"fresh":%d,"cause":"%s","app":"%s"},"switch":"%s","no_switch":%d,"config":' \
    "$monitor" "$fresh" "$(printf '%s' "$M_CAUSE" | sed 's/[\\"]//g')" "$(printf '%s' "$M_APP" | sed 's/[\\"]//g')" \
    "$switch" "$([ -f "$CP_RUN/no_switch" ] && echo 1 || echo 0)"
  json_config
  printf ',"policies":'
  json_policies
  printf ',"state":%s' "${state:-null}"
  if [ "$cp_status_detail" != live ]; then
    printf ',"kernel":'; kernel_json
    [ "$cp_status_detail" = brief ] || { printf ',"cooling":'; cooling_json; }
    printf ',"peer":'; peer_json "$CT_MOD" "$CT_DATA/run/sampler.pid" sampler.sh
  fi
  printf ',"controls":'; controls_json
  printf ',"restore_pending":%d' "$([ -f "$CP_RUN/restore_pending" ] && echo 1 || echo 0)"
  printf ',"backend":'; json_string "$(cat "$CP_RUN/backend" 2>/dev/null)"
  printf '}\n'
}

events_json() {
  n=$1
  case "$n" in ''|*[!0-9]*) n=30 ;; esac
  tail -n "$n" "$EVENTS" 2>/dev/null | awk -F '\t' '
    { ts[NR] = $1; text[NR] = $2; gsub(/[\\"]/, "", text[NR]) }
    END { printf "["; for (i = NR; i >= 1; i--) printf "%s{\"ts\":%d,\"text\":\"%s\"}", (i < NR ? "," : ""), ts[i], text[i]; print "]" }'
}

detect() {
  if ! is_charging; then
    echo '{"ok":0,"error":"Colokkan charger dulu: saklar hanya bisa dicari saat HP sedang mengecas"}'
    return 0
  fi
  mkdir -p "$CP_RUN"
  lock_take "$CP_RUN/step.lock" || { echo '{"ok":0,"error":"Pengendali sedang bekerja"}'; return; }
  : > "$CP_RUN/detecting"
  rm -f "$CP_DATA/switch"
  if detect_switch > "$CP_RUN/detect.log"; then ok=1; rm -f "$CP_RUN/no_switch"; else ok=0; : > "$CP_RUN/no_switch"; fi
  rm -f "$CP_RUN/detecting" "$CP_RUN/charge_off"   # charging is on again after the test
  if [ "$ok" = 1 ]; then event "Saklar cas ditemukan: $(cut -d '|' -f 1 "$CP_DATA/switch")"
  else event "Saklar cas tidak ditemukan di HP ini"; fi
  printf '{"ok":%d,"switch":"%s","tried":[' "$ok" "$(cut -d '|' -f 1 "$CP_DATA/switch" 2>/dev/null)"
  awk '{ printf "%s{\"node\":\"%s\",\"result\":\"%s\"}", (NR > 1 ? "," : ""), $1, $2 }' "$CP_RUN/detect.log"
  echo ']}'
  wake
  lock_drop "$CP_RUN/step.lock"
}

# Serialize writes. Reads remain cheap and never refresh a stopped client's heartbeat.
case "$1" in status|events|live|cooling) ;; *)
  mkdir -p "$CP_RUN"
  lock_take "$CP_DATA/api.lock" || { echo '{"ok":0,"error":"Perintah lain sedang berjalan"}'; exit 0; }
  trap 'restore_probe; lock_drop "$CP_DATA/api.lock"; lock_drop "$CP_RUN/step.lock"' EXIT
  trap 'exit 1' TERM INT
  load_config
  ;;
esac
case "$1" in
  status) status_json "$2" ;;
  live) status_json live ;;
  cooling) cooling_json; printf '\n' ;;
  mode) set_values MODE "$2"; wake ;;
  set|save) shift; set_values "$@" ;;
  apply|force) shift; apply_now "$@" ;;
  detect) detect ;;
  events) events_json "$2" ;;
  start)
    AUTOSTART=1; persist_config
    if start_controller; then status_json brief; else echo '{"ok":0,"error":"Pengendali gagal mulai"}'; fi ;;
  stop)
    AUTOSTART=0; save_failed=0; write_config || save_failed=1
    if stop_controller; then
      [ "$save_failed" = 0 ] || { echo '{"ok":0,"error":"Berhenti, tetapi setelan berhenti gagal disimpan untuk reboot"}'; exit 0; }; status_json
    else echo '{"ok":0,"error":"Pengendali belum berhenti; status kontrol belum dipulihkan"}'; fi ;;
  restart)
    if stop_controller; then AUTOSTART=1; persist_config; start_controller; status_json
    else echo '{"ok":0,"error":"Pengendali belum berhenti"}'; fi ;;
  reset)
    if ! stop_controller; then echo '{"ok":0,"error":"Pengendali belum berhenti; reset dibatalkan"}'; exit 0; fi
    defaults; AUTOSTART=0; persist_config
    rm -f "$CP_DATA/switch" "$CP_RUN/no_switch" "$CP_RUN/backend" "$CP_RUN/apply.tsv"
    event 'Reset: setelan bawaan dipulihkan (cas 95/90), pengendali dihentikan'
    status_json brief ;;
  *) echo 'Pakai: report.sh status|mode NAME|set KEY VALUE ...|apply [KEY VALUE ...]|detect|events [N]|start|stop|restart|reset' >&2; exit 1 ;;
esac
