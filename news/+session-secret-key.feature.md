`reflex run` reads the session signing keys from `REFLEX_SECRET_KEY`. Without it, `reflex run` generates a temporary key for that run. A configured key shorter than 32 bytes stops the run at startup.
