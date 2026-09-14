# check=skip=JSONArgsRecommended
# The simplest single-container deployment: one Reflex process serves the
# static frontend and the backend on the same port. No reverse proxy, no Redis.
#
# The frontend is compiled at build time and the container start skips that
# step, but the production bundle is still rebuilt on each start, so startup
# takes longer than the other examples and bun stays in the image. For an image
# that serves a prebuilt frontend see `production`.
FROM python:3.13-slim

# uv installs python packages; reflex uses a bun found on PATH instead of downloading its own.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

# Install python requirements first so app edits do not reinstall them.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# Copy local context to `/app` inside container (see .dockerignore)
COPY . .

# Compile the app and install frontend dependencies at build time so the
# container does not need network access to start.
RUN reflex export --frontend-only --no-zip

EXPOSE 3000

# Apply migrations before starting the backend. The nocompile flag makes
# reflex reuse the compile from the image instead of redoing it; reflex deletes
# the flag once read, so it is recreated on every start.
CMD [ -d alembic ] && reflex db migrate; \
    touch .web/nocompile && \
    exec reflex run --env prod --frontend-port ${PORT:-3000}
