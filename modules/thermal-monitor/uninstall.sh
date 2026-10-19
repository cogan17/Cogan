#!/system/bin/sh
# Cogan Thermal Monitor: remove the recorded history. Logs saved to Download stay with the user.
MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.
. "$MODDIR/common.sh"
sh "$MODDIR/report.sh" stop >/dev/null
if ! safe_pid "$CT_RUN/sampler.pid" "$MODDIR/sampler.sh" >/dev/null; then rm -rf "$CT_DATA"; fi
