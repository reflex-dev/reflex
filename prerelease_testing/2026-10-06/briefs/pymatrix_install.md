# Cluster `pymatrix_install` — Python 3.10/3.14, user-realistic install paths, CLI changes, AppHarness

Ports: frontend 3380-3399, backend 8380-8399. Work dir: $SB/apps/pymatrix_install/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/

## Why this cluster exists
The previous campaign ran everything on Python 3.12/3.13 with `--prerelease=allow` (which also pulled
pydantic 2.14.0b2). Real users will run `pip install reflex==0.10.0a1` (no --pre → stable component
packages + alpha base!) or `uv add reflex==0.10.0a1`, on 3.10 (oldest supported) and 3.14 (newest).
Changelog lines in scope (verbatim):
- (reflex, Bug Fixes) Reflex now checks the Node.js version before running npm, so an unsupported Node.js no longer leaves npm lockfiles behind that switch later runs to npm. (#7210)
- (reflex, Bug Fixes) When a project keeps using npm because `reflex.lock/` only has `package-lock.json` (for example after a run with `REFLEX_USE_NPM=1`), Reflex now logs why and how to switch back to bun with `REFLEX_USE_NPM=0`. (#7093)
- (reflex, Breaking) Remove the `reflex component` CLI ... (#6425)
- (reflex, Misc) Allow wrapt 2.4 and 2.5, and keep SQLModel below 0.0.45 to preserve existing datetime storage behavior. (#7424)
- (reflex, Bug Fixes) `reflex db` commands run without the `db` extra installed now exit with the "pip install reflex[db]" message instead of a raw traceback. (#7259)
- (reflex-base, Misc) Update generated apps to React 19.3, Vite 8.3.2, Socket.IO client 4.8.4, Autoprefixer 10.6.1, and PostCSS 8.5.29. Update the bundled Bun runtime to 1.4.2. (#7424)
- (reflex-base, Bug Fixes) Calling an event handler of up to four arguments on the state class ... now type-check under ty, as they already did under pyright. (#7414)

## What to do
1. Install-path matrix (record the resolved graph of each with `uv pip freeze`/`pip freeze`, and whether a
   blank app + a small state app init/run/compile in dev and prod):
   a) `uv --no-config pip install reflex==0.10.0a1` (NO prerelease flag) on 3.12 → expect alpha
      reflex/reflex-base with STABLE 0.9.x component packages. Does it resolve? Does the app run? Do all
      components render (rx.upload, rx.data_editor, rx.plotly, rx.recharts, rx.code_block, rx.markdown,
      rx.moment, rx.toast, rx.icon) — the stable component wheels declare `reflex-base>=0.9.12`, so they
      install, but they were built against 0.9.12 APIs.
   b) real `pip` (`$SB/envs/driver/bin/python -m pip download` has pip; create a venv with
      `uv venv --seed` to get pip): `pip install reflex==0.10.0a1` and `pip install --pre reflex==0.10.0a1`.
   c) `uv init` a project, `uv add 'reflex==0.10.0a1'` (uv project mode; check uv's prerelease handling
      and the lock), `uv run reflex run`.
   d) `pip install 'reflex[db]==0.10.0a1'` then `python -c "import sqlmodel; print(sqlmodel.__version__)"`
      → must be < 0.0.45; and the stable 0.9.12 pulls 0.0.47 — write a tiny `rx.Model` with a
      `datetime` column on both and check the stored representation/timezone behavior that the changelog
      says the cap preserves (insert, read back, compare types).
2. Python matrix: venvs on 3.10 and 3.14 (`uv venv --python 3.10`): init blank, run dev + prod, and a
   state app using every annotation shape: `list[int] | None`, `dict[str, list[str]]`, `Optional[...]`,
   `typing.Annotated`, a dataclass var, a pydantic model var (if `reflex[pydantic]`), `Literal`, an Enum,
   a `datetime` var, `rx.Field[...]` with `rx.field(default_factory=...)`; computed vars returning
   `list[dict]`; background task with `async with self`; an `ABC` mixin state. Drive in Chromium. 3.14:
   watch for deprecation/syntax warnings in the server log (e.g. `asyncio` policy changes, `ast`), and
   check `reflex --version`, `reflex db` without the db extra (#7259) — graceful message, exit code.
3. Node/npm paths (#7210/#7093): with a FRESH app, (a) `REFLEX_USE_NPM=1 reflex run` once → stop →
   plain `reflex run` → does it keep npm, and does the log explain why and how to switch back
   (`REFLEX_USE_NPM=0`)? then `REFLEX_USE_NPM=0 reflex run` → back to bun, lockfile state in
   `reflex.lock/`; (b) put a fake `node` shim earlier on PATH that prints `v16.0.0` (and one that prints
   `v18.0.0`) and run with `REFLEX_USE_NPM=1`: expect a clear unsupported-Node error BEFORE npm runs and
   NO `package-lock.json` left behind in `reflex.lock/` or `.web/`. Restore PATH after.
4. CLI: `reflex component ...` on the alpha (exit code + message), `reflex --help` listing, `reflex init
   --template <name>` for a non-blank template (check `reflex init --help` for template options;
   the templates come from github `reflex-dev/templates`; the proxy may allow it) and run it.
5. `reflex.testing.AppHarness` from the PUBLISHED package in a neutral dir (this is what downstream test
   suites use): a script that creates two different apps with `AppHarness.create(root=..., app_source=...)`
   SEQUENTIALLY (and then simultaneously, different ports) and drives each with Playwright
   (`harness.frontend_url`); check for registration leakage between the two apps (second app's pages
   showing first app's state/components), and that `harness.app_instance`, `harness.poll_for_clients`,
   `harness.app_state_manager` still exist (list the public attributes alpha vs 0.9.12).
6. ty/pyright: run published `pyright` and `ty` over a small app with handlers of 0..5 args called with
   literals/Vars and passed uncalled to triggers (the previous campaign ran ty on 0-4 args; also check 5
   args and the pyright side), on 3.10 and 3.14 interpreters.
