# verify_hydration — independent verification of the a4_hydration "near-simultaneous cross-tab writes" finding (reflex 0.10.0a4, #7505)

## VERIFICATION

Verifier: `verify_hydration` (2026-10-08). Published packages only: `$SB/envs/a4` (0.10.0a4), `$SB/envs/a3` (0.10.0a3),
`$SB/envs/stable` (0.9.12), driver `$SB/envs/driver` + `/opt/pw-browsers/chromium` (headless). Every app runs from
`$SB/apps/verify_hydration4/run/<name>` and asserts `reflex.__file__` is under `/scratchpad/envs/$RVH_VENV/`; drivers assert
`/envs/driver/`. Ports 3660 (frontend) / 8660 (backend) / 8661 (100 ms RTT proxy). One server at a time, dev mode. Compiled
`state.js` md5 checked per run dir: a4 `b7915eda` (= wheel template, contains `sentStorageValues`), a3 `caea5520`, 0.9.12 `e0743b88`.
Everything started was stopped (final `lsof`: no listener in 3660-3679 / 8660-8679, no proxy / Chromium left).

### Verdict (short)
**NARROWED + RECLASSIFIED: by-design, consistent "last-storage-write-wins" within one round trip; low severity; not a regression
vs a3 or 0.9.12 (both lose the same race at gap 0 and STORM at 100 ms RTT, where a4 converges quietly); do not block 0.10.0.**
The reporter's mechanism sentence is incomplete: besides "the slower delta is written last", a second, more common path loses the
later write — a tab that has its own event in flight when another tab's (older) value hits storage pipelines that older value to
its backend AFTER its own event (0.10's event queue no longer waits for the previous event's reply), and #7505's "write an echo over
this tab's own later write" rule then writes the older value back over the tab's own newer one. Net effect: when two tabs write the
same sync=True var within ~one RTT, the earlier write wins, the later writer's tab shows its value for ~1 RTT and flips. End state is
always consistent (every tab display = localStorage = every tab's backend), no storm, no value nobody wrote.

### Setup / rerun
```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/verify_hydration4
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
mkdir -p $W/{run,logs,results/race,results/b2b} && cp -r src drivers scripts $W/      # from this directory
# (optional) seed run dirs with node_modules: cp -a $SB/apps/a4_hydration/run/h4-<a4dev|a3dev|stabledev>/.web $W/run/hv-<same>/
# reporter's repro (h4mix, unchanged):
cd $W && scripts/srv.sh start h4-a4dev a4 dev $W/src/h4mix 3660 8660
cd $W/drivers && $NP $DRV b2b_probe.py http://localhost:3660 $W/results/b2b/a4dev_alt_repro.json 5 alt; cd $W && scripts/srv.sh stop h4-a4dev
# verification app h4v (= h4mix + #probe backend read-out, /st/[slug] on_load stamp, #bgloop background writes bg1..bg5 100 ms
# apart, /norm and /normslow on_load that re-assign syn, H4TRACE lines with server timestamps):
scripts/srv.sh start hv-a4dev a4 dev $W/src/h4v 3660 8660            # localhost
# 100 ms RTT: proxy in front of the backend, frontend pointed at it
setsid $DRV -I $W/drivers/latency_proxy.py 8661 8660 50 > $W/logs/proxy-8661.log 2>&1 &
scripts/srv.sh start hv-a4dev a4 dev $W/src/h4v 3660 8660 REFLEX_API_URL=http://localhost:8661   # env.json EVENT -> ws://localhost:8661
# drivers (LOG = the server log srv.sh printed; used to read H4TRACE server-apply timestamps)
cd $W/drivers && $NP $DRV race.py http://localhost:3660 OUT.json LOG <reps> gap:0 gap:10 gap:20 gap:40 gap:80 pwalt onload:0 bg:570 freeze:1500
$NP $DRV bootwin.py http://localhost:3660 OUT.json LOG /norm 0 2 4 6 8 10    # O-2 window (see below)
# same for a3 / stable: srv.sh start hv-a3dev a3 ... / hv-stabledev stable ...
```
`race.py`: two tabs of one fresh context; per rep a warm-up write (`c5`), then the scenario; clicks are in-page `el.click()` (no
Playwright click overhead, timestamps on the shared browser clock); 3 s settle, then every tab's display, localStorage, every tab's
BACKEND value (`#probe` copies `Prefs.syn` into a plain var), every `h4_syn` `setItem` of both tabs with timestamps, display changes,
ws frames in the last second (storm if >10), and the server's apply order (H4TRACE `ts`). `last_server` = value of the last
handler / background write the server applied; `=last_store` = final equals the last localStorage write of any tab.
`gap:<ms>` t1 clicks c8, <ms> later t2 clicks c9. `pwalt` = the reporter's alternation (Playwright clicks c0..c9, t1/t2).
`onload:<ms>` t1 loads /st/a, <ms> later t2 loads /st/b. `bg:<ms>` t1 starts a background task writing bg1..bg5 (100 ms apart),
<ms> later t2 clicks c9. `freeze:<ms>` CDP `Page.setWebLifecycleState frozen` on t1 during the bg task — **ineffective** (headless
Chromium kept delivering t1's messages; recorded but it is just another bg run, not a sleep/reconnect test).

### Q1 — reproduces? where does it stop?
Reporter's repro, unchanged (`b2b_probe.py ... 5 alt` on h4mix, a4 dev): **5/5 `finals=['c8','c8'] ls=c8`**, t1 writes c0..c8, t2
c1..c9, no ping-pong — reproduced exactly (`results/b2b/a4dev_alt_repro.json`).

Gap sweep, a4 dev, final value of t1-c8 / t2-c9 (`results/race/a4dev_gap.txt`, `a4dev_rtt100.txt`):

| gap t1→t2 | localhost (6 reps) | 100 ms RTT proxy (3 reps) |
|---|---|---|
| 0 ms | c8 4/6, c9 2/6 | c8 2/3, c9 1/3 |
| 10 ms | c9 6/6 | — |
| 20 ms | c9 6/6 | **c8 3/3** |
| 40 ms | c9 6/6 | **c8 3/3** |
| 80 ms | c9 6/6 | **c8 3/3** |
| 150 / 250 ms | — | c9 3/3, c9 3/3 |
| `pwalt` (reporter's) | c8 4/4 | c8 3/3 |

Window = about one round trip of the EARLIER writer (localhost: < 10 ms; 100 ms RTT: between 80 and 150 ms). Every run consistent,
0 storms, ≤3 storage writes per race. In every lost run the server applied t2's c9 AFTER t1's c8 (H4TRACE), so the "lost" value is
the later one by click time AND by server-apply time.

Two mechanisms (both end on the earlier value):
1. Reporter's (pwalt, localhost): the server applies c8 then c9 15 ms apart, but t1's c8 delta reaches its localStorage 17 ms
   AFTER t2's c9 (`s:c8@+5254 c9@+5269; stores t2:c9@+5280 t1:c8@+5297`): t1's main thread processes the ws message before t2's
   `storage` event, so its sync reads its own c8 ("value stored NOW") and t2 follows c8. Storage-order LWW.
2. Pipelined sync (most gap runs, all 100 ms RTT runs): `gap:40 @100ms: server c8@+53 c9@+96; stores t1:c8@+104 t2:c9@+148
   t2:c8@+208`. t2's click is in flight when t1's c8 lands in storage; t2 sends `update_vars_internal(c8)` immediately (a4's
   queue does not wait for the c9 reply), its backend applies c9 then c8, and the c8 echo is WRITTEN over t2's own c9 by the
   "own later write" rule (correct w.r.t. t2's backend, which now holds c8). Here the handler writes reached storage in click
   order (c8 then c9); the final c8 is t2's own re-write. So "storage-order last value" describes the result only if the re-write
   counts as a write; the user-meaningful statement is "the earlier of two writes within one RTT wins".

### Q2 — always consistent?
Yes. 136 a4 runs (96 `race.py` + 40 `bootwin.py`, localhost and 100 ms RTT; JSON in `results/race/a4dev_*.json`, `smoke.json`): **every** a4 run ended with every tab's display =
localStorage = every tab's backend value, 0 frames in the last second, and the final value was always one of the written values
(never an intermediate / nobody's value). Contrast at 100 ms RTT: a3 still storming (>10 frames in the last second) 12/18 and inconsistent 11/18 (`gap:40` 2/3, `gap:80` 3/3,
`bg:570` 3/3, `pwalt` 3/3; up to 568 storage writes in 3 s); 0.9.12 storming 13/18, inconsistent 11/18 (same pattern, up to 567 writes).
All 23 gap/pwalt runs on a4 that ended on c8 had the server apply c9 last (`last_server=c9`).

### Q3 — user-visible loss in realistic programmatic cases (a4)
| case | result on a4 | lost? |
|---|---|---|
| two tabs' on_load stamping different values (`onload:0`, `onload:30`, localhost) | one value, consistent, 0 storm (st-b 7/8, st-a 1/8) | by design: either stamp is acceptable for a synced var; ordering follows the race above |
| background task in t1 writing bg1..bg5 while the user clicks c9 in t2 (localhost `bg:480/520/560/650`) | bg5 when bg5 was applied after the click (correct), c9 when the click came after bg5 (correct) | no (window < 10 ms not hit) |
| same at 100 ms RTT (`bg:520/570/620`) | `bg:570`: user clicks 11 ms after the server applied bg5 but before bg5 reached t2's storage; server applies c9 68 ms after bg5; **final bg5 3/3**, t2 shows c9 for ~36 ms then reverts. `bg:620`: c9 3/3 | **yes, within one RTT after the last background write**; consistent, no storm (a3/0.9.12 storm 3/3 here) |
| "sleep" via CDP freeze | freeze had no effect in headless Chromium (messages kept flowing) | not covered |
| reconnect after sleep | not run (no reliable way to drop one tab's socket in the time box) | not covered |

User-noticeable form: the tab that wrote last shows its value for ~1 RTT and then shows the other tab's (older) value, with no
further action. A human cannot produce two writes in two tabs within one RTT; programmatic writers can (background task, on_load,
boot re-assignments). The user's value is never silently replaced without a visible flip in that tab.

### Q4 — a4 vs a3 vs 0.9.12 (same h4v app, same driver)
| scenario | a4 | a3 | 0.9.12 |
|---|---|---|---|
| localhost `gap:0` | c8 4/6 (+ c9 2/6), consistent, ≤3 writes | **c8 4/4**, ≤21 writes | **c8 3/3**, ≤27 writes |
| localhost `gap:10` / `gap:40` | c9 | c9 | c9 |
| localhost `pwalt` | c8 4/4, 10 writes | c9 4/4 after ping-pong (≤114 writes) | c9 3/3 after ping-pong (≤114 writes) |
| 100 ms `gap:0` | c8 2/3 | c8 3/3 | c8 2/3 + 1 storm |
| 100 ms `gap:40` / `gap:80` | c8 6/6, quiet | storm 6/6, inconsistent 5/6 | storm 6/6, inconsistent 4/6 |
| 100 ms `gap:150` | c9 3/3 | c9 3/3 | c9 3/3 |
| 100 ms `bg:570` | bg5 3/3, quiet | storm 3/3 | storm 3/3 |
| 100 ms `pwalt` | c8 3/3, quiet (≤14 writes) | storm 3/3 (≤568 writes) | storm 3/3 (≤567 writes) |
So the "later write lost within one RTT" exists on all three versions (gap 0 localhost: a3 4/4, 0.9.12 3/3); a3/0.9.12 only
"recover" the later value in the reporter's alternation because they keep ping-ponging until it happens to end there, and at a
realistic RTT they storm instead. **a4 is better overall** (deterministic, quiet, consistent); the only a4-specific difference is
the `pwalt` localhost outcome (c8 instead of a ping-pong ending on c9).

### Coordinator follow-up — O-2: a booting tab's second boot delta for a sync=True var (`drivers/bootwin.py`)
t2 has stored `c5`; t1 (returning tab) reloads; when t1's websocket sends its hydrate (BroadcastChannel hook) t2 clicks `c9`
OFFSET ms later. Results `results/race/*bootwin*`.
* Core, page without on_load (`/`): a4 receives the snapshot (not hydrated, skipped) and ONE hydrated delta with the boot value
  (recognised echo, skipped); t1 writes nothing — no second same-value delta in core, so the O-2 window does not exist there
  (a4 3/3 c9; a3 at 100 ms 4/4 c9, but a3 writes the echo so t2 transiently reverts 1/4).
* Core analogue of O-2: `/norm`, whose on_load re-assigns the stored value (`self.syn = self.syn`) = a second hydrated delta
  carrying the boot value, which a4 writes (not an echo any more). This is the window:

| /norm | a4 | a3 | 0.9.12 |
|---|---|---|---|
| localhost, offsets 0-28 ms (25 runs over two sweeps) | **c5 6/25** (offsets 0-4 ms), c9 19/25; all consistent, 0 storm | c9 6/6 (offsets 0-10), transient revert 2/6 | c9 5/5 (0-8), transient revert 5/5 |
| 100 ms RTT, offsets 0-120 ms | c9 12/12, transient revert 1/12 (t2 shows c9→c5→c9 for ~100 ms) | c9 4/4, transient revert 1/4 | — |

Mechanism of the a4 losses (`a4dev_bootwin_norm*.txt`): t2 stores c9, then t1's on_load delta (c5) is written over it 0.3-13 ms
later, BEFORE t1 handles t2's `storage` event (t1 is busy booting; ws message runs first); t1's sync then reads its own c5 ("value
stored NOW") and t2 follows c5: t2 showed c9 for 4-14 ms and reverted, no further action. In 3 of the 6 losses the server had applied
the on_load AFTER the click (c5 is the server-order last write too); in the other 3 the click was applied 1-3 ms later. When t1
handles the storage event before writing (every 100 ms RTT run), it has already sent c9 and the "own later write" rule restores c9
everywhere: transient flip only. So: **yes**, a second boot write can overwrite another tab's newer value and make it revert; it
always converges (no storm, consistent); a permanent loss needs the other tab's write to land a few ms before the booting tab
writes, while the booting tab's main thread is busy. a3 / 0.9.12 recover the newer value here (they send `e.newValue`) at the cost
of extra writes (a3 6, 0.9.12 more) and storm-prone ping-pong elsewhere. Low severity; a narrow a4-specific window, the price of the
"send the value stored now" design that fixed the A3-11 storms.

### Q5 — verdict
* **NARROWED / RECLASSIFIED** — consistent last-writer-wins by storage order (incl. a tab's own echo re-write) for writes from two
  tabs within ~one RTT of the earlier writer; deterministic, always converges, never a storm, never an un-written value.
* Severity **low**. Regression vs a3: **no** (a3 loses the same race at gap 0 localhost 4/4 and storms at 100 ms RTT); vs 0.9.12:
  **no** (same). Only a4-specific facets: the reporter's `pwalt` outcome and the O-2/`/norm` boot window (c5 6/25 at localhost vs
  0/11 on a3 + 0.9.12) — both sub-RTT programmatic races ending consistent.
* **Does not block 0.10.0.** Optional follow-up (not filed): document that sync=True LocalStorage is last-writer-wins across tabs
  and that writes from several tabs within one round trip may resolve to the earlier one; exact ordering would need per-update
  echo correlation (already floated by the PR author as a possible follow-up in the #7505 review threads).

### PR context (#7505 review threads, read via GitHub MCP)
The rejected design ("old echoes erase newer values: the socket reply can arrive before the storage event, the counter has not
changed, the tab writes old over new, the delayed storage event then reads old") was fixed in d03ddb107 by reading localStorage
itself: a recognised echo is written only over this tab's own later write. That fix is in a4 and holds: no run here wrote a
recognised echo over another tab's newer value. The losses above are different paths: (1) non-echo writes (a handler's /
on_load's delta) that land a few ms after another tab's newer write, before the storage event is handled; (2) the pipelined sync
of an older value that the backend applies after the tab's own newer event (the "own later write" branch, intentional: storage
follows that tab's backend). The author's own reply to the cubic thread describes (2)'s ordering ("which value wins depends on the
order the backend applied them") and proposes backend echo correlation as a follow-up.

### Pre-existing C21 anomaly — filed?
`rx.remove_local_storage` of a synced key → other tab syncs `null` into a `str` var → computed var `TypeError: object of type
'NoneType' has no len()` (a3, a4, 0.9.12): **not filed.** GitHub MCP `search_issues` on reflex-dev/reflex (three queries:
remove_local_storage / clear_local_storage / storage event null / NoneType computed var) returned only #7506 (several sync=True
vars sharing one name), #7507 (class-level None assignment to a storage var, closed), #4612, #1431, #1677 — none matches.

### Server logs (`logs/*.trimmed.log`)
No traceback on any version; only the pre-existing granian shutdown line and one a3 `Failed to close websocket ... Broken pipe`
(during a storm).

### Not covered
Reconnect after sleep (CDP freeze ineffective in headless; no per-tab socket drop in the time box); prod / Redis (dev only; the
reporter showed dev = prod = prod+Redis for C3); real background tabs (headful, throttled timers) — could widen the "busy tab"
window of the O-2 path; reflex-enterprise vauthx itself (core `/norm` used as the O-2 analogue).
