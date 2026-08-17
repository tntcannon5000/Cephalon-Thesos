#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3-venv

python3 -m venv /opt/thesos/oci-cli
/opt/thesos/oci-cli/bin/pip install --no-cache-dir --disable-pip-version-check oci-cli==3.90.2

install -d -m 0755 -o root -g root /usr/local/libexec
install -m 0755 -o root -g root "${script_dir}/upload-backup.sh" \
  /usr/local/sbin/thesos-upload-backup
install -m 0755 -o root -g root "${script_dir}/prune-object-storage.py" \
  /usr/local/libexec/thesos-prune-object-storage

cat > /etc/systemd/system/thesos-backup.service <<'EOF'
[Unit]
Description=Create and upload an encrypted Thesos PostgreSQL backup
Wants=network-online.target docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
EnvironmentFile=/etc/thesos/backup.env
ExecStart=/usr/local/sbin/thesos-upload-backup
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

cat > /etc/systemd/system/thesos-backup.timer <<'EOF'
[Unit]
Description=Run the Thesos database backup each night

[Timer]
OnCalendar=*-*-* 03:17:00 UTC
RandomizedDelaySec=20min
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable thesos-backup.timer
echo "Backup operations installed; timer remains idle until the application is deployed."
