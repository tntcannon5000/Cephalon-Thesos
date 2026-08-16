# Thesos: OCI VM Manifest

Status: proposed production baseline  
Cost target: OCI Always Free limits only  
Architecture: one VM, one attached data volume, one Object Storage bucket

This document describes the intended first production host for Thesos. It is a deployment contract, not yet an applied Terraform configuration. Values marked `TBD` must be selected when the OCI tenancy and domain are ready.

## 1. Physical Topology

```text
Cloudflare DNS, proxy, cache, and Turnstile
                    |
                    v
        OCI public IPv4: ports 80/443
                    |
                    v
       One VM.Standard.A1.Flex VM
       - Caddy
       - static frontend
       - FastAPI application
       - PostgreSQL + pgvector
       - temporary ingestion jobs
       - temporary backup jobs
                    |
          +---------+----------+
          |                    |
          v                    v
  attached block volume   OCI Object Storage
  PostgreSQL + state      encrypted backups and
                          compressed source snapshots
```

The named application components are containers on the same Linux host. They are not separate VMs or separately allocated compute instances.

## 2. OCI Resource Inventory

| Resource | Quantity | Proposed configuration | Purpose |
|---|---:|---|---|
| Compartment | 1 | `thesos-prod` | Cost, policy, and resource boundary |
| VCN | 1 | `10.20.0.0/16` | Application network |
| Public subnet | 1 | `10.20.10.0/24` | Initial single-VM subnet |
| Internet gateway | 1 | Attached to VCN | HTTPS and outbound API access |
| Route table | 1 | `0.0.0.0/0` to internet gateway | Public routing |
| Network security group | 1 | Rules defined below | VM firewall boundary |
| Ampere A1 VM | 1 | 2 OCPU, 12 GB RAM, ARM64 | All live application compute |
| Boot volume | 1 | 50 GB | Ubuntu, Docker, images, logs |
| Block volume | 1 | 100 GB | PostgreSQL and durable app data |
| Reserved block allowance | 50 GB | Leave unallocated | Recovery and growth headroom |
| Public IPv4 | 1 | Reserved if Always Free eligibility is confirmed | Stable DNS target |
| Object Storage bucket | 1 | Private, versioning off initially | Dumps and source snapshots |
| Block-volume backups | Up to 2 retained | Rotating data-volume backups | Rapid volume recovery |
| Monitoring alarms | 5-8 | CPU, memory, disk, health, backup age | Operations |
| Notifications topic | 1 | Email destination `TBD` | Alerts |

Do not provision an OCI load balancer, Autonomous Database, MySQL system, Kubernetes cluster, second VM, or public database endpoint for the initial release.

Current Oracle documentation must be checked again during provisioning. The planning ceiling is deliberately the conservative Always Free allocation of 2 OCPU, 12 GB RAM, and 200 GB combined boot/block storage in the tenancy's home region.

## 3. VM Definition

```yaml
name: thesos-prod-01
shape: VM.Standard.A1.Flex
architecture: arm64
ocpus: 2
memory_gb: 12
region: TBD_HOME_REGION
availability_domain: TBD
image: Ubuntu 24.04 LTS ARM64
boot_volume_gb: 50
data_volume_gb: 100
public_ip: true
```

The VM must use an Always Free-eligible image and be created in the tenancy's home region. All container images and native dependencies must support ARM64.

### Host packages

Install only:

- Docker Engine and the Docker Compose plugin.
- OCI monitoring/management agent where not already included.
- `fail2ban` only if SSH is publicly reachable.
- Minimal disk, network, and troubleshooting utilities.

Do not install Node.js, PostgreSQL, Python application dependencies, or build toolchains globally on the host. Production artifacts should be built elsewhere and delivered as pinned ARM64 container images.

### Host users

| User | Purpose |
|---|---|
| `ubuntu` | Initial OCI administration only |
| `veris-deploy` | Non-root deployment and service maintenance |
| `root` | System operations; direct SSH login disabled |

Password SSH authentication and direct root SSH login must be disabled. Administrative access should use SSH keys and either an IP allowlist or OCI Bastion.

## 4. Disk Layout

Mount the 100 GB attached volume by filesystem UUID, not device name.

```text
/srv/veris/
|-- postgres/            PostgreSQL data directory
|-- app-state/           Durable non-database application state
|-- corpus-staging/      Temporary ingestion workspace
|-- backup-staging/      Temporary encrypted database dumps
`-- models/              Pinned local embedding model files
```

Proposed filesystem: `ext4`, mounted with `defaults,noatime`. The mount must be present before Docker starts. Failure to mount must stop service startup so PostgreSQL cannot accidentally initialize on the boot volume.

Disk responsibilities:

```text
Boot volume
- operating system
- Docker engine and image layers
- static frontend files inside the Caddy image
- bounded system and container logs

Attached volume
- PostgreSQL data
- local embedding model
- ingestion workspace
- short-lived backup staging

Object Storage
- encrypted logical database backups
- selected compressed raw-source snapshots
- ingestion manifests needed to reproduce a corpus revision
```

Keep at least 20% free space on both mounted volumes. Temporary ingestion files must be deleted after a successful corpus publication.

## 5. Runtime Services

Use one `compose.yaml` project named `veris`.

### Continuously running

| Service | Replicas/processes | Target memory | Hard ceiling | Notes |
|---|---:|---:|---:|---|
| `caddy` | 1 | 50-100 MB | 256 MB | TLS, compression, static frontend, API proxy |
| `api` | 1 container, initially 2 Uvicorn workers | 0.8-1.8 GB | 2.5 GB | Async HTTP, RAG orchestration, streaming |
| `postgres` | 1 | 1.5-3 GB | 4 GB | Relational, full-text, and vector retrieval |

### Run only when needed

| Service | Concurrency | Hard ceiling | Trigger |
|---|---:|---:|---|
| `ingest` | 1 | 2.5 GB | Scheduled update or manual run |
| `backup` | 1 | 768 MB | Nightly timer and pre-migration |
| `migrate` | 1 | 512 MB | Explicit deployment step |

Container memory limits are safety rails, not reservations. The ingestion container must use reduced CPU and I/O priority and must never have more than one replica.

The production frontend is a static build served by Caddy. There is no permanent Vite, Node.js, Next.js, Celery, Redis, Elasticsearch, or model-serving process initially.

### API process policy

Start with:

```text
Uvicorn workers:                  2
PostgreSQL pool per worker:       min 1, max 5
Total ordinary app connections:  <= 10
Request body limit:               32 KiB for chat/API JSON unless route-specific
LLM generation concurrency:      controlled by provider-specific semaphores
Queue:                            short bounded in-memory queue
```

If the embedding model's per-worker memory is material, change to one API worker or one small local embedding sidecar after measurement. Do not duplicate a large model across workers by default.

## 6. PostgreSQL Manifest

### Engine and extensions

```yaml
engine: PostgreSQL
major_version: 17
image: pinned ARM64 image containing pgvector
database: veris
application_role: veris_app
migration_role: veris_migrate
backup_role: veris_backup
public_listener: false
```

Required extensions:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
```

Pin the exact PostgreSQL patch version, pgvector version, and image digest in deployment configuration. A major-version upgrade requires a tested dump/restore or `pg_upgrade` procedure and a fresh backup.

### Initial tuning

```ini
max_connections = 30
shared_buffers = 1536MB
effective_cache_size = 7GB
work_mem = 8MB
maintenance_work_mem = 512MB
wal_compression = on
max_wal_size = 2GB
checkpoint_completion_target = 0.9
huge_pages = try
log_min_duration_statement = 500ms
```

These are commissioning values, not permanent truths. Revisit them after recording production query latency, cache hit rate, connection use, WAL growth, autovacuum behavior, and memory pressure.

### Logical data domains

The initial schema should keep these domains distinct:

| Domain | Responsibility |
|---|---|
| `source` | Source identity, authority, crawl policy, and freshness |
| `document` | Canonical pages/resources and immutable revisions |
| `retrieval` | Chunks, full-text vectors, embeddings, and chunk/entity links |
| `game` | Warframe entities, aliases, versions, platforms, and structured facts |
| `answer` | Cached answers, citations, corpus revision, TTL, and invalidation group |
| `ingestion` | Runs, checkpoints, failures, and publication state |
| `operations` | Provider usage, anonymous rate-limit state, and audit events |

Do not store raw HTML or large API dumps indefinitely in PostgreSQL. Store their hashes and Object Storage keys. The active, parsed text needed for retrieval belongs in PostgreSQL.

### Index policy

- B-tree indexes for foreign keys, timestamps, source IDs, revisions, and cache keys.
- GIN indexes for PostgreSQL full-text search and selected JSONB fields.
- Trigram indexes for entity aliases and misspellings.
- HNSW pgvector indexes once the initial corpus is loaded and representative recall tests exist.
- Partial indexes for current document revisions and unexpired cache entries.
- No speculative indexes without query evidence; every index increases ingestion and storage cost.

## 7. Network and Ports

### OCI ingress

| Port | Source | Purpose |
|---:|---|---|
| 80/TCP | Internet initially, preferably Cloudflare ranges later | Redirect and certificate challenge |
| 443/TCP | Internet initially, preferably Cloudflare ranges later | Public application traffic |
| 22/TCP | Administrator IP allowlist only, or closed when using Bastion | SSH administration |

No other ingress is permitted. In particular, ports `5432`, `8000`, and Docker daemon ports must never be public.

### Container network

```text
caddy -> api:8000
api -> postgres:5432
ingest -> postgres:5432
backup -> postgres:5432
```

Only Caddy publishes host ports. PostgreSQL uses an internal Docker network and still requires password authentication. Caddy must discard spoofed forwarding headers and trust proxy headers only from the configured edge.

### Outbound access

Permit HTTPS for:

- Approved LLM providers.
- Approved Warframe corpus sources and APIs.
- OCI Object Storage.
- Container registry pulls and OS security updates.

Provider API keys must be stored in a root-owned environment file outside Git with mode `0600`. OCI Object Storage access should use an instance principal and IAM policy rather than a long-lived access key on disk.

## 8. Backups and Recovery

### Logical backups

Nightly backup procedure:

1. Run `pg_dump` in custom or directory format.
2. Compress where the selected dump format benefits from it.
3. Encrypt before leaving the VM.
4. Upload to the private Object Storage bucket.
5. Verify object size and checksum.
6. Record successful completion and corpus revision.
7. Remove local staging files.

Retention target, subject to the Always Free Object Storage capacity:

```text
daily:   7
weekly:  4
monthly: 2 once database size permits
```

Retention must be capacity-aware. Alert at 70% bucket use and stop retaining extra historical dumps before exceeding the free allowance.

### Volume backups

Retain up to two rotating attached-volume backups:

- One recent known-good backup.
- One backup taken before the latest significant database or host migration.

Logical dumps remain the portable recovery mechanism. Volume backups are the faster OCI-specific recovery mechanism.

### Recovery objectives

Initial non-commercial targets:

```text
RPO: 24 hours for ordinary data
RTO: 4 hours once deployment automation is complete
```

Purchased user accounts and irreplaceable user data are out of scope for the first anonymous release. If that changes, backup frequency and recovery objectives must be reconsidered.

A restore test must be performed at least quarterly and before declaring the service production-ready.

## 9. Scheduling and Workload Protection

Use host `systemd` timers to invoke temporary Compose jobs. Do not run a permanent scheduler process.

```text
Nightly:     logical PostgreSQL backup
Daily:       reset-sensitive structured data refresh
Weekly:      broader corpus reconciliation
Monthly:     restore drill reminder and dependency review
On deploy:   migration followed by health check
```

Ingestion rules:

- Incremental updates by source hash and revision.
- One embedding worker maximum.
- Small database transaction batches.
- Build new corpus revisions without replacing the active revision in place.
- Atomically activate only a fully processed revision.
- Pause or yield when API latency, CPU load, or database contention crosses configured thresholds.
- Major re-embedding jobs run manually during low traffic.

## 10. Observability

### Required metrics

- VM CPU, memory, load average, disk use, disk latency, and network traffic.
- Container restarts and OOM kills.
- API request rate, latency, status code, and active streams.
- Retrieval latency split into entity, lexical, vector, and reranking stages.
- PostgreSQL connections, slow queries, cache hit rate, locks, WAL, and autovacuum health.
- LLM calls, tokens where available, provider errors, queue depth, and cache hit rate.
- Ingestion duration, changed documents, failed documents, and active corpus revision.
- Last successful logical backup and last tested restore.

### Initial alerts

```text
disk use > 75% warning; > 85% critical
memory pressure or swap activity sustained for 10 minutes
API health check failing for 3 consecutive checks
PostgreSQL unavailable
backup older than 30 hours
repeated container restart or OOM kill
LLM provider error rate above configured threshold
```

Logs must be structured JSON where practical and rotated. Default application logs must not retain chat contents. Log request IDs, timings, provider route, token counts, cache status, and redacted error metadata.

## 11. Security Baseline

- Automatic installation of Ubuntu security updates; controlled reboot window.
- Docker socket accessible only to root and the deployment operator.
- Containers run as non-root where their images support it.
- Read-only container filesystems except declared temporary and persistent mounts.
- Drop unnecessary Linux capabilities and set `no-new-privileges`.
- PostgreSQL has no host-published port.
- Separate application, migration, and backup database roles with least privilege.
- Cloudflare rate limits and Turnstile protect expensive chat-generation paths.
- Backend independently enforces per-IP/session limits; edge controls are not the sole defense.
- Prompts and retrieved source text are treated as untrusted input.
- No secrets, raw chat histories, or personal data in source control or ordinary logs.
- Object Storage bucket remains private and backups are encrypted before upload.

## 12. Cost Guardrails

- Create every OCI resource in the home region unless a reviewed exception exists.
- Confirm the `Always Free-eligible` label before creating compute and storage resources.
- Keep the combined boot and block allocation at or below 200 GB.
- Keep Object Storage data and request volume below the current Always Free limits.
- Configure an OCI budget alert at the smallest useful nonzero threshold; understand that budgets alert but do not automatically stop spending.
- Add compartment quotas where OCI supports a useful hard ceiling.
- Tag all resources with `project=thesos`, `environment=production`, and `cost_class=always-free`.
- Do not enable a paid shape, paid database, paid load balancer tier, cross-region copy, or excess backup retention without an explicit manifest revision.

## 13. Deployment and Rebuild Contract

The VM is disposable; its data is not. A clean replacement VM must be reproducible from:

```text
Terraform/OpenTofu configuration
cloud-init host bootstrap
Docker Compose configuration
pinned ARM64 images
database migrations
encrypted Object Storage backup
documented DNS and IAM settings
```

Normal deployment sequence:

1. Build and test ARM64 images outside the production VM.
2. Pull images by immutable digest.
3. Run the one-shot migration container.
4. Start or update Caddy, API, and PostgreSQL with Compose.
5. Verify database, retrieval, generation, citation, and streaming health checks.
6. Roll back application images if health checks fail; never reverse a database migration blindly.

## 14. Commissioning Gates

The service is not ready for public traffic until all of these pass:

- VM and attached volume can be recreated from infrastructure code.
- PostgreSQL refuses public network access.
- A logical dump restores successfully into an empty database.
- Rebooting the VM automatically mounts the data volume and restores services.
- Missing data-volume mounts prevent PostgreSQL startup.
- Cloudflare-to-origin TLS operates in strict mode.
- ARM64 images build and pass tests.
- Load test covers cached responses, retrieval-only requests, and simultaneous streamed generations.
- Ingestion runs concurrently without unacceptable interactive latency, or pauses correctly.
- Rate limits prevent one client from exhausting provider quotas.
- Monitoring detects a deliberately stopped API and a stale backup.

## 15. Decisions Still Open

- OCI home region and availability domain.
- Final public domain and origin hostname.
- Reserved versus ephemeral public IPv4 eligibility and choice.
- Exact PostgreSQL 17 patch and pgvector image digest.
- Query embedding model, dimensions, runtime, and memory footprint.
- Whether API workers share a singleton embedding service after benchmarking.
- LLM provider concurrency and daily-budget policies.
- External off-OCI backup destination for tenancy-level disaster recovery.
- Exact corpus sources, update cadence, and storage retention per source.

Any decision that changes recurring cost, introduces another always-running service, exposes another public port, or stores user conversations must update this manifest first.
