#!/bin/bash

PROGNAME="$0"
PORT=554
IP=
CREDS=
DEBUG=0
CHANNEL=1

die() {
  echo >&2 "error: $@"
  exit 1
}

usage() {
  cat <<EOF
usage: $PROGNAME [OPTIONS] COMMAND

Options:
  --outdir  output directory
  --ip      camera IP
  --port    RTSP port (default: 554)
  --creds
  --debug
  --channel 1|2

EOF
  exit
}

validate_channel() {
  local c="$1"
  case "$c" in
    1|2)
      :
      ;;
    *)
      die "Invalid channel"
      ;;
    esac
}

[ -z "$1" ] && usage

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ip|--port|--creds|--outdir)
      _var=${1:2}
      _var=${_var^^}
      printf -v "$_var" '%s' "$2"
      shift
      ;;

    --debug)
      DEBUG=1
      ;;

    --channel)
      CHANNEL="$2"
      shift
      ;;

    *)
      die "Unrecognized argument: $1"
      ;;
  esac
  shift
done

[ -z "$OUTDIR" ] && die "You must specify output directory (--outdir)."
[ -z "$IP" ] && die "You must specify camera IP address (--ip)."
[ -z "$PORT" ] && die "Port can't be empty."
[ -z "$CREDS" ] && die "You must specify credentials (--creds)."
validate_channel "$CHANNEL"

if [ ! -d "${OUTDIR}" ]; then
  mkdir "${OUTDIR}" || die "Failed to create ${OUTDIR}/${NAME}!"
  echo "Created $OUTDIR."
fi

if [ "$DEBUG" = "1" ]; then
  args="-v info"
else
  args="-nostats -loglevel warning"
fi

[ ! -z "$CREDS" ] && CREDS="${CREDS}@"

ffmpeg $args -i rtsp://${CREDS}${IP}:${PORT}/Streaming/Channels/${CHANNEL} \
  -c copy -f segment -strftime 1 -segment_time 00:10:00 -segment_atclocktime 1 \
  "$OUTDIR/record_%Y-%m-%d-%H.%M.%S.mp4"
