# Validation of reflex-dev/reflex#7505 (A3-11 / A3-12 fix, branch `claude/a3-11-storage-echo`)

Runs the campaign's own reproductions against the PR branch (worktree `/home/user/wt-a3-11`, reflex and reflex-base editable from it,
venv symlinked as `$SB/envs/a311fix`), with the published 0.10.0a3 (`$SB/envs/a3`) as the control. The apps are copies of
`a3_hydration/src/{bootecho,syncstamp}` and `a3_hydration/verification/src/vhsync` whose venv guard is changed to the worktree path.

| scenario | published 0.10.0a3 | PR branch |
|---|---|---|
| explorer storm (`sync_race.py` Part S: tab0 changes a synced var 5x while 6 tabs load), dev | 3/4 storm (48k–61k frames, never converge) | 0/11 storm, all converge on s5 (65–81 frames) |
| same, prod | 2/5 (campaign) | 0/7 storm, all converge |
| explorer `stamp_storm.py /stamp 6` (A3-12), dev | 4/4 storm (330k–478k frames) | 0/6 storm, 6/6 converge |
| same, 3 tabs, dev | storms (campaign) | 0/6 storm, 6/6 converge |
| same, 6 tabs, prod | — | 0/4 storm, 4/4 converge |
| verifier raw CDP, 3 restored background tabs, one click, 100 ms RTT | 3/3 storm (verifier) | 0/3 storm; race triggered 3/3 (`vtrigger.txt`) |
| verifier restore 7 tabs + click, 100 ms RTT | storm whenever triggered | 0/4 storm; race triggered 4/4 |
| verifier 6 restored background tabs on stamping pages (A3-12) | 2/2 storm | 0/2 |
| verifier 4 stamping tabs + dev backend reload (A3-12) | 2/2 storm | 0/2 |

Rerun: `scripts/matrix.sh` (explorer drivers, ports 3150/3151, 8150/8151) and `scripts/vh_matrix.sh` (verifier drivers, 100 ms RTT
proxy, ports 3660/8660/8661). Results: `results/final_matrix.txt`, `results/fix_*.json`, `results/vtrigger.txt`.

The table above is for the first design (398d4b97a / d14c025bd: skip every recognised echo, resync a crossed synced var).

## Revisions after review, and the final commit

| commit | echo rule | result |
|---|---|---|
| 5994b9141 | retire the oldest pending value on any unmatched reply (Greptile: a replaced echo hid a later handler write) | **storm regression**: verifier dev-reload scenario stormed 2/6 — rejected |
| ff23ef3b9 | skip an echo only if a counter of other tabs' `storage` events grew since it was sent | stamp matrix 16/16 converge; Greptile then showed the socket reply can arrive before the `storage` event (the tab writes the old value over the new one) — confirmed by `test_synced_storage_echo_crossed_by_another_tab_is_not_written[False]`, which fails on it |
| **d03ddb107 (final)** | write an echo only if the value stored now is one this tab wrote after sending it; storage map back to synced vars only | below |

Final commit d03ddb107 (`results/d03ddb107/`):

| scenario | result |
|---|---|
| explorer storm, dev / prod | 0/5, 0/3 storm; all converge, 67–95 frames, 0 in the quiet window |
| explorer stamp 6 tabs dev / 3 tabs dev / 6 tabs prod (A3-12) | 6/6, 6/6, 4/4 converge, no storm (37–159 frames) |
| verifier raw CDP 3 tabs, one click, 100 ms RTT | 0/3 storm, converge; race fired 3/3 (`vtrigger.txt`) |
| verifier restore 7 + click, 100 ms RTT | 0/4 storm, converge; race fired 4/4 |
| verifier 6 background stamping tabs | 0/2 storm |
| verifier 4 stamping tabs + dev backend reload (the scenario that caught 5994b9141) | 0/4 storm |

Plus: `test_hydration_storage.py` 22/22 (dev+prod), Selenium client_storage/upload/connection_banner/call_script 23/23, state.js
unit test, pre-commit. Rerun as above after `rm -rf` of the `.web` dirs in `stamp-fix`, `run-fix` and `vh-fix-dev` (template
changes only reach `.web` on a reflex version change).

## Lean variant tried at the maintainer's request (10-08): no echo bookkeeping

`results/lean_variant.diff` on top of main: the storage event sends `localStorage.getItem` and dispatches it locally, every
echo is still written. Result: it does **not** stop the loop. PR Playwright tests: `keeps_newer_value` ping-pongs in prod
(`old, new, old, new, …` writes) and ends on the older value in dev. Storm matrix (`results/lean_variant_matrix.txt`): explorer storm
1/3 runs stormed (~3.5k storage events per tab, tabs split s3/s2); `/stamp 6` 2/3 stormed (32–36k frames per 5 s), the third
converged after 1,737 frames (PR: ~100). Writing a stale echo flips storage and the other tab answers that flip, so a frontend
fix has to recognise and skip stale echoes, which needs a record of the values sent.

## Final head 4cfafa359 (10-08): design kept, tightened

After the lean-variant result the maintainer kept the design and asked for it to be as tight as possible. Since d03ddb107:
c38383dc8 ignores session-storage `storage` events (cubic); 05f0e4bfd tracks this tab's writes by storage name (Greptile: a write
through a non-synced var sharing a synced var's `name` was missed; new `[shared_name]` test fails on c38383dc8); 4cfafa359 is a
no-behaviour-change cleanup of the code and tests. `results/4cfafa359/`: explorer 24/24 converge, 0 storms (storm dev 71–83 frames,
prod 95; stamp dev6 83–107, dev3 33–51, prod6 89–111); verifier 13/13, 0 storms, race fired 7/7. Playwright 24/24, Selenium 23/23.

## 33bf76643 and 2063422c8 (10-08): send-time read, and echo skipping for synced vars only

33bf76643 (another session) queues a storage event as `_sync_local_storage` and reads `localStorage` when the event is sent, so a
sync that waits for a reconnect sends the value stored then (`test_synced_storage_event_while_disconnected_sends_current_value`).

Maintainer review on 33bf76643 ([comment](https://github.com/reflex-dev/reflex/pull/7505#issuecomment-6052694969)): a `sync=False`
var whose boot echo an override replaced keeps its sent value recorded; another tab writes the key; a later handler setting the
recorded value is taken for its echo and skipped, so storage keeps the other tab's value for good. Reproduced in the browser:
`test_replaced_storage_echo_does_not_hide_later_change[plain-other_tab]` fails on 33bf76643 in dev and prod, passes on main.

2063422c8: only `sync=True` localStorage vars record sent values, so only their echoes can be skipped. Skipping is safe only
because the tab then syncs another tab's newer value to its backend, which a non-synced var never does; non-synced values are
written as on main. `results/2063422c8/matrix.txt`: stamp 6 tabs dev 0/3 storm (86–139 frames), storm dev 0/3 (65–83), prod 0/2
(87–91), all converge, 0 frames in the quiet window. Playwright 32/32 (dev+prod), Selenium 23/23, state.js tests, pre-commit.
