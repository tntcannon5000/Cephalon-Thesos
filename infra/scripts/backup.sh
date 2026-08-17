#!/bin/sh
set -eu

backup_root="${BACKUP_ROOT:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-7}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${backup_root}/thesos-${timestamp}.dump"

mkdir -p "${backup_root}"
pg_dump --format=custom --file="${target}" "${DATABASE_URL}"
find "${backup_root}" -type f -name 'thesos-*.dump' -mtime "+${retention_days}" -delete
printf 'Created %s\n' "${target}"
