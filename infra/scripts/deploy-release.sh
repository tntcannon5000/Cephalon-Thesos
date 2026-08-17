#!/usr/bin/env bash
set -euo pipefail

if [[ "${USER}" != "thesos-deploy" ]]; then
  echo "Run this script as thesos-deploy." >&2
  exit 1
fi
if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: thesos-deploy-release <40-character-git-sha>" >&2
  exit 1
fi

release_sha=$1
release_root=/opt/thesos/releases
release_dir="${release_root}/${release_sha}"
compose_file="${release_dir}/compose.production.yaml"
image_env="${release_dir}/images.env"
production_env=/etc/thesos/production.env
current_link=/opt/thesos/current

exec 9>/run/lock/thesos-deploy.lock
flock -n 9 || { echo "Another deployment is already active." >&2; exit 1; }

test -r "${compose_file}"
test -r "${production_env}"
cat > "${image_env}" <<EOF
THESOS_API_IMAGE=ghcr.io/tntcannon5000/cephalon-thesos-api:${release_sha}
THESOS_WEB_IMAGE=ghcr.io/tntcannon5000/cephalon-thesos-web:${release_sha}
THESOS_BACKUP_IMAGE=ghcr.io/tntcannon5000/cephalon-thesos-backup:${release_sha}
EOF
chmod 0600 "${image_env}"

compose() {
  docker compose --env-file "${production_env}" --env-file "${image_env}" \
    --file "${compose_file}" "$@"
}

compose config --quiet
compose pull
compose up --detach postgres

for _ in $(seq 1 40); do
  health=$(docker inspect --format '{{.State.Health.Status}}' thesos-postgres-1 2>/dev/null || true)
  [[ "${health}" == "healthy" ]] && break
  sleep 3
done
[[ "${health:-}" == "healthy" ]] || { echo "PostgreSQL did not become healthy." >&2; exit 1; }

previous_release=""
if [[ -L "${current_link}" ]]; then
  previous_release=$(readlink -f "${current_link}")
  sudo /bin/systemctl start thesos-backup.service
fi

if ! compose run --rm migrate; then
  echo "Database migration failed; the current application remains selected." >&2
  exit 1
fi

if ! compose up --detach --wait --wait-timeout 180 postgres api worker web; then
  echo "Release health checks failed." >&2
  if [[ -n "${previous_release}" && -d "${previous_release}" ]]; then
    previous_images="${previous_release}/images.env"
    previous_compose="${previous_release}/compose.production.yaml"
    docker compose --env-file "${production_env}" --env-file "${previous_images}" \
      --file "${previous_compose}" up --detach --wait --wait-timeout 180 \
      postgres api worker web
  fi
  exit 1
fi

ln -sfn "${release_dir}" "${current_link}.next"
mv -Tf "${current_link}.next" "${current_link}"

find "${release_root}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -nr | tail -n +6 | cut -d' ' -f2- \
  | while IFS= read -r old_release; do
      [[ "${old_release}" == "$(readlink -f "${current_link}")" ]] || rm -rf "${old_release}"
    done
docker image prune --force --filter until=168h >/dev/null
echo "Activated Thesos release ${release_sha}."
