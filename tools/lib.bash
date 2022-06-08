# colored output
# --------------

BOLD=$(tput bold)
RST=$(tput sgr0)
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
CYAN=$(tput setaf 6)
VERBOSE=

echoinfo() {
	>&2 echo "${CYAN}$@${RST}"
}

echoerr() {
	>&2 echo "${RED}${BOLD}error:${RST}${RED} $@${RST}"
}

echowarn() {
	>&2 echo "${YELLOW}${BOLD}warning:${RST}${YELLOW} $@${RST}"
}

die() {
    echoerr "$@"
    exit 1
}

debug() {
	if [ -n "$VERBOSE" ]; then
		>&2 echo "$@"
	fi
}


# measuring executing time
# ------------------------

__time_started=

time_start() {
	__time_started=$(date +%s)
}

time_elapsed() {
	local fin=$(date +%s)
	echo $(( fin - __time_started ))
}


# config parsing
# --------------

read_config() {
	local config_file="$1"
	local dst="$2"

	[ -f "$config_file" ] || die "read_config: $config_file: no such file"

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
	done < <(cat "$config_file")

	[ -z "$failed" ]
}

check_config() {
	local var="$1"
	local keys="$2"

	local failed=

	for key in $keys; do
		if [ -z "$(eval "echo -n \${$var[$key]}")" ]; then
			echoerr "config: ${BOLD}${key}${RST}${RED} is missing"
			failed=1
		fi
	done

	[ -z "$failed" ]
}


# other functions
# ---------------

installed() {
	command -v "$1" > /dev/null
	return $?
}

download() {
	local source="$1"
	local target="$2"

	if installed curl; then
		curl -f -s -o "$target" "$source"
	elif installed wget; then
		wget -q -O "$target" "$source"
	else
		die "neither curl nor wget found, can't proceed"
	fi
}
