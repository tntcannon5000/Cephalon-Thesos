#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
usermod --append --groups docker thesos-deploy
install -d -m 0750 -o root -g thesos-deploy /etc/thesos
install -d -m 0770 -o thesos-deploy -g thesos-deploy /opt/thesos/releases
install -m 0755 -o root -g root "${script_dir}/deploy-release.sh" \
  /usr/local/sbin/thesos-deploy-release

cat > /etc/sudoers.d/thesos-deploy <<'EOF'
thesos-deploy ALL=(root) NOPASSWD: /bin/systemctl start thesos-backup.service
EOF
chmod 0440 /etc/sudoers.d/thesos-deploy
visudo --check --file=/etc/sudoers.d/thesos-deploy
echo "Deployment operations installed."
