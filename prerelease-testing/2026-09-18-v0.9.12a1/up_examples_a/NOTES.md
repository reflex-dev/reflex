# Cluster `up_examples_a` — upgrade regression 0.9.11.post1 -> 0.9.12a1

Six `reflex-examples` apps (`counter`, `todo`, `clock`, `upload`, `lorem-stream`, `snakegame`)
driven end-to-end in Chromium on the previous stable, then upgraded **in place** (same venv, same
app dir, `.web/` and `reflex.lock/` preserved), then cold (`rm -rf .web`), then prod.
Plus an extra exploration page bolted onto the `counter` app that combines 0.9.12 changes with
`rx.ComponentState`, `rx._x.client_state`, `@rx.memo`, `rx.foreach`/`rx.cond`, an event chain and a
background task.

**Headline: no regressions found.** Every app behaved identically on 0.9.11.post1 and 0.9.12a1 in
dev, after the in-place upgrade, cold, and in prod. Zero browser console errors, zero page errors,
zero 4xx/5xx responses on every run. The two findings below are a pre-existing example-app bug and
a cosmetic packaging oddity, both recorded as low severity.

Date: 2026-09-19. Host: 4-CPU linux container, Node 22.22.2, bun 1.4.0, Python 3.11.15.

---

## 1. Environment / exact rerun commands

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
BASE=$SB/apps/up_examples_a          # working dir used for this run
export REFLEX_TELEMETRY_ENABLED=false
```

### Baseline venv (previous stable, resolved as a real user's would — NO `--prerelease`)

```bash
cd $SB                                # never from the reflex checkout
uv venv $SB/envs/up_a --python 3.11
uv pip install --python $SB/envs/up_a/bin/python \
    'reflex==0.9.11.post1' 'pytz==2022.7.1' 'lorem_text>=2.1'
```

The apps' own `requirements.txt` lines were honoured except for `reflex>=0.9.2`, which was replaced
by the pin above. `pytz` is `clock`'s dep, `lorem_text` is `lorem-stream`'s. No stubs were needed —
none of these six apps calls a blocked network service.

Resolved baseline (`uv pip freeze --python $SB/envs/up_a/bin/python | grep -i reflex`):

```
reflex==0.9.11.post1              reflex-components-markdown==0.9.3
reflex-base==0.9.11.post1         reflex-components-moment==0.9.4
reflex-components-code==0.9.5     reflex-components-plotly==0.9.6
reflex-components-core==0.9.9     reflex-components-radix==0.9.9
reflex-components-dataeditor==0.9.2   reflex-components-react-player==0.9.2
reflex-components-gridjs==0.9.1   reflex-components-recharts==0.9.3
reflex-components-lucide==1.0.4   reflex-components-sonner==0.9.3
                                  reflex-hosting-cli==0.1.72
```

### Copy the apps out of the checkout (never run them in place)

```bash
mkdir -p $BASE/{logs,shots,scripts}
cd /home/user/reflex-dev/reflex-examples
tar --exclude=.web --exclude=node_modules --exclude=.states --exclude=__pycache__ --exclude='*.db' \
    -cf - counter todo clock upload lorem-stream snakegame | tar -C $BASE -xf -
```

### Baseline run + drive (all six, sequentially, one server at a time)

```bash
cd $BASE && bash scripts/all.sh base          # -> logs/all-base.log, logs/<app>-base.drive.json
```

`scripts/all.sh <tag>` loops the six apps through `scripts/run_app.sh`, which starts
`reflex run --frontend-port 3460 --backend-port 8460 --loglevel debug`, polls the frontend until
200, runs `scripts/drive.py <app> <url> <tag> <shotdir>` (Playwright, console + pageerror +
requestfailed + >=400 response capture + screenshots), then kills the server **and** the orphaned
vite/node process still holding the port.

### In-place upgrade (same venv, same app dirs, `.web/` and `reflex.lock/` kept)

```bash
cd $SB
# what a naive upgrade resolves -- recorded for the packaging audit:
uv pip install --python $SB/envs/up_a/bin/python --upgrade --prerelease=allow --dry-run 'reflex==0.9.12a1'
# the actual upgrade:
uv pip install --python $SB/envs/up_a/bin/python --upgrade --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1'
cd $BASE && bash scripts/all.sh up             # -> logs/all-up.log, logs/<app>-up.drive.json
```

Resolved after upgrade (`uv pip freeze --python $SB/envs/up_a/bin/python | grep -i reflex`):

```
reflex==0.9.12a1                  reflex-components-markdown==0.9.4a1
reflex-base==0.9.12a1             reflex-components-moment==0.9.4
reflex-components-code==0.9.6a1   reflex-components-plotly==0.9.7a1
reflex-components-core==0.9.10a1  reflex-components-radix==0.9.10a1
reflex-components-dataeditor==0.9.3a1  reflex-components-react-player==0.9.2
reflex-components-gridjs==0.9.2a1 reflex-components-recharts==0.9.4a1
reflex-components-lucide==1.0.4   reflex-components-sonner==0.9.4a1
                                  reflex-hosting-cli==0.1.72
```

### Cold run and prod run

```bash
cd $BASE && for a in counter todo clock upload lorem-stream snakegame; do rm -rf $a/.web; done
bash scripts/all.sh cold                       # -> logs/all-cold.log
bash scripts/allprod.sh                        # reflex run --env prod on ONE port (3461)
```

### Exploration page on the `counter` app (0.9.12a1 only)

`counter/counter/extras.py` is **added by this QA run**, registered at `/extras` from
`counter/counter/counter.py`. Drive it with:

```bash
cd $BASE/counter && $SB/envs/up_a/bin/reflex run --frontend-port 3460 --backend-port 8460 --loglevel debug &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $BASE/scripts/extras_probe.py http://localhost:3460/ up $BASE/shots
```

### Persisted-state-across-upgrade probe

```bash
# app copy: $BASE/todo_persist (plain `todo`), profile: $BASE/pwprofile
# write phase on 0.9.11.post1, then read phase on 0.9.12a1 with the SAME client token injected
$SB/envs/prev/bin/reflex run --frontend-port 3460 --backend-port 8460 &     # write
$SB/envs/driver/bin/python $BASE/scripts/persist_probe.py http://localhost:3460/ write $BASE/pwprofile $BASE/shots
TOKEN=$(python3 -c "import json;print(json.load(open('$BASE/shots/todo-persist-write.json'))['token'])")
$SB/envs/up_a/bin/reflex run --frontend-port 3460 --backend-port 8460 &     # read
$SB/envs/driver/bin/python $BASE/scripts/persist_probe.py http://localhost:3460/ read $BASE/pwprofile $BASE/shots "$TOKEN"
```

Ports used throughout: frontend **3460** (dev) / **3461** (prod, both flags), backend **8460**.
No redis was needed (all six apps use the default `StateManagerDisk`).

---

## 2. What each app was driven through

| app | flow (identical on every tag) |
|---|---|
| `counter` | read count, 3x Increment, Decrement, Randomize, reload, colour-mode button |
| `todo` | read seed items, add 3 items via the form (Enter), finish/delete the first, reload |
| `clock` | read zone, flip the switch on, watch 2.5 s of ticking, change zone to Europe/Paris **while running**, flip off, confirm no further ticks, reload (cookie zone + `on_load` reset) |
| `upload` | `set_input_files` two files, Upload, read the rendered link list, reload, `GET` an uploaded file through the backend and compare the body |
| `lorem-stream` | 3x "New Task", let the background streams run, toggle one stream off, kill one task, add another, navigate (`/?nav=1`) while streams run, confirm the stream text kept growing |
| `snakegame` | RUN, six keyboard moves through the `GlobalKeyWatcher` (arrows + `h`/`k`), PAUSE, confirm the board freezes, `Escape` to resume via the key watcher, reload |
| `counter/extras` (new) | 7 bumps watching the websocket deltas, `rx._x.client_state` set, two independent `rx.ComponentState` toggles, event chain into another state + a background task, upload through an `rx.upload` inside `@rx.memo`, client-side nav to `/` and back, direct load of `/extras` |

Each app was run at four tags: `base` (0.9.11.post1) / `up` (0.9.12a1, preserved `.web`) /
`cold` (0.9.12a1, `.web` deleted) / `prod` (0.9.12a1, `--env prod`).
Per-run JSON with every captured value lives in `logs/<app>-<tag>.drive.json`.

---

## 3. Results

### 3.1 Functional comparison — all six apps PASS at every tag

Every stable observation matched across `base` / `up` / `cold` / `prod`. Examples:

* `counter`: `0 -> 3 -> 2 -> <random>`, value survives a reload (disk state manager, same token).
* `todo`: seed `['Write Code','Sleep','Have Fun']` -> `+3 items` -> first item removed -> survives reload.
* `clock`: ticks once a second while the switch is on (`7:32:05 PM` -> `7:32:07 PM`), zone change to
  Europe/Paris applies immediately **while the background tick task is running**
  (`4:36:23 AM`), stops ticking when switched off, and after a reload the `rx.Cookie` zone is still
  `Europe/Paris` while `on_load` has reset the switch to `unchecked`. Screenshot:
  `screenshots/clock-up-paris.png`.
  *Note on the cluster brief:* the current `clock` example does **not** use `rx.moment`; it drives an
  analog + digital clock from a `@rx.event(background=True)` tick loop, so there is no
  moment-0.9.4 `on_change`-on-mount behaviour to observe here.
* `upload`: both files land on disk (`uploaded_files/alpha.txt`, `beta.txt`), the progress bar
  reaches `data-value="100"`, the rendered links point at `http://localhost:8460/_upload/<name>`,
  and fetching one returns `200` with the exact bytes uploaded. Same in dev, cold and prod.
* `lorem-stream`: three concurrent background streams keep appending text; toggling one off leaves
  the others running; `kill` removes one card; **a navigation to `/?nav=1` does not interrupt the
  remaining streams** (text length kept growing across the navigation: 148 -> 209 chars).
* `snakegame`: the `GlobalKeyWatcher` receives arrow keys, `h`/`j`/`k`/`l` and `Escape` (Escape
  flipped the switch `unchecked` -> `checked`); PAUSE freezes the 19x19 grid (361 cells, byte-identical
  DOM over 2 s). The `Game Over` in `screenshots/snakegame-up-playing.png` is my own key sequence
  reversing the snake into itself — it does the same on 0.9.11.post1.

### 3.2 In-place upgrade mechanics

The first 0.9.12a1 run against a `.web/` compiled by 0.9.11.post1 was clean for all six apps:
lockfiles restored from `reflex.lock/`, frontend recompiled (`Compiling: 100% 15/14`), `bun install
--frozen-lockfile` re-run, new lockfile saved back to `reflex.lock/`. **No state/schema mismatch, no
`client_error` socket event, no hydration failure** — despite the router state keys being split in
#7068. Full first-run logs: `logs/<app>-up.server.log`.

`.web/package.json` diff (identical for all six apps, `packagejson/<app>-base.package.json` vs
`packagejson/<app>-up.package.json`):

```
  "@react-router/node":     8.3.1 -> 8.4.0
  "react-router":           8.3.1 -> 8.4.0
  "@react-router/dev":      8.3.1 -> 8.4.0   (devDependencies)
  "@react-router/fs-routes": 8.3.1 -> 8.4.0  (devDependencies)
+ "mergician": "v2.0.2"                       (new dependency)
```

The transitional `warn: incorrect peer dependency "react-router@8.3.1"` lines during the upgrade
install are the documented benign migration noise; the final `bun.lock` is consistent
(`grep -c 8.3.1 .web/bun.lock` -> 0, `8.4.0` -> 8) and `reflex.lock/package.json` matches `.web/package.json`.

**Naive-upgrade resolution is fine on this train.** `uv pip install --upgrade --prerelease=allow
'reflex==0.9.12a1'` alone (dry-run) pulls *all* the component alphas — core 0.9.10a1, radix 0.9.10a1,
code 0.9.6a1, dataeditor 0.9.3a1, gridjs 0.9.2a1, markdown 0.9.4a1, plotly 0.9.7a1, recharts 0.9.4a1,
sonner 0.9.4a1 — so the previous campaign's "stable components left behind" trap does not reproduce.
Evidence in `logs/` and section 1 above.

### 3.3 Cold run and prod run

`rm -rf .web` then re-run: all six apps produced results identical to the preserved-`.web` run on
every stable key. Prod (`reflex run --env prod --frontend-port 3461 --backend-port 3461`): all six
built and served, every flow identical to dev, zero console errors. The `counter` prod build also
prerendered the added `/extras` route (`Prerender (html): /extras -> build/client/extras/index.html`)
and shut down cleanly on SIGTERM (`Reflex app stopped.`, no "exit code 143" — #6981).

### 3.4 `reflex init` on the oldest-looking app (`snakegame`)

`snakegame` is the most legacy-flavoured of the six (it imports `reflex.constants.colors.Color`,
`reflex.event.EventSpec` and `reflex.utils.imports.ImportDict` and hand-rolls a `GlobalKeyWatcher`
component). `reflex init` with 0.9.12a1 on a pristine copy exits 0 with **no migration warnings and
no deprecation warnings** (`logs/snakegame-init.log`): it copies the templates, restores lockfiles,
writes `reflex.lock/package.json`, initialises `.npmrc`/bun config and the public dir. The only
warning is the standard `SitemapPlugin is enabled by default but not explicitly added to the config`
notice, which also appears on 0.9.11.post1. No npmmirror fallback errors occurred in this run.

### 3.5 Exploration on `/extras` (0.9.12a1) — all PASS

`logs/extras-up.json` has the raw record including the websocket frames.

* **#6946 (uncached-var delta suppression) holds, measured.** `bucket_uncached`
  (`@rx.var(cache=False)`, value `clicks // 3`) appears in the delta only on the bumps where it
  actually changes:

  ```
  bump 1  {"clicks_rx_state_":1,"clicks_uncached_rx_state_":1,"bucket_cached_rx_state_":0}
  bump 3  {"bucket_uncached_rx_state_":1,"clicks_rx_state_":3,"clicks_uncached_rx_state_":3,"bucket_cached_rx_state_":1}
  bump 4  {"clicks_rx_state_":4,"clicks_uncached_rx_state_":4,"bucket_cached_rx_state_":1}
  bump 6  {"bucket_uncached_rx_state_":2,"clicks_rx_state_":6,"clicks_uncached_rx_state_":6,"bucket_cached_rx_state_":2}
  ```

  It is present at bumps 3 and 6 and absent at 1, 2, 4, 5, 7 — exactly the claim — and the rendered
  value stayed correct throughout (`bucket-uncached` read `2` at `clicks=7`). Worth knowing: the
  *cached* twin `bucket_cached` is still re-sent on **every** delta even when its value is unchanged,
  because it is invalidated by `clicks`. The optimisation is uncached-var-only, as documented, but the
  asymmetry is easy to misread from the changelog line. Recorded as an observation, not a defect.
* **#7176 (`@rx.memo` dropping app wraps) is fixed in a real app.** An `rx.upload` nested inside an
  `@rx.memo` function accepted a file and the handler ran: the page log gained
  `uploaded memo-up.txt 20b` (`screenshots/extras-up-memoupload.png`).
* **#7068 router split:** `rx.State.router.url.path` and `rx.State.router.session.client_token` render
  correctly on direct load, after client-side navigation and after a back-navigation. A computed var
  declared with the legacy `deps=["router"]` still recomputes correctly. It did **not** emit the
  documented deprecation warning in my app, which is correct behaviour rather than a bug: with
  `auto_deps` on (the default) the var body's `self.router.url.path` access already contributes the
  per-field router deps, and `reflex/state.py:1211` only warns when the dep set carries `router` and
  *none* of the new `ROUTER_VARS` — i.e. only the pure legacy string form with `auto_deps=False`.
* `rx._x.client_state` value survived a client-side navigation to `/` and back (`client-updated`).
* Two `rx.ComponentState` instances stayed independent (`a=ON`, `b=OFF`).
* Event chain `ExtraState.chain -> CounterState.increment -> ExtraState.background_ticks` produced
  `counter=1` and `bg=3`, and the chained `rx.foreach` log rendered.
* `rx.cond` flipped at the right threshold; state survived client-side nav and a direct page load.
* Console on the whole run: zero notable messages, zero page errors, zero >=400 responses.

### 3.6 Persisted `.states/` across the upgrade (protocol step 4)

`todo_persist` was driven on 0.9.11.post1 with a persistent Chromium profile, adding
`OLDSTATE-alpha` / `OLDSTATE-beta`; the two resulting pickles are kept verbatim in
`logs/states-0911/`. The same directory was then run on 0.9.12a1 with the **same client token**
injected into `sessionStorage` (the token lives in `sessionStorage`, not `localStorage`, so a plain
persistent profile is not enough — `scripts/persist_probe.py` takes the token as argv[5]).

Result on 0.9.12a1: the page came up with the **default** seed items rather than the two OLDSTATE
items, then behaved normally (add / delete worked, the pickles were rewritten with the new content,
no traceback, no console error, no `client_error`).

**This is not a 0.9.12 regression.** The identical control — restore the same 0.9.11-written pickles
and reopen with 0.9.11.post1 and the same token — produced exactly the same default seed items
(`logs/todo_persist-control.server.log`). A disk-persisted state from a previous process is simply
not re-attached to a reconnecting token on either version. The relevant upgrade question — does a
0.9.11-written pickle break a 0.9.12 backend — answers **no**: the files were read/replaced cleanly.

Evidence caveat: `persist_probe.py` writes `todo-persist-<phase>.json`, so the control pass
overwrote the 0.9.12a1 read pass's JSON. `logs/todo-persist-read.json` therefore holds the
**control** (0.9.11.post1) result; both passes produced byte-identical values, and the two runs are
distinguishable by their server logs (`logs/todo_persist-read2.server.log` is the 0.9.12a1 pass,
`logs/todo_persist-control.server.log` the 0.9.11.post1 control). Pass a distinct `<tag>` if you
rerun this.

---

## 4. Findings

### F1 (low, pre-existing on both versions) — `upload` example never refreshes its file list

`upload/upload/upload.py` declares

```python
@rx.var
def files(self) -> list[str]:
    return ["/".join(p.parts[1:]) for p in Path(rx.get_upload_dir()).rglob("*") if p.is_file()]
```

`@rx.var` defaults to `cache=True`, and this var has no state dependencies, so it is computed once
per state instance and never invalidated. Uploading a file therefore does **not** add it to the
rendered "Files:" list — the list only ever shows whatever was on disk when the state was created.

Repro (identical on 0.9.11.post1 and 0.9.12a1):
1. `rm -rf $BASE/upload/uploaded_files` and run the `upload` app.
2. Load the page, `set_input_files` one file, click Upload.
3. The file is written to `uploaded_files/` (verify with `ls`) and the progress bar hits 100%, but no
   `<a>` link appears under "Files:".
4. Reload the page; the link still does not appear until a *fresh* backend state instance is created.

Evidence: `logs/upload-probe-base.json` (0.9.11.post1) — a third file `probe-base.txt` was uploaded
while the list kept showing only the two files that existed at hydrate time; `logs/upload-base.drive.json`
(`links: []` with the files present on disk); `screenshots/upload-probe-base-afterupload.png`.
**Baseline checked: yes. Regression: no** — this is an example-app bug that predates the release
(the example was written when `@rx.var` still defaulted to uncached). Worth an upstream fix in
`reflex-examples` (`@rx.var(cache=False)`), not a release blocker.

### F2 (low, new in this train, cosmetic) — generated `package.json` pins `mergician` with a leading `v`

The 0.9.12a1 template adds `"mergician": "v2.0.2"` to `.web/package.json` and
`reflex.lock/package.json`. Every other dependency in the generated file uses a bare semver
(`"react": "19.2.8"`, `"vite": "8.2.2"`, …). npm/bun accept a leading `v`, and it installed here
correctly (`bun.lock` resolves `mergician@2.0.2`, sha512 recorded), so nothing breaks — but it is an
inconsistency in a framework-generated file that a user reading their lockfile will notice, and a
stricter registry proxy or a tool that string-compares the spec against the resolved version could
trip on it.

Evidence: `packagejson/counter-up.package.json` line 13, `logs/counter-up.server.log`
(`'mergician@v2.0.2'` in the install command line).
**Baseline checked: yes** — the key is absent from `packagejson/*-base.package.json`, so the entry is
new in 0.9.12a1. **Regression: no** (nothing regressed functionally).

---

## 5. Benign / pre-existing noise seen (not findings)

* `Warning: Event handler on_submit expects (dict[str, typing.Any]) -> () but got (dict[str, str]) -> ()
  as annotated in State.add_item instead.` — printed by the `todo` example on **both** 0.9.11.post1
  and 0.9.12a1 (`logs/todo-base.server.log` and `logs/todo-up.server.log`). Pre-existing.
* `Warning: SitemapPlugin is enabled by default, but not explicitly added to the config` — every app,
  both versions.
* `Debug: Unable to bind to any port for 10: [Errno 97] Address family not supported by protocol` —
  this container has no IPv6; reflex retries on AF_INET and continues. Both versions.
* `Warning: rx._x contains experimental features` and the `@rx.memo` "add `rx.Var[...]` annotations"
  deprecation — both come from *my* `extras.py`, not from the examples.
* Killing `reflex run` orphans the `react-router dev` node process, which keeps the frontend port
  bound and will silently serve the *previous* app to the next test. `scripts/run_app.sh` handles
  this (`freeports()` loops on `$SB/bin/ports.py` and kills by pid); anyone rerunning this cluster
  should keep that guard. This happens on both versions.

## 6. Layout of this directory

```
NOTES.md                    this file
counter/ todo/ clock/ upload/ lorem-stream/ snakegame/   app sources as run
                            (counter/counter/extras.py + the two add_page lines in
                             counter/counter/counter.py are additions made by this QA run)
todo_persist/               plain `todo` copy used for the state-persistence probe
scripts/drive.py            per-app Playwright flows + console/network capture
scripts/run_app.sh          start/poll/drive/kill one app at one tag (dev or prod)
scripts/all.sh              the six apps at one tag (dev); scripts/allprod.sh the prod pass
scripts/extras_probe.py     drives /extras and records the websocket deltas
scripts/upload_probe.py     focused upload DOM/ws probe used for F1
scripts/persist_probe.py    write/read a state pickle across the upgrade with a fixed token
logs/*.drive.json           every captured value, per app per tag
logs/*.server.log           trimmed reflex server logs (config dumps stripped)
logs/states-0911/           the two .states pickles written by 0.9.11.post1
packagejson/                .web/package.json before (`-base`) and after (`-up`) the upgrade
screenshots/                21 PNGs: base vs up for each app plus the extras/persist probes
```
