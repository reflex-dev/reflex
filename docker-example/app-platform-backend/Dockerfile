# check=skip=JSONArgsRecommended
# Backend-only image for container hosting services. The frontend is exported
# separately and served from a static host; see README.md.
#
# Note: many container hosting platforms require amd64 images, so when building on an M1 Mac
# for example, pass `docker build --platform=linux/amd64 ...`
FROM python:3.13-slim

ENV UV_COMPILE_BYTECODE=1 UV_NO_CACHE=1 PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
# The app user needs to own /app itself so reflex can create .states there.
RUN adduser --disabled-password --home /app reflex && chown reflex /app

# Install python requirements first so app edits do not reinstall them. uv is
# mounted only for this step so it does not end up in the image.
COPY requirements.txt .
RUN --mount=from=ghcr.io/astral-sh/uv:0.12,source=/uv,target=/bin/uv \
    uv venv && uv pip install -r requirements.txt

# Copy local context to `/app` inside container (see .dockerignore)
COPY --chown=reflex . .
USER reflex
RUN mkdir -p data uploaded_files

# Apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    exec reflex run --env prod --backend-only --backend-port ${PORT:-8000}
