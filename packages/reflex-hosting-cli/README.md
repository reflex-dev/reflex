# reflex-hosting-cli
Hosting CLI for Reflex.

If an access token is expired or rejected, run `reflex login` to authenticate
again. If you supply a token explicitly, replace it with a valid token or remove
the override before using the saved login: unset `REFLEX_ACCESS_TOKEN` or omit
`--token`. Logging in does not replace an environment variable or command-line
token. Noninteractive commands exit on rejection without opening a browser.
