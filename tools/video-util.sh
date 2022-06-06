#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROGNAME="$0"
BOLD=$(tput bold)
RST=$(tput sgr0)
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
CYAN=$(tput setaf 6)

input=
command=
roi_file=
motion_threshold=1
ffmpeg_args="-nostats -loglevel error"
dvr_scan_args="-q"
verbose=
config_dir=$HOME/.config/video-util
config_dir_set=

debug() {
	if [ -n "$verbose" ]; then
		>&2 echo "$@"
	fi
}

echoinfo() {
	echo "${CYAN}$@${RST}"
}

echoerr() {
	>&2 echo "${RED}${BOLD}error:${RST}${RED} $@${RST}"
}

echowarn() {
	>&2 echo "${YELLOW}${BOLD}warning:${RST}${YELLOW} $@${RST}"
}

die() {
    >&2 echo "error: $@"
    exit 1
}

file_in_use() {
	[ -n "$(lsof "$1")" ]
}

get_mtime() {
	stat -c %Y "$1"
}

# converts date in format yyyy-mm-dd-hh.ii.ss to unixtime
date_to_unixtime() {
	local date="$1"
	date=${date//./-}
	date=${date//-/ }

	local nums=($date)
	
	local y=${nums[0]}
	local m=${nums[1]}
	local d=${nums[2]}
	local h=${nums[3]}
	local i=${nums[4]}
	local s=${nums[5]}

	date --date="$y-$m-$d $h:$i:$s" +"%s"
}

filename_as_unixtime() {
	local name="$1"
	name="$(basename "$name")"
	name="${name/record_/}"
	name="${name/.mp4/}"
	date_to_unixtime "$name"
}

config_get_prev_mtime() {
	local prefix="$1"
	[ -z "$prefix" ] && die "config_get_prev_mtime: no prefix"

	local file="$config_dir/${prefix}_mtime"
	if [ -f "$file" ]; then
		debug "config_get_prev_mtime: $(cat "$file")"
		cat "$file"
	else
		debug "config_get_prev_mtime: 0"
		echo "0"
	fi
}

config_set_prev_mtime() {
	local prefix="$1"
	[ -z "$prefix" ] && die "config_set_prev_mtime: no prefix"

	local mtime="$2"
	[ -z "$mtime" ] && die "config_set_prev_mtime: no mtime"

	local file="$config_dir/${prefix}_mtime"
	
	debug "config_set_prev_mtime: writing '$mtime' to '$file'"
	echo "$mtime" > "$file"
}

usage() {
	cat <<-_EOF 
	usage: $PROGNAME OPTIONS command

	Options:
	    -i|--input    input file/directory
	    -o|--output   output file/directory
	    --roi-file    path to file with ROI sets
	    -mt           motion threshold
	    -v, -vv, vx   be verbose
	    --config-dir  config directory

	Commands:
	    fix, mass-fix  fix video timestamps
	    mass-fix-mtime fix mtimes of recordings
	    motion         detect motion
	    snapshot       take video snapshot

	_EOF
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

fix_video_timestamps() {
	local input="$1"
	local dir=$(dirname "$input")
	local temp="$dir/.temporary_fixing.mp4"

	local mtime=$(get_mtime "$input")

	# debug "fix_video_timestamps: ffmpeg $ffmpeg_args -i \"$input\" -y -c copy \"$temp\""
	ffmpeg $ffmpeg_args -i "$input" -y -c copy "$temp" </dev/null
	rm "$input"
	mv "$temp" "$input"

	local unixtime=$(filename_as_unixtime "$input")
	touch --date=@$unixtime "$input"
}

do_mass_fix() {
	local mtime=$(config_get_prev_mtime "fix")
	local tmpfile=$(mktemp)
	debug "do_mass_fix: created temporary file $tmpfile"
	
	touch --date=@$mtime "$tmpfile"
	debug "do_mass_fix: mtime of temp file: $(get_mtime $tmpfile)"
	
	[ -f "$input/.temporary_fixing.mp4" ] && {
		echowarn "do_mass_fix: '$input/.temporary_fixing.mp4' exists, deleting"
		rm "$input/.temporary_fixing.mp4"
	}

	# find all files in $input directory, newer than $tmpfile's time,
	# sort them in ascending order, and finally remove timestamps
	# leaving only file names. Then loop through each line
	find "$input" -type f -newer "$tmpfile" -printf "%T+ %p\n" | sort | awk '{print $2}' | while read file; do
		if ! file_in_use "$file"; then
			debug "do_mass_fix: calling fix_video_timestamps($file)"
			
			fix_video_timestamps "$file"
			echoinfo "fixed $file"
		
			config_set_prev_mtime "fix" "$(filename_as_unixtime "$file")"
		else
			echowarn "file '$file' is in use"
		fi
	done

	rm "$tmpfile"
}

do_mass_fix_mtime() {
	local time
	find "$input" -type f -name "*.mp4" | while read file; do
		if [[ "$(basename "$file")" =~ ^record_.* ]]; then
			time="$(filename_as_unixtime "$file")"
			debug "$file: $time"
			touch --date=@$time "$file"
		else
			echowarn "unrecognized file: $file"
		fi
	done
}

do_motion() {
	local timecodes=()
	if [ -z "$roi_file" ]; then
		timecodes+=($(dvr_scan "$input"))
	else
		[ -f "$roi_file" ] || die "specified ROI sets file does not exists"
		echoinfo "using roi sets from file: ${BOLD}$roi_file"
		while read line; do
			if ! [[ "$line" =~ ^#.*  ]]; then
				timecodes+=("$(dvr_scan "$input" "$line")")
			fi
		done < <(cat "$roi_file")
	fi

	timecodes="${timecodes[@]}"
	timecodes=${timecodes// /,}

	echo "all timecodes: $timecodes"
}

dvr_scan_fake() {
	echo "00:05:06.930,00:05:24.063"
}

dvr_scan() {
	local input="$1"
	local args=
	if [ ! -z "$2" ]; then
		args="-roi $2"
		echoinfo "starting dvr-scan, roi=($2), mt=$motion_threshold"
	else
		echoinfo "starting dvr-scan, no roi, mt=$motion_threshold"
	fi
	dvr-scan $dvr_scan_args -i "$input" -so --min-event-length 3s -df 3 --frame-skip 2 -t $motion_threshold $args | tail -1
}

[[ $# -lt 1 ]] && usage

while [[ $# -gt 0 ]]; do
	case $1 in
		-i|--input)
			input="$2"
			shift; shift
			;;

		--roi-file)
			roi_file="$2"
			shift; shift
			;;

		-mt)
			motion_threshold="$2"
			shift; shift
			;;

		fix|mass-fix|motion|snapshot|mass-fix-mtime)
			command="$1"
			shift
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
			dvr_scan_args=""
			shift
			;;

		--config-dir)
			config_dir="$2"
			config_dir_set=1
			shift; shift
			;;

		*)
			die "unrecognized option $1"
			exit 1
			;;
	esac
done

[ -z "$config_dir_set" ] && echowarn "no --config-dir specified, using default ($config_dir)"
if [ ! -d "$config_dir" ]; then
	mkdir "$config_dir" || die "failed to create config directory ($config_dir)"
fi

[ -z "$command" ] && die "command not specified"
case "$command" in
	fix)
		check_input_file
		fix_video_timestamps "$input"
		echo "done"
		;;

	mass-fix)
		check_input_dir
		do_mass_fix
		;;

	mass-fix-mtime)
		check_input_dir
		do_mass_fix_mtime
		;;

	motion)
		check_input_file
		do_motion
		;;

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
