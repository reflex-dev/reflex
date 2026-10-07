## Enterprise fixture (entv): `.ag-header-cell` / `.ag-cell` counts 4 s after boot settled

Cells: state-var grid | literal grid (or the grids present on that page). h = header cells, c = body cells.

| scenario | entv_s912_prod | entv_a1_prod | entv_a2_prod | entv_a2_dev | entv_a2_prod_lazyflag |
|---|---|---|---|---|---|
| s1_full_load | w_state=2h/6c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c<br>PAGEERROR Minified React error #418; visit https:/ |
| s2_reload | w_state=2h/6c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c<br>PAGEERROR Minified React error #418; visit https:/ |
| s3_after_unrelated_event | w_state=2h/6c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s4_after_same_substate_event | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s5_reload_after_state_changed | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c<br>PAGEERROR Minified React error #418; visit https:/ |
| s6_client_nav_from_other | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s7_full_load_then_nav_away_and_back | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c |
| s8_memo_full_load | w_memo_props=2h/6c<br>w_memo_state=2h/6c | w_memo_props=0h/0c<br>w_memo_state=0h/0c | w_memo_props=0h/0c<br>w_memo_state=0h/0c | w_memo_props=2h/6c<br>w_memo_state=2h/6c | w_memo_props=2h/6c<br>w_memo_state=2h/6c |
| s9_onload_page_full_load | w_onload=2h/6c<br>w_state2=2h/6c | w_onload=2h/6c<br>w_state2=0h/0c | w_onload=2h/6c<br>w_state2=0h/0c | w_onload=2h/6c<br>w_state2=2h/6c | w_onload=2h/6c<br>w_state2=2h/6c |
| s10_full_load_second_context | w_state=2h/6c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=0h/0c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c | w_state=2h/6c<br>w_literal=2h/6c<br>PAGEERROR Minified React error #418; visit https:/ |
| s11_detail_expand | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] | w_detail_state=2h/4c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=[], w_detail_literal=['Count', 'Value'] | w_detail_state=2h/4c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=[], w_detail_literal=['Count', 'Value'] | n/a | w_detail_state=4h/8c<br>w_detail_literal=4h/8c<br>detail-grid headers: w_detail_state=['Count', 'Value'], w_detail_literal=['Count', 'Value'] |
| s12_renderer_full_load | w_renderer=2h/6c<br>badges=3 | w_renderer=2h/6c<br>badges=3 | w_renderer=2h/6c<br>badges=3 | n/a | badges=0<br>React #130 (page crashed) |
| s13_dynamic_route_full_load | n/a | n/a | w_state=2h/6c | n/a | n/a |

## Core-only fixture (corev, no enterprise): ReflexProbe text (`typeof window.__reflex` at render) and render count

| scenario | corev_s912_prod | corev_a1_prod | corev_a2_prod | corev_a2_dev |
|---|---|---|---|---|
| c1_full_load | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: HAS_REFLEX (renders 2) |
| c2_reload | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 3)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 3)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: HAS_REFLEX (renders 2) |
| c3_after_unrelated_event | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 3)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 4)<br>literal: HAS_REFLEX (renders 2) |
| c4_after_same_substate_event | untouched: HAS_REFLEX (renders 3)<br>untouched_n: HAS_REFLEX (renders 3)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 3)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 4)<br>untouched_n: HAS_REFLEX (renders 4)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 4)<br>literal: HAS_REFLEX (renders 2) |
| c5_reload_after_state_changed | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: HAS_REFLEX (renders 2) |
| c6_client_nav_from_second | untouched: HAS_REFLEX (renders 1)<br>untouched_n: HAS_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 1)<br>literal: HAS_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 1)<br>untouched_n: HAS_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 1)<br>literal: HAS_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 1)<br>untouched_n: HAS_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 1)<br>literal: HAS_REFLEX (renders 1) | n/a |
| c6a_second_full_load | second_untouched: HAS_REFLEX (renders 2) | second_untouched: NO_REFLEX (renders 1) | second_untouched: NO_REFLEX (renders 1) | n/a |
| c7_full_load_second_context | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 3)<br>other: HAS_REFLEX (renders 2)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) | untouched: NO_REFLEX (renders 1)<br>untouched_n: NO_REFLEX (renders 1)<br>touched: HAS_REFLEX (renders 2)<br>other: NO_REFLEX (renders 1)<br>literal: NO_REFLEX (renders 1) | untouched: HAS_REFLEX (renders 2)<br>untouched_n: HAS_REFLEX (renders 2)<br>touched: HAS_REFLEX (renders 2)<br>other: HAS_REFLEX (renders 2)<br>literal: HAS_REFLEX (renders 2) |
| c8_dynamic_component_full_load | n/a | n/a | dyn_label: NO_REFLEX (renders 1)<br>dynamic component badge='dynamic-ok' | n/a |

## Boot websocket deltas (first full load) — substates carried by each delta frame

- **corev_s912_prod / c1_full_load**: `window.__reflex` assigned at 177.3 ms
  - 186.9 ms OUT reflex___state____state.hydrate
  - 187.1 ms OUT reflex___state____state.reflex___state____on_load_internal_state.on_load_internal
  - 192.2 ms IN delta ['reflex___state____state', 'reflex___istate___shared____shared_state_base_internal', 'reflex___state____update_vars_internal_state', 'reflex___state____frontend_event_exception_state', 'corev___corev____other', 'corev___corev____untouched', 'corev___corev____touched', 'reflex___state____on_load_internal_state']
  - 194.1 ms IN delta ['reflex___state____state']
  - 655.5 ms IN delta ['corev___corev____touched']
  - 656.5 ms IN delta ['reflex___state____state']
- **corev_a1_prod / c1_full_load**: `window.__reflex` assigned at 133.7 ms
  - 133.2 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 141.7 ms IN delta ['reflex___state____state']
  - 142.8 ms IN delta ['reflex___state____state']
  - 143.1 ms IN delta ['corev___corev____touched']
  - 143.3 ms IN delta ['reflex___state____state']
- **corev_a2_prod / c1_full_load**: `window.__reflex` assigned at 149.4 ms
  - 148.8 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 152.9 ms IN delta ['reflex___state____state']
  - 153.4 ms IN delta ['reflex___state____state']
  - 153.5 ms IN delta ['corev___corev____touched']
  - 153.6 ms IN delta ['reflex___state____state']
- **corev_a2_dev / c1_full_load**: `window.__reflex` assigned at 1488.4 ms
  - 1483.4 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 1498.5 ms IN delta ['reflex___state____state']
  - 1499 ms IN delta ['reflex___state____state']
  - 1499.2 ms IN delta ['corev___corev____touched']
  - 1499.3 ms IN delta ['reflex___state____state']
- **entv_s912_prod / s1_full_load**: `window.__reflex` assigned at 239.8 ms
  - 339.3 ms OUT reflex___state____state.hydrate
  - 339.4 ms OUT reflex___state____state.reflex___state____on_load_internal_state.on_load_internal
  - 342.1 ms IN delta ['reflex___state____state', 'reflex___istate___shared____shared_state_base_internal', 'reflex___state____frontend_event_exception_state', 'reflex___state____on_load_internal_state', 'entv___entv____grid_state', 'reflex___state____update_vars_internal_state', 'entv___entv____other_state', 'entv___entv____load_state']
  - 369.4 ms IN delta ['reflex___state____state']
- **entv_a1_prod / s1_full_load**: `window.__reflex` assigned at 296.9 ms
  - 296.5 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 403.2 ms IN delta ['reflex___state____state']
  - 403.9 ms IN delta ['reflex___state____state']
- **entv_a2_prod / s1_full_load**: `window.__reflex` assigned at 241.1 ms
  - 240.6 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 329.5 ms IN delta ['reflex___state____state']
  - 330.1 ms IN delta ['reflex___state____state']
- **entv_a2_dev / s1_full_load**: `window.__reflex` assigned at 1995.0 ms
  - 1994.2 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 2018.1 ms IN delta ['reflex___state____state']
  - 2018.8 ms IN delta ['reflex___state____state']
- **entv_a2_prod_lazyflag / s1_full_load**: `window.__reflex` assigned at 128.4 ms
  - 232.1 ms OUT reflex___state____state.hydrate_and_load (in socket.io connect auth)
  - 352.5 ms IN delta ['reflex___state____state']
  - 353.1 ms IN delta ['reflex___state____state']
