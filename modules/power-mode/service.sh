#!/system/bin/sh
# Cogan Power Mode: start the controller once Android has finished booting.
MODDIR=${0%/*}; [ "$MODDIR" = "$0" ] && MODDIR=.
until [ "$(getprop sys.boot_completed)" = 1 ]; do sleep 5; done
. "$MODDIR/common.sh"
load_config
boot_session
[ "$AUTOSTART" = 1 ] || exit 0
sleep 20        # let Cogan Thermal Monitor take its first sample
sh "$MODDIR/report.sh" start > /dev/null 2>&1
