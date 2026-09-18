Reuse one long-lived Redis client for the `/_health` endpoint instead of opening and closing a new TCP connection on every probe.
