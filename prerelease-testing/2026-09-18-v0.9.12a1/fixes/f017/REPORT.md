# f017 — FINDING-017 / reflex-dev/reflex#7213: supervisor-owned socket makes dev requests hang

- Worktree: `/home/user/wt/f017` · Branch: `fix/finding-017-supervisor-socket` · Commit: `eaf3f4822`
- Status: **fixed**, e2e verified (repro fails on published 0.9.12a1, passes on the fixed tree)
- Files changed: `reflex/utils/exec.py`, `tests/units/utils/test_exec.py`,
  `news/+dev-release-socket-without-worker.bugfix.md`
- Evidence: `evidence/` in this directory

## Root cause (confirmed independently)

`reflex/utils/exec.py:726` on `origin/main` (727 after the fix) — `run_granian_backend` runs the dev backend under a local
`ParentBoundGranian(granian.server.Server)` subclass whose `_init_shared_socket` builds the listening
socket in the **supervisor** (`SocketSpec(...).build()`, `sock.set_inheritable(True)`), instead of
granian's Linux default of letting every worker bind its own `SO_REUSEPORT` socket. That is #7114 and
it works as designed: the supervisor's descriptor keeps the port bound while a worker is replaced, so
requests wait in the accept backlog instead of being refused.

Two details of granian's supervisor turn that into the hang:

1. `granian/server/common.py:58 AbstractWorker._watcher` (granian 2.8.1) — when a worker exits on its own, and
   `reload_ignore_worker_failure=True` (which `exec.py` sets so a bad save does not kill the dev
   server), the watcher logs `Unexpected exit from worker-1` and **returns**. The supervisor keeps
   running with zero workers, still holding the listening socket. The socket was put into `LISTEN` by
   the worker that is now gone — the state lives on the shared open file description — so the kernel
   goes on completing handshakes into a backlog nobody will ever accept from. Every request blocks
   until the client's own timeout.
2. `granian/server/mp.py:392 MPServer._unlink_pidfile` (granian 2.8.1) — granian's shutdown only **detaches** the
   socket object (2.7.4 unconditionally, 2.8.x guarded), i.e. deliberately leaks the descriptor
   because the process is about to exit. Under `reflex run` the process does *not* exit (FINDING-018:
   the CLI keeps running the frontend), so after a SIGTERM the port stays bound with no worker — the
   `portprobe_new.json` result from the campaign.

0.9.11.post1 has no such subclass, so nothing was bound while no worker existed and clients got an
immediate `ECONNREFUSED`.

Verified mechanically before designing: `SocketSpec.build()` binds but does not listen, `get_fd()`
hands out a raw descriptor, and `SocketHolder` does **not** close it when dropped — so closing the
`socket.socket` object wrapping that fd is both necessary and sufficient to free the port, with no
double-close hazard.

## The fix

Kept in `ParentBoundGranian`, `reflex/utils/exec.py`:

- `_shared_socket_is_open()` / `_close_shared_socket()` — close the supervisor's listening socket.
  The closed socket **object** is deliberately left in `self._sso` (only `_shd`/`_sfd` are cleared)
  because granian 2.7.4's `_unlink_pidfile` calls `self._sso.detach()` with no `None` check;
  `detach()` on a closed socket returns -1 and is harmless, whereas `self._sso = None` would raise
  `AttributeError` on the declared minimum granian.
- `_release_socket_unless_served(wrk, spawn_count)` — invoked when a worker's watcher thread observes
  that worker exit. It closes the socket only when (a) the supervisor did not stop that worker
  (`wrk.interrupt_by_parent` is False), (b) no worker is alive, and (c) no newer worker has been
  spawned since. (b) and (c) are checked under a lock.
- `_spawn_worker()` — wraps granian's per-worker watcher with the hook above, and re-creates the
  listening socket if it was released, so the next spawn (the save that fixes the module) rebinds the
  port before the worker starts.
- `shutdown()` — closes the socket before granian's shutdown runs, so the port is released even when
  the `reflex run` process itself lingers.
- `_init_shared_socket()` now pins `self.bind_port` to the port actually bound, so a re-created socket
  returns to the same port when the caller asked for port 0.

Why this shape: a worker stopped by the supervisor keeps the socket, which is exactly #7114's
behaviour (the replacement is already on its way and requests should queue for it); the socket is
dropped only in the window where nothing can serve, which is the window 0.9.11.post1 spent unbound.
There are no new threads and no polling: the only new work runs on the watcher thread granian already
starts per worker.

### Alternatives considered and rejected

- **Revert #7114** (let workers bind). Loses the hot-reload benefit the release shipped; the finding
  is the missing bound, not the socket ownership.
- **Answer a 503 from the supervisor.** Needs an accept loop, an HTTP/1 writer and a websocket story
  in the supervisor process — far more code and more ways to be wrong than closing a descriptor.
- **Time-bound the window** ("stop listening N seconds after the last worker"). Needs a timer thread
  and leaves an arbitrary hang window; the worker-exit signal is already available and exact.
- **`listen(0)` / `shutdown(SHUT_RD)` on the listening socket.** Neither reliably refuses on Linux.
- **Close in `_stop_workers` and re-open in `_spawn_workers`.** That is precisely the hot-reload path,
  so it would re-introduce refused requests during a reload.
- **`try/finally` around granian's watcher body** so the release also runs if granian's own watcher
  raises. Rejected: granian's watcher only joins and logs, and a `finally` would fire our logic from a
  state we cannot reason about.

## Regression tests (`tests/units/utils/test_exec.py`)

Four new tests drive `ParentBoundGranian` over a granian `Server` stand-in (the pattern the existing
#7114 test in this file already uses), plus one that runs a real dev supervisor in a subprocess:

| test | before fix | after fix |
| --- | --- | --- |
| `..._releases_socket_when_worker_dies` | FAIL | pass |
| `..._rebinds_socket_for_the_next_worker` | FAIL | pass |
| `..._releases_socket_on_shutdown` | FAIL | pass |
| `..._keeps_socket_across_worker_restart` (guards #7114) | pass | pass |
| `..._refuses_requests_while_the_app_is_broken` (real granian supervisor) | FAIL | pass |

Before (unfixed `reflex/utils/exec.py`, final tests) — `evidence/unit_before_fix.txt`,
`evidence/unit_e2e_before_fix.txt`:

```
FAILED tests/units/utils/test_exec.py::test_run_granian_backend_releases_socket_when_worker_dies
FAILED tests/units/utils/test_exec.py::test_run_granian_backend_rebinds_socket_for_the_next_worker
FAILED tests/units/utils/test_exec.py::test_run_granian_backend_releases_socket_on_shutdown
3 failed, 1 passed, 18 deselected in 0.14s

E   AssertionError: the backend port kept accepting connections with no worker to serve them
1 failed, 21 deselected in 20.82s
```

After — `evidence/unit_after_fix.txt`: `22 passed in 3.88s` (whole file, including the pre-existing
`test_run_granian_backend_holds_requests_across_reload`).

## End-to-end verification (campaign repro)

`evidence/break_reload_probe.py` is the campaign's own probe (`dev_server_cli/verification/scripts/`),
run unmodified against the campaign's `dsc` app copied to scratch. It starts `reflex run`, appends
`raise RuntimeError(...)` to `dsc/dsc.py`, probes `/ping` with a raw socket, then restores the file.

| probe point | published 0.9.12a1 (`envs/shared`) | fixed worktree |
| --- | --- | --- |
| before break | `200` (0.0 s) | `200` (0.0 s) |
| +10 s after break | `TIMEOUT_NO_REPLY_6s` (6.01 s) | `CONNECTION_REFUSED` (0.0 s) |
| +24 s after break | `TIMEOUT_NO_REPLY_6s` (6.00 s) | `CONNECTION_REFUSED` (0.0 s) |
| +12 s after fix | `200` | `200` (0.01 s) |
| +20 s after fix | `200` | `200` (0.0 s) |

`evidence/breakreload_pub_0912a1.json` (ports 3940/8940) vs
`evidence/breakreload_fixed_worktree_final.json` (ports 3944/8944, final code;
`breakreload_fixed_worktree.json` is the identical run of an earlier revision on 3941/8941).

**#7114 not regressed** — `evidence/hotreload_fixed_worktree_final.json` (+ `.tsv`), the campaign's
20 Hz `ping_probe.py` run across two harmless edits of `dsc.py` while the server runs:

```
total=543 refused=0 errors=0 ok=543
slowest: [(15.138, 0.993, '200'), (5.143, 0.992, '200'), (25.826, 0.013, '200'), ...]
```

The two ~1 s samples are exactly the two reload windows: requests waited for the new worker instead of
being refused, which is what #7114 is for.

**SIGTERM path** (the campaign's original repro, `evidence/portprobe_fixed_worktree.json`, ports
3942/8942) now matches 0.9.11.post1 — `CONNECTION_REFUSED` at +8 s and +18 s, where 0.9.12a1 logged
`TIMEOUT_NO_REPLY_6s` (campaign `logs/portprobe_new.json`). The process still ignores the signal —
that is FINDING-018 and is untouched here — but the port no longer swallows connections.

## Checks

- `uv run ruff check .` — clean (whole repo).
- `uv run ruff format .` — 1626 files already formatted.
- `uv run pyright reflex tests` — `0 errors, 0 warnings, 0 informations` (`evidence/pyright_full.txt`).
- `uv run pytest tests/units/utils` — `714 passed, 6 skipped`.
- `uv run pytest tests/units/utils/test_exec.py` — `22 passed`.
- No component signature/prop change, so `pyi_hashes.json` is untouched.
- Granian minimum-version check: granian 2.7.4 (the `pyproject.toml` floor) was downloaded and its
  `server/common.py` / `server/mp.py` inspected — `interrupt_by_parent`, `_watcher`, `is_alive`,
  `wrks`, `_spawn_worker(idx, target, callback_loader)` and `shutdown(exit_code)` are identical there,
  and its unguarded `self._sso.detach()` is the reason the closed socket object is kept (see above).

## Risks and behaviour changes

- Dev-only: `run_granian_backend_prod` uses plain `Granian` and is untouched.
- The dev backend port now **disappears** while the app module cannot be imported, instead of
  accepting and hanging. That is 0.9.11.post1's behaviour; a proxy in front of the dev backend will
  see connection-refused during that window rather than a stalled connection.
- A stale-generation guard (`_spawn_count`) plus an `RLock` protect the one race that would matter —
  a slow watcher thread from a crashed worker closing the socket a newly spawned worker has already
  inherited. Without it the dev server could silently stop listening until the next save; with it the
  close is skipped whenever a newer worker exists. The lock is only taken on spawn and on worker exit.
- `_init_shared_socket` now assigns `self.bind_port`. Only meaningful for port 0 (and it makes
  granian's `Listening at:` line print the real port). The override ignores `bind_uds`, as before —
  reflex never configures a UDS here.

## Open questions for the maintainers

1. The commit's trailer says `Co-Authored-By: Claude Opus 5 (1M context)`, the model that actually
   wrote it, rather than the `Claude Fable 5.1` line the shared fix brief dictates. Amend if the
   release train wants identical trailers across the five fix branches.
2. Worth considering upstream: granian could refuse rather than queue when no worker is alive, which
   would make this subclass unnecessary. Reporting it to granian is out of scope here.
3. `tests/units/utils/test_exec.py` now contains five separate `FakeGranian` stand-ins (four were
   already there). Collapsing them into one shared helper is a worthwhile cleanup but was left out as
   an unrelated refactor.
4. FINDING-018 (`reflex run` ignoring SIGTERM at its own pid) is untouched; only its port-level
   symptom is gone.
