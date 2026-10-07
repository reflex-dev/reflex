ITEM: verify_upgrade
KIND: verify
REF: A3-08 (a3_upgrade-3)
TITLE: CONFIRMED: the half record is written by reflex (supervisor exits mid-`os.write` of a ~135 KB batch); happens at the 30 s wall cap AND on a second Ctrl-C during the drain (plain-text "Aborted!", rc 1); a consumer that stops reading entirely never lets shutdown finish (cap never starts)
SEVERITY: low
STATUS: confirmed
REGRESSION_VS_0.9.12: no (0.9.12 has no supervisor; its --json stream is not JSON-only: 1873/1876 lines raw in my run; no truncation)
REGRESSION_VS_0.10.0a2: no (a2 truncates identically at its 5 s cap and on a second Ctrl-C; a3 is strictly better)
REPRO: Own chatty blank app (`verification/apps/blank_a3`, VU_CHATTY_RATE=400) + own reader `verification/probes/vu_reader.py`:
  vu_reader.py --venv a3 --app <app> --fp 3640 --bp 8640 --json --chatty 400 --warm 3 --pause 4 --sig TERM --target pid --rate-bps 2000 [--freeze-after-inner-exit --strace out/x.strace] --max-wait 150 --out out/x.json
  a3 2 KB/s: child exit 1.93 s, supervisor +30.07 s, stream ends in a 144 B partial record, 356 lines lost. 40 KB/s: drained in 3.27 s, clean, 0 lost (a2 40 KB/s also clean, 3.23 s).
  Decisive: reader frozen from the child's exit until the supervisor exited, then raw read -> still ends `{"timestamp": "...", "l` (a2: same at +5.04 s). strace: pump thread
  `write(1, ..., 134848 <unfinished ...>`, main `exit_group(0)` 30.07 s after the child exit, `<... write resumed>) = ?`. Reader buffering cannot be involved.
  Second Ctrl-C 10 s into the drain: immediate exit rc 1, `Aborted!` plain text on stderr, 168 B partial record (a2 identical). Second SIGTERM: harmless (cap as usual).
  Consumer that reads nothing after the signal: never exits (killed at 45 s and 90 s) on a3, a2 and 0.9.12 — inner child blocked in write(1) on its stdout pipe, so the 30 s cap
  (which starts at child exit) never starts.
  Explorer rerun (json_drain.py on 3641/8641): a3 TERM-pid r6 -> 30.64 s, last line `{"timestamp": "...", "level"<NO-NEWLINE-AT-EOF>`; r40 -> 7.05 s clean; a2 r6 -> 5.51 s truncated. Reproduced.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_upgrade/verification/out/a3-drain-*.json (+ .stdout.tail, .stderr), a3-drain-TERM-2k-freeze.strace, a2-drain-TERM-2k-freeze.strace, a2-drain-*.json, s912-drain-*.json, explorer_rerun/{a3,a2}-TERM-pid-r6.json; NOTES.md "## VERIFICATION" A3-08
ROOT_CAUSE_GUESS: reflex-base 0.10.0a3 reflex_base/utils/log.py: `_OutputPump._write` (:420-437) passes the whole converted batch to `_write_all` (:365-374) on a daemon thread (:389); `supervise_output` returns at `_DRAIN_WALL_SECONDS` (:279, loop :527-530) while that write is blocked, so the process exits mid-syscall. KeyboardInterrupt is caught only around `proc.wait()` (:520-526), not around `pump.drain`. Comment :278 "Stop shutdown after 30 seconds even when a consumer blocks every write" overstates (child blocks first).
