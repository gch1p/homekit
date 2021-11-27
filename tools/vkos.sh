#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROGNAME="$0"

die() {
	>&2 echo "error: $@"
	exit 1
}

usage() {
	cat <<EOF
usage: $PROGNAME [OPTIONS] COMMAND

Options:
	-b  use backup server
	-d  don't delete files after merge

Supported commands:
	list NODE
	fetch NODE PREFIX
	merge
EOF
	exit
}

[ -z "$1" ] && usage

COMMAND=
NODE=
PREFIX=
FROM_BACKUP=0
DONT_DELETE=0
while [[ $# -gt 0 ]]; do
	case "$1" in
		list)
			COMMAND="$1"
			NODE="$2"
			shift
			;;

		fetch)
			COMMAND="$1"
			NODE="$2"
			PREFIX="$3"
			shift; shift
			;;

		merge)
			COMMAND="$1"
			;;

		-b)
			FROM_BACKUP=1
			;;

		-d)
			DONT_DELETE=1
			;;

		*)
			die "unrecognized argument: $1"
			;;
	esac
	shift
done

[ -z "$COMMAND" ] && usage

if [ "$FROM_BACKUP" = "0" ]; then
	SRV_HOST=solarmon.ru
	SRV_PORT=60681
	SRV_USER=user
	SRV_DIR=/var/recordings
else
	SRV_HOST=srv_nas4
	SRV_PORT=22
	SRV_USER=root
	SRV_DIR=/var/storage1/solarmon/recordings
fi

case "$COMMAND" in
	list)
		[ -z "$NODE" ] && usage
		ssh -p${SRV_PORT} ${SRV_USER}@${SRV_HOST} "ls -rt --time creation \"${SRV_DIR}/${NODE}\""
		;;

	fetch)
		[ -z "$NODE" ] && usage
		[ -z "$PREFIX" ] && usage
		rsync -azPv -e "ssh -p${SRV_PORT}" ${SRV_USER}@${SRV_HOST}:"${SRV_DIR}/${NODE}/${PREFIX}*" .
		;;

	merge)
		args=
		if [ "$DONT_DELETE" = "0" ]; then args="-D"; fi
		$DIR/merge-recordings.py $args
		;;
esac
