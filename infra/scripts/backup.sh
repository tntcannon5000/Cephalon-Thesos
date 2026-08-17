#!/bin/sh
set -eu

backup_root="${BACKUP_ROOT:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-2}"
max_local_bytes="${BACKUP_MAX_LOCAL_BYTES:-5368709120}"
: "${BACKUP_AGE_RECIPIENT:?Set BACKUP_AGE_RECIPIENT}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${backup_root}/thesos-${timestamp}.dump.age"
partial="${target}.partial"

umask 077
mkdir -p "${backup_root}"
find "${backup_root}" -type f \( -name 'thesos-*.dump.age' -o -name 'thesos-*.dump.age.sha256' \) \
  -mtime "+${retention_days}" -delete

trap 'rm -f "${partial}"' EXIT
pg_dump --format=custom "${DATABASE_URL}" \
  | age --encrypt --recipient "${BACKUP_AGE_RECIPIENT}" --output "${partial}"
mv "${partial}" "${target}"
(
  cd "${backup_root}"
  sha256sum "$(basename "${target}")" > "$(basename "${target}").sha256"
)

local_bytes=$(find "${backup_root}" -type f -name 'thesos-*.dump.age' \
  -exec stat -c '%s' {} + | awk '{ total += $1 } END { print total + 0 }')
if [ "${local_bytes}" -gt "${max_local_bytes}" ]; then
  rm -f "${target}" "${target}.sha256"
  echo "Backup staging would exceed ${max_local_bytes} bytes." >&2
  exit 1
fi

printf 'Created %s\n' "${target}"
