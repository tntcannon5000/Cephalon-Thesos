#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

state_dir=/etc/thesos/firewall
cidr_file="${state_dir}/cloudflare-ips-v4.txt"
candidate=$(mktemp)
trap 'rm -f "${candidate}"' EXIT
public_interface=$(ip -4 route show default | awk 'NR == 1 {print $5}')

if [[ -z "${public_interface}" ]]; then
  echo "Could not determine the public network interface." >&2
  exit 1
fi

install -d -m 0700 -o root -g root "${state_dir}"

if curl --fail --silent --show-error --location \
  --proto '=https' --tlsv1.2 \
  https://www.cloudflare.com/ips-v4 -o "${candidate}"; then
  python3 - "${candidate}" <<'PY'
import ipaddress
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
networks = [line.strip() for line in path.read_text().splitlines() if line.strip()]
if len(networks) < 10:
    raise SystemExit("Cloudflare IPv4 response contained too few networks")
for network in networks:
    parsed = ipaddress.ip_network(network, strict=True)
    if parsed.version != 4:
        raise SystemExit(f"Unexpected non-IPv4 network: {network}")
PY
  install -m 0600 -o root -g root "${candidate}" "${cidr_file}"
elif [[ ! -s "${cidr_file}" ]]; then
  echo "No valid Cloudflare IPv4 allowlist is available." >&2
  exit 1
fi

ipset create thesos_cloudflare4 hash:net family inet -exist
ipset create thesos_cloudflare4_next hash:net family inet -exist
ipset flush thesos_cloudflare4_next
while IFS= read -r network; do
  [[ -n "${network}" ]] && ipset add thesos_cloudflare4_next "${network}"
done < "${cidr_file}"
ipset swap thesos_cloudflare4_next thesos_cloudflare4
ipset destroy thesos_cloudflare4_next

iptables -N THESOS-WEB-INGRESS 2>/dev/null || true
iptables -F THESOS-WEB-INGRESS
iptables -A THESOS-WEB-INGRESS \
  -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
iptables -A THESOS-WEB-INGRESS \
  -i "${public_interface}" \
  -m set --match-set thesos_cloudflare4 src \
  -p tcp -m multiport --dports 80,443 -j RETURN
iptables -A THESOS-WEB-INGRESS \
  -i "${public_interface}" \
  -p tcp -m multiport --dports 80,443 -j DROP
iptables -A THESOS-WEB-INGRESS -j RETURN

iptables -N DOCKER-USER 2>/dev/null || true
iptables -C DOCKER-USER -j THESOS-WEB-INGRESS 2>/dev/null \
  || iptables -I DOCKER-USER 1 -j THESOS-WEB-INGRESS

echo "Applied $(ipset list thesos_cloudflare4 | awk '/Number of entries:/ {print $4}') Cloudflare IPv4 networks."
