#!/bin/bash

set -e

DIR="$( cd "$( dirname "$(realpath "${BASH_SOURCE[0]}")" )" &> /dev/null && pwd )"
PROGNAME="$0"

. "$DIR/lib.bash"

input=
output=
command=
ffmpeg_args="-nostats -loglevel error"
config_dir=$HOME/.config/video-util
config_dir_set=

usage() {
	cat <<EOF
usage: $PROGNAME OPTIONS command

Options:
	-i|--input  FILE  input file/directory
	-o|--output FILE  output file/directory
	--name NAME       camera name, affects config directory.
	                  default is $config_dir, specifying --name will make it 
	                  ${config_dir}-\$name
	-v, -vv, vx       be verbose.
	                  -v enables debug logs.
	                  -vv also enables verbose output of ffmpeg.
	                  -vx does \`set -x\`, may be used to debug the script.

Commands:
	snapshot        take video snapshot

EOF
	exit 1
}

check_input_file() {
	[ -z "$input" ] && die "input file not specified"
	[ -f "$input" ] || die "input file '$input' doesn't exist"
}

check_input_dir() {
	[ -z "$input" ] && die "input directory not specified"
	[ -d "$input" ] || die "input directory '$input' doesn't exist"
}

[[ $# -lt 1 ]] && usage

while [[ $# -gt 0 ]]; do
	case $1 in
		snapshot)
			command="$1"
			shift
			;;

		-i|--input)
			input="$2"
			shift; shift
			;;

		-o|--output)
			output="$2"
			shift; shift
			;;

		-v)
			verbose=1
			shift
			;;

		-vx)
			verbose=1
			set -x
			shift
			;;

		-vv)
			verbose=1
			ffmpeg_args="-loglevel info"
			shift
			;;

		--name)
			config_dir="$config_dir-$2"
			config_dir_set=1
			shift; shift
			;;

		*)
			die "unrecognized option $1"
			exit 1
			;;
	esac
done

if [ -z "$config_dir_set" ]; then
	echowarn "no --name specified, using default ($config_dir)"
else
	if [ ! -d "$config_dir" ]; then
		mkdir "$config_dir" || die "failed to create config directory ($config_dir)"
	fi
	>&2 echo "using ${BOLD}$config_dir${RST} as config directory"
fi

[ -z "$command" ] && die "command not specified"
case "$command" in
	snapshot)
		check_input_file
		[ -z "$output" ] && {
			echowarn "--output not specified, using snapshot.jpg as default"
			output="snapshot.jpg"
		}
		ffmpeg $ffmpeg_args -i "$input" -frames:v 1 -q:v 2 "$output" </dev/null
		echoinfo "saved to $output"
		;;

	*)
		echo "error: invalid command '$command'"
		;;
esac
