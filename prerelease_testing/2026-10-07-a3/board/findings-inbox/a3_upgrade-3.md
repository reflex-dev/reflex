ITEM: a3_upgrade
KIND: new
REF: - (#7428, new in a3)
TITLE: #7428 works: `reflex run --json` stopped by Ctrl-C/SIGTERM no longer drops or truncates output for a slow consumer; at the 30 s wall cap the stream still ends in a truncated JSON record
SEVERITY: low
STATUS: confirmed
REGRESSION_VS_0.9.12: no (0.9.12 has no output supervisor; its --json stream is not pure JSON lines)
REGRESSION_VS_0.10.0a2: no (a2 truncates after 5 s in every slow-consumer case)
REPRO: app `a3_upgrade/apps/jsondrain` (blank template + env-gated lifespan thread printing numbered `QA-SEQ` lines and recording the last one in `chatty.seq`);
  driver `a3_upgrade/scripts/json_drain.py <venv> <appdir> 3210 8210 <INT-group|TERM-pid|INT-pid> <lines/s> <out.json>` (reads fast until /ping answers,
  stops reading 4 s so both pipes fill, signals, then reads <lines/s> until EOF); matrix `a3_upgrade/bin/json_matrix.sh <label> <a3|alpha2> INT-group:40 TERM-pid:40 TERM-pid:6`.
  Results (exit = signal -> process exit; lost = lines the worker printed but the consumer never got):
    Ctrl-C (SIGINT to the group), 40 lines/s:  a3 6.5 s, 0 lost, 0 invalid (2 runs) | a2 5.6 s, 63 lost + truncated last record
    SIGTERM to the pid, 40 lines/s:            a3 6.7 s, 0 lost, 0 invalid          | a2 5.2 s, 49 lost + truncated last record
    SIGTERM to the pid, 6 lines/s:             a3 30.4 s (wall cap), 82 lost, last line `{"timestamp": "2026-10-07T20:08:42.496757+00:00", "level"` with no newline | a2 5.5 s, 249 lost + truncated record
  Exit code 0 in all of them; no leftover processes or listeners.
  The remaining wart: when `_DRAIN_WALL_SECONDS` fires, `supervise_output` returns while a pump thread is inside `_write_all`, the process exits and
  the consumer gets half a record at EOF, so a strict JSON-lines reader fails on the last line. Only reachable with a consumer that cannot take
  ~128 KB in 30 s; bounded shutdown is the documented intent.
EVIDENCE: a3_upgrade/shots/jsondrain/{a3,a2}-{INT-group-r40,TERM-pid-r40,TERM-pid-r6}.json (+ .stderr), a3_upgrade/logs/jsondrain-matrix.txt, NOTES.md "Item 4b"
ROOT_CAUSE_GUESS: reflex_base/utils/log.py:279 `_DRAIN_WALL_SECONDS = 30` / `supervise_output` (~:527) returns while `_OutputPump._write` is mid-`_write_all`; a fix could write a trailing newline (or stop on a record boundary) before exiting at the wall deadline.
