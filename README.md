# Thesos

Thesos is an unofficial, Warframe-centered conversational archive. This repository contains the local alpha frontend, API, persistence layer, and initial bounded LLM loop.

## Local alpha

Requirements:

- Node.js 22 or newer
- pnpm
- Python 3.12
- uv

Run `Launch Thesos.cmd` from Windows Explorer, or run `scripts/dev.ps1` from PowerShell. The launcher installs locked dependencies, prepares the local database, starts both services, waits for readiness, and opens the app.

The zero-install local profile uses SQLite. Deployment configuration targets PostgreSQL by changing `DATABASE_URL` and `DBOS_SYSTEM_DATABASE_URL`; application code and migrations use SQLAlchemy-compatible schemas.

## Repository layout

```text
apps/web       React, TypeScript, Vite, Tailwind, Three.js
apps/api       FastAPI, Pydantic AI, DBOS, SQLAlchemy, Alembic
docs           Product, architecture, prompting, and visual references
infra          Deployment-oriented service definitions
scripts        Local development and verification entry points
```

This is an unofficial fan project and is not affiliated with Digital Extremes.
