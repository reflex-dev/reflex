# check=skip=JSONArgsRecommended
# Single-container Reflex deployment for services like Render, Railway, Heroku,
# GCP, and others. Caddy serves the exported frontend and proxies backend routes
# from a single exposed port; TLS termination is expected at the platform edge.

# If the service expects a different port, provide it here (f.e Render expects port 10000)
ARG PORT=8080
# Only set for local/direct access. When TLS is used, the API_URL is assumed to be the same as the frontend.
ARG API_URL

FROM python:3.13-slim AS builder

# uv installs python packages; reflex uses a bun found on PATH instead of downloading its own.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun
ENV UV_COMPILE_BYTECODE=1 UV_NO_CACHE=1 PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install python requirements first so app edits do not reinstall them.
COPY requirements.txt .
RUN uv venv && uv pip install -r requirements.txt

# Copy local context to `/app` inside container (see .dockerignore)
COPY . .

ARG PORT API_URL
# Compile the app and build the static frontend. The cache mount keeps bun's
# package cache between builds so unchanged dependencies are not downloaded again.
RUN --mount=type=cache,target=/root/.bun/install/cache \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT} reflex export --frontend-only --no-zip


# Final image: the python environment, the app source, the static frontend for
# caddy, and .web/backend so the backend only evaluates stateful pages at startup.
FROM python:3.13-slim

RUN apt-get update -y && apt-get install -y --no-install-recommends redis-server && rm -rf /var/lib/apt/lists/*
COPY --from=caddy:2 /usr/bin/caddy /usr/bin/caddy

ARG PORT
ENV PATH="/app/.venv/bin:$PATH" PORT=$PORT REFLEX_REDIS_URL=redis://localhost PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY --from=builder /app/.web/backend .web/backend
COPY --from=builder /app/.web/build/client /srv
COPY . .

EXPOSE $PORT

# Apply migrations before starting the backend; a failed migration stops the container.
CMD if [ -d alembic ]; then reflex db migrate; fi && \
    caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
