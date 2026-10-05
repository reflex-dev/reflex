# Published alpha Redis, rolling deploy, and optional database checks

The covered cases passed on published `reflex==0.10.0a1` / `reflex-base==0.10.0a1`. Tests used real Redis at `localhost:9141`, **database 5 only**, and disposable SQLite files. No checkout package, editable install, framework fix, or repository test was used.

## Plan and source references

1. Run a real browser app through ordinary State, inherited background mutations, memoized ComponentState instances, and independent concurrent sessions.
2. Replace only this app's stored session pickles with truncated, empty, invalid, missing-module, or missing-class data. Verify recovery by clicking the next event, checking unaffected sibling state, and reloading.
3. Delay delivery of a real Redis subscription confirmation, then exercise opportunistic leases and contention between two installed state managers.
4. Compare actual Redis reads and writes by published 0.9.12 and 0.10.0a1 workers using the same app module and fields.
5. Check the missing database-extra guidance before installing database libraries; install only SQLAlchemy and Alembic, then run actual migrations and native mapped CRUD.
6. Preserve sources, provenance, browser/network/server evidence and generated migrations; stop the app and remove only owned keys and installer side effects.

Read the alpha changelogs and PR descriptions [#7312](https://github.com/reflex-dev/reflex/pull/7312), [#7322](https://github.com/reflex-dev/reflex/pull/7322), [#7329](https://github.com/reflex-dev/reflex/pull/7329), and [#7372](https://github.com/reflex-dev/reflex/pull/7372). Their descriptions are retained under `evidence/`. **#7332 is a dependency-floor change; #7372 is the opportunistic-lock readiness fix.**

## Results

| Area | Result | Evidence |
| --- | --- | --- |
| Redis browser persistence and two concurrent independent sessions | 12 and 9 rapidly queued increments retained independently; backend audits agree; reload retains values | `evidence/browser/browser-results.json` |
| Two ComponentState instances through one memo body | Independent counts/checksums and handlers; backend mutable audits survive reload | Same browser results and screenshots |
| Background substate mutating inherited frontend/backend lists | Both mutations arrive and survive reload | Same browser results |
| Corrupted ordinary state | Truncated, empty, invalid-opcode, removed-module and removed-class payloads all recover on the next browser event; a subsequent event and reload remain usable | Five individual recovery scenarios, recorded key/byte counts and timings |
| Corrupted ComponentState | Truncating instance A resets only A; instance B and ordinary state retain values and backend audit-derived checksums | Component recovery scenario and screenshot |
| Subscription not yet confirmed | Single update persists immediately, leaves no opportunistic lease or Redis lock; final run 3.3 ms | `evidence/oplock-results.json` |
| Confirmed subscription and contention | Real acknowledgement allows a lease; a second manager's keyspace notification breaks its five-second lease in 2.7 ms | Same lock results |
| Concurrent manager operations | Thirty contending operations return every value 4–33 exactly once; persisted count 33 and audit 1–33 match; no lock remains after close | Same lock results |
| New → old → new persisted state | Old worker reads new pickle, assignments to frontend and backend fields persist, new worker reads them; schemas equal | `evidence/compatibility/results.json` and per-worker JSON/pickles |
| Old frontend list mutation after a new pickle | In-place frontend mutation persists and is read by the new worker | Same compatibility results |
| Old → new → old persisted state | New worker reads old pickle, updates frontend/backend fields, old worker reads the updated values; schemas equal | Same compatibility results |
| Documented rolling-deploy exception | An old worker's in-place mutable **backend** change to a new pickle changes memory but leaves `dirty_vars` empty and is not persisted; reproduced as expected | `caveat-*.json` and corresponding stored pickle files |
| Missing optional database packages | `db init`, `migrate`, `makemigrations`, and `status` each exit 1 with `reflex[db]` guidance and no traceback | `evidence/missing-db-results.json`, `no-db-*.log` |
| Bare SQLAlchemy migrations | `db init`, `makemigrations`, `migrate`, and status succeed with SQLAlchemy/Alembic present and SQLModel/Pydantic absent | `evidence/db-results.json`, CLI logs and generated migration text |
| Native mapped CRUD and multiple metadata bases | Original row retained after adding a nullable column and a second registered declarative base; both models can insert/select/update through Reflex's SQLAlchemy session | Same DB results and session logs |
| `rx.Model` when SQLModel is absent | Declaring a model still raises the expected `reflex[db]` guidance | Same DB results |

The browser run recorded **7 scenarios and 79 rendered-value assertions**, plus HTTP success, hydration, distinct-token, Redis key replacement and stored-byte checks. It had zero console errors, page errors, failed requests or HTTP errors. The server log has expected compile warnings for literal state-class names displayed by the repro, and no application traceback.

## Provenance

`evidence/provenance-before-db.json` captures all **52 distributions** before optional database installation. `evidence/provenance-with-db.json` captures **56** afterward. Only `SQLAlchemy==2.1.3`, `alembic==1.20.0`, `Mako==1.4.3`, and `MarkupSafe==3.0.4` were added; all existing versions remained unchanged. SQLModel and Pydantic were absent throughout these alpha database checks. Full exact pins are in `requirements-before-db.lock.txt` and `requirements-with-db.lock.txt`.

Alpha commands ran through `/private/tmp/reflex-alpha-core-state/venv/bin/python` (Python 3.13.16), with `uv run --no-project --python ...`, `PYTHONPATH` unset, and neutral app directories. Framework modules resolve to this environment's `site-packages`. `evidence/summary.json` adds the Redis manager/token/model module origins and SHA-256 hashes, source hashes, assertion counts, and cleanup checks. No direct-URL or editable distributions are present.

Rolling checks used the parent campaign's published 0.9.12 environment at `/private/tmp/reflex-pre-20261005-verify-stable/bin/python` (Python 3.12.1, 65 distributions). Each worker verifies its installed `reflex`/`reflex-base` versions and origins, rejects checkout `sys.path` entries and direct-URL installs, and records its complete graph. Both versions run identical saved `rolling_app.py`; the real Redis managers perform the persistence. Stored pickle bytes and schema hashes are retained per phase.

## Reproduction

Use only PyPI packages. Create the venv under `/private/tmp`, install `evidence/requirements-before-db.lock.txt` using `uv pip install --python <exact env interpreter> --index-url https://pypi.org/simple -r <lock file>`, and copy saved app/probe sources into neutral directories before executing them. Every execution must use `env -u PYTHONPATH REFLEX_DIR=/private/tmp/reflex-alpha-core-state/runtime UV_CACHE_DIR=/private/tmp/reflex-alpha-core-state/uv-cache /Users/masenf/.local/bin/uv run --no-project --python /private/tmp/reflex-alpha-core-state/venv/bin/python ...`.

The scripts use this campaign's exact neutral paths and disposable Redis endpoint. Redis must already be running; they do not start, stop, or flush the server.

- Redis app: initialize `reflex init --name redis_probe --template blank --no-agents`, put `redis_probe.py` at `redis_probe/redis_probe.py` and copy `rxconfig.py`. Run `reflex run --frontend-port 3111 --backend-port 8111` with `REFLEX_OPLOCK_ENABLED=false`, then the copied `browser_checks.py <output directory>`. It launches its own headless local Chrome through Playwright; user tabs are untouched.
- Missing DB: before adding database packages, run copied `db_missing.py <evidence directory>` from that same app directory.
- Opportunistic lock: run copied `oplock_checks.py <results.json>` from the Redis app directory with `REFLEX_OPLOCK_ENABLED=true`. `GatedPubSub` delays only delivery of an acknowledgement actually received from Redis; lock state, subscription commands, contention notifications, reads and writes remain real.
- Rolling workers: copy the three `compatibility/*.py` files into one neutral directory. With the exact published old/new environments above available, run `checks.py <compatibility evidence directory>`. It launches fresh workers, reads back actual stored bytes, verifies both directions and deletes its unique tokens afterward.
- SQLAlchemy: install only `sqlalchemy==2.1.3` and `alembic==1.20.0` with `uv pip install --python <exact env> --index-url https://pypi.org/simple ...`. In a **fresh** neutral directory create `plain_db/__init__.py`, copy `db_rxconfig.py` as `rxconfig.py`, and copy `db_checks.py`. Run `db_checks.py <evidence directory> <saved source directory>`. It copies the saved v1/v2 models, initializes SQLite, generates/applies migrations, asserts row retention, and verifies both registries.

## Cleanup, limits, and adversarial review

The app was stopped with SIGINT without a TTY; ports 3111 and 8111 are closed and no campaign app children remain. Database 5 began and ended empty. Cleanup deletes only this reproduction's unique browser/worker keys, never calls `FLUSHDB`, and leaves the root-owned Redis service running. No other Redis database was used.

1. The fresh Bun installer had appended a persistent PATH block for `/private/tmp/reflex-alpha-core-state/runtime/bun` to `~/.zshrc` despite the temporary `REFLEX_DIR`. Cleanup removed exactly that owned 114-byte append, preserving unrelated bytes. `evidence/bun-shell-cleanup.json` records before/after hashes and zero remaining owned-path references in checked zsh/bash/profile/fish files. No unrelated shell configuration was printed or saved. This installation side effect belongs in the campaign findings.
2. The rolling backend-mutable exception is an advertised limitation, reproduced explicitly. The old computed checksum also stays cached during that untracked mutation. Reassignment persists; this report does not propose a framework fix.
3. Redis corruption browser checks deliberately disable opportunistic caching so each event reads the externally altered payload. Op-lock readiness/concurrency is covered separately with two real managers; browser hot reload across worker versions, multi-host deployment and forced Redis outages/ACL denial are not covered.
4. Rolling tests use the old worker's existing optional-library graph and a different Python minor version. They cover built-in field values and one app state, not custom-object evolution, every root/router field, generated ComponentState names across releases, or changed app schemas. The schema-preserving cases actually tested pass.
5. Database coverage uses SQLite and bare declarative models; other SQL dialects, async sessions, ORM relationships and callable-default migration behavior belong to other campaign coverage.

No new state, Redis-lock, or SQLAlchemy regression was identified in these covered scenarios. Ruff check/format and compilation pass for all saved standalone sources; the final lock, migration, and cross-version worker sources were executed after lint changes. No framework changes or commits were made.
