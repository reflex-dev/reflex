# Final-release pre-flight (0.9.11)

Checks run on 2026-09-11 against **published** artifacts only, in a throwaway
`uv --no-config` venv (`reflex==0.9.11a2`, `reflex-enterprise==0.9.5`). Nothing
was installed from a checkout.

## 1. Release-set coupling — the floors will not pull the fixes

`reflex 0.9.11a2` pins `reflex-base` exactly and **floors** every component package:

```
reflex-base==0.9.11a2
reflex-components-moment>=0.9.0     latest stable on PyPI: 0.9.3
reflex-components-radix>=0.9.2      latest stable on PyPI: 0.9.8
reflex-components-core>=0.9.6       latest stable on PyPI: 0.9.9
reflex-components-code>=0.9.0       latest stable on PyPI: 0.9.4
reflex-components-plotly>=0.9.0     latest stable on PyPI: 0.9.5
reflex-components-recharts>=0.9.0   latest stable on PyPI: 0.9.2
reflex-components-sonner>=0.9.0     latest stable on PyPI: 0.9.2
reflex-hosting-cli>=0.1.71          latest stable on PyPI: 0.1.71
```

Two of the a2 fixes validated in `PUBLISHED_VALIDATION_RESULTS.md` do **not** live
in `reflex` or `reflex-base`:

- **FINDING-033** (moment locale bleed; `locale="en"` 500s dev and breaks the prod
  build) is fixed in **reflex-components-moment 0.9.4**.
- **Half of FINDING-022** (stale Radix Themes registrations retained across
  recompiles, #7109) is fixed in **reflex-components-radix 0.9.9**.

If `reflex 0.9.11` ships final without `reflex-components-moment 0.9.4` and
`reflex-components-radix 0.9.9` also shipping final, a fresh `pip install reflex`
resolves moment 0.9.3 / radix 0.9.8 and **both bugs are still present for users**
even though the changelog says they are fixed.

These packages still sit at a1 on PyPI (no a2 was cut), so they also carry
unreleased changes: `reflex-components-code 0.9.5a1`, `plotly 0.9.6a1`,
`recharts 0.9.3a1`, `sonner 0.9.3a1`, `reflex-hosting-cli 0.1.72a1`.

## 2. reflex-otel ships a prerelease floor

Published `reflex-otel 0.1.0a2` metadata (PyPI):

```
reflex-base>=0.9.11a1
```

The floor was **not** lifted to a published version. A specifier that names a
prerelease enables prerelease resolution for that package (PEP 440), so a final
`reflex-otel 0.1.0` carrying this line lets `pip install reflex-otel` pull
`reflex-base` *prereleases* — e.g. a future `0.9.12a1` — into an otherwise stable
install. The pyproject comment says the release tooling lifts this floor; it did
not happen for a2. Worth confirming the final publish lifts it to `>=0.9.11`.

## 3. FINDING-018 blast radius — narrower than feared, but real

Mechanism traced through the published a2 wheels:

- `reflex_components_radix/plugin.py:74` registers `@radix-ui/themes` lazily from
  `enter_component`, i.e. only once a Radix component is actually walked, and
  registers it **non-explicitly** (deliberate, per #7109) so
  `_reset_bundled_libraries_for_compile()` can drop it.
- `compile_app`'s two non-compiling branches (`compiler.py:1234` and `:1254`) call
  `utils._compile_initial_state(app._state)` and `return` **before** the reset at
  `:1264` and the plugin-dependency bundling at `:1271`.
- Enterprise's `serialize_lambda` -> `LiteralLambdaVar` ->
  `_validate_and_extend_return_expr` (`reflex_enterprise/vars.py:165`) raises
  `ValueError: Library @radix-ui/themes is not bundled` when the library is
  absent at that moment.

Both non-compiling branches evaluate pages *before* `_compile_initial_state`, so
any app whose Radix usage appears on an evaluated stateful page has
`@radix-ui/themes` registered by the time the initial state is serialized, and
escapes the raise. The crash needs a component-bearing state default to be
serialized before any evaluated page registers that library.

The shipped `demos/ag_grid` is the exact 018 *shape* —
`formatters.py:258` is `cols_defs: list[dict] = cols_defs`, a state-field default
holding `lambda params: rx.text(...)`, `lambda params: rx.tooltip(...)` and
`lambda params: row_counter(...)` — but its Radix-heavy `/formatters` page is
stateful and evaluated first, so it most likely escapes by ordering rather than by
design. **Not confirmed end-to-end:** `reflex-enterprise` exits at startup
demanding `reflex login` / `REFLEX_ACCESS_TOKEN`, which this session does not
have, so the demo could not be driven past app construction.

## 4. Unchanged from the a2 validation

- **FINDING-036 (HIGH) is still open.** `reflex_base/.templates/web/utils/state.js`
  is byte-identical between a1 and a2; the `backend_state_mismatch` one-way latch
  still leaves enterprise apps that import the auth enforcement module inert in the
  browser. Re-reproduced on the tickets demo.
- **Delta key ordering** is a documented breaking change (#7087). Downstream
  snapshot/golden tests that assert on serialized delta JSON will fail on upgrade.
  It is in the changelog; expect issue reports regardless.
- **FINDING-018** remains open as #7096, accepted with the failure moved to compile
  time rather than silent delta dropping.
