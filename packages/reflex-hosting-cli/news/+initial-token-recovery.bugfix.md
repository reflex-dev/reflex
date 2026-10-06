Show `reflex login` guidance when initial authentication rejects an access token, including instructions to replace or remove an explicit `REFLEX_ACCESS_TOKEN` or `--token` override.
When `reflex cloud whoami` cannot validate a token due to a temporary service or connection failure, suggest retrying instead of replacing credentials.
