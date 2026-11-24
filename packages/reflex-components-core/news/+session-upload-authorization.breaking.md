File uploads carry the browser session cookie, and an upload for a client token that the session does not own returns HTTP 403. `REFLEX_SESSION_TOKEN_MODE=warn` or `off` turns the rejection off.
