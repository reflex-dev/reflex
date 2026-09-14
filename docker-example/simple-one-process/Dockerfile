# check=skip=JSONArgsRecommended
# The simplest single-container deployment: one Reflex process serves the
# static frontend and the backend on the same port. No reverse proxy, no Redis.
#
# The frontend is compiled and built each time the container starts, so startup
# takes longer than the other examples and bun stays in the image. For an image
# with a prebuilt frontend see `simple-one-port` or `production-one-port`.
FROM python:3.13-slim

# Reflex uses a bun found on PATH instead of downloading its own.
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install python requirements first so app edits do not reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy local context to `/app` inside container (see .dockerignore)
COPY . .

# Install frontend dependencies at build time so the container does not need
# network access to start. The build output itself is regenerated on startup.
RUN reflex export --frontend-only --no-zip && rm -rf .web/build

EXPOSE 3000

# Apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    exec reflex run --env prod --frontend-port ${PORT:-3000}
