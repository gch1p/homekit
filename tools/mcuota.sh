#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "$DIR/lib.bash"

if [ -d "$DIR/../venv" ]; then
	echoinfo "activating python venv"
	. "$DIR/../venv/bin/activate"
else
	echowarn "python venv not found"
fi

"$DIR/mcuota.py" "$@"