# Cluster: ent_mantine_highcharts_tickets — the remaining reflex-enterprise demos

Completes the enterprise regression sweep begun in `ent_aggrid/` and `ent_map_dnd_flow/`. The
three demos left over — `mantine`, `highcharts` and `tickets` — run unmodified from the
`reflex-enterprise` checkout against **reflex-enterprise 0.9.5 from PyPI** on reflex 0.9.11a1 and
on 0.9.10.post2, in dev mode with `CI=true` (see AGENT_BRIEF.md: `rxe.App` exits for an anonymous
licence tier as soon as a frontend is served).

`drive_ent.py` loads each route, records a structural fingerprint (svg / button / input / row /
`.highcharts-container` / `mantine-*` / canvas counts and body-text length), clicks up to six
visible buttons recording the fingerprint after each, and captures console messages, page errors,
failed requests and every HTTP >= 400. `runpair.sh` is the stop-kill-orphans-start-drive wrapper.

```
./runpair.sh mantine   ent     5451 9851 a1   / /dates /pill /tags-input
./runpair.sh mantine_base entbase 5461 9861 base / /dates /pill /tags-input
```

## Result: no regression in any of the three

| demo | routes | 0.9.11a1 vs 0.9.10.post2 |
| --- | --- | --- |
| `highcharts` | `/` | identical (2 `.highcharts-container`, 3 svg, no errors either side) |
| `mantine` | `/`, `/dates`, `/pill`, `/tags-input` | identical on every count, including the 387 `mantine-*` elements, 156 buttons and 23 calendar rows of `/dates` |
| `tickets` | `/`, `/ticket` | identical counts, and the same one console error on both versions (below) |

The `mantine` demo's per-component routes are **not** the `route="/accordion"` values in
`mantine/*_demo.py`; only `/dates`, `/pill` and `/tags-input` are actually registered (the index
page's own links are the reliable list). Anything else renders reflex's `404: Page not found`
with an HTTP 200, on both versions.

## Also exercised: `EventHandlerAPIPlugin` (the tickets demo's whole point)

* `POST /_reflex/event/tickets___tickets____ticket_state/create_ticket` with an app-issued bearer
  from `POST /_reflex/auth/token` returns **200** and the resulting state delta, and the row really
  lands in sqlite (`select ... from ticketrecord` → `(1, 'QA smoke ticket', 'high', 'qa')`).
* `GET /.well-known/api-catalog` returns the RFC 9727 linkset, pointing at the OpenAPI document.
* `GET /_reflex/events/openapi.yaml` returns **500** — FINDING-035.
* The single-underscore spelling of the state segment (`tickets___tickets___ticket_state`) 404s;
  the four-underscore one from `search_events` is the right one.

## Findings raised

* FINDING-035 — `EventHandlerAPIPlugin`'s OpenAPI endpoint 500s because `pyyaml` is not declared
  (LOW, pre-existing, reflex-enterprise).
* FINDING-036 — every page of the tickets demo logs `Cannot process state update: no dispatch
  function for substate(s) ...generic_oidc_auth_state, ...is_iframed_state` (LOW, pre-existing).
