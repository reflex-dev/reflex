ITEM: a3_upgrade
KIND: new
REF: - (#7350 output supervisor vs #7328 "stops on SIGTERM and SIGINT without a TTY")
TITLE: `reflex run --json` ignores SIGINT sent to its pid: the supervisor swallows it and never forwards it, so the server keeps running (plain `reflex run` exits in 0.25 s)
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no (0.9.12 does not stop on a pid-only SIGINT either, with or without --json, and not on SIGTERM to the pid in dev)
REGRESSION_VS_0.10.0a2: no (identical on a2)
REPRO: app `a3_upgrade/apps/jsondrain` (any blank app works). `QA_CHATTY_OFF=1 QA_EOF_CAP=40 QA_WAIT_CAP=20 a3_upgrade/bin/json_matrix.sh a3fast a3 INT-pid:100000`
  (driver `scripts/json_drain.py`: starts `$SB/envs/a3/bin/reflex run --json --frontend-port 3210 --backend-port 8210` in its own session, reads stdout
  fast, then `os.kill(pid, SIGINT)` on the `reflex` process only). Manual equivalent:
    cd <blank app> && $SB/envs/a3/bin/reflex run --json --frontend-port 3210 --backend-port 8210 > out.jsonl 2>&1 &  P=$!
    (wait for http://localhost:8210/ping) ; kill -INT $P ; sleep 30 ; kill -0 $P && echo STILL RUNNING; curl -s localhost:8210/ping
  Results (signal -> exit): a3 --json SIGINT-to-pid: never (killed after 60 s; also 210 s in the slow-consumer run); a2 --json: never;
  a3 --json SIGTERM-to-pid: 2.0 s rc 0; a3 plain `reflex run` SIGINT-to-pid: 0.25 s rc 0 (a2 plain 0.2 s); Ctrl-C to the whole process group
  (terminal): 6.5 s rc 0 with --json. 0.9.12 (no supervisor): SIGINT-to-pid never exits with or without --json; SIGTERM-to-pid never in 60 s (#7328 era).
  Impact: tools that drive `reflex run --json` (the machine-readable mode) and stop it the usual way for a child process — `proc.send_signal(SIGINT)`,
  `kill -INT <pid>`, `timeout -s INT` — leave the dev server, its backend worker and the vite node process running and the ports bound.
EVIDENCE: a3_upgrade/shots/jsondrain/{a3fast,a2fast,s912fast,s912plainfast}-INT-pid-r100000.json, a3-INT-pid-r40.json (210 s), a3plain-INT-pid-r40.json, a2plain-INT-pid-r40.json, a3fast-TERM-pid-r100000.json; logs/jsondrain-followup{,2}.txt
ROOT_CAUSE_GUESS: reflex_base/utils/log.py `supervise_output`: line 519 forwards SIGTERM (`signal.signal(signal.SIGTERM, lambda *_: proc.terminate())`) but SIGINT only raises KeyboardInterrupt in the supervisor, which `except KeyboardInterrupt: continue` (line 524, comment "The child gets the same interrupt and shuts down on its own") swallows; that only holds for a terminal Ctrl-C delivered to the whole process group. Forwarding SIGINT to the child (`proc.send_signal(SIGINT)`) when the supervisor receives it would cover the pid-only case.
