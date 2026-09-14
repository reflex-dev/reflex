# check=skip=JSONArgsRecommended
# This docker file is intended to be used with container hosting services
#
# After deploying this image, get the URL pointing to the backend service
# and run REFLEX_API_URL=https://path-to-my-container.example.com reflex export --frontend-only --no-zip
# then copy the contents of `.web/build/client` to your static file server (github pages, s3, etc).
#
# Azure Static Web App example:
#    npx @azure/static-web-apps-cli deploy --env production --app-location .web/build/client
#
# For dynamic routes to function properly, ensure that 404s are redirected to /404 on the
# static file host (for github pages, this works out of the box; remember to create .nojekyll).
#
# For azure static web apps, add `staticwebapp.config.json` to to `.web/build/client` with the following:
#  {
#     "responseOverrides": {
#        "404": {
#            "rewrite": "/404.html"
#        }
#     }
#  }
#
# Note: many container hosting platforms require amd64 images, so when building on an M1 Mac
# for example, pass `docker build --platform=linux/amd64 ...`

# Stage 1: build the python environment
FROM python:3.13-slim AS builder

# uv installs python packages much faster than pip.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
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

# Stage 2: copy artifacts into slim image
# The backend does not need bun, node_modules, or .web, so `reflex init` and
# the frontend build are skipped entirely; export the frontend separately.
FROM python:3.13-slim
WORKDIR /app
# The app user needs to own /app itself so reflex can create .states, data, and uploads there.
RUN adduser --disabled-password --home /app reflex && chown reflex /app
COPY --chown=reflex --from=builder /app /app
USER reflex
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

# Always apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; \
    exec reflex run --env prod --backend-only --backend-port ${PORT:-8000}
