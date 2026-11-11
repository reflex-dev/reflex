# Release plan — what blocks reflex 0.11.0 vs what gets filed — DRAFT

Draft from the 0.11.0a1 pass; `compile_memo` and `verify_cv` still running. Finding numbers
refer to `FINDINGS.md`. Rubric (SKILL.md): **fix before release** = confirmed regression vs 0.10.1, security-relevant, or
significant user impact / trivially small; everything else is filed. Each entry names the arm that put it there.

## Already in flight
| PR | Covers | Gap check |
|---|---|---|
| reflex-dev/reflex#7761 (open) "Stream event handler yield and return values to the frontend caller" | touches the return-value path of FINDING-015 | does not restore the explanatory TypeError for mistaken returns (`return self.handler`) |
| — | no open PR in reflex or reflex-enterprise addresses any other finding (searched open PRs 2026-11-11) | |

## Fix before release

### Security / deployment-breaking
- **FINDING-022** (HIGH, regression): new prod CORS default breaks same-origin prod behind a TLS proxy (no
  `X-Forwarded-Proto`) and every documented split / CDN deployment. Arm: confirmed regression + significant impact.
  Shape: keep the secure default; update self-hosting.md, scaling.md, docker-example READMEs (set `REFLEX_DEPLOY_URL` on the
  backend; reverse-proxy headers; Caddy `trusted_proxies`); upgrade note; recommended code: Reflex origin callable that also
  accepts `https://{Host}` behind a TLS proxy and logs one actionable WARNING (also closes FINDING-023).

### Confirmed regressions (reflex)
- **FINDING-001** (HIGH): a second `@rx.event` crashes import (breaks reflex-examples `overkey`). Arm: regression +
  trivially small. Shape: in `rx.event`'s `wrapper`, unwrap an input that is already an `EventHandler` and merge actions
  (verified on a scratch copy). Regression test: the six stacking patterns.
- **FINDING-005** (MEDIUM): hand-edited 0.10.x env.py now executed; any exception crashes `reflex run` / `reflex db` with
  a raw traceback. Arm: regression. Shape: catch all exceptions from env.py in `check_schema_up_to_date` and
  `_alembic_errors`, log the "move env.py aside, run `reflex db init`" hint.
- **FINDING-006** (MEDIUM): kept user env.py → empty revision on every `makemigrations` (also `migrate(autogenerate=True)`
  at import: chained empty revisions). Arm: regression. Shape: `alembic check` first, write a revision only on changes.
- **FINDING-007** (MEDIUM): pyright 3.11–3.13 loses bare-`@rx.event` argument types; `rx.event.EventCallback[int]` is a
  pyright error. Arm: regression + small. Shape: point the overload return annotation at a module-level alias; CI
  pyright with `--pythonversion 3.12`.
- **FINDING-009** (MEDIUM-LOW): `reflex db migrate` exits 1 on a fresh reflex-enterprise app. Arm: regression. Shape: do
  not compile initial state in `evaluate_pages`, or bundle plugin frontend deps in the skip-compile branch.
- **FINDING-016** (LOW): `@staticmethod` above `@rx.event` returns an EventSpec. Arm: regression + small. Shape: re-wrap
  as `staticmethod(inner.fn)`.

### Downstream compatibility (reflex-enterprise 0.9.11 on reflex 0.11 — coordinate the final with an rxe release)
- **FINDING-002** (HIGH, rxe): MCPPlugin prod startup crash without `deploy_url`. rxe: `deploy_url or api_url`. reflex:
  Breaking Changes line for code reading `config.deploy_url` (point to `frontend_url`). Release 0.11.0 together with a fixed
  rxe, or have rxe cap `reflex<0.11` until then (rxe currently requires `reflex[db]>=0.9.6`, no upper bound).
- **FINDING-003** (HIGH, rxe + reflex shim): AG Grid API `refs is not defined`. rxe: attach `refs` var data. reflex
  (recommended, one line): keep importing `refs` next to `useRegisteredRef` in the 0.11 line so published rxe and
  third-party libraries keep working; otherwise list under Breaking Changes.
- **FINDING-008** (MEDIUM, rxe): MCP consent redirect to backend in dev. rxe only.

### High impact and/or trivially small (not regressions)
- **FINDING-004** (HIGH): unregistered DeclarativeBase → silent `drop_table` for every table. Arm: significant impact (the
  0.11 docs move every user to DeclarativeBase; data loss). Shape: refuse autogenerate when target metadata lacks tables
  present in the DB; warn about unregistered DeclarativeBase subclasses.
- **FINDING-010** (MEDIUM): `await State.handler()` outside an event handler runs on a shared empty-token session
  (cross-caller read). Arm: security-adjacent + small. Shape: treat an empty token as no context → `EventHandlerTypeError`.
- **FINDING-012** (MEDIUM): `mapped_column(default_factory=)` add-column migration fails NOT NULL. Arm: impact on the newly
  documented path + small. Shape: env.py server-default hook also reads the dataclass `default_factory`.
- **FINDING-011** (MEDIUM): JSON column on DeclarativeBase typed `object`. Arm: impact on the documented rewrite + small.
  Shape: fall back to the `Mapped[]` annotation when `python_type` is `object`.
- **Changelog/doc lines** (trivial): FINDING-024 (`rx.App()()` → Breaking), FINDING-015 (return values no longer raise),
  FINDING-006 note, FINDING-014 (admin guide: trailing slash, dataclass models, `MyAuthProvider`), FINDING-020 (serializer
  example), #7534 wording (FINDING-030).
- **FINDING-028** (LOW, small): exclude `reflex_components_*` frames from deprecation locations.
- **FINDING-030** (LOW, small): reset `StateManagerRedis._instance_id` per forked worker (one line next to the token
  manager's reset) — or reword the #7534 changelog sentence, which is false as written for Linux prod with ≥2 workers.

## File as issues, fix after release

### reflex-dev/reflex
- FINDING-013 (duplicate table in two metadatas, random), FINDING-017 (env.old overwrite), FINDING-018 (serializer silent
  blanks), FINDING-019 (naming_convention lost in merge), FINDING-023 (if not closed by FINDING-022's code change),
  FINDING-025 (lifespan skipped silently behind a non-http-safe middleware), FINDING-026 (case-duplicate routes),
  FINDING-027 (prod repeated Ctrl-C), FINDING-029 (package.json formatting).
- events_await lows: memory-manager `CancelledError` for a bg task awaiting a superseded handler; bg task that catches an
  awaited exception still shows the error toast; deprecation names only the first stacked method per class.
- FINDING-031 (cross-worker updates lost after > 5 s Redis outage), FINDING-032 (dead worker's socket record → new token),
  FINDING-033 (no granian respawn; consider `respawn_failed_workers=True`), the in-process "instaque" barging note.
- client_vars lows (pending verify_cv): client_state name hint wrong; client_state identifier collisions break every page;
  `rx.match` on sets order-dependent; `set[str]` handler args arrive as list; `set | None` ops break the prod build;
  `split()` UTF-16; int/list storage factories; remaining cryptic backend-var errors; foreach row-index client state (docs).

### reflex-dev/reflex-enterprise
- FINDING-021 (`use_single_port=True` dev proxy never mounts); ENT-07 still broken (prod cookie sync 405, 2 workers);
  `VarData(position=...)` deprecations printed by rxe's own dnd.py / mantine combobox.py.

## Decisions needed from a maintainer
1. **CORS default (FINDING-022):** docs-only before final, or also the TLS-proxy-aware origin check? And whether
   `--frontend-only`/`--backend-only` deployments deserve a startup warning when `deploy_url` is unset.
2. **`refs` compatibility (FINDING-003):** ship the one-line shim for 0.11, or declare the implicit `refs` import gone
   (Breaking Changes)?
3. **reflex-enterprise coordination (FINDING-002/-003/-008):** release order / rxe upper bound on reflex.
4. **Sibling floors (PKG-A):** raise `reflex-components-lucide>=1.1.2` and `reflex-hosting-cli>=0.2.2` at final so a plain
   upgrade delivers #7674 / #7670?
5. **redis-py beta:** `uv --prerelease=allow` resolves redis-py 8.2.0b1 for alpha testers; acceptable, or cap `redis<8.2`
   until it is final?
6. **Undocumented behaviour changes:** handler return values silently dropped (FINDING-015), `print(State._x)` in server
   code now raises (client_vars anomaly), `default_factory` of storage-compatible vars called once more at compile — bug or
   missing changelog entry?

## Suggested sequencing
- Parallel, independent files: FINDING-001 + -016 (reflex_base/event + state.py), FINDING-007 (reflex_base/event typing
  only — same file as -001: land after it or in one PR), FINDING-005/-006/-017 (reflex/utils/migrations.py, reflex.py,
  model.py — one DB PR or three stacked), FINDING-004/-012/-011 (model.py, env.py template, reflex_base types.py),
  FINDING-009 (compiler.py), FINDING-010 (base_state_processor.py), FINDING-022 docs (docs/hosting, docker-example) and code
  (app.py), FINDING-003 shim (reflex_base component.py), FINDING-028 (reflex_base log.py).
- Then cut 0.11.0a2 and re-run the original repros (Phase 7), together with a fixed reflex-enterprise build.
