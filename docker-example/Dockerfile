# Stage 1: init
FROM python:3.11 as init

# Pass `--build-arg API_URL=http://app.example.com:8000` during build
ARG API_URL

# Copy local context to `/app` inside container (see .dockerignore)
WORKDIR /app
COPY . .

# Reflex will install bun, nvm, and node to `$HOME/.reflex` (/app/.reflex)
ENV HOME=/app

# Create virtualenv which will be copied into final container
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python3 -m venv $VIRTUAL_ENV

# Install app requirements and reflex inside virtualenv
RUN pip install -r requirements.txt

# Deploy templates and prepare app
RUN reflex init

# Export static copy of frontend to /app/.web/_static (and pre-install frontend packages)
RUN reflex export --frontend-only --no-zip


# Stage 2: copy artifacts into slim image 
FROM python:3.11-slim
ARG API_URL
WORKDIR /app
RUN adduser --disabled-password --home /app reflex
COPY --chown=reflex --from=init /app /app
USER reflex
ENV PATH="/app/.venv/bin:$PATH" API_URL=$API_URL

CMD reflex db migrate && reflex run --env prod
