# syntax=docker/dockerfile:1.7
FROM node:22.22.0-alpine3.23 AS build
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web ./apps/web
RUN pnpm --filter @thesos/web build

FROM caddy:2.10.2-alpine AS runtime
COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/apps/web/dist /srv
