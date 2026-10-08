# a5_upgrade_ent — enterprise, install/upgrade and third-party re-verification on reflex 0.10.0a5 (2026-10-08)

Agent `a5_upgrade_ent`. Everything installs from PyPI (uv `--no-config`, cwd `$SB`), or for enterprise from the offline
0.9.7a5 wheel (shared venvs `a5-ent` / `a4-ent` / `s912-ent-a5`, used read-only). Nothing was installed from or run inside
`/home/user/reflex` or `/home/user/reflex-enterprise`. Every app config / driver carries a venv guard (`QA_EXPECT_VENV` /
`TP_EXPECT_VENV` in rxconfig, `VENV_GUARD` banner in the enterprise start scripts, a `/scratchpad/envs/driver/` assertion in
every Playwright driver). Host: 4-CPU container shared with `a5_hydration_router`; one app server set at a time (three
sequential chains: `ent/bin_chain1.sh`, `chain2.sh`, `chain3.sh`).

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
export W=$SB/apps/a5_upgrade_ent   # this DEST dir mirrors $W (minus .web, dbs, run dirs, a4ref/); tools/sync_dest.sh copies
# set-up from the repo: copy this DEST dir to $W (the scripts carry absolute $W paths), mkdir -p the logs/out/run dirs.
```
$W was created from the a4 pass's work dir (`2026-10-08-a4/a4_upgrade_ent/`, paths rewritten a4_upgrade_ent -> a5_upgrade_ent);
the a4 pass's own logs/outputs sit in `$W/a4ref/` (not copied to DEST: they are in `../../2026-10-08-a4/a4_upgrade_ent/`).
Ports (all mine): enterprise auth 3620/8620 dev, 8621 prod, 3622-3623/8622-8623 + backend-only 8626 (matrix), Redis 8629,
mock IdP 8638; grid/demos 3470-3479/8470-8479; upgrades 3600/8600 (fd), 3604/8604 + stub 8608 (gh), 3612 (twr), 3614 (twa4),
Redis 8609; N-001 prod CRUD 3602; third party 3463/8463, 8467, Redis 8469.

(sections below are filled in as runs complete)

## Part 2a — install paths (N-001, F-005, F-006, F-014) — `inst/`
```bash
$W/inst/bin/n001.sh > $W/inst/logs/n001.txt          # pip venvs (py3.11 / 3.14 'reflex[db]==0.10.0a5', py3.12 plain 'reflex==0.10.0a5'), no --pre
SPECS="uv311:uv:3.11:db uv314:uv:3.14:db" $W/inst/bin/n001.sh > $W/inst/logs/n001-uv.txt   # uv venvs, --prerelease=allow
$W/inst/bin/dbcli.sh > $W/inst/logs/dbcli.txt        # greenlet_probe + reflex db init / makemigrations / migrate / makemigrations noop, per venv
$W/inst/bin/prod_crud.sh > $W/inst/logs/prod_crud.txt   # dbcli app --env prod on 3602: add x2, reload (drive_app.py)
cd $W/inst/cli_neutral && for a in component "component init" ...; do $SB/envs/a5/bin/reflex $a; done   # F-014 -> logs/f014_component_a5.txt
```
Venvs `$SB/envs/a5_upgrade_ent-n001-{uv311,uv314,pip311,pip314,f006pip312}`; nothing added by hand (no greenlet, no pydantic pin).
| check | result | evidence |
|---|---|---|
| N-001 pip py3.11 / py3.14 `pip install 'reflex[db]==0.10.0a5'` (NO `--pre`) | rc 0; sqlalchemy 2.1.4 + **greenlet 3.5.6** (via the extra) + sqlmodel 0.0.48 + alembic 1.20.0, pydantic 2.14.0; `import reflex.model` OK; `pip check` clean | `logs/n001.txt`, `logs/freeze-pip3*.txt` |
| N-001 uv py3.11 / py3.14 `uv pip install --prerelease=allow 'reflex[db]==0.10.0a5'` | rc 0; same graph (greenlet 3.5.6, pydantic 2.14.0); `uv pip check` clean | `logs/n001-uv.txt` |
| uv WITHOUT `--prerelease=allow` | refuses: "reflex-base was requested with a pre-release marker ... try --prerelease=allow" — pre-existing uv semantics, identical on every alpha (10-06 pymatrix_install, 10-07 reverify_db_install) | `logs/install-uv311-noflag.log` |
| N-001 original repro + F-005 fresh DB, all 4 db venvs: `greenlet_probe.py`, `reflex db init`, `makemigrations --message init`, `migrate`, `makemigrations --message noop` | every command rc 0, 0 error lines; `rx.Model` subclass created; 1 version file (the noop generated nothing); tables `alembic_version`, `note`; sqlmodel 0.0.48 (>= 0.0.45) | `logs/dbcli.txt`, `logs/db-<venv>-*.log` |
| F-006 `pip install reflex==0.10.0a5` (py3.12, no extra, no `--pre`) | rc 0; the full train: reflex/reflex-base 0.10.0a5, reflex-build-sdk 0.1.0a1, components code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2, dataeditor/react-player/sonner 0.10.0a1, lucide 1.1.0a1, hosting-cli 0.2.0a1 (= the a4 set with reflex/reflex-base at a5) | `logs/n001.txt`, `logs/freeze-f006pip312.txt` |
| F-014 `reflex component`, `component init/build/share`, `--help` forms | every form prints "`reflex component` was removed in Reflex 0.10. Wrap React components directly in your app (https://reflex.dev/docs/wrapping-react/overview/) and start reusable component packages from the component template: https://github.com/reflex-dev/component-template", rc 1 (`--help` forms rc 0); hidden from `reflex --help` (= a3/a4) | `logs/f014_component_a5.txt` |
| benign | `reflex.Model has been deprecated in version 0.9.2 ...` printed by `greenlet_probe.py` on a5, a4, a3 and 0.9.12 alike (pre-existing, documented deprecation) | `inst/run/probe_neutral` re-run |

## Part 3a — third-party grep for #7360 patterns + import sweep — `tp/`
Sources: the 37 wheels the a4 pass collected (`$SB/downloads/wheels/`, the a4_class_state downstream set incl. reflex-enterprise
0.9.7a4), the PyPI reflex-enterprise 0.9.7a5 wheel, `downloads/{reflex-local-auth,reflex-google-auth,reflex-magic-link-auth}` and
reflex-examples (ebe19ff). Unpacked under `$W/tp/grep7360/unz/` (scratch only).
- `tp/logs/grep_7360.txt` (pattern `router.headers|headers.cookie|headers["cookie"]|raw_headers|router_data|.router.session|router.url|router.page`):
  **every hit is server side** (`self.router...` / `instance.router...` / `state.router...` in handlers, on_load handlers, plugins).
- `tp/logs/grep_7360_frontend.txt` (any `State.router...` Var / `router.headers.cookie|raw_headers|[...]` outside `self.router`):
  **no frontend (component) use of `State.router.headers.cookie`, `headers["cookie"]` or `raw_headers` in any downstream package**; the only
  `.headers.cookie` read is enterprise `auth/cookie.py:225 instance.router.headers.cookie` (server side, by design unchanged by #7360).
- On_load handlers among the hits that read the router (the part #7360 changed — on_load events no longer carry router_data) and where
  each is exercised: enterprise page guards (`page_guard.py:163/216 login_url_for(str(state.router.url))`), OIDC callback
  (`oidc/state.py:2065` query params, `:1329/1342` `_redirect_uri`/`_index_uri`, `:1571` `redirect_to`), MCP consent (`consent_state.py:224`
  `txn`), `auth/replay.py:84`, audit `route` -> Part 1 suites + `vauthd`/`deeplink.py`; reflex-local-auth `login.py:59` (require_login
  redirect_to) and form-designer `form_entry.py:21` (client_token) -> local-auth flows + form-designer upgrade; reflex-magic-link-auth
  `page.py:16` (link query params) -> magic-link flows; github-stats `widget.py:18` (`page.params` appearance) -> seq_gh;
  **reflex-azure-auth 0.1.2** (`state.py:240` `auth_callback` on_load reads code/state from `router.url.query_parameters`, `:181`
  `redirect_to_login` stores `self.router.url`) -> `tp/az/` (pointed at the mock IdP); reflex-examples `azure_auth` (MSAL, `router.page.params`
  on its callback) needs real Azure — not run; recaptcha (`router.headers` x_forwarded_for in a click handler) — server side, not exercised.
- Import sweep (`tp/run/probes/import_sweep.py` on my `$SB/envs/a5_upgrade_ent-tp`, built by `tp/bin/build_venv.sh` = the a4 spec with
  `==0.10.0a5`): **22/22 identical to the a4 pass** (`tp/logs/import_sweep.cmp_a4_a5.txt`; the one "DIFF" is reflex-chakra's identical
  `_issubclass` ImportError differing only in the venv path in the message); reflex-chakra and community reflex-ag-grid fail as known,
  reflex-clerk imports with its 1 known warning. Matches the sibling a5_class_state (22 = a4, 112 enterprise modules import).
