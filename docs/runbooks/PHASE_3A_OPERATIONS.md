# Phase 3A Operations

## Runtime topology

- `web`: immutable Vite build served by Caddy; `/api/*` is proxied to FastAPI.
- `api`: accepts and owns requests, streams stored events, and records cancellation intent. It never imports or executes the model agent.
- `worker`: exclusively claims persisted runs with a PostgreSQL lease, launches DBOS workflows, renews leases, propagates cancellation, records provider attempts, and purges expired data.
- `migrate`: one-shot Alembic role that must complete before API or worker startup.
- `postgres`: private application and DBOS database.
- `backup`: one-shot custom-format `pg_dump` image. Scheduling and encrypted object-storage upload are Phase 3C work.

Browser-local conversations and preferences remain local until Phase 3B introduces authenticated ownership. Phase 3A stores temporary run execution state; it does not create user profiles.

## Local startup

1. Install PostgreSQL 18 or Docker, then copy `.env.example` to `.env` and provide an OpenRouter key.
2. If PostgreSQL is native, create the `thesos` login and database matching `.env.example`.
3. Run `Launch Thesos.cmd` or `scripts/dev.ps1`.

The launcher applies `alembic upgrade head`, starts API, worker, and Vite separately, waits for `/api/v1/health/ready` and `/api/v1/health/worker`, then opens `http://127.0.0.1:5173`.

## Production images

Build every image for both supported architectures:

```sh
docker buildx bake -f infra/docker-bake.hcl
```

The API image is reused for API, worker, and migration roles. `infra/compose.production.yaml` requires immutable image tags in `infra/production.env.example`; SHA tags become mandatory in Phase 3C publishing.

Validate expanded Compose configuration before deployment:

```sh
docker compose --env-file infra/production.env -f infra/compose.production.yaml config --quiet
```

## Recovery contract

- Run insertion and `run.accepted` are one transaction.
- A worker claim uses `FOR UPDATE SKIP LOCKED`, a renewable lease, and a bounded retry count.
- Terminal state, safety disposition, title, and terminal event commit together.
- Event sequence allocation locks the parent run, so reconnects can replay with `Last-Event-ID` without gaps or duplicates.
- Cancellation is persisted by the API and observed by the worker, which cancels both the local task and DBOS workflow.
- Idempotency is scoped to the current anonymous session in Phase 3A and moves to authenticated ownership in Phase 3B.

## Retention and accounting

Terminal runs expire after `RUN_RETENTION_DAYS` (30 by default). The worker deletes expired application rows and their DBOS workflow records. Provider accounting records requested and resolved models, provider, token counts, best-effort cost, latency, request ID, outcome, and cancellation point.

Inspect local state with:

```sql
SELECT status, count(*) FROM agent_run GROUP BY status;
SELECT provider, status, count(*), sum(total_tokens), sum(estimated_cost_usd)
FROM provider_usage GROUP BY provider, status;
```
