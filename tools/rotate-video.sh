#!/bin/bash

set -e

DIR="$( cd "$( dirname "$(realpath "${BASH_SOURCE[0]}")" )" &>/dev/null && pwd )"
PROGNAME="$0"

. "$DIR/lib.bash"


usage() {
	cat <<EOF
usage: $PROGNAME FILENAME
EOF
	exit 1
}

[[ $# -lt 1 ]] && usage

oldname="$1"
if file_in_use "$oldname"; then
  die "file $oldname is in use by another process"
fi

newname="${oldname/.mp4/_rotated.mp4}"

ffmpeg -y -i "$(realpath "$1")" -map_metadata 0 -metadata:s:v rotate="90" -codec copy \
  "$(realpath "$newname")"
rm "$oldname"
mv "$newname" "$oldname"