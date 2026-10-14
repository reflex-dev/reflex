`reflex run --json` now forwards SIGINT to its child process, so supervisors that signal only the Reflex PID can stop the app cleanly.
