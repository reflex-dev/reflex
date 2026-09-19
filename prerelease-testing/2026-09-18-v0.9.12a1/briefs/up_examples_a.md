# Cluster `up_examples_a` — upgrade regression, batch A (core interactions)

Follow `UPGRADE_PROTOCOL.md` (same directory) for each app, in this order:
1. `counter` — increment/decrement/random; check the uncached/cached var behavior of the count.
2. `todo` — add 3 items, complete, delete; reload (state persists per token?).
3. `clock` — timezone select, start/stop the ticking (`rx.moment` interval; note moment 0.9.4
   fires `on_change` on mount — document what you see, it is a known 0.9.4 behavior).
4. `upload` — upload two files via Playwright `set_input_files`, clear, check the uploaded list
   and the file on disk; the upload response is parsed by the new native JSON path (#7165).
5. `lorem-stream` — start several streams, stop one, check background-task streaming keeps
   going across a client-side navigation.
6. `snakegame` — play a few moves with the keyboard (global key handlers), pause, restart.
Also record the `reflex init`/first-run migration output for the oldest-looking app.
