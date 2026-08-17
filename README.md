# Thesos

Thesos is an unofficial, Warframe-centered conversational archive. This repository contains the local alpha frontend, API, persistence layer, and initial bounded LLM loop.

## Local alpha

Requirements:

- Node.js 22 or newer
- pnpm
- Python 3.12
- uv
- PostgreSQL 18, either installed locally or available through Docker

Run `Launch Thesos.cmd` from Windows Explorer, or run `scripts/dev.ps1` from PowerShell. The launcher installs locked dependencies, starts PostgreSQL when Docker is available, applies migrations, then starts the API, agent worker, and frontend as separate processes. It opens the app only after both API and worker health checks pass.

PostgreSQL is authoritative for application and DBOS state in development and production. SQLite is used only by isolated unit tests. The local PostgreSQL URL and role are documented in `.env.example`; production topology and operations live under `infra/`.

## Repository layout

```text
apps/web       React, TypeScript, Vite, Tailwind, Three.js
apps/api       FastAPI, Pydantic AI, DBOS, SQLAlchemy, Alembic
docs           Product, architecture, prompting, and visual references
infra          Deployment-oriented service definitions
scripts        Local development and verification entry points
```

The hosted runtime contract and recovery checks are documented in
`docs/runbooks/PHASE_3A_OPERATIONS.md`. Private-alpha identity, access bootstrap, quotas, and
administration are documented in `docs/runbooks/PHASE_3B_PRIVATE_ALPHA.md`.

This is an unofficial fan project and is not affiliated with Digital Extremes.
