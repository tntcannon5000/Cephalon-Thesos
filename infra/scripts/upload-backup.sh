#!/usr/bin/env bash
set -euo pipefail

: "${THESOS_BACKUP_BUCKET:?Set THESOS_BACKUP_BUCKET}"
: "${THESOS_BACKUP_REGION:?Set THESOS_BACKUP_REGION}"

compose_file=${THESOS_COMPOSE_FILE:-/opt/thesos/current/compose.production.yaml}
image_env=${THESOS_IMAGE_ENV:-/opt/thesos/current/images.env}
production_env=${THESOS_PRODUCTION_ENV:-/etc/thesos/production.env}
staging_root=${THESOS_BACKUP_STAGING:-/srv/thesos/backup-staging}
maximum_bytes=${THESOS_BACKUP_MAX_BYTES:-5368709120}
oci_cli=${OCI_CLI:-/opt/thesos/oci-cli/bin/oci}
pruner=${THESOS_BACKUP_PRUNER:-/usr/local/libexec/thesos-prune-object-storage}

exec 9>/run/lock/thesos-backup.lock
flock -n 9 || { echo "Another backup operation is already active." >&2; exit 1; }

test -x "${oci_cli}"
test -x "${pruner}"
test -r "${compose_file}"
test -r "${image_env}"
test -r "${production_env}"

docker compose --env-file "${production_env}" --env-file "${image_env}" \
  --file "${compose_file}" \
  --profile operations run --rm backup

encrypted=$(find "${staging_root}" -maxdepth 1 -type f -name 'thesos-*.dump.age' \
  -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)
test -n "${encrypted}"
checksum="${encrypted}.sha256"
test -f "${checksum}"

inventory=$(mktemp)
trap 'rm -f "${inventory}"' EXIT
list_objects() {
  "${oci_cli}" os object list --auth instance_principal \
    --region "${THESOS_BACKUP_REGION}" \
    --bucket-name "${THESOS_BACKUP_BUCKET}" \
    --prefix postgres/ --all > "${inventory}"
}

list_objects
while IFS= read -r object_name; do
  [[ -n "${object_name}" ]] || continue
  "${oci_cli}" os object delete --auth instance_principal \
    --region "${THESOS_BACKUP_REGION}" \
    --bucket-name "${THESOS_BACKUP_BUCKET}" \
    --name "${object_name}" --force
done < <("${pruner}" "${inventory}" --daily 7 --weekly 4)

list_objects
remote_bytes=$("${pruner}" "${inventory}" --total-bytes)
candidate_bytes=$(stat -c '%s' "${encrypted}")
if (( remote_bytes + candidate_bytes > maximum_bytes )); then
  echo "Backup upload would exceed the ${maximum_bytes}-byte Object Storage ceiling." >&2
  exit 1
fi

day_path=$(date --utc +%Y/%m/%d)
object_name="postgres/${day_path}/$(basename "${encrypted}")"
"${oci_cli}" os object put --auth instance_principal \
  --region "${THESOS_BACKUP_REGION}" \
  --bucket-name "${THESOS_BACKUP_BUCKET}" \
  --name "${object_name}" --file "${encrypted}" --force >/dev/null
"${oci_cli}" os object put --auth instance_principal \
  --region "${THESOS_BACKUP_REGION}" \
  --bucket-name "${THESOS_BACKUP_BUCKET}" \
  --name "${object_name}.sha256" --file "${checksum}" --force >/dev/null

rm -f "${encrypted}" "${checksum}"
printf 'Uploaded encrypted backup %s (%s bytes).\n' "${object_name}" "${candidate_bytes}"
