FROM library/caddy

COPY --from=local/reflex-app /app/.web/_static /srv
ADD Caddyfile /etc/caddy/Caddyfile