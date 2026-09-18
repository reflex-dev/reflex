With `REFLEX_OPLOCK_ENABLED`, concurrent events for the same token in a single backend process now share one Redis lock instead of each taking and releasing their own.
