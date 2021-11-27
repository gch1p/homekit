#!/bin/bash

PROGNAME="$0"
NODE_CONFIG="/etc/sound_node.toml"
REMOTE_USER=user
REMOTE_SERVER=solarmon.ru
REMOTE_DIRECTORY=/var/recordings

set -e

echoerr() {
	>&2 echo "error: $@"
}

echowarn() {
	>&2 echo "warning: $@"
}

telegram_alert() {
	if [ -z "$TG_TOKEN" ] || [ -z "$TG_CHAT_ID" ]; then return; fi
	curl -X POST \
		-F "chat_id=${TG_CHAT_ID}" \
		-F "text=$1" \
		"https://api.telegram.org/bot${TG_TOKEN}/sendMessage"
}

fatal() {
	echoerr "$@"
	telegram_alert "$PROGNAME: $@"
	exit 1
}

get_config_var() {
	local varname="$1"
	cat "$NODE_CONFIG"  | grep "^$varname = \"" | awk '{print $3}' | tr -d '"'
}

get_mp3_count() {
	find "$LOCAL_DIR" -mindepth 1 -type f -name "*.mp3" -printf x | wc -c
}

[ -z "$TG_TOKEN" ] && echowarn "TG_TOKEN is not set"
[ -z "$TG_CHAT_ID" ] && echowarn "TG_CHAT_ID is not set"

NODE_NAME=$(get_config_var name)
LOCAL_DIR=$(get_config_var storage)

[ -z "$NODE_NAME" ] && fatal "failed to parse NODE_NAME"
[ -z "$LOCAL_DIR" ] && fatal "failed to parse LOCAL_DIR"

[ -d "$LOCAL_DIR" ] || fatal "$LOCAL_DIR is not a directory"

COUNT=$(get_mp3_count)
(( $COUNT < 1 )) && {
	echo "seems there's nothing to sync"
	exit
}

cd "$LOCAL_DIR" || fatal "failed to change to $LOCAL_DIR"

rsync -azPv -e "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR" \
	*.mp3 \
	${REMOTE_USER}@${REMOTE_SERVER}:"${REMOTE_DIRECTORY}/${NODE_NAME}/" \
	--exclude temp.mp3

RC=$?

if [ $RC -eq 0 ]; then
	find "$LOCAL_DIR" -name "*.mp3" -type f -mmin +1440 -delete || fatal "find failed to delete old files"
else
	fatal "failed to rsync: code $RC"
fi
