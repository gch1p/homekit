#!/bin/bash

set -e

DIR="$( cd "$( dirname "$(realpath "${BASH_SOURCE[0]}")" )" &>/dev/null && pwd )"
PROGNAME="$0"

. "$DIR/lib.bash"

allow_multiple=
config_file="$HOME/.config/ipcam_motion_worker/config.txt"
declare -A config=()

usage() {
	cat <<EOF
usage: $PROGNAME OPTIONS

Options:
    -c|--config FILE  configuration file, default is $config_file
    -v, -vx           be verbose.
                      -v enables debug logs.
                      -vx does \`set -x\`, may be used to debug the script.
    --allow-multiple  don't check for another instance
EOF
	exit 1
}

get_recordings_dir() {
	curl -s "${config[api_url]}/api/camera/list" \
		| jq ".response.\"${config[camera]}\".recordings_path" | tr -d '"'
}

# returns two words per line:
# filename filesize
get_recordings_list() {
	curl -s "${config[api_url]}/api/recordings/${config[camera]}?filter=motion" \
		| jq '.response.files[] | [.name, .size] | join(" ")' | tr -d '"'
}

report_failure() {
	local file="$1"
	local message="$2"
	local response=$(curl -s -X POST "${config[api_url]}/api/motion/fail/${config[camera]}" \
		-F "filename=$file" \
		-F "message=$message")
	print_response_error "$response" "report_failure"
}

report_timecodes() {
	local file="$1"
	local timecodes="$2"
	local response=$(curl -s -X POST "${config[api_url]}/api/motion/done/${config[camera]}" \
		-F "filename=$file" \
		-F "timecodes=$timecodes")
	print_response_error "$response" "report_timecodes"
}

print_response_error() {
	local resp="$1"
	local sufx="$2"

	local error="$(echo "$resp" | jq '.error')"
	local message

	if [ "$error" != "null" ]; then
		message="$(echo "$resp" | jq '.message' | tr -d '"')"
		error="$(echo "$error" | tr -d '"')"

		echoerr "$sufx: $error ($message)"
	fi
}

get_roi_file() {
	if [ -n "${config[roi_file]}" ]; then
		file="${config[roi_file]}"
		if ! [[ "$file" =~ ^/.* ]]; then
			file="$(dirname "$config_file")/$file"
		fi

		debug "get_roi_file: detected file $file"
		[ -f "$file" ] || die "invalid roi_file: $file: no such file"
		
		echo "$file"
	fi
}

process_local() {
	local recdir="$(get_recordings_dir)"
	local tc
	local words
	local file

	while read line; do
		words=($line)
		file=${words[0]}

		debug "processing $file..."

		tc=$(do_motion "${recdir}/$file")
		debug "$file: timecodes=$tc"

		report_timecodes "$file" "$tc"
	done < <(get_recordings_list)
}

process_remote() {
	local tc
	local url
	local words
	local file
	local size
	
	pushd "${config[fs_root]}" >/dev/null || die "failed to change to ${config[fs_root]}"
	touch tmp || die "directory '${config[fs_root]}' is not writable"
	rm tmp

	[ -f "video.mp4" ] && {
		echowarn "video.mp4 already exists in ${config[fs_root]}, removing.."
		rm "video.mp4"
	}

	while read line; do
		words=($line)
		file=${words[0]}
		size=${words[1]}

		if (( size > config[fs_max_filesize] )); then
			echoerr "won't download $file, size exceedes fs_max_filesize ($size > ${config[fs_max_filesize]})"
			report_failure "$file" "too large file"
			continue
		fi

		url="${config[api_url]}/api/recordings/${config[camera]}/download/${file}"
		debug "downloading $url..."

		if ! download "$url" "video.mp4"; then
			echoerr "failed to download $file"
			report_failure "$file" "download error"
			continue
		fi

		tc=$(do_motion "video.mp4")
		debug "$file: timecodes=$tc"

		report_timecodes "$file" "$tc"

		rm "video.mp4"
	done < <(get_recordings_list)

	popd >/dev/null
}

do_motion() {
	local input="$1"
	local roi_file="$(get_roi_file)"

	local timecodes=()
	if [ -z "$roi_file" ]; then
		timecodes+=($(dvr_scan "$input"))
	else
		echoinfo "using roi sets from file: ${BOLD}$roi_file"
		while read line; do
			if ! [[ "$line" =~ ^#.*  ]]; then
				timecodes+=("$(dvr_scan "$input" "$line")")
			fi
		done < <(cat "$roi_file")
	fi

	timecodes="${timecodes[@]}"
	timecodes=${timecodes// /,}

	echo "$timecodes"
}

dvr_scan() {
	local input="$1"
	local args=
	if [ ! -z "$2" ]; then
		args="-roi $2"
		echoinfo "dvr_scan(${BOLD}${input}${RST}${CYAN}): roi=($2), mt=${config[threshold]}"
	else
		echoinfo "dvr_scan(${BOLD}${input}${RST}${CYAN}): no roi, mt=${config[threshold]}"
	fi
	time_start
	dvr-scan -q -i "$input" -so --min-event-length 3s -df 3 --frame-skip 2 -t ${config[threshold]} $args | tail -1
	debug "dvr_scan: finished in $(time_elapsed)s"
}

[[ $# -lt 1 ]] && usage

while [[ $# -gt 0 ]]; do
	case $1 in
		-c|--config)
			config_file="$2"
			shift; shift
			;;

		--allow-multiple)
			allow_multiple=1
			shift
			;;

		-v)
			VERBOSE=1
			shift
			;;

		-vx)
			VERBOSE=1
			set -x
			shift
			;;

		*)
			die "unrecognized argument '$1'"
			exit 1
			;;
	esac
done

if [ -z "$allow_multiple" ] && pidof -o %PPID -x "$(basename "${BASH_SOURCE[0]}")" >/dev/null; then
	die "process already running"
fi

read_config "$config_file" config
check_config config "api_url camera threshold"

if [ -n "${config[remote]}" ]; then 
	check_config config "fs_root fs_max_filesize"
fi

if [ -z "${config[remote]}" ]; then
	process_local
else
	process_remote
fi
