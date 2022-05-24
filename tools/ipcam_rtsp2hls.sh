#!/bin/bash

PROGNAME="$0"
OUTDIR=/var/ipcamfs # should be tmpfs
PORT=554
NAME=
IP=
USER=
PASSWORD=
DEBUG=0
CHANNEL=1
FORCE_UDP=0
FORCE_TCP=0

die() {
  echo >&2 "error: $@"
  exit 1
}

usage() {
  cat <<EOF
usage: $PROGNAME [OPTIONS] COMMAND

Options:
  --ip    camera IP
  --port  RTSP port (default: 554)
  --name  camera name (chunks will be stored under $OUTDIR/{name}/)
  --user
  --password
  --debug
  --force-tcp
  --force-udp
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
    --ip|--port|--name|--user|--password)
      _var=${1:2}
      _var=${_var^^}
      printf -v "$_var" '%s' "$2"
      shift
      ;;

    --debug)
      DEBUG=1
      ;;

    --force-tcp)
      FORCE_TCP=1
      ;;

    --force-udp)
      FORCE_UDP=1
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

[ -z "$IP" ] && die "You must specify camera IP address (--ip)."
[ -z "$PORT" ] && die "Port can't be empty."
[ -z "$NAME" ] && die "You must specify camera name (--name)."
[ -z "$USER" ] && die "You must specify username (--user)."
[ -z "$PASSWORD" ] && die "You must specify username (--password)."
validate_channel "$CHANNEL"

if [ ! -d "${OUTDIR}/${NAME}" ]; then
  mkdir "${OUTDIR}/${NAME}" || die "Failed to create ${OUTDIR}/${NAME}!"
fi

args=
if [ "$DEBUG" = "1" ]; then
  args="-v info"
else
  args="-nostats -loglevel error"
fi

if [ "$FORCE_TCP" = "1" ]; then
  args="$args -rtsp_transport tcp"
elif [ "$FORCE_UDP" = "1" ]; then
  args="$args -rtsp_transport udp"
fi

ffmpeg $args -i rtsp://${USER}:${PASSWORD}@${IP}:${PORT}/Streaming/Channels/${CHANNEL} \
  -c:v copy -c:a copy -bufsize 1835k \
  -pix_fmt yuv420p \
  -flags -global_header -hls_time 2 -hls_list_size 3 -hls_flags delete_segments \
  ${OUTDIR}/${NAME}/live.m3u8
