#!/system/bin/sh
# Cogan Power Mode: put CPU speed and charging back to normal, then remove the settings.
MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.
. "$MODDIR/common.sh"
sh "$MODDIR/report.sh" stop >/dev/null
if ! safe_pid "$CP_RUN/pid" "$MODDIR/controller.sh" >/dev/null; then rm -rf "$CP_DATA"; fi
