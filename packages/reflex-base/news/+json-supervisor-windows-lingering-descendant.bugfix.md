`reflex run --json` no longer waits on exit for a descendant process that outlives the app and keeps its output open, which could happen on Python 3.13 to 3.15, most often on Windows.
