# Infrastructure

PostgreSQL is authoritative for both application and DBOS state in development and production. `scripts/dev.ps1` starts the database from `compose.yaml`, migrates it, then runs the API, agent worker, and Vite as separate processes. SQLite is retained only for isolated unit tests.

The production-shaped topology is defined in `infra/compose.production.yaml`. It keeps PostgreSQL private, serves the static frontend through Caddy, and runs migrations, API traffic, model work, and backups as separate container roles.
