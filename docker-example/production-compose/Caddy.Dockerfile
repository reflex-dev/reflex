FROM caddy:2

# The `app` build context is the app service image (see compose.yaml).
COPY --from=app /app/.web/build/client /srv
COPY Caddyfile /etc/caddy/Caddyfile
