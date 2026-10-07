## Enterprise fixture (entv): `.ag-header-cell` / `.ag-cell` counts 4 s after boot settled

Cells: state-var grid | literal grid (or the grids present on that page). h = header cells, c = body cells.

| scenario | entv_a3ent_dev | entv_a3ent_prod | entv_a3ent_prod_lazyflag | entv_a3enta4_prod | entv_alpha2ent_prod | entv_alpha2enta5_dev | entv_alpha2enta5_prod | entv_s912enta5_prod |
|---|---|---|---|---|---|---|---|---|
| s1_full_load | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c<br>PAGEERROR Minified React error #418; visit https:/ | w_state=0h/0c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s2_reload | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c<br>PAGEERROR Minified React error #418; visit https:/ | w_state=0h/0c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s3_after_unrelated_event | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s4_after_same_substate_event | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s5_reload_after_state_changed | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c<br>PAGEERROR Minified React error #418; visit https:/ | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s6_client_nav_from_other | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | n/a | n/a | n/a | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s7_full_load_then_nav_away_and_back | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | n/a | n/a | n/a | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s8_memo_full_load | w_memo_props=2h/6c<br>w_memo_state=2h/6c | w_memo_props=2h/6c<br>w_memo_state=2h/6c | w_memo_props=2h/6c<br>w_memo_state=2h/6c | w_memo_props=0h/0c<br>w_memo_state=0h/0c | n/a | w_memo_props=2h/6c<br>w_memo_state=2h/6c | w_memo_props=2h/6c<br>w_memo_state=2h/6c | w_memo_props=2h/6c<br>w_memo_state=2h/6c |
| s9_onload_page_full_load | w_onload=2h/6c<br>w_state2=2h/6c | w_onload=2h/6c<br>w_state2=2h/6c | n/a | n/a | n/a | w_onload=2h/6c<br>w_state2=2h/6c | w_onload=2h/6c<br>w_state2=2h/6c | w_onload=2h/6c<br>w_state2=2h/6c |
| s10_full_load_second_context | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | n/a | n/a | n/a | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s11_detail_expand | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] | w_detail_state=2h/4c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=[], w_detail_literal=['Count', 'Value'] | w_detail_state=2h/4c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=[], w_detail_literal=['Count', 'Value'] | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] |
| s12_renderer_full_load | w_renderer=2h/6c<br>badges=3 | w_renderer=2h/6c<br>badges=3 | badges=0<br>React #130 (page crashed) | n/a | n/a | w_renderer=2h/6c<br>badges=3 | w_renderer=2h/6c<br>badges=3 | w_renderer=2h/6c<br>badges=3 |
| s13_dynamic_route_full_load | w_state=2h/6c | w_state=2h/6c | n/a | n/a | n/a | w_state=2h/6c | w_state=2h/6c | w_state=2h/6c |

## Core-only fixture (corev, no enterprise): ReflexProbe text (`typeof window.__reflex` at render) and render count

| scenario | corev_a3_prod |
|---|---|
| c1_full_load | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) |
| c2_reload | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) |
| c3_after_unrelated_event | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) |
| c4_after_same_substate_event | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) |
| c5_reload_after_state_changed | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) |

## Boot websocket deltas (first full load) — substates carried by each delta frame

- **corev_a3_prod / c1_full_load**: `window.__reflex` assigned at 434.7 ms
  - 475.3 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 540.6 ms IN delta ['reflex___state____state']
  - 541.8 ms IN delta ['reflex___state____state']
  - 543 ms IN delta ['corev___corev____touched']
  - 543.1 ms IN delta ['reflex___state____state']
- **entv_a3ent_dev / s1_full_load**: `window.__reflex` assigned at 2190.6 ms
  - 2189.6 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 2208.6 ms IN delta ['reflex___state____state']
  - 2209.2 ms IN delta ['reflex___state____state']
- **entv_a3ent_prod / s1_full_load**: `window.__reflex` assigned at 350.3 ms
  - 349.3 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 488.4 ms IN delta ['reflex___state____state']
  - 489.1 ms IN delta ['reflex___state____state']
- **entv_a3ent_prod_lazyflag / s1_full_load**: `window.__reflex` assigned at 135.2 ms
  - 256.1 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 372.6 ms IN delta ['reflex___state____state']
  - 373.1 ms IN delta ['reflex___state____state']
- **entv_a3enta4_prod / s1_full_load**: `window.__reflex` assigned at 235.3 ms
  - 234.6 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 339.9 ms IN delta ['reflex___state____state']
  - 340.4 ms IN delta ['reflex___state____state']
- **entv_alpha2ent_prod / s1_full_load**: `window.__reflex` assigned at 255.2 ms
  - 254.6 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 369.8 ms IN delta ['reflex___state____state']
  - 370.4 ms IN delta ['reflex___state____state']
- **entv_alpha2enta5_dev / s1_full_load**: `window.__reflex` assigned at 1706.3 ms
  - 1705.1 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 1728.4 ms IN delta ['reflex___state____state']
  - 1729.1 ms IN delta ['reflex___state____state']
- **entv_alpha2enta5_prod / s1_full_load**: `window.__reflex` assigned at 247.0 ms
  - 246.3 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 346.9 ms IN delta ['reflex___state____state']
  - 347.6 ms IN delta ['reflex___state____state']
- **entv_s912enta5_prod / s1_full_load**: `window.__reflex` assigned at 251.0 ms
  - 347.8 ms OUT reflex___state____state.hydrate
  - 347.9 ms OUT reflex___state____state.reflex___state____on_load_internal_state.on_load_internal
  - 352.8 ms IN delta ['reflex___state____state', 'entv___entv____load_state', 'reflex___state____on_load_internal_state', 'entv___entv____other_state', 'entv___entv____detail_state', 'reflex___istate___shared____shared_state_base_internal', 'reflex___state____frontend_event_exception_state', 'reflex___state____update_vars_internal_state', 'entv___entv____grid_state']
  - 354.2 ms IN delta ['reflex___state____state']
