File uploads now carry the browser session cookie, and with `REFLEX_SESSION_TOKEN_MODE=enforce` an upload for a client token that the session does not own returns HTTP 403.
