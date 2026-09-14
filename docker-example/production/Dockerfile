# check=skip=JSONArgsRecommended
# This Dockerfile is used to deploy a single-container Reflex app instance
# to services like Render, Railway, Heroku, GCP, and others.

# If the service expects a different port, provide it here (f.e Render expects port 10000)
ARG PORT=8080
# Only set for local/direct access. When TLS is used, the API_URL is assumed to be the same as the frontend.
ARG API_URL

# It uses a reverse proxy to serve the frontend statically and proxy to backend
# from a single exposed port, expecting TLS termination to be handled at the
# edge by the given platform.
FROM python:3.13-slim AS builder

# uv installs python packages; reflex uses a bun found on PATH instead of downloading its own.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy VIRTUAL_ENV=/app/.venv PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install python app requirements and reflex in the container. This layer is
# only rebuilt when requirements.txt changes.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && uv pip install -r requirements.txt

# Copy local context to `/app` inside container (see .dockerignore)
COPY . .

ARG PORT API_URL
# Download npm dependencies and compile frontend into /srv. The cache mount
# keeps bun's package cache between builds so unchanged dependencies are not
# downloaded again. Keep .web/backend so the backend only
# evaluates stateful pages at startup instead of every page.
RUN --mount=type=cache,target=/root/.bun/install/cache \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT} reflex export --frontend-only --no-zip \
    && cp -r .web/build/client/. /srv/ \
    && mv .web/backend /tmp/backend && rm -rf .web && mkdir .web && mv /tmp/backend .web/backend


# Final image with only necessary files
FROM python:3.13-slim

# Install redis server inside image; take caddy from its official image.
RUN apt-get update -y && apt-get install -y --no-install-recommends redis-server && rm -rf /var/lib/apt/lists/*
COPY --from=caddy:2 /usr/bin/caddy /usr/bin/caddy

ARG PORT API_URL
ENV PATH="/app/.venv/bin:$PATH" PORT=$PORT REFLEX_API_URL=${API_URL:-http://localhost:$PORT} REFLEX_REDIS_URL=redis://localhost PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app /app
COPY --from=builder /srv /srv

EXPOSE $PORT

# Apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
