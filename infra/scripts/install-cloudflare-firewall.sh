#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

apt-get update
apt-get install -y --no-install-recommends curl ipset

install -m 0755 -o root -g root \
  "${script_dir}/update-cloudflare-firewall.sh" \
  /usr/local/sbin/thesos-update-cloudflare-firewall

cat > /etc/systemd/system/thesos-cloudflare-firewall.service <<'EOF'
[Unit]
Description=Apply the Thesos Cloudflare-only Docker ingress policy
Wants=network-online.target
After=network-online.target
Before=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/thesos-update-cloudflare-firewall
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/thesos-cloudflare-firewall-refresh.service <<'EOF'
[Unit]
Description=Refresh the Thesos Cloudflare IP allowlist
Wants=network-online.target docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/thesos-update-cloudflare-firewall
EOF

cat > /etc/systemd/system/thesos-cloudflare-firewall-refresh.timer <<'EOF'
[Unit]
Description=Refresh the Thesos Cloudflare IP allowlist daily

[Timer]
OnBootSec=10min
OnUnitActiveSec=1d
RandomizedDelaySec=30min
Persistent=true

[Install]
WantedBy=timers.target
EOF

install -d -m 0755 /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/20-thesos-firewall.conf <<'EOF'
[Unit]
Requires=thesos-cloudflare-firewall.service
After=thesos-cloudflare-firewall.service
EOF

systemctl daemon-reload
systemctl enable thesos-cloudflare-firewall.service
systemctl enable --now thesos-cloudflare-firewall-refresh.timer
/usr/local/sbin/thesos-update-cloudflare-firewall

echo "Cloudflare ingress policy installed."
