## Enterprise fixture (entv): `.ag-header-cell` / `.ag-cell` counts 4 s after boot settled

Cells: state-var grid | literal grid (or the grids present on that page). h = header cells, c = body cells.

| scenario | entv_a4ent_prod |
|---|---|
| s1_full_load | w_state=2h/6c<br>w_literal=2h/6c |
| s2_reload | w_state=2h/6c<br>w_literal=2h/6c |
| s3_after_unrelated_event | w_state=2h/6c<br>w_literal=2h/6c |
| s4_after_same_substate_event | w_state=2h/6c<br>w_literal=2h/6c |
| s5_reload_after_state_changed | w_state=2h/6c<br>w_literal=2h/6c |
| s6_client_nav_from_other | w_state=2h/6c<br>w_literal=2h/6c |
| s7_full_load_then_nav_away_and_back | w_state=2h/6c<br>w_literal=2h/6c |
| s8_memo_full_load | w_memo_props=2h/6c<br>w_memo_state=2h/6c |
| s9_onload_page_full_load | w_onload=2h/6c<br>w_state2=2h/6c |
| s10_full_load_second_context | w_state=2h/6c<br>w_literal=2h/6c |
| s11_detail_expand | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] |
| s12_renderer_full_load | w_renderer=2h/6c<br>badges=3 |
| s13_dynamic_route_full_load | w_state=2h/6c |

## Core-only fixture (corev, no enterprise): ReflexProbe text (`typeof window.__reflex` at render) and render count

| scenario |  |
|---|

## Boot websocket deltas (first full load) — substates carried by each delta frame

- **entv_a4ent_prod / s1_full_load**: `window.__reflex` assigned at 213.2 ms
  - 212.7 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 313.9 ms IN delta ['reflex___state____state']
  - 314.7 ms IN delta ['reflex___state____state']
