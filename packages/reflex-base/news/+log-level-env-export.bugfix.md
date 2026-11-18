Setting the log level now always exports `REFLEX_LOGLEVEL`, so an explicitly requested level reaches subprocesses and later config loads even when it equals the level already in effect.
