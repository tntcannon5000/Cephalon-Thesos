#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

storage_root=/srv/thesos
minimum_free_kib=$((10 * 1024 * 1024))
postgres_uid=70
postgres_gid=70

install -d -m 0755 -o root -g root "${storage_root}"

root_source=$(findmnt --noheadings --output SOURCE --target /)
storage_source=$(findmnt --noheadings --output SOURCE --target "${storage_root}")
if [[ "${root_source}" != "${storage_source}" ]]; then
  echo "${storage_root} unexpectedly resolves to a different filesystem." >&2
  exit 1
fi

install -d -m 0700 -o "${postgres_uid}" -g "${postgres_gid}" \
  "${storage_root}/postgres" \
  "${storage_root}/backup-staging"
install -d -m 0770 -o root -g thesos-deploy \
  "${storage_root}/app-state" \
  "${storage_root}/corpus-staging"
install -d -m 0750 -o root -g thesos-deploy \
  "${storage_root}/indexes"

if [[ ! -e "${storage_root}/.thesos-storage-root" ]]; then
  printf 'storage=boot-volume\ncreated_at=%s\n' "$(date --utc +%FT%TZ)" \
    > "${storage_root}/.thesos-storage-root"
fi
chmod 0600 "${storage_root}/.thesos-storage-root"
chown root:root "${storage_root}/.thesos-storage-root"

cat > /usr/local/sbin/thesos-storage-guard <<EOF
#!/usr/bin/env bash
set -euo pipefail
storage_root=${storage_root}
minimum_free_kib=${minimum_free_kib}

test -f "\${storage_root}/.thesos-storage-root"
test ! -L "\${storage_root}"
test ! -L "\${storage_root}/postgres"
test ! -L "\${storage_root}/backup-staging"

root_source=\$(findmnt --noheadings --output SOURCE --target /)
storage_source=\$(findmnt --noheadings --output SOURCE --target "\${storage_root}")
test "\${root_source}" = "\${storage_source}"

available_kib=\$(df --output=avail "\${storage_root}" | tail -n 1 | tr -d ' ')
if (( available_kib < minimum_free_kib )); then
  echo "Insufficient free space under \${storage_root}: \${available_kib} KiB" >&2
  exit 1
fi
EOF
chmod 0755 /usr/local/sbin/thesos-storage-guard
chown root:root /usr/local/sbin/thesos-storage-guard

cat > /etc/systemd/system/thesos-storage-guard.service <<'EOF'
[Unit]
Description=Validate Thesos production storage before Docker starts
Before=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/thesos-storage-guard
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

install -d -m 0755 /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/30-thesos-storage.conf <<'EOF'
[Unit]
Requires=thesos-storage-guard.service
After=thesos-storage-guard.service
EOF

systemctl daemon-reload
systemctl enable thesos-storage-guard.service
/usr/local/sbin/thesos-storage-guard

echo "Prepared ${storage_root} on ${storage_source}."
df -h "${storage_root}"
