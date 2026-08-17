#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  ipset \
  jq \
  unattended-upgrades

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc

. /etc/os-release
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt-get update
apt-get install -y --no-install-recommends \
  containerd.io \
  docker-buildx-plugin \
  docker-ce \
  docker-ce-cli \
  docker-compose-plugin

install -m 0755 -d /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "live-restore": true,
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "no-new-privileges": true,
  "userland-proxy": false
}
EOF

systemctl enable --now docker

systemctl disable --now rpcbind.service rpcbind.socket 2>/dev/null || true
systemctl mask rpcbind.service rpcbind.socket

if id veris-deploy >/dev/null 2>&1 && ! id thesos-deploy >/dev/null 2>&1; then
  usermod --login thesos-deploy veris-deploy
  groupmod --new-name thesos-deploy veris-deploy
  usermod --home /home/thesos-deploy --move-home thesos-deploy
fi
if ! id thesos-deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash thesos-deploy
fi
usermod --append --groups docker thesos-deploy
passwd --lock thesos-deploy >/dev/null

install -d -m 0700 -o thesos-deploy -g thesos-deploy /home/thesos-deploy/.ssh
if [[ -s /home/ubuntu/.ssh/authorized_keys ]]; then
  install -m 0600 -o thesos-deploy -g thesos-deploy \
    /home/ubuntu/.ssh/authorized_keys \
    /home/thesos-deploy/.ssh/authorized_keys
else
  echo "Missing ubuntu authorized_keys; refusing to harden SSH." >&2
  exit 1
fi

install -d -m 0750 -o root -g thesos-deploy /opt/thesos
install -d -m 0770 -o thesos-deploy -g thesos-deploy /opt/thesos/releases
install -d -m 0750 -o root -g thesos-deploy /etc/thesos

cat > /etc/ssh/sshd_config.d/90-thesos-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
AllowUsers ubuntu thesos-deploy
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitTunnel no
EOF

sshd -t
systemctl reload ssh

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

install -d -m 0755 /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/90-thesos-limits.conf <<'EOF'
[Journal]
SystemMaxUse=512M
RuntimeMaxUse=128M
MaxRetentionSec=30day
Compress=yes
EOF
systemctl restart systemd-journald

hostnamectl set-hostname thesos-prod-01

echo "Host bootstrap complete."
docker version --format 'Docker Engine {{.Server.Version}}'
docker compose version
if [[ -f /var/run/reboot-required ]]; then
  echo "REBOOT_REQUIRED=yes"
else
  echo "REBOOT_REQUIRED=no"
fi
