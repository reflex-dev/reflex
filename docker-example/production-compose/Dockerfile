# check=skip=JSONArgsRecommended
# This docker file is intended to be used with docker compose to deploy a production
# instance of a Reflex app.

# Stage 1: build the python environment and export the static frontend
FROM python:3.13-slim AS builder

# uv installs python packages; reflex uses a bun found on PATH instead of downloading its own.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy VIRTUAL_ENV=/app/.venv PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install app requirements and reflex inside virtualenv. This layer is only
# rebuilt when requirements.txt changes.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && uv pip install -r requirements.txt

# Copy local context to `/app` inside container (see .dockerignore)
COPY . .
RUN mkdir -p /app/data /app/uploaded_files

# Export static copy of frontend to /app/.web/build/client, then drop the rest
# of .web (node_modules etc.) to save space in the backend image. The cache
# mount keeps bun's package cache between builds. Keep .web/backend so the backend only
# evaluates stateful pages at startup instead of every page.
RUN --mount=type=cache,target=/root/.bun/install/cache \
    reflex export --frontend-only --no-zip \
    && mv .web/build/client .web/backend /tmp/ && rm -rf .web \
    && mkdir -p .web/build && mv /tmp/client .web/build/client && mv /tmp/backend .web/backend

# Stage 2: copy artifacts into slim image
FROM python:3.13-slim
WORKDIR /app
# The app user needs to own /app itself so reflex can create .states, data, and uploads there.
RUN adduser --disabled-password --home /app reflex && chown reflex /app
COPY --chown=reflex --from=builder /app /app
USER reflex
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

# Always apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    exec reflex run --env prod --backend-only
