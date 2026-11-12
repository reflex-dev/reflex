# Phase 7 close-out: published reflex 0.11.0 final (2026-11-12)

Packages under test came only from PyPI, through this container's proxy. Released tags: `v0.11.0`, `reflex-base-v0.11.0`,
`reflex-components-{code,core,radix}-v0.11.0`, `reflex-components-lucide-v1.1.2`, `reflex-hosting-cli-v0.2.2`,
`reflex-otel-v0.2.1`, `reflex-release-v0.2.2`. `origin/main` head is `46ffe5185` (#7864). Enterprise: reflex-enterprise
0.9.12 from PyPI, and the `ag_grid` demo taken from the enterprise checkout's `v0.9.12` tag with `git archive`, so nothing was
installed from a checkout.

Scratch work dir: `W=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/final`. Every venv
was built from `$W` with `uv --no-config venv`, a private `UV_CACHE_DIR=$W/uvcache`, `UV_LINK_MODE=copy`, Python 3.12.3 and
no prerelease flag. Plain-pip venvs were made with `--seed`, and their installs used `pip install --no-cache-dir`.
Ports: 3500 (frontend, and the single port in prod) and 8500 (dev backend). One server ran at a time. All were stopped at
the end, and ports 3500 and 8500 are free.
Browser: Chromium (`/opt/pw-browsers/chromium`) via `uv run --script .claude/skills/prerelease-test/scripts/drive_app.py`,
or via the enterprise fixture grid drivers. Evidence is in `phase7/final/` (339 KB, scanned for access-token strings: none).

## Results

| # | check | result | evidence / command |
|---|---|---|---|
| 1 | Publication | **PASS**: 20/20 packages OK with wheel+sdist on the first try, so no PyPI JSON fallback was needed (reflex 0.11.0, reflex-base 0.11.0, code/core/radix 0.11.0, lucide 1.1.2, hosting-cli 0.2.2, otel 0.2.1, release 0.2.2, and the unchanged siblings at their current versions) | `uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref v0.11.0` (exit 0), `logs/check_release_versions.txt` |
| 1b | Tag vs wheel contents | **PASS**: the 77 source files changed in `v0.10.1..v0.11.0` are byte-identical in the stock install. The 5 packages not installed are the expected ones: internal, otel, release, site-shared, workflow | `check_wheel_sources.py --repo /home/user/reflex --base v0.10.1 --ref v0.11.0 --site-packages $W/venvs/stock-uv/...`, `logs/check_wheel_sources.txt` |
| 2 | Stub audit | **PASS**: 122 stubs ship in both wheel and sdist, no foreign stubs, and every count matches `pyi_hashes.json` (core 36, radix 65, code 2, reflex 3, ...) | `check_release_versions.py --ref v0.11.0 --specs > specs.txt && xargs uv run --script .../audit_pyi.py --manifest-ref v0.11.0 < specs.txt` (exit 0), `logs/audit_pyi.txt`, `logs/specs.txt` |
| 3 | `reflex` 0.11.0 `Requires-Dist` | **PASS**: every reflex-* floor is final. `reflex-base==0.11.0`, `reflex-components-code>=0.11.0`, `-core>=0.11.0`, `-radix>=0.11.0`, `-lucide>=1.1.2`, `reflex-hosting-cli>=0.2.2`. The unchanged siblings stay at their current finals (dataeditor/moment >=0.10.1, the rest >=0.10.0). Also `redis<9.0,>=6.4` | `logs/metadata_requires_dist.txt` (read from each downloaded wheel's `METADATA`) |
| 3b | Sibling wheels' `Requires-Dist` | **PASS (informational)**: all floors are final. core 0.11.0: `reflex-base>=0.11.0`, `lucide>=1.1.0`, `sonner>=0.10.0`. radix 0.11.0: `reflex-base>=0.10.1`, `core>=0.10.1`, `lucide>=1.1.0`. code 0.11.0: `reflex-base>=0.10.0`, `core>=0.10.0`, `radix>=0.10.0`, `lucide>=1.1.0`. These floors sit below the train versions, but no reflex user can end up with a stale sibling, because reflex 0.11.0 itself requires `reflex-base==0.11.0`, core/radix/code `>=0.11.0` and lucide `>=1.1.2`. The low radix/code floors do work in practice: see 5b | same file |
| 4a | Stock `uv pip install reflex==0.11.0` | **PASS**: the graph is all-final, with 0 `a`/`b`/`rc`/`.dev` versions across 41 packages. reflex 0.11.0, reflex-base 0.11.0, code/core/radix 0.11.0, lucide 1.1.2, hosting-cli 0.2.2, build-sdk 0.1.1, dataeditor 0.10.1, moment 0.10.1, gridjs/markdown/plotly/react-player/recharts/sonner 0.10.0, **redis 8.1.0**, **granian 2.8.8**. `uv pip check` clean | `logs/stock_uv_freeze.txt`, `logs/stock_uv_check.txt` |
| 4b | Stock plain `pip install reflex==0.11.0` (pip 26.3) | **PASS**: the same 41 packages at the same versions as uv (the freeze diff differs only in name normalisation: `Pygments`, `typing_extensions`). `pip check` clean | `logs/stock_pip_freeze.txt`, `logs/stock_pip_check.txt` |
| 4c | `reflex init --template blank`, dev | **PASS**: clean on all four channels. Page "Welcome to Reflex!", title "Stock \| Index". The color-mode toggle switches `html.light` to `html.dark`. Console 0 messages (0 even before the benign filter), no page errors, no failed requests, no 4xx/5xx. Server log has no warnings or tracebacks. `/ping` returns pong and `/_health` returns `{"status":true}` | `logs/stock_dev.drive.json`, `logs/stock_dev_toggle.drive.json`, `logs/stock_dev.server.trimmed.log`, `shots/stock_dev.png` |
| 4d | same app, `reflex run --env prod` | **PASS**: clean on all four channels, with the "Built with Reflex" badge. `/sitemap.xml` returns 200. The plain-pip venv's own blank app in prod is also clean | `logs/stock_prod.drive.json`, `logs/stockpip_prod.drive.json`, `shots/stock_prod.png` |
| 5a | In-place upgrade from 0.10.1, with siblings held to 0.10.1's upload time (an existing 0.10.1 user) | **PASS**. Before: reflex/base/core/radix/code 0.10.1, lucide 1.1.1, hosting-cli 0.2.1, redis 7.4.1. `pip install -U reflex` upgraded exactly reflex 0.11.0, reflex-base 0.11.0, code 0.11.0, core 0.11.0, **lucide 1.1.2**, radix 0.11.0 and **hosting-cli 0.2.2**. `pip check` clean. The app is the blank template plus `State.count`, `increment`, an input `on_change`, `rx.icon`, `rx.callout` and `rx.code_block`. On 0.10.1 it was clean in dev and prod. After the upgrade, in the same dir with `.web/` and `reflex.lock/` kept, dev and prod are clean too: Count 0 → 2, "Hello ADA", 3 lucide svgs, callout and code block rendered, no console, network or server anomalies. A cold run (`rm -rf .web`) in prod is clean as well. The only `.web/package.json` change is a trailing newline (#7812's stable writer); no dependency changed | `logs/upg_held_before_freeze.txt`, `logs/upg_held_upgrade.txt`, `logs/upg_held_after_freeze.txt`, `logs/upg_held_after_pipcheck.txt`, `logs/upg_held_0{10,11}_{dev,prod}.drive.json`, `logs/upg_held_011_cold_prod.drive.json`, `logs/upg_held_package.diff`, `shots/upg_held_0{10,11}_prod.png` |
| 5b | In-place upgrade from a fresh `pip install reflex==0.10.1` done today | **PASS**. Today pip resolves 0.10.1 to a mixed graph: reflex/base/core 0.10.1 with **radix 0.11.0, code 0.11.0, lucide 1.1.2, hosting-cli 0.2.2**, all allowed by those packages' floors, and `pip check` is clean. The same app runs clean on that mixed graph in dev and prod. `pip install -U reflex` then upgrades reflex, reflex-base and core to 0.11.0 and leaves the rest already current. That ends at the same reflex-* set as 5a. `pip check` clean, dev and prod clean | `logs/upg_before_freeze.txt`, `logs/upg_pip_upgrade.txt`, `logs/upg_pip_after_freeze.txt`, `logs/upg_fresh_0{10,11}_{dev,prod}.drive.json` |
| 6 | Enterprise: `pip install reflex==0.11.0 reflex-enterprise==0.9.12` | **PASS**: resolves all-final (rxe requires `reflex[db]>=0.9.6`), giving sqlmodel 0.0.49, SQLAlchemy 2.1.8, alembic 1.20.1, pydantic 2.14.3 and redis 8.1.0. Adding the demo's requirements (faker 36.2.2, pandas 2.2.3) leaves 0 pre-releases and a clean `pip check` | `logs/ent_install.txt`, `logs/ent_freeze.txt` |
| 6b | ag_grid demo (rxe v0.9.12) in prod, `CI=true` | **PASS**. `REFLEX_DB_URL=sqlite:///reflex.db reflex db migrate` returns 0 and creates `friend` and `alembic_version`. The demo sets only `async_db_url`, and without the env var migrate says "db_url is not configured", which is known and not a regression (see db_upgrade NOTES). Prod single port 3500 with `REFLEX_ACCESS_TOKEN` comes up in 18 s. Fixture grid drivers (their version guard reads `0.11.0 0.9.12`): **smoke 17/17 routes** (every upstream route returns 200 with grids rendered); **features 31/32**, where the single miss is the known pre-existing clipboard Ctrl+C/V check (ENT-32); **model 20/23**, where the 2 ssrm misses are the same known ones as on a2 / rxe 0.9.11 and the third is `/qa-model-workaround` returning 404, because this run used the unmodified upstream demo without the QA overlay. Channels: console 0 errors, 1 AG Grid #129 warning (benign), 0 page errors, 0 failed requests, 0 4xx/5xx (apart from the overlay 404). Server log: 0 tracebacks; 2 pydantic `met` str→datetime serializer warnings (the known demo-data issue seen on 0.10.1) and the known rxe/demo deprecation warnings (`console.*`, `ArrayVar.foreach`, `disable_plugins` strings, form-control `id`) | `enterprise/ent_prod-{smoke,features,model}.txt`, `logs/ent_db_migrate.log`, `logs/ent_prod.server.trimmed.log`, `enterprise/*.jpg` |
| 7 | Changelogs on `origin/main` | **PASS**: across all 20 `CHANGELOG.md` files, 0 headings with a pre-release version and 0 lines mentioning one. The top entries are `## v0.11.0 (2026-11-11)` (root, reflex-base, code, core, radix), `## v1.1.2` (lucide), `## v0.2.2` (hosting-cli, release), `## v0.2.1` (otel). The root (78 lines), reflex-base (41) and core (13) 0.11.0 sections exist, with only `###` category subheadings and no alpha headings. No `news/` fragments are left for any released package; leftover fragments exist only for the unpublished internal, site-shared and workflow packages | `git show origin/main:<path>` over `git ls-tree -r origin/main`, `logs/changelogs_main.txt`, `logs/*CHANGELOG.md.v0.11.0.txt` |

## Defects

None found. Every anomaly seen is on the known-benign list or already recorded in this pass (ENT-32 clipboard, ssrm driver
assumption, the demo `met` datetime data, the rxe deprecation family, the `db_url` wording).

## Observations (no action needed)

- Because radix 0.11.0 and code 0.11.0 have `>=0.10.x` floors, anyone who runs `pip install reflex==0.10.1` today gets them
  next to reflex-base 0.10.1. That mixed graph ran clean (5b), so the low floors are compatible in practice.
- `pip install -U reflex` keeps redis 7.4.1, because pip's only-if-needed strategy leaves it alone and reflex 0.11.0 allows `>=6.4`. A fresh install
  gets redis 8.1.0. Both are finals.

## Rerun

```
W=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/final
export UV_CACHE_DIR=$W/uvcache UV_LINK_MODE=copy; cd $W
uv --no-config venv $W/venvs/stock-uv --python 3.12 && uv --no-config pip install --python $W/venvs/stock-uv/bin/python reflex==0.11.0
uv --no-config venv --seed $W/venvs/stock-pip --python 3.12 && $W/venvs/stock-pip/bin/pip install --no-cache-dir reflex==0.11.0
mkdir -p $W/apps/stock && cd $W/apps/stock && REFLEX_TELEMETRY_ENABLED=false $W/venvs/stock-uv/bin/reflex init --template blank
$W/bin/srv.sh start $W/venvs/stock-uv $W/apps/stock dev stock_dev    # scripts/srv.sh; prod: ... prod stock_prod
$W/bin/drive.sh $W/drv/stock_actions.json stock_dev                    # scripts/drive.sh + scripts/stock_actions.json
$W/bin/srv.sh stop stock_dev
# upgrade (5a): held 0.10.1 = uv pip install with --exclude-newer-package=<reflex pkg>=2026-10-27T01:29:13.479189Z for every
#   reflex* requirement of 0.10.1, then $W/venvs/upg-held/bin/pip install -U reflex; app source in apps/upg_held/,
#   actions in scripts/upg_actions.json
# enterprise (6): pip install reflex==0.11.0 reflex-enterprise==0.9.12 -r demos/ag_grid/requirements.txt;
#   git -C /home/user/reflex-enterprise archive v0.9.12 demos/ag_grid | tar -x -C $W/apps/ent;
#   srv.sh start <venv> <demo> prod ent_prod CI=true REFLEX_DB_URL=sqlite:///reflex.db REFLEX_ACCESS_TOKEN="$(cat $SB/secrets/reflex_access_token)";
#   fixture drivers copied from $SB/apps/enterprise/fx/grid/scripts (smoke_routes.py, drive_ag_features.py, drive_ag_model.py)
#   with SB=$W/fxsb (symlinks envs/ent, envs/driver) and $W/fx/pids/current.pgid = the server pgid
```

## Verdict

The published reflex 0.11.0 is good. Every package is published with complete stubs. Its metadata pulls in every
fixed sibling, and stock install, in-place upgrade and enterprise all resolve to final versions. Dev and prod run clean
in Chromium.
