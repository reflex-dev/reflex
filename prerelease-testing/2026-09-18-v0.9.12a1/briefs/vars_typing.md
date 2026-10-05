# Cluster `vars_typing` — Var hashing (#7015), `Annotated` (#7189), var-op memory/speed (#7198), masked AttributeError (#7115), EnvVar timedelta (#7131), Python 3.15 + lazy imports (#6930), `.pyi` union props (#7080), State vars in page metadata (#6923)

Changelog lines (verbatim):
- (reflex-base) Fix hooks and imports being silently dropped from the compiled output when two vars with the same value but different metadata were interpolated into the same f-string. Var hashing is now derived from the same identity `Var.equals` uses, which also fixes `Var.equals` raising `VarTypeError` for vars that carry dependencies, and makes `NumberVar` and `BooleanVar` hashable. (#7015)
- (reflex-base) `Annotated[...]` hints now resolve to the type they annotate wherever Reflex inspects a type. A var typed with a pydantic discriminated union — `Annotated[Cat | Dog, Field(discriminator="kind")]` — no longer raises `Unsupported type ... for guess_type.` when read out of a state var, and its attributes resolve through the union as usual. (#7189)
- (reflex-base) Var operations no longer keep a permanent reference to every operand they are built from, fixing a memory leak that grew with each operation an app created, and building them is 1.5x to 3.8x faster depending on the operation. (#7198)
- (reflex-base) An `AttributeError` raised while computing a var, such as a typo inside an `@rx.serializer`, is now re-raised as a `ReflexRuntimeError` chained to the original error instead of a misleading `Attribute _cached_var_name not found` error. (#7115)
- (reflex-base) `EnvVar` reads `timedelta` values as a number of seconds, or with a `us`, `ms`, `s`, `m`, `h` or `d` suffix. (#7131)
- (reflex-base) Python 3.15 has provisional support and is tested in CI. Upstream dependency limitations remain, including dill-based function serialization... (#6930) / Lazy imports now cache resolved attributes on the package, so repeated access is a plain attribute lookup instead of a `__getattr__` round-trip. On Python 3.15+, lazy loading delegates to the interpreter's native lazy imports (PEP 810). (#6930)
- Generated `.pyi` stubs now type a prop declared as a union — `content: Var[str] | Component`, say — as optional, matching the `None` default that `create()` gives every prop. (#7080)
- Allow State Vars for page titles and descriptions in `@rx.page` and compiled metadata. (#6923)

## Build (compile-time scripts with the venv guard + one small app, dev AND prod)

1. #7015: a page interpolating two vars with the same string value but different `VarData` (one
   carrying a hook + import, e.g. built with `rx.Var("x", _var_data=rx.vars.VarData(hooks={...}, imports={...}))`,
   the other plain) into ONE f-string; also `rx.color_mode` together with a same-valued plain var;
   compile and grep the page's compiled JS for BOTH hooks/imports; render it. `hash(State.count + 1)`,
   `{State.a, State.b}` sets, `NumberVar`/`BooleanVar` as dict keys in `rx.match`; `State.a.equals(State.a)`
   where `a` has deps (a computed var) — no `VarTypeError`. Baseline 0.9.11.post1 to show the drop.
2. #7189: pydantic v2 models `Cat`/`Dog` with `kind: Literal[...]`, state var
   `pet: Annotated[Cat | Dog, Field(discriminator="kind")]`, list of them; render `State.pet.name`,
   `rx.match(State.pet.kind, ...)`, `rx.foreach(State.pets, lambda p: rx.text(p.name))`, change the
   var at runtime between Cat and Dog; also `Annotated[int, Field(gt=0)]`, `Annotated[list[str], ...]`
   vars and a handler arg typed `Annotated[int, ...]`. Prod too. Baseline (expect the guess_type error).
3. #7198: a loop building 200k var operations (`State.count + i`, `.to_string()`, `&`, `[i]`),
   `tracemalloc`/RSS sampled every 20k — flat on 0.9.12a1, growing on 0.9.11.post1; time both and
   report the ratio per operation kind. Also confirm a page with thousands of operations still
   compiles and renders correctly (no dropped var data after the operand-reference change).
4. #7115: an `@rx.serializer` for a custom class with a typo (`obj.nmae`) used by a state var and
   by a computed var; render → the server log/traceback must be a `ReflexRuntimeError` chained
   (`__cause__`) to the AttributeError naming `nmae`; check what the browser shows. Also a typo
   inside the computed var body itself, and inside a `hybrid_property`. Baseline.
5. #7131: grep `timedelta` in `/home/user/reflex/packages/reflex-base/src/reflex_base/config.py`
   and `environment.py` to find the affected env vars; set each with `30`, `500ms`, `2m`, `1.5h`,
   `1d`, and a bad value (`abc`, `5x`) and observe (a) `reflex run` startup and (b) the parsed value
   via `reflex_base.config.environment.<VAR>.get()` in a guarded script. Judge the error message for bad input.
6. #6930: `python -X importtime -c "import reflex"` on 3.11 (new vs prev); time 1e6 accesses of
   `rx.text` after first access; check `rx.__getattr__` still handles a bad name with a helpful
   `AttributeError`. Own venvs on Python 3.10 and 3.14: install the train and run the small app
   (dev) on each. Try `uv python install 3.15` and `uv pip install --prerelease=allow reflex==0.9.12a1 ...`
   on it — record whether the dependency graph resolves and whether the app runs; a failure to
   install deps on 3.15 is context, not a finding, unless reflex's own metadata blocks it.
7. #7080: in a venv with `pyright` (uv pip install pyright), type-check a snippet calling
   components whose stubs declare a union prop (grep the installed `.pyi` files for
   `| Component` / `Var[str] | Component`), e.g. leaving the prop unset; also `rx.el.div(...)`,
   `rx.data_editor(...)`, `rx.recharts.sankey_chart(...)` — no errors from the generated signatures.
8. #6923: `@rx.page(title=State.title, description=State.desc)` and `rx.App(...)` with an
   `rx.el.title` alternative; change `State.title` at runtime → `document.title` updates; the
   `<meta name="description">` updates; in prod the SSR/prerendered HTML carries the default; two
   pages with State titles + client-side navigation between them; a title using an f-string
   `f"{State.n} items"`. Baseline (previous behavior: rejected or raw Var text?).
