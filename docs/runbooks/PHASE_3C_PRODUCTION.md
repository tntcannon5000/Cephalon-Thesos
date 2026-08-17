# Phase 3C Production Operations

This runbook covers the private-alpha deployment at `chat.cephalonthesos.com`. The single
ARM64 OCI instance runs Caddy, the web application, API, worker, and PostgreSQL through Docker
Compose. Cloudflare proxies public HTTP traffic. OCI Object Storage holds encrypted database
backups; the age private key remains offline.

## Release path

Pushes to `main` run the web, API, PostgreSQL integration, and ARM64 container checks. A successful
run publishes immutable SHA-tagged images to GHCR and deploys that exact SHA through the protected
`production` GitHub environment. GitHub Actions connects as `thesos-deploy` using a dedicated key
and a pinned host key. The workflow sends its short-lived package token through standard input,
logs out after pulling, and does not leave a registry credential on the host.

`/usr/local/sbin/thesos-deploy-release` serializes deployments. It validates the manifest, pulls
the release, starts PostgreSQL, takes a pre-migration backup after the first release, applies
Alembic migrations, waits for service health, and atomically moves `/opt/thesos/current`. If an
application health check fails, it restores the previous application images. A schema rollback is
never automatic; use the encrypted pre-migration backup when a migration must be reversed.

## Host configuration

Production secrets live at `/etc/thesos/production.env` with owner `root`, group
`thesos-deploy`, and mode `0640`. The Cloudflare origin certificate and key live under
`/etc/thesos/tls`. Never place either location in Git or workflow logs.

The `DOCKER-USER` chain delegates to `THESOS-WEB-INGRESS`, which accepts established traffic and
Cloudflare IPv4 ranges on ports 80 and 443 and drops other traffic to those published ports. The
`thesos-cloudflare-firewall-refresh.timer` refreshes the address set daily. OCI's security list
must expose TCP 443 publicly so Cloudflare can reach the origin; SSH should remain restricted to
the administrator's current address.

## Initial identity bootstrap

After the first migration, run the idempotent command inside the API image:

```bash
cd /opt/thesos/current
docker compose --env-file /etc/thesos/production.env --env-file images.env \
  -f compose.production.yaml run --rm api python -m veris_api.manage bootstrap-access \
  --email niranjan.kewalramani@outlook.com \
  --email niranjan.kewalramani@gmail.com \
  --email oranjan@outlook.com \
  --admin-email niranjan.kewalramani@outlook.com
```

Register the selected administrator normally, verify the email, then enroll TOTP immediately and
store the one-time recovery codes offline.

## Backups

`thesos-backup.timer` runs at 03:17 UTC with a randomized delay. The database dump is streamed
directly into age encryption, so no plaintext dump is written to disk. The service creates a
checksum, uploads both files with OCI instance-principal authentication, and prunes the bucket to
seven recent backups plus four older weekly anchors. A five-GiB cap is enforced locally and in the
bucket to remain comfortably inside the Always Free storage allowance.

Run and inspect a backup manually:

```bash
sudo systemctl start thesos-backup.service
sudo systemctl status thesos-backup.service --no-pager
sudo journalctl -u thesos-backup.service -n 100 --no-pager
```

## Restore drill

1. Download one `.dump.age` object and its `.sha256` companion to an administrator workstation.
2. Verify the checksum before decrypting.
3. Decrypt with the offline age identity into a temporary dump on an encrypted workstation.
4. Restore into a new disposable PostgreSQL database using `pg_restore`; never test against the
   live database.
5. Run the current migrations and API readiness check against the restored database.
6. Securely remove the plaintext temporary dump and record the drill date and result.

Do not copy the age identity to the VM or Object Storage. A backup is not considered proven until
a disposable restore drill succeeds.

## Verification and incidents

After each deployment, verify the public static page, `/api/v1/health/live`,
`/api/v1/health/ready`, registration gating, email delivery, login, quota display, and an actual
streamed run. Confirm ordinary accounts receive `404` from admin routes.

For an application regression, redeploy a known-good commit or invoke the release script with a
known-good published SHA. For a suspected credential leak, revoke the affected provider key,
replace `/etc/thesos/production.env`, restart the affected services, and revoke sessions when an
identity key may have been exposed. For database damage, stop API and worker writes before restore.
Keep Cloudflare proxying enabled during normal operation so the origin firewall remains effective.
