#!/bin/bash

DIR=/var/lib/clickhouse/backup
MAX_COUNT=3
NAME=backup_$(date -u +%Y-%m-%d)

create() {
	local name="$1"
	clickhouse-backup create "$name"
}

del() {
	local name="$1"
	clickhouse-backup delete local "$name"
}

# create a backup
create "$NAME"

# compress backup
cd "$DIR"
tar czvf $NAME.tar.gz $NAME

# delete uncompressed files
del "$NAME"

# delete old backups
for file in $(ls -t "${DIR}" | tail -n +$(( MAX_COUNT+1 ))); do
	echo "removing $file..."
	rm "$file"
done