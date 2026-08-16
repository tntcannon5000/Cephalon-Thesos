# Infrastructure

The local alpha defaults to SQLite so it can run without a resident database service. The production profile uses PostgreSQL for application and DBOS state. `compose.yaml` provides a development PostgreSQL service when Docker is available; the OCI deployment manifest will be added in the infrastructure phase.

