# Cluster `ent_map_dnd_flow_mantine` — reflex-enterprise 0.9.5 demos on reflex 0.9.12a1 vs 0.9.11.post1

Tested 2026-09-19 with **PyPI packages only** (never the checkout at `/home/user/reflex`
or `/home/user/reflex-enterprise`). Demos: `map`, `dnd`, `flow`, `mantine`, `highcharts`,
`tickets`, copied unmodified out of the read-only clone
`/home/user/reflex-enterprise/demos/` except for one QA-only module noted below.

## TL;DR

| demo | 0.9.12a1 | 0.9.11.post1 | verdict |
|---|---|---|---|
| dnd (react-dnd) | **18/18** dev | (not needed) | clean |
| flow (xyflow) | **11/11 + 9/9** dev | (not needed) | clean |
| map (leaflet) | **13/13** dev | (not needed) | clean |
| mantine — shipped `/dates` | **52/52 steps**, 8 picker round-trips | (not needed) | clean |
| mantine — QA `/qa-slot` (PR #6850 + #7068) | **13/13** dev | (not needed) | clean |
| **tickets (`EventHandlerAPIPlugin`)** | **BACKEND DIES ON STARTUP** | starts fine | **REGRESSION — ISSUE 1** |
| highcharts | compile-diff only (browser run skipped, timebox) | compile-diff only | no diff beyond the two known compiler changes |

**Two regressions of this train, both rooted in reflex core:**

1. **ISSUE 1 (CRITICAL)** — `type(rx.State)` changed from the public
   `reflex.vars.BaseStateMeta` to the private `reflex.istate.validation._StateMeta`.
   Any downstream `class MyMeta(BaseStateMeta)` used as `metaclass=` on an `rx.State`
   subclass now raises `TypeError: metaclass conflict`. reflex-enterprise 0.9.5 does
   exactly this (`reflex_enterprise/auth/oidc/state.py:347,381`), so the **tickets demo's
   backend worker exits during `post_compile`** and the app never serves. Reproduces in
   **pure reflex with no reflex-enterprise at all**.
2. **ISSUE 2 (HIGH, security-relevant)** — PR #7068 renamed the root state's `router` base
   var into five `rx_router_*` vars. reflex-enterprise 0.9.5's
   `redact_router_session()` (`plugins/event_handler_api.py:733`) keys on the old
   `router` + FIELD_MARKER name, so it is now a **silent no-op** and the
   server-generated `client_token` / `session_id` — which the rxe source itself calls
   "a session-takeover vector" — survive into REST responses and event deltas.

Everything else in the cluster is clean: **0 page errors, 0 non-benign console messages,
0 4xx/5xx** across dnd, flow, map and mantine. The only network failures anywhere are
`*.tile.openstreetmap.org` (this sandbox's egress proxy blocks the host — environmental,
present on both versions).

Both PR #6850 (memo wrappers transparent to Slot-injected props/refs) and PR #7068
(router split) were verified to **work as advertised** in the browser — see "What was
tested", checks `slot_injects_name_onto_memo_input` and `router_*`.

## Exact rerun commands

```bash
SB=<any scratch dir>
D=$SB/apps/ent_map_dnd_flow_mantine
mkdir -p $D/logs $D/shots $D/out

# demo sources (unmodified copies; *_prev is the same source run on the old venv)
for d in map dnd flow mantine highcharts tickets; do
  cp -r /home/user/reflex-enterprise/demos/$d $D/${d}_new
  cp -r /home/user/reflex-enterprise/demos/$d $D/${d}_prev
done
# then overlay this directory's mantine_new/mantine/qa_slot.py + the two edited
# lines in mantine_new/mantine/mantine.py (see "QA-only module" below)

# venvs — run uv from a NEUTRAL cwd, never from /home/user/reflex (its
# [tool.uv] exclude-newer silently filters the fresh alphas out)
cd $SB
uv venv $SB/envs/ent_tk --python 3.11
uv pip install --python $SB/envs/ent_tk/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1' aiosqlite \
  "reflex-enterprise[mcp] @ file://$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl"

uv venv $SB/envs/entprev_tk --python 3.11
uv pip install --python $SB/envs/entprev_tk/bin/python --prerelease=allow \
  'reflex==0.9.11.post1' 'reflex-components-core==0.9.9' 'reflex-components-radix==0.9.9' \
  'reflex-components-code==0.9.5' 'reflex-components-dataeditor==0.9.2' \
  'reflex-components-gridjs==0.9.1' 'reflex-components-markdown==0.9.3' \
  'reflex-components-plotly==0.9.6' 'reflex-components-recharts==0.9.3' \
  'reflex-components-sonner==0.9.3' aiosqlite \
  "reflex-enterprise[mcp] @ file://$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl"
```

`CI=true` is mandatory for every enterprise run — `rxe.App` otherwise `exit()`s with
"`reflex-enterprise` is free to use but you must be logged in"
(`reflex_enterprise/app.py:104`).

### Servers (ONE at a time; this cluster's reserved ports 3620-3639 / 8620-8639)

```bash
cd $D/dnd_new     && CI=true REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/reflex run \
                     --frontend-port 3620 --backend-port 8620 --loglevel debug > $D/logs/dnd_new_dev.log 2>&1 &
cd $D/flow_new    && ... --frontend-port 3621 --backend-port 8621   # logs/flow_new_dev.log
cd $D/mantine_new && ... --frontend-port 3622 --backend-port 8622   # logs/mantine_new_dev3.log
cd $D/map_new     && ... --frontend-port 3623 --backend-port 8623   # logs/map_new_dev.log
cd $D/tickets_new && CI=true ... $SB/envs/ent_tk/bin/reflex     run \
                     --frontend-port 3625 --backend-port 8625      # logs/tickets_new_dev.log  -> ISSUE 1
cd $D/tickets_prev&& CI=true ... $SB/envs/entprev_tk/bin/reflex run \
                     --frontend-port 3630 --backend-port 8630      # logs/tickets_prev_dev.log -> starts fine
```

Poll `http://localhost:<FP>/` until 200 (first run does a bun install, 1-2 min here).
Stop a server by pid: `python3 $SB/bin/ports.py <FP> <BP>` lists the listening pids
(`ss`/`netstat` are not installed); killing `reflex run` can orphan the vite node
process, so re-check the ports afterwards.

### Drivers

```bash
cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drivers/drive_dnd.py        http://localhost:3620 $D/shots/dnd_new_dev  dnd_new_dev
  $SB/envs/driver/bin/python drivers/drive_flow.py       http://localhost:3621 $D/shots/flow_new_dev
  $SB/envs/driver/bin/python drivers/drive_flow_extra.py http://localhost:3621 $D/shots/flow_new_dev_extra
  $SB/envs/driver/bin/python drivers/drive_qa_slot.py    http://localhost:3622 $D/shots/qa_slot_new
  $SB/envs/driver/bin/python scripts/drive_mht.py        http://localhost:3622 actions/mantine_dates.json \
                                                         $D/out/mantine_dates_new.json $D/shots/mantine_dates_new
  $SB/envs/driver/bin/python drivers/drive_map.py        http://localhost:3623 $D/shots/map_new_dev  map_new_dev
```

Every driver prints one `RESULT PASS/FAIL <check>` line per check plus console /
network-failure / page-error summaries, writes screenshots + `results.json` into its shots
dir, and exits non-zero on any FAIL. `drivers/*` and `scripts/drive_mht.py` +
`actions/*.json` are carried over unchanged from the 2026-09-10 campaign
(`prerelease-testing/2026-09-10-v0.9.11a1/ent_map_dnd_flow` and
`.../ent_mantine_highcharts_tickets/pass2`), so the comparison is apples-to-apples.
`drivers/drive_qa_slot.py` is new for this campaign.

### Offline probes (no server, no licence gate — run from a NEUTRAL cwd)

```bash
cd $D
# ISSUE 1 — minimal pure-reflex repro, no reflex-enterprise involved
$SB/envs/ent_tk/bin/python     scripts/repro_statemeta.py envs/ent_tk/       # -> RESULT FAIL, exit 1
$SB/envs/entprev_tk/bin/python scripts/repro_statemeta.py envs/entprev_tk/   # -> RESULT PASS, exit 0

# ISSUE 2 — rxe's REST redaction against the new state shape
$SB/envs/ent_tk/bin/python     scripts/probe_router_redact.py envs/ent_tk      # -> VERDICT LEAK
$SB/envs/entprev_tk/bin/python scripts/probe_router_redact.py envs/entprev_tk  # -> VERDICT OK

# compiled-JS diff of all 6 demos on both versions (no bun, no paid-tier gate)
$SB/envs/ent/bin/python     scripts/compile_dump.py $D/<demo>_new  $D/out/js_<demo>_new  envs/ent/
$SB/envs/entprev/bin/python scripts/compile_dump.py $D/<demo>_prev $D/out/js_<demo>_prev envs/entprev/
# the compiled pages land in <appdir>/.web/app and <appdir>/.web/app_components
```

`scripts/compile_dump.py` is the cheap way to diff two reflex versions' frontend output:
it imports the app, runs `reflex.compiler.compiler.compile_app()` in process and copies
`.web/app*` out. It needs neither a bun install nor a paid subscription, so it is the only
way to see prod-shaped compiler output for an enterprise app without a licence.

### Resolved versions actually used

```
$ uv pip freeze --python $SB/envs/ent_tk/bin/python | grep -iE 'reflex|aiosqlite'
aiosqlite==0.22.1
reflex==0.9.12a1
reflex-base==0.9.12a1
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-enterprise @ file:///.../wheels/reflex_enterprise-0.9.5-py3-none-any.whl
reflex-hosting-cli==0.1.72

$ uv pip freeze --python $SB/envs/entprev_tk/bin/python | grep -iE 'reflex|aiosqlite'
aiosqlite==0.22.1
reflex==0.9.11.post1
reflex-base==0.9.11.post1
reflex-components-code==0.9.5
reflex-components-core==0.9.9
reflex-components-dataeditor==0.9.2
reflex-components-gridjs==0.9.1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.3
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.6
reflex-components-radix==0.9.9
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.3
reflex-components-sonner==0.9.3
reflex-enterprise @ file:///.../wheels/reflex_enterprise-0.9.5-py3-none-any.whl
reflex-hosting-cli==0.1.72
```

`$SB/envs/ent` / `$SB/envs/entprev` (the shared read-only venvs, same package sets minus
`aiosqlite`) were used for the four demos that do not need a DB.

---

## ISSUE 1 (CRITICAL, **regression of this train**, reflex core) — a user-defined `State` metaclass no longer works; the tickets demo's backend dies on startup

### What changed

| | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| `type(rx.State)` | `reflex_base.vars.base.BaseStateMeta` | **`reflex.istate.validation._StateMeta`** |
| `type(rx.State).__mro__` | `BaseStateMeta, ABCMeta, type, object` | `_StateMeta, BaseStateMeta, ABCMeta, type, object` |

`reflex/istate/validation.py` introduces `_StateMeta(BaseStateMeta)` and `rx.State` now
uses it. `BaseStateMeta` is a **public, importable name** (`from reflex.vars import
BaseStateMeta`), and deriving from it to add class-construction behaviour is the only way
a downstream package can hook state creation. That pattern is now a hard `TypeError`,
because `MyMeta(BaseStateMeta)` is not a subclass of `_StateMeta`. `_StateMeta` is
private, so there is no supported replacement.

### Minimal repro — pure reflex, **no reflex-enterprise**

`scripts/repro_statemeta.py`:

```python
from reflex.vars import BaseStateMeta

class MyStateMeta(BaseStateMeta):
    def __new__(cls, name, bases, attrs, **kwargs):
        if not kwargs.get("mixin"):
            attrs.setdefault("__annotations__", {})["injected"] = str
            attrs["injected"] = "hello"
        return super().__new__(cls, name, bases, attrs, **kwargs)

class MyState(rx.State, metaclass=MyStateMeta):   # <-- TypeError on 0.9.12a1
    n: int = 0
```

```
$ $SB/envs/entprev_tk/bin/python scripts/repro_statemeta.py envs/entprev_tk/
reflex 0.9.11.post1 ...
type(rx.State) = reflex_base.vars.base.BaseStateMeta
meta usable    = True
RESULT PASS  class created; injected = reflex___state____state____main______my_state.injected_rx_state_

$ $SB/envs/ent_tk/bin/python scripts/repro_statemeta.py envs/ent_tk/
reflex 0.9.12a1 ...
type(rx.State) = reflex.istate.validation._StateMeta
BaseStateMeta  = reflex_base.vars.base.BaseStateMeta
is subclass ok = True
meta usable    = False
RESULT FAIL  TypeError: metaclass conflict: the metaclass of a derived class must be a
             (non-strict) subclass of the metaclasses of all its bases
```

### End-to-end consequence: the tickets demo never serves

The tickets demo configures **no auth at all** — it only adds
`rxe.EventHandlerAPIPlugin`. That plugin's `post_compile` walks the page handlers, which
calls `is_exempt()`, which imports `reflex_enterprise.auth.oidc.state`, which executes
`class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta)` at
module scope. The backend worker raises and exits:

```
File ".../reflex/app.py", line 813, in __call__
    plugin.post_compile(app=self)
File ".../reflex_enterprise/plugins/event_handler_api.py", line 1486, in post_compile
    pages, all_dynamic_args = collect_page_info(app)
File ".../reflex_enterprise/plugins/event_handler_api.py", line 596, in collect_page_info
    if handler is not None and _is_public_handler(handler):
File ".../reflex_enterprise/plugins/event_handler_api.py", line 305, in _is_public_handler
    return not is_exempt(handler.state)
File ".../reflex_enterprise/auth/enforcement.py", line 947, in is_exempt
    from reflex_enterprise.auth.oidc.state import OIDCAuthState
File ".../reflex_enterprise/auth/oidc/state.py", line 381, in <module>
    class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta):
TypeError: metaclass conflict: ...
[ERROR] Unexpected exit from worker-1
```

The vite frontend keeps serving HTTP 200, so the symptom a user sees is a page that loads
and then never connects.

- Evidence: `logs/tickets_new_dev.TRACEBACK.txt` (full traceback),
  `logs/tickets_new_dev.log`, and `logs/tickets_prev_dev.log` /
  `logs/tickets_prev_dev.tail.txt` — the **same demo, same wheel, 0.9.11.post1 →
  `App running at: http://localhost:3630/` + `Backend running at: http://0.0.0.0:8630`**.
- Baseline checked: **yes**, 0.9.11.post1 is correct in both the minimal repro and the
  real app. This is a regression of 0.9.12a1.
- Blast radius: the whole `reflex_enterprise.auth` surface (OIDC, `AuthPlugin`, the
  `EventHandlerAPIPlugin` REST/OpenAPI surface and, by the same import chain,
  `plugins/mcp_auth`), plus any third-party or user code deriving from
  `reflex.vars.BaseStateMeta`.
- The orchestrator's `ent_import_probe.py` already sees the import-level half of this
  (`FAIL reflex_enterprise.auth.oidc.state -> TypeError metaclass conflict`, `BAD = 1`);
  what is added here is the root cause, the pure-reflex repro, and the fact that it takes
  down an ordinary enterprise app with no auth configured.

## ISSUE 2 (HIGH, **regression of this train**, reflex core × reflex-enterprise 0.9.5) — the REST API's session-token redaction is now a silent no-op

PR #7068 split the root state's `router` base var into `rx_router_session`,
`rx_router_headers`, `rx_router_page`, `rx_router_url`, `rx_router_route_id`, and
`router` itself "has no backing field, so it never reaches a delta".

reflex-enterprise 0.9.5's `redact_router_session()`
(`plugins/event_handler_api.py:733`) looks the router up **by name**:

```python
router_key = "router" + FIELD_MARKER
for sub in state_dict.values():
    if isinstance(sub, dict) and router_key in sub:
        sub[router_key] = _redact_router_value(sub[router_key])
```

That key no longer exists, so the function returns the dict untouched. Its docstring says
why that matters: *"so an API read never discloses the server-generated session token
(the websocket path keys on it, so leaking it would be a session-takeover vector)"*.
Call sites: `resolve_state_dict` (line 901, the REST `retrieve_state` response), the
event-response delta path (line 852 — with #7068 `rx_router_session` lands in the delta on
the **first event of a connection**, which is exactly what a REST-triggered handler
produces), and `plugins/mcp_builtin_resources.py:374`.

`scripts/probe_router_redact.py` builds the router exactly the way the plugin does
(`router_data_for_token(...)` → `state.router = RouterData.from_router_data(...)`), then
runs `redact_router_session()` over `state.dict()` and searches the result for the token:

```
0.9.11.post1:
  reflex___state____state:
      router_rx_state_ = RouterData(session=SessionData(client_token='SECRET-CLIENT-TOKEN', ...
  SECRET-CLIENT-TOKEN still present at: NOWHERE (redacted ok)
  VERDICT OK

0.9.12a1:
  reflex___state____state:
      rx_router_headers_rx_state_   = HeaderData(host='x', ...)
      rx_router_page_rx_state_      = PageData(path='/tickets', ...)
      rx_router_route_id_rx_state_  = /tickets
      rx_router_session_rx_state_   = SessionData(client_token='SECRET-CLIENT-TOKEN', client_ip='0.0.0.0', session_id='')
      rx_router_url_rx_state_       = URLData(...)
  SECRET-CLIENT-TOKEN still present at:
      ['.reflex___state____state.rx_router_session_rx_state_.client_token']
  VERDICT LEAK
```

The probe also confirms the **read** side of the property setter is fine on 0.9.12a1 —
`self.router.session.client_token`, `self.router.url`, `self.router.page.params`,
`self.router.url.query_parameters` and `self.router.headers.host` all read back correctly
after `state.router = RouterData.from_router_data(...)`, so PR #7068's switchboard works;
only rxe's name-keyed redaction broke.

- Evidence: `scripts/probe_router_redact.py` (run on both venvs, output above).
- Baseline checked: **yes** — `VERDICT OK` on 0.9.11.post1.
- Not reproducible end-to-end through HTTP **on 0.9.12a1 today**, because ISSUE 1 stops
  the same app from starting. It will surface the moment ISSUE 1 is fixed, so the two
  should be fixed together (or rxe 0.9.6 must key on the new names).
- Fix belongs on one of two sides: reflex could keep a `router` entry in `.dict()`, or
  reflex-enterprise must redact `rx_router_session` instead. Since rxe 0.9.5 is already
  published, a core-side compatibility shim is the only fix that protects existing
  installs.

---

## What was tested (per demo)

### dnd (react-dnd) — 18/18 dev, clean

`drivers/drive_dnd.py`: index cards; `/basic` and `/foreach` real
`mouse.down/move/up` drags with the `is_over` highlight sampled *while holding*
(`rgb(0,0,255)` → `rgb(0,128,0)`), `on_drop` toast + state move, drag back; `/kanban`
create 2 columns + 2 items through the forms, drag an item between columns
(`@rxe.static` `can_drop` preview), `on_end` toast, column reorder by dragging a heading,
localStorage persistence across reload. The `rx.EventChain.create` call sites at
`dnd.py:413/642/651` that PR #7122's interning touches all behave identically to the
previous campaign. `UNEXPECTED_CONSOLE 0 / NET_FAIL 0 / PAGE_ERRORS 0`.

### flow (xyflow) — 11/11 + 9/9 dev, demo unmodified, clean

`drivers/drive_flow.py`: index (6 pages via the shimmed `DECORATED_PAGES`); `/overview`
11 nodes / 6 edges / minimap / controls, node drag round-trip, node-toolbar emoji
(🚀→🔥); `/nodes/custom-node`; `/nodes/drag-handle` (handle drags, body inert);
`/nodes/connection-limit` connect + limit enforcement; `/nodes/add-node-on-edge-drop`;
`/nodes/intersections` highlight.

`drivers/drive_flow_extra.py`: single-node select + delete (11 → 10) sticking through
`on_nodes_change` → `apply_node_changes` → state round-trip; edge select + delete (5 → 4);
shift box-select 7 nodes + delete (10 → 3); connect-then-delete on
`/nodes/connection-limit`; SPA navigation across all 6 routes with back-navigation; node
position persisting across a hard reload **and** an SPA navigate-away-and-back
(`start=(0.0,100.0) dragged=(86.3,157.5) reload=(86.3,157.5) spa_back=(86.3,157.5)` — the
same numbers as the 0.9.11a1 campaign).

The `VarData`-heavy hooks in `flow/util.py` that PRs #7015 (var hashing) and #7198
(operand references) touch produce **no dropped hooks or imports**: the compiled
`app_components/flow/*.jsx` differ from 0.9.11.post1 only by the two expected compiler
changes (see "Compiled-output diff" below), and every `useCallback`/`useContext`/`useRef`
line is preserved verbatim.

### map (leaflet) — 13/13 dev, clean

`drivers/drive_map.py`: index cards; `/map-controls` non-default control placement (zoom
topright, scale bottomleft, attribution topleft); `/fly-to-location` two markers, hover
tooltip, popup with a working `rx.toast` button, mouse-wheel zoom → debounced `on_zoom`
state round-trip, click-on-map `on_click=lambda e: my_api.set_view(...)`, drag-pan,
`MapAPI.fly_to`, `locate()` with mocked geolocation (51.6, -0.2) → `on_locationfound`;
`/vector-layers` circle/circle-marker/polygon/polyline/rectangle + `get_bounds(callback=…)`.
The layer-event `EventChain` dict props all fire. 77 `net::ERR_TUNNEL_CONNECTION_FAILED`
to `*.tile.openstreetmap.org` — environmental, see "Benign observations".

### mantine — shipped `/dates`, 52/52 steps, clean

`scripts/drive_mht.py actions/mantine_dates.json`: 12 picker cards, 386-387 `mantine-*`
elements, and eight distinct `on_change` → backend → `rx.toast` round-trips captured:
DatePicker, DatePickerInput, MonthPicker, YearPicker (`Year selected: 2020-01-01`),
DateTimePicker (`Date selected: 2026-09-09 00:00:00`), the `Today` preset
(`Date selected: 2026-09-19`), TimeInput and TimePicker (`Time selected: 13:45`), plus
the Source tab rendering the page source through `rx.code_block`.
`FAILED STEPS: [] / CONSOLE ERRORS: [] / PAGE ERRORS: [] / HTTP>=400: []`.

### mantine — QA `/qa-slot` (new this campaign), 13/13 dev, clean

**QA-only module, NOT part of the shipped demo:**
`mantine_new/mantine/qa_slot.py`, registered by two edited lines in
`mantine_new/mantine/mantine.py` (an import and an `__all__` entry). It exists because
the shipped mantine demo has no `as_child` / Slot surface and no router-derived computed
var, so PR #6850 and PR #7068 would otherwise go untested in this cluster.

| check | result |
|---|---|
| `router_computed_var` — `@rx.var` reading `self.router.url.path` / `.query` | PASS `/qa-slot?qa=1` |
| **`slot_injects_name_onto_memo_input`** — PR #6850: `rx.input` under `rx.form.control(as_child=True, name="core_name")` | PASS, `input[name=core_name]` count=1 |
| `form_input_attrs` | `[{"id":"core-input","name":"core_name","type":"text"}]` |
| **`form_submit_delivers_field`** — `new FormData(form)` reaches `on_submit` | PASS, `('core_name','Ada')` present |
| `foreach_memo_chips_grow` — `rx.foreach` over a state list rendering an `@rx.memo` mantine pill | PASS 4 → 8 |
| `rx_cond_badge_flips` | PASS |
| `mantine_tags_input_reflects_state` — `rxe.mantine.tags_input` bound to a `list[str]` state var | PASS `["alpha","beta","t2","t3"]` |
| `event_chain_runs_both_links` — `yield QAState.step_two` | PASS `chain: one,two` |
| `background_task_streams` — `@rx.event(background=True)` | PASS `ticks: 3` |
| `client_state_hover_counter` — `rx._x.client_state` | PASS `hovers: 3` |
| `spa_nav_to_dates` | PASS 387 mantine elements |
| `router_var_after_spa_back` | PASS `/qa-slot?qa=1` |
| `router_var_after_hard_reload` | PASS `/qa-slot?qa=2` |

0 page errors, 0 non-benign console messages, 0 failed requests.
Screenshots: `shots/qa_slot_new/01_loaded.png`, `02_submitted.png`, `04_reload.png`.

### highcharts — compile-diff only

Browser run skipped for time. The compiled output differs from 0.9.11.post1 only by the
two expected compiler changes; nothing specific to highcharts. The previous campaign's
`actions/hc*.json` are carried in this directory so the run is one command away.

### tickets — blocked by ISSUE 1 on 0.9.12a1

Browser and REST coverage of the `EventHandlerAPIPlugin` surface on 0.9.12a1 is
**unavailable**: the backend never starts. What could be checked offline is in ISSUE 2.
(Independently, the 2026-09-10 campaign established that the tickets demo's shipped `/`
UI is inert on **both** 0.9.10.post2 and 0.9.11a1 because the OIDC substates join the
state tree without a frontend dispatcher — pre-existing, not re-tested here.)

## Compiled-output diff, all 6 demos, both versions

`scripts/compile_dump.py` compiled each demo on each version. Across all six, the
compiled pages and memo components differ **only** by these two changes, both expected:

1. **PR #6850** — every auto-memoized wrapper whose body renders a *tagged* root switched
   from `memo(({children}) => …)` to `memo(({children, ...rest}) => …)` with the root's
   props spliced through `{...mergeSlotProps(rest, ({ … }))}`, and `mergeSlotProps` added
   to the `$/utils/state` import. User-authored `@rx.memo` components (`ButtonEdge`,
   `ToolbarNode`, `KanbanColumn`, …) correctly keep the bare destructuring signature, as
   the PR's "Scope" section says they should. Memo names are content-hashed, so the hash
   changes ripple into the page that imports them — that is the only page-level diff.
   `mergician@v2.0.2` appears in the new bun install (`logs/*_dev.log`).
2. **PR #7068** — `State.router.page.path` used to compile to
   `reflex___state____state.router_rx_state_?.["page"]?.["path"]` and now compiles to
   `reflex___state____state.rx_router_page_rx_state_?.["path"]`, i.e. the per-field base
   var, as designed. No compiled page in any demo references a `router_rx_state_` any more.

A third, cosmetic change appears in the same files: every memo is now wrapped in
`/*#__PURE__*/ (() => { const X = memo(…); X.displayName = …; return X; })()` instead of
being assigned directly. Tree-shaking hint; no behavioural difference observed.

No dropped hooks, no dropped imports, no duplicated hooks — the specific risk the brief
called out for #7015 / #7198.

## Benign-but-surprising observations (recorded, not filed as issues)

1. **OSM tiles are unreachable in this sandbox** — 77 `net::ERR_TUNNEL_CONNECTION_FAILED`
   per map driver run against `*.tile.openstreetmap.org`. Environmental (the egress proxy
   blocks the host); every leaflet interaction works anyway because panes and SVG do not
   need the tile bitmaps. Present on both versions.
2. **`rx.form` `on_submit` payload carries extra id-keyed entries.** On `/qa-slot` the
   submit delivered
   `[('core_input','Ada'), ('core_name','Ada'), ('qa_form',None), ('submit_btn',None)]`
   — the same value under both the Slot-injected `name` and the input's `id`, plus `None`
   entries for the form's and the button's ids. Reflex's form collects refs by id in
   addition to `FormData`, so this is the framework's documented-ish behaviour rather
   than a #6850 effect; **not baselined** (would need a prev-version mantine build).
   Worth a look only if the duplication is unintended.
3. **`rx.form.control` rejects non-Radix children** —
   `TypeError: Only Radix TextFieldRoot and DebounceInput are allowed as children of
   FormControl` (`reflex_components_radix/primitives/form.py:112`) when an
   `rxe.mantine.tags_input` is placed under it. That is a deliberate guard, but it means
   PR #6850's Slot transparency cannot be exercised through `rx.form.control` with a
   third-party widget; the QA page tests the core `rx.input` shape instead.
4. **An app-module error during dev hot reload kills the backend worker permanently.**
   Adding a page that raises at evaluation time logged the traceback and
   `[ERROR] Unexpected exit from worker-1`; the server did not recover when the source was
   fixed and had to be restarted manually. Observed on 0.9.12a1 (`logs/mantine_new_dev.log`
   and `logs/mantine_new_dev2.log`); **not baselined**, and plausibly long-standing.
5. **Auto-generated `set_<var>` setters are gone.** `QAState.set_tags` raised
   `AttributeError: type object 'QAState' has no attribute 'set_tags'`; an explicit
   `@rx.event` handler is required. Expected for this train, but it is the kind of thing
   that breaks copy-pasted demo code — noted so nobody re-files it.
6. **Demo-code deprecation warnings**, identical in kind to the previous campaign and all
   originating in demo source, not in the released libraries: `Passing strings to
   disable_plugins`, `@rx.memo on <name> without explicit annotations` (9 in dnd, 9 in
   flow), `Passing base-component prop(s) key to @rx.memo`, `ArrayVar.foreach` →
   `ArrayVar.map`, `App(theme=...)` → `RadixThemesPlugin(theme=...)`, `Implicit Radix
   Themes enablement`, `RouterData.page` → `RouterData.url`.
7. **Driver pitfall, carried over:** Playwright's `text=Example` matches substrings
   case-insensitively and hits the page description paragraph instead of the `Example`
   tab, so the last two steps of `actions/mantine_dates.json` do not switch the tab back.
   Driver artifact, not a product defect.

## Not tested / structurally unavailable

- **Prod mode for every demo in this cluster.** `reflex run --env prod` and
  `reflex export` are refused by `reflex_enterprise.utils.check_paid_tier_for_command()`
  for an anonymous tier; `CI=true` bypasses only the *login* gate. The one exemption in
  rxe's code is reflex's own `APP_HARNESS_FLAG`, which I deliberately did not set —
  using a test-harness flag to get past a paid-subscription check is circumventing the
  vendor's licence gate, not testing it. Consequence for the release: **prod-mode
  coverage of reflex-enterprise apps is unavailable to unlicensed QA**; run these drivers
  from a paid-tier account, or from reflex-enterprise's own CI, if it is wanted.
  `scripts/compile_dump.py` gives the compiler-output half of prod coverage without the
  gate, and that is what the compiled-output diff above rests on.
- highcharts in the browser (timebox), tickets in the browser and over REST on 0.9.12a1
  (ISSUE 1), `drive_map_extra.py` (timebox).

## VERIFICATION

Independent adversarial verifier, 2026-09-19. Worked only from this NOTES.md, the shipped
scripts and the app sources (no access to the explorer's conversation). Own venvs built from
a neutral cwd; evidence under `verification/`. Ports 4120/4121 (frontend) + 9120/9121 (backend).
All processes started here were killed (`ports.py 4120 4121 9120 9121` reports nothing).

Versions used (full freeze in `verification/v_versions.txt`):

| venv | contents |
|---|---|
| `$SB/envs/vf_a` (mine, new) | `reflex==0.9.12a1`, `reflex-base==0.9.12a1` (pure reflex, no rxe) |
| `$SB/envs/vf_b` (mine, baseline) | `reflex==0.9.11.post1`, `reflex-base==0.9.11.post1` |
| `$SB/envs/ent_tk` (reused) | reflex 0.9.12a1 + all component alphas + `reflex_enterprise-0.9.5-py3-none-any.whl` |
| `$SB/envs/entprev_tk` (reused) | reflex 0.9.11.post1 + stable components + the same rxe 0.9.5 wheel |

Venv build (mine, from a neutral cwd — NOT the checkout):

```bash
cd $SB
uv venv $SB/envs/vf_a --python 3.11 && uv pip install --python $SB/envs/vf_a/bin/python --prerelease=allow 'reflex==0.9.12a1'
uv venv $SB/envs/vf_b --python 3.11 && uv pip install --python $SB/envs/vf_b/bin/python 'reflex==0.9.11.post1'
```

### ISSUE 1 — downstream `BaseStateMeta` subclass breaks every rxe auth/API app — **CONFIRMED (critical, regression)**

Reproduced exactly as written, at both levels, plus one extra confirmation the explorer did not run.

(A) Pure reflex, my own venvs, from `$SB/apps/verify_ent_map_dnd_flow_mantine`:

```bash
$SB/envs/vf_b/bin/python repro_statemeta.py envs/vf_b/   # RESULT PASS, exit 0
$SB/envs/vf_a/bin/python repro_statemeta.py envs/vf_a/   # RESULT FAIL TypeError, exit 1
```

```
0.9.11.post1: type(rx.State) = reflex_base.vars.base.BaseStateMeta   meta usable = True   RESULT PASS
0.9.12a1    : type(rx.State) = reflex.istate.validation._StateMeta   meta usable = False  RESULT FAIL
              TypeError: metaclass conflict: the metaclass of a derived class must be a
              (non-strict) subclass of the metaclasses of all its bases
```

Evidence: `verification/v_issue1_statemeta.txt`.

(B) Real app (tickets demo, copied unmodified out of `/home/user/reflex-enterprise/demos/tickets`):

```bash
cd $D/tickets_new  && CI=true REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent_tk/bin/reflex     run --frontend-port 4120 --backend-port 9120 --loglevel debug
cd $D/tickets_prev && CI=true REFLEX_TELEMETRY_ENABLED=false $SB/envs/entprev_tk/bin/reflex run --frontend-port 4121 --backend-port 9121
```

* 0.9.12a1: identical traceback to the one reported (`app.py:813 post_compile` ->
  `event_handler_api.py:1486/596/305` -> `enforcement.py:947` -> `oidc/state.py:381`
  `TypeError: metaclass conflict`), `[ERROR] Unexpected exit from worker-1`.
  `curl http://localhost:4120/` -> **200**, `curl http://localhost:9120/ping` -> **connection refused (000)**.
  Chromium load of `/` renders the app shell with the banner
  *"Cannot connect to server: websocket error. Check if server is reachable at ws://localhost:9120/_event"*
  and repeated `ERR_CONNECTION_REFUSED` console errors — exactly the "loads and never connects" symptom.
  Evidence: `verification/v_issue1_tickets_912_traceback.txt`,
  `verification/v_issue1_tickets_912_frontend.png`.
* 0.9.11.post1, same demo, same rxe 0.9.5 wheel: `App running at: http://localhost:4121/`,
  `Backend running at: http://0.0.0.0:9121`, `/ping` -> 200.
  Evidence: `verification/v_issue1_tickets_911_start.txt`.

(C) Extra confirmation of the root cause (not in the original report). Adding one QA-only shim to
`rxconfig.py` — `import reflex.vars as _rxvars; from reflex.state import State as _State;
_rxvars.BaseStateMeta = type(_State)` — makes the *unmodified* 0.9.12a1 tickets demo start
cleanly (`/ping` -> 200, no traceback). So the metaclass identity is the whole failure; nothing
else in rxe 0.9.5 is incompatible with 0.9.12a1's startup path.
Evidence: `verification/v_shim_rxconfig.py`, `verification/v_issue1_shim_start.txt`.

Refutation attempts, all failed:
* Not environmental — reproduces in a 2-package pure-reflex venv with no server, no bun, no ports.
* Not API misuse — `BaseStateMeta` is exported in `reflex_base.vars.__all__`
  (`packages/reflex-base/src/reflex_base/vars/__init__.py:37`) and re-exported by `reflex/vars/__init__.py`
  (`from reflex_base.vars import *`), so `from reflex.vars import BaseStateMeta` is public API.
* Not a documented behavior change — the 0.9.12a1 changelog documents #7136 only as
  "State vars, event handlers, and dynamic route arguments now reject names reserved by framework
  methods and bookkeeping before registration". Nothing says the state metaclass changed identity,
  and no replacement is exported (`_StateMeta` is private).
* Not pre-existing — 0.9.11.post1 passes both (A) and (B).

Root cause (release source, read-only): `reflex/istate/validation.py:90` `class _StateMeta(BaseStateMeta)`
and `reflex/state.py:629` `class BaseState(EvenMoreBasicBaseState, metaclass=_StateMeta)` (introduced by
`0d68f4615` "Validate reserved state names before registration (#7136)"). Downstream declaration sites:
`reflex_enterprise/auth/oidc/state.py:26,347,381`.

### ISSUE 2 — rxe's REST session-token redaction is a silent no-op — **CONFIRMED (high, regression)**

The in-process probe reproduced as written:

```bash
$SB/envs/entprev_tk/bin/python probe_router_redact.py envs/entprev_tk   # VERDICT OK
$SB/envs/ent_tk/bin/python     probe_router_redact.py envs/ent_tk       # VERDICT LEAK
#  -> ['.reflex___state____state.rx_router_session_rx_state_.client_token']
```

Evidence: `verification/v_issue2_inprocess_probe.txt`.

**The report said this "cannot currently be reproduced over HTTP". It can** — once ISSUE 1 is
shimmed out (section C above), the running 0.9.12a1 tickets demo leaks the token over real HTTP.
With `verification/v_leak_http.py` (issue an anonymous app token at `/_reflex/auth/token`, then
`POST /_reflex/retrieve_state` and `POST /_reflex/event/tickets___tickets____ticket_state/seed`):

| | 0.9.11.post1 (port 9121, unmodified demo) | 0.9.12a1 (port 9120, + ISSUE-1 shim only) |
|---|---|---|
| root state keys | `is_hydrated`, `router` | `is_hydrated`, `rx_router_headers`, `rx_router_page`, `rx_router_route_id`, `rx_router_session`, `rx_router_url` |
| `retrieve_state` session secrets | **NONE** — `router.session.client_token = ""` | **`rx_router_session.client_token = "95ddb344-b60b-447f-8d97-745bf8243192"`** |
| event-endpoint delta | **NONE** (blanked) | same token present in the ndjson delta |
| leaked token == the caller's bearer? | — | **no** (bearer `Z11NOX7KK…`), i.e. a server-side identifier the caller never had |

Evidence: `verification/retrieve_state_911.json`, `verification/retrieve_state_912.json`,
`verification/event_delta_911.ndjson`, `verification/event_delta_912.ndjson`, `verification/v_leak_http.py`.

Refutation attempts, all failed:
* Not the shim's doing — the shim only rebinds `reflex.vars.BaseStateMeta`; it touches neither the
  router vars nor redaction, and the no-app in-process probe shows the same on both venvs.
* Not a pre-existing leak — on 0.9.11.post1 the `router` var *is* present in the same responses with
  `client_token`/`session_id` blanked, so redaction genuinely worked there and silently stopped working.
* Not a harmless self-disclosure — the value is the server-generated session token bound to the
  presented bearer (`event_handler_api.py:1297` "the caller never names a session directly"), and rxe's
  own comment at `_ROUTER_SESSION_SECRETS` calls handing it back "a session-takeover vector".
* Not documented — the 0.9.12a1 changelog for #7068 says "`State.router` itself is unchanged", which is
  true for app code reading `self.router` (the probe confirms the read side is healthy), but the `router`
  **base var disappears from `.dict()` and from deltas**, which the changelog does not mention. Any
  downstream code that filters/redacts/inspects serialized state by var name is silently affected.

Root cause: core `reflex/istate/data.py` + `reflex/state.py` split under #7068 (root state now stores
`rx_router_session` etc.; `router` is a property with no backing field) vs. rxe 0.9.5
`plugins/event_handler_api.py:733` `redact_router_session()` keying on `"router" + FIELD_MARKER`
(also reached from `:852` `sanitize_agent_delta`, `:901` `resolve_state_dict`, and
`plugins/mcp_builtin_resources.py:374`). Fix belongs on one of the two sides before 0.9.12 GA —
rxe 0.9.5 is already published, so a core compat shim protects existing installs; otherwise rxe 0.9.6
must ship first.
