FROM python:3.11-slim as base

RUN adduser --disabled-password reflex


FROM base as build

WORKDIR /app
ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . .

RUN pip install wheel \
    && pip install -r requirements.txt


FROM base as runtime

RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_19.x | bash - \
    && apt-get update && apt-get install -y \
    nodejs \
    unzip \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/venv/bin:$PATH"


FROM runtime as init

WORKDIR /app
ENV BUN_INSTALL="/app/.bun"
COPY --from=build /app/ /app/
RUN reflex init


FROM runtime

COPY --chown=reflex --from=init /app/ /app/
USER reflex
WORKDIR /app

CMD ["reflex", "run" , "--env", "prod"]

EXPOSE 3000
EXPOSE 8000
