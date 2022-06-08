#!/bin/bash

set -e

DIR="$( cd "$( dirname "$(realpath "${BASH_SOURCE[0]}")" )" &>/dev/null && pwd )"
PROGNAME="$0"

. "$DIR/lib.bash"

configs=()

usage() {
    cat <<EOF
usage: $PROGNAME [OPTIONS] CONFIG_NAME ...

Options:
    -v  be verbose
EOF
    exit 1
}

[[ $# -lt 1 ]] && usage

while [[ $# -gt 0 ]]; do
	case $1 in
		-v)
			VERBOSE=1
			shift
			;;

		*)
            configs+=("$1")
            shift
			;;
	esac
done

[ -z "$configs" ] && die "no config files supplied"

if pidof -o %PPID -x "$(basename "${BASH_SOURCE[0]}")" >/dev/null; then
	die "process already running"
fi

worker_args=
[ "$VERBOSE" = "1" ] && worker_args="-v"
for name in "${configs[@]}"; do
    echoinfo "starting worker $name..."
    $DIR/ipcam_motion_worker.sh $worker_args -c "$HOME/.config/ipcam_motion_worker/$name.txt" --allow-multiple
done
