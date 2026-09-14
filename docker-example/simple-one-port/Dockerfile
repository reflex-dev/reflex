# check=skip=JSONArgsRecommended
# This Dockerfile is used to deploy a single-container Reflex app instance
# to services like Render, Railway, Heroku, GCP, and others.

# It uses a reverse proxy to serve the frontend statically and proxy to backend
# from a single exposed port, expecting TLS termination to be handled at the
# edge by the given platform.
FROM python:3.13-slim

# If the service expects a different port, provide it here (f.e Render expects port 10000)
ARG PORT=8080
# Only set for local/direct access. When TLS is used, the API_URL is assumed to be the same as the frontend.
ARG API_URL
ENV PORT=$PORT REFLEX_API_URL=${API_URL:-http://localhost:$PORT} REFLEX_REDIS_URL=redis://localhost PYTHONUNBUFFERED=1

# Install redis server inside image; take caddy and bun from their official images.
RUN apt-get update -y && apt-get install -y --no-install-recommends redis-server && rm -rf /var/lib/apt/lists/*
COPY --from=caddy:2 /usr/bin/caddy /usr/bin/caddy
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun

WORKDIR /app

# Install python requirements first so app edits do not reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy local context to `/app` inside container (see .dockerignore)
COPY . .

# Download all npm dependencies and compile frontend into /srv for caddy. Keep .web/backend so the backend only
# evaluates stateful pages at startup instead of every page.
RUN reflex export --frontend-only --no-zip \
    && cp -r .web/build/client/. /srv/ \
    && mv .web/backend /tmp/backend && rm -rf .web && mkdir .web && mv /tmp/backend .web/backend

EXPOSE $PORT

# Apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
