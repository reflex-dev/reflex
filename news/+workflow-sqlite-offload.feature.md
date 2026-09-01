SQLite workflow store calls now run on a worker thread, so slow or contended storage no longer stalls the event loop serving the app.
