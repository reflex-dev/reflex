# check=skip=JSONArgsRecommended
# Backend image for the docker compose deployment. The frontend is exported
# here too, so the Caddy image can copy it out (see Caddy.Dockerfile).

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

# Compile the app and build the static frontend. The cache mount keeps bun's
# package cache between builds so unchanged dependencies are not downloaded again.
RUN --mount=type=cache,target=/root/.bun/install/cache \
    reflex export --frontend-only --no-zip


# Final image: the python environment, the app source, the static frontend, and
# .web/backend so the backend only evaluates stateful pages at startup.
FROM python:3.13-slim

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
# The app user needs to own /app itself so reflex can create .states there.
RUN adduser --disabled-password --gecos "" --home /app reflex && chown reflex /app
COPY --chown=reflex --from=builder /app/.venv .venv
COPY --chown=reflex --from=builder /app/.web/backend .web/backend
COPY --chown=reflex --from=builder /app/.web/build/client .web/build/client
COPY --chown=reflex . .
USER reflex
RUN mkdir -p data uploaded_files

# Apply migrations before starting the backend; a failed migration stops the container.
CMD if [ -d alembic ]; then reflex db migrate; fi && \
    exec reflex run --env prod --backend-only
