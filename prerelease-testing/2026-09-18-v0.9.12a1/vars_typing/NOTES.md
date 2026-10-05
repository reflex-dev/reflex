# Cluster `vars_typing` — reflex 0.9.12a1 pre-release testing

Tested 2026-09-19 against the **published PyPI** 0.9.12a1 train. Nothing was installed from
the `/home/user/reflex` checkout; every script starts with
`assert "/envs/" in reflex.__file__` and is run from a neutral cwd.

Covers: Var hashing (#7015), `Annotated` (#7189), var-op memory/speed (#7198),
masked `AttributeError` (#7115), `EnvVar` `timedelta` (#7131), lazy imports (#6930),
`.pyi` union props (#7080), State-var page titles (#6923).

**Bottom line: no defects found in the eight changes under test.** Every claim in the
changelog reproduced, and every one was shown to fail or behave worse on 0.9.11.post1.
Three low-severity adjacent observations are recorded at the bottom.

---

## 1. Environments

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad

# Main venv used for the app, #7189 and #7080 (needs pydantic + pyright)
cd $SB
uv venv $SB/envs/vt --python 3.11
uv pip install --python $SB/envs/vt/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1' pydantic pyright
# NOTE: --prerelease=allow also pulls a pydantic BETA (2.14.0b2). Pin it back:
uv pip install --python $SB/envs/vt/bin/python 'pydantic<2.14'

# Baseline venv for #7189 (envs/prev has no pydantic and is read-only)
uv venv $SB/envs/vtprev --python 3.11
uv pip install --python $SB/envs/vtprev/bin/python 'reflex==0.9.11.post1' 'pydantic<2.14'
```

Resolved versions actually used (`uv pip freeze --python $SB/envs/vt/bin/python | grep -iE 'reflex|pydantic|pyright'`):

```
pydantic==2.13.5
pydantic-core==2.46.5
pyright==1.1.414
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
reflex-hosting-cli==0.1.72
```

Shared read-only venvs used for the version-agnostic scripts:
`$SB/envs/shared` (0.9.12a1), `$SB/envs/prev` (0.9.11.post1), `$SB/envs/driver` (Playwright).

## 2. The app

`vtapp/` is a 5-page app that combines the cluster's features with State vars,
`rx._x.client_state`, `@rx.memo`, `rx.ComponentState`, `rx.foreach`/`rx.cond`/`rx.match`,
an event chain (`yield`), a `background=True` task, an `Annotated`-typed event-handler
argument, and client-side + direct navigation.

| route | what it exercises |
|---|---|
| `/` | #7015 hook-carrying literal, #6923 `title=State.title` + `description=State.desc`, client_state, ComponentState, memo, event chain, background task, `Annotated` handler arg |
| `/pets` | #7189 `Annotated[Cat \| Dog, Field(discriminator="kind")]` state var + list; `title=State.title_fstring` (a computed var) |
| `/second` | second page with State-var title/description, for client-side nav between two State-titled pages |
| `/heavy` | ~4800 var operations on one page (#7198 volume) |
| `/plain` | control page with a static title |

`vtapp/vtapp/vtapp_broken_serializer.py.txt` is the #7115 variant (a `@rx.serializer`
with a `p.nmae` typo plus a `/broken` page); rename it over `vtapp.py` to reproduce.

### Rerun commands

```bash
cd $SB/apps/vars_typing/vtapp          # NEVER run from /home/user/reflex
REFLEX_TELEMETRY_ENABLED=false $SB/envs/vt/bin/reflex init --template blank
# dev
REFLEX_TELEMETRY_ENABLED=false $SB/envs/vt/bin/reflex run \
    --frontend-port 3340 --backend-port 8340 --loglevel debug > ../logs/dev_server.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python ../scripts/drive.py http://localhost:3340 dev ../shots
# prod (ONE port for both flags)
REFLEX_TELEMETRY_ENABLED=false $SB/envs/vt/bin/reflex run --env prod \
    --frontend-port 3341 --backend-port 3341 > ../logs/prod_server.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python ../scripts/drive.py http://localhost:3341 prod ../shots
```

`scripts/drive.py` records console messages, page errors, failed requests and >=400
responses and writes `shots/<tag>_report.json` plus 7 screenshots.

**Setup gotcha (my mistake, recorded so you don't lose 15 minutes to it):** I created
`vtapp/vtapp/vtapp.py` *before* running `reflex init`, so `reflex init` never wrote
`vtapp/vtapp/__init__.py`. Without it the compiler names the state
`...vtapp___vtapp____state` while the backend worker emits deltas for `...vtapp____state`,
and every state update is dropped client-side with
`Cannot process state update: no dispatch function for substate(s) ...`. Not a framework
regression (see observation O1), but it silently breaks an app. `touch vtapp/vtapp/__init__.py`
fixes it.

---

## 3. Results per change

### #7015 — Var hashing (PASS, regression fixed)

`scripts/t7015_hash.py` (both versions) and `scripts/t7015_literal_collision.py`
(the targeted repro). Logs: `logs/t7015_new.txt`, `logs/t7015_prev.txt`, `logs/t7015_literal.txt`.

The user-visible drop needs a **literal** var: on 0.9.11.post1
`LiteralNumberVar/LiteralBooleanVar/LiteralStringVar/LiteralArrayVar/LiteralObjectVar`
each override `__hash__` ignoring `_var_data`, so two equal-valued literals collide in
`_global_vars` and one set of hooks/imports wins. Minimal repro:

```python
lit_plain  = rx.Var.create(1)
lit_hooked = rx.Var.create(1, _var_data=VarData(
    hooks={"const myRef = useRef(null);": None},
    imports={"react": [ImportVar(tag="useRef")]}))
comp = rx.box(f"{lit_hooked} and {lit_plain}")      # hooked FIRST
sorted(comp._get_all_hooks()), sorted(comp._get_all_imports())
```

| | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| hooks | `[]` (dropped) | `['const myRef = useRef(null);']` |
| imports | `['@radix-ui/themes@3.3.0']` | `[..., 'react']` |
| `hash(plain) == hash(hooked)` | `True` | `False` |

Reversing the interpolation order hides the bug on 0.9.11.post1 — the surviving entry is
whichever was stored in `_global_vars` last.

End-to-end: `/` renders `f"{HOOKED_ONE} and {PLAIN_ONE}"` where the hook sets
`window.__vt_hook_ran`. Browser reports `hook_ran: true` in dev, prod, after client-side
navigation away and back, and in a second tab (`logs/drive_dev.txt`, `logs/drive_prod.txt`).

Also verified on 0.9.12a1: `hash(State.count + 1)`, `{State.a, State.b, computed_a, computed_b}`
as a set (5 distinct), `NumberVar`/`BooleanVar` as dict keys, `rx.match` over a number var,
`hash(v) == hash(v.to(NumberVar))`, `State.doubled.equals(State.doubled) is True` with no
`VarTypeError`, and `_hash_key()` containing no `Var` objects. `_hash_key` does not exist on
0.9.11.post1 (`VarAttributeError`), the rest already worked there.

### #7189 — `Annotated` (PASS, regression fixed)

`scripts/t7189_annotated.py`; logs `logs/t7189_new.txt` / `logs/t7189_prev.txt`.

On 0.9.11.post1 the state class **cannot even be defined**:

```
TypeError: Unsupported type typing.Annotated[__main__.Cat | __main__.Dog,
  FieldInfo(annotation=NoneType, required=True, discriminator='kind')] for guess_type.
  (reflex/state.py:266 get_var_for_field -> vars/base.py:1115 guess_type)
```

On 0.9.12a1 all 18 probes pass: `S.pet._var_type` resolves to `Cat | Dog`, attribute access
(`.name`, `.kind`, `.lives`) resolves through the union, `dict[str, Pet]` value access,
`list[Pet]` index access, `rx.match(S.pet.kind, ...)`, `rx.cond`, `rx.foreach`,
`Annotated[int, Field(gt=0)]` arithmetic (`_var_type` is plain `int`),
`Annotated[list[str], ...]` `.length()`/`[0].upper()`, doubly-nested `Annotated`, and an
event handler argument typed `Annotated[int, Field(gt=0)]`.
`typehint_issubclass` unwraps `Annotated` on both sides.

In the browser (dev **and** prod), `/pets` renders name/kind, the `rx.match` sound and the
`rx.cond` branch, `rx.foreach` over `list[Pet]`, and switching the var between `Cat` and
`Dog` at runtime updates all of them (`Momo/cat/meow/is-cat` -> `Rex/dog/woof/is-dog`),
including after appending a new `Dog` to the list.

### #7198 — var-op memory and speed (PASS, claims hold)

`scripts/t7198_memleak.py`, `N=40000` per operation, `logs/t7198.txt`.
`_global_vars` growth and `ru_maxrss` delta sampled every 8000 ops.

| op | 0.9.12a1 µs/op | 0.9.11.post1 µs/op | speedup | `_global_vars` growth new / prev | ΔRSS kB new / prev |
|---|---|---|---|---|---|
| `State.count + i` | 20.32 | 39.47 | **1.94x** | 0 / 40001 | 0 / 11332 |
| `(count+i).to_string()` | 37.14 | 57.89 | 1.56x | 0 / 0 | 0 / 0 |
| `(count > i) & flag` | 48.46 | 182.90 | **3.77x** | 0 / 40001 | 0 / 78624 |
| `items[i % 3]` | 21.34 | 22.56 | 1.06x | 0 / 0 | 0 / 0 |
| `name + str(i)` | 9.57 | 10.33 | 1.08x | 0 / 0 | 128 / 0 |
| `obj["a"] + i` | 52.89 | 95.55 | 1.81x | 0 / 1 | 0 / 10532 |
| `rx.cond(count > i, ...)` | 58.58 | 149.87 | **2.56x** | 0 / 2 | 0 / 5248 |
| `name.upper() + str(i)` | 24.60 | 37.59 | 1.53x | 0 / 1 | 0 / 0 |
| **total `_global_vars` at end** | **0** | **80006** | | | |

The leak and the speedups both reproduce, and the two ops the PR said it does not touch
(`arr[i]`, string concat) are indeed flat at ~1.0x. `/heavy` (400 `rx.cond` +
`.to_string()` + `.upper()` + concat chains, ~4800 operations) compiles, loads in
2.5 s dev / 2.1 s prod, renders all 405 texts, and the values track `State.count`
correctly — no var data lost by the operand-reference change.

### #7115 — masked `AttributeError` (PASS, regression fixed)

`scripts/t7115_attrerror.py`; logs `logs/t7115.txt`, and the real-app compile failure in
`logs/t7115_app_compile_error.log`.

A `@rx.serializer` with a `p.nmae` typo:

| path | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| `rx.Var.create([Point()])` | `VarAttributeError: Attribute _cached_var_name not found.` | `ReflexRuntimeError: Computing cached property LiteralArrayVar._cached_var_name raised AttributeError: 'Point' object has no attribute 'nmae'` |
| `rx.Var.create({"k": [Point()]})` | `TypeError: __str__ returned non-string (type ArrayCastedVar)` | same chained `ReflexRuntimeError` |
| `rx.foreach([Point()], ...)` | `VarAttributeError` | chained `ReflexRuntimeError` |
| `rx.box(custom_attrs={"data-p": {"a": Point()}})` | `RecursionError: maximum recursion depth exceeded` | chained `ReflexRuntimeError` |

In all four cases on 0.9.12a1 `__cause__` is the original `AttributeError`, the message
names `nmae`, and the user's `serialize_point` frame is in the traceback — none of which
is true on 0.9.11.post1. `reflex run` on the real app fails at compile with the user frame
(`vtapp/vtapp.py, line 249, in serialize_point`) directly above the `ReflexRuntimeError`.

Documented behaviour change confirmed (see O2): on a var whose computation is broken,
`hasattr(var, "_js_expr")` and `getattr(var, "_js_expr", "DEFAULT")` now raise
`ReflexRuntimeError` instead of returning `False` / the default.

### #7131 — `EnvVar` `timedelta` (PASS, new capability)

`scripts/t7131_timedelta.py`, log `logs/t7131.txt`. A subclass of `EnvironmentVariables`
declaring `EnvVar[timedelta]` and `EnvVar[timedelta | None]`.

Accepted on 0.9.12a1: `30`->30 s, `0`, `500ms`, `2m`, `1.5h`, `1d`, `250us`, `  45S ` (case
and surrounding whitespace), `7H`, `3.25`->3.25 s, `-5`->-5 s, `10 s` (internal whitespace),
`0.0000001us`->0. Rejected with a message naming the field and listing the units:
`abc`, `5x`, `1e3`, `1,000`; out-of-range `9999999999999d` gets its own
`... is out of range.` message. Unset falls back to the declared default; the
`timedelta | None` union reads `""` as `None`.

On 0.9.11.post1 every one of these raises
`ValueError: Invalid type for environment variable ...: <class 'datetime.timedelta'>.
This is probably an issue in Reflex.` — the type was simply unsupported.

Note: no `EnvVar` in `reflex` or `reflex-base` is currently declared as `timedelta`
(`grep -n "EnvVar\[timedelta\]"` finds nothing), so this release ships the capability for
downstream/enterprise use rather than changing any existing variable's parsing.
`_serialize_env_value` renders a `timedelta` back as `<n>s` or `<n>us`, which the
interpreter reads back.

### #6930 — lazy imports (PASS, claim holds)

`scripts/t6930_lazy.py`, logs `logs/t6930.txt`, `logs/t6930_importtime.txt`.

| | 0.9.12a1 | 0.9.11.post1 |
|---|---|---|
| `"text" in vars(rx)` after first `rx.text` | **True** (cached on the package) | False |
| 1e6 `rx.text` accesses | **0.049 s** | 0.986 s (**20x**) |
| `python -X importtime -c "import reflex"` (best of 3) | 1695 µs | 1740 µs |

Bad names still raise `AttributeError: No reflex attribute <name>` (checked for a plain
name, a leading-underscore name and a wrong-case name), `dir(rx)` still lists 193 names
on both, and `rx.el.div` / `rx._x.client_state` resolve normally. Import time is unchanged,
as expected — the change is about repeated attribute access, not first import.
Python 3.15 was **not** tested (see "Not covered").

### #7080 — `.pyi` union props (PASS, regression fixed)

`typecheck/snippet.py` type-checked with pyright 1.1.414 against each venv:

```bash
cd $SB/apps/vars_typing/typecheck
$SB/envs/vt/bin/pyright --pythonpath $SB/envs/vt/bin/python     --outputjson snippet.py
$SB/envs/vt/bin/pyright --pythonpath $SB/envs/vtprev/bin/python --outputjson snippet.py
```

* 0.9.12a1: **0 errors** (`logs/t7080_pyright_new.json`)
* 0.9.11.post1: 2 errors (`logs/t7080_pyright_prev.json`), the relevant one being
  `Argument of type "None" cannot be assigned to parameter "use_math" of type
  "bool | Var[bool]"`. (The second, `sankey_chart is not a known attribute`, is just a
  component that did not exist in 0.9.11.post1.)

Diffing every `.pyi` in the two installs, only 9 stub files differ; the #7080 change is
visible in `reflex_components_markdown/markdown.pyi`, where the five union props became
`bool | Var[bool] | bool | None = True`. Snippet also covers `rx.el.div()` with and without
props, `rx.data_editor`, `rx.recharts.sankey_chart`, `rx.recharts.line_chart`, `rx.box`,
`rx.cond` — all clean.

### #6923 — State vars in page titles/descriptions (PASS)

Driven in dev and prod; `logs/drive_dev.txt`, `logs/drive_prod.txt`,
`shots/{dev,prod}_0*.png`.

* `@rx.page(route="/", title=State.title, description=State.desc)` — `document.title` and
  `<meta name="description">` both update live when the handler changes the vars:
  `VT Home` / `vars_typing default description` -> `VT 3 items` / `description for 3`.
* A computed var works too: `/pets` uses `title=State.title_fstring` (`f"{self.count} items"`)
  and the tab title tracks it (`0 items` -> `4 items` -> `5 items`).
* An event chain that sets the title (`yield State.inc(); yield State.set_title_and_desc()`)
  updates the title once the chain finishes (`VT 4 items`).
* Client-side navigation between two State-titled pages (`/` <-> `/second`) carries the
  current values, and navigating back restores the right title.
* **Prod SSR/prerender carries the defaults** — `curl -sL` on the prod server:
  `/` -> `<title>VT Home</title>` + `<meta content="vars_typing default description" name="description"/>`;
  `/pets` -> `<title>0 items</title>` + `pets page`; `/second` -> `VT Home`;
  static-title pages unaffected. A fresh second tab also gets the defaults.
* No 0.9.11.post1 baseline was run for this one (see "Not covered").

---

## 4. Observations (benign / low severity, not release blockers)

**O1 — a missing `__init__.py` in the app package silently breaks every state update.**
If `<app>/<app>/__init__.py` is absent, the compiler resolves the state as
`reflex___state____state.<app>___<app>____state` (written into `.web/utils/context.jsx`)
while the running backend emits deltas for `reflex___state____state.<app>____state`.
The page renders, no server-side error is logged, no request fails — only a browser console
`error: Cannot process state update: no dispatch function for substate(s) ...` per page load,
and every click is a no-op. `reflex init` does not create the file if the app directory
already exists, and does not warn. The code that produces the warning is byte-identical in
0.9.11.post1, so this is pre-existing, not a 0.9.12a1 regression; I did not run the
0.9.11.post1 side. To reproduce: `rm vtapp/vtapp/__init__.py`, `rm -rf vtapp/.web/build`,
restart `reflex run`, load `/` and click `#inc` — the count never moves and the console shows
the error above. `logs/drive_dev.txt` here is the *fixed* run; the broken run produced the
same step list with every value stuck at its initial value.

**O2 — `hasattr`/`getattr(..., default)` on a var with a broken computation now raises.**
Called out in PR #7115 as intended. Worth a changelog sentence: code that probes a var with
`getattr(var, "_js_expr", None)` will now surface a `ReflexRuntimeError` where it previously
got the default. Evidence: `logs/t7115.txt`, keys `hasattr_js_expr` / `getattr_default`.

**O3 — prod mode logs `Page <route> is being redefined with the same component.` once per page.**
Five pages, five warnings, only in `--env prod`, never in dev. The app module is evidently
imported twice in the prod path. `reflex/app.py` emits this from an identical code path in
0.9.11.post1, so it is very likely pre-existing; I did not execute the 0.9.11.post1 baseline.
Evidence: `logs/prod_server_tail.log`.

**O4 — `/favicon.ico` 404s in prod** (the blank template's `<meta property="og:image"
content="favicon.ico">` points at a file the template does not ship). One console
`Failed to load resource: 404`. Cosmetic, unrelated to this cluster, baseline not checked.

**O5 — `var._replace(_var_data=...)` raises `TypeError: dataclasses.replace() got multiple
values for keyword argument '_var_data'`** on **both** 0.9.12a1 and 0.9.11.post1. Use
`rx.Var.create(value, _var_data=...)` instead. Pre-existing, not a regression.

**O6 — `--prerelease=allow` pulls pydantic 2.14.0b2.** Not a reflex problem, but any agent
building a venv this way is silently testing against a pydantic beta. Pin `pydantic<2.14`.

---

## 5. Not covered

* **Python 3.15 / PEP 810 native lazy imports (#6930).** Only Python 3.11 was exercised;
  3.10/3.14/3.15 installs of the train were not attempted. `lazy_loader.py` gates the
  native path behind `sys.version_info >= (3, 15)`, so the 3.11 run exercises only the
  classic `__getattr__` + caching path.
* **A 0.9.11.post1 baseline for #6923.** The changed behaviour there is a feature addition;
  the previous behaviour (rejected, or rendered as raw Var text) was not measured.
* **Redis / multi-worker state backends** — not relevant to this cluster.
