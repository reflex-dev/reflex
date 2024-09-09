# This Dockerfile is used to deploy a simple single-container Reflex app instance.
FROM python:3.12

RUN apt-get update && apt-get install -y redis-server && rm -rf /var/lib/apt/lists/*
ENV REDIS_URL=redis://localhost PYTHONUNBUFFERED=1

# Copy local context to `/app` inside container (see .dockerignore)
WORKDIR /app
COPY . .

# Install app requirements and reflex in the container
RUN pip install -r requirements.txt

# Deploy templates and prepare app
RUN reflex init

# Download all npm dependencies and compile frontend
RUN reflex export --frontend-only --no-zip

# Needed until Reflex properly passes SIGTERM on backend.
STOPSIGNAL SIGKILL

# Always apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    redis-server --daemonize yes && \
    exec reflex run --env prod
