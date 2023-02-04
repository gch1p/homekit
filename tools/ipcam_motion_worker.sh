#!/bin/bash

set -e

DIR="$( cd "$( dirname "$(realpath "${BASH_SOURCE[0]}")" )" &>/dev/null && pwd )"
PROGNAME="$0"

. "$DIR/lib.bash"

curl_opts="-s --connect-timeout 10 --retry 5 --max-time 180 --retry-delay 0 --retry-max-time 180"
allow_multiple=
fetch_limit=10

config=
config_camera=
is_remote=
api_url=

dvr_scan_path="$HOME/.local/bin/dvr-scan"
fs_root="/var/ipcam_motion_fs"
fs_max_filesize=146800640

declare -A config=()

usage() {
	cat <<EOF
usage: $PROGNAME OPTIONS

Options:
    -v, -vx             be verbose.
                        -v enables debug logs.
                        -vx does \`set -x\`, may be used to debug the script.
    --allow-multiple    don't check for another instance
    --L, --fetch-limit  default: $fetch_limit
    --remote
    --local
    --dvr-scan-path     default: $dvr_scan_path
    --fs-root           default: $fs_root
    --fs-max-filesize   default: $fs_max_filesize
EOF
	exit 1
}

get_recordings_dir() {
	local camera="$1"
	curl $curl_opts "${api_url}/api/camera/list" \
		| jq ".response.\"${camera}\".recordings_path" | tr -d '"'
}

# returns three words per line:
# filename filesize camera
get_recordings_list() {
	curl $curl_opts "${api_url}/api/recordings?limit=${fetch_limit}" \
		| jq '.response.files[] | [.name, .size, .cam] | join(" ")' | tr -d '"'
}

read_camera_motion_config() {
	local camera="$1"
	local dst=config

	if [ "$config_camera" != "$camera" ]; then
		local n=0
		local failed=
		local key
		local value

		while read line; do
			n=$(( n+1 ))

			# skip empty lines or comments
			if [ -z "$line" ] || [[ "$line" =~ ^#.*  ]]; then
				continue
			fi

			if [[ $line = *"="* ]]; then
				key="${line%%=*}"
				value="${line#*=}"
				eval "$dst[$key]=\"$value\""
			else
				echoerr "config: invalid line $n"
				failed=1
			fi
		done < <(curl $curl_opts "${api_url}/api/motion/params/${camera}")

		config_camera="$camera"

		[ -z "$failed" ]
	else
		debug "read_camera_motion_config: config for $camera already loaded"
	fi
}

dump_config() {
	for key in min_event_length downscale_factor frame_skip threshold; do
		debug "config[$key]=${config[$key]}"
	done
}

get_camera_roi_config() {
	local camera="$1"
	curl $curl_opts "${api_url}/api/motion/params/${camera}/roi"
}

report_failure() {
	local camera="$1"
	local file="$2"
	local message="$3"

	local response=$(curl $curl_opts -X POST "${api_url}/api/motion/fail/${camera}" \
		-F "filename=$file" \
		-F "message=$message")

	print_response_error "$response" "report_failure"
}

report_timecodes() {
	local camera="$1"
	local file="$2"
	local timecodes="$3"

	local response=$(curl $curl_opts -X POST "${api_url}/api/motion/done/${camera}" \
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

process_queue() {
	local tc
	local url
	local words
	local file
	local size
	local camera
	local local_recs_dir

	if [ "$is_remote" = "1" ]; then
		pushd "${fs_root}" >/dev/null || die "failed to change to ${fs_root}"
		touch tmp || die "directory '${fs_root}' is not writable"
		rm tmp

		[ -f "video.mp4" ] && {
			echowarn "video.mp4 already exists in ${fs_root}, removing.."
			rm "video.mp4"
		}
	fi

	while read line; do
		words=($line)
		file=${words[0]}
		size=${words[1]}
		camera=${words[2]}

		debug "next video: cam=$camera file=$file"

		read_camera_motion_config "$camera"
#		dump_config

		if [ "$is_remote" = "0" ]; then
			local_recs_dir="$(get_recordings_dir "$camera")"

			debug "[$camera] processing $file..."

			tc=$(do_motion "$camera" "${local_recs_dir}/$file")
			debug "[$camera] $file: timecodes=$tc"

			report_timecodes "$camera" "$file" "$tc"
		else
			if (( size > fs_max_filesize )); then
				echoerr "[$camera] won't download $file, size exceeds fs_max_filesize ($size > ${fs_max_filesize})"
				report_failure "$camera" "$file" "too large file"
				continue
			fi

			url="${api_url}/api/recordings/${camera}/download/${file}"
			debug "[$camera] downloading $url..."

			if ! download "$url" "video.mp4"; then
				echoerr "[$camera] failed to download $file"
				report_failure "$camera" "$file" "download error"
				continue
			fi

			tc=$(do_motion "$camera" "video.mp4")
			debug "[$camera] $file: timecodes=$tc"

			report_timecodes "$camera" "$file" "$tc"

			rm "video.mp4"
		fi
	done < <(get_recordings_list)

	if [ "$is_remote" = "1" ]; then popd >/dev/null; fi
}

do_motion() {
	local camera="$1"
	local input="$2"
	local tc

	local timecodes=()

	time_start
	while read line; do
		if ! [[ "$line" =~ ^#.*  ]]; then
			tc="$(do_dvr_scan "$input" "$line")"
			if [ -n "$tc" ]; then
				timecodes+=("$tc")
			fi
		fi
	done < <(get_camera_roi_config "$camera")

	debug "[$camera] do_motion: finished in $(time_elapsed)s"

	timecodes="$(echo "${timecodes[@]}" | sed 's/  */ /g' | xargs)"
	timecodes="${timecodes// /,}"

	echo "$timecodes"
}

dvr_scan() {
	"${dvr_scan_path}" "$@"
}

do_dvr_scan() {
	local input="$1"
	local args=
	
	if [ ! -z "$2" ]; then
		args="-roi $2"
		echoinfo "dvr_scan(${BOLD}${input}${RST}${CYAN}): roi=($2), mt=${config[threshold]}"
	else
		echoinfo "dvr_scan(${BOLD}${input}${RST}${CYAN}): no roi, mt=${config[threshold]}"
	fi
	
	dvr_scan -q -i "$input" -so \
		--min-event-length ${config[min_event_length]} \
		-df ${config[downscale_factor]} \
		--frame-skip ${config[frame_skip]} \
		-t ${config[threshold]} $args | tail -1
}

[[ $# -lt 1 ]] && usage

while [[ $# -gt 0 ]]; do
	case $1 in
		-L|--fetch-limit)
			fetch_limit="$2"
			shift; shift
			;;

		--allow-multiple)
			allow_multiple=1
			shift
			;;

		--remote)
			is_remote=1
			shift
			;;

		--local)
			is_remote=0
			shift
			;;

		--dvr-scan-path)
			dvr_scan_path="$2"
			shift; shift
			;;

		--fs-root)
			fs_root="$2"
			shift; shift
			;;

		--fs-max-filesize)
			fs_max_filesize="$2"
			shift; shift
			;;

		--api-url)
			api_url="$2"
			shift; shift
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

[ -z "$is_remote" ] && die "either --remote or --local is required"
[ -z "$api_url" ] && die "--api-url is required"

process_queue