# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.8.12 AS uv
FROM python:3.12.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/apps/api/.venv/bin:$PATH"

RUN groupadd --system --gid 10001 thesos \
    && useradd --system --uid 10001 --gid thesos --home-dir /app thesos

COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./apps/api/
RUN uv sync --project apps/api --frozen --no-dev --no-install-project

COPY apps/api ./apps/api
RUN uv sync --project apps/api --frozen --no-dev \
    && chown -R thesos:thesos /app

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "veris_api"]
