# Benchmarks

A harness for measuring what the engine costs, against a real Postgres and real
worker processes.

```bash
REFLEX_TEST_POSTGRES=postgresql://postgres@127.0.0.1:5432/bench \
    uv run python packages/reflex-workflow/benchmarks/bench.py all \
    --repeat 5 --driver-cpu 2 --worker-cpus 4,6,8,10 --postgres-cpus 12,13,14,15
```

Scenarios: `scaling` (1, 2 and 4 worker processes), `limits` (a declared
concurrency limit, and attempt history), `population` (100k dormant runs in the
table), `latency` (work becoming due gradually rather than all at once). Each
worker is a separate process running up to 8 steps at once, so the figures
include the connection pooling and claim contention a deployment has, but not the
network between an application and its database.

## Reading the numbers

**The rows check the harness.** Every run records which worker ran it and when it
started and finished. After each trial the harness computes how many steps each
worker ran at once, and how many of each customer's, and fails rather than
prints if either exceeds its cap. A figure in the table is one the rows agree
with.

**Trials are interleaved and summarized.** `--repeat N` runs every scenario once,
then every scenario again, N times over, so a noisy stretch on the machine lands
on all of them rather than on one. The table shows the median and the range.

**Pin everything.** `--driver-cpu` and `--worker-cpus` pin the harness and each
worker to a CPU of its own; pin the server yourself, and name its CPUs with
`--postgres-cpus` so the table reports how busy they were:

```bash
postmaster=$(head -1 "$PGDATA/postmaster.pid")
for pid in $postmaster $(pgrep -P "$postmaster"); do taskset -a -p -c 12-15 "$pid"; done
```

New backends inherit the postmaster's CPUs. Pick one hardware thread per
physical core for the workers (`lscpu -e` shows which threads share a core) and
leave a core to the rest of the machine. Pinning keeps these processes on their
CPUs; it does not keep everything else off them, which takes kernel or cgroup
configuration, so a busy desktop still shows up as spread between trials.

`wrk %` and `pg %` are how busy those CPUs were during the measured window, by
anything: near 100% on the workers means they are what limits throughput.

## Results

One laptop: AMD Ryzen 9 7940HS (8 cores, 16 threads), Postgres 18.6 from a
default `initdb` over a Unix socket, Python 3.14. Harness on CPU 2, workers on
CPUs 4, 6, 8 and 10, Postgres on 12–15, each worker up to 8 steps at once,
polling every 50ms. 2000 runs per trial; medians of 5 interleaved trials for a
no-op step and 3 for a 50ms one.

| scenario | workers | no-op step, steps/s | 50ms step, steps/s | 50ms, share of ceiling |
| --- | --- | --- | --- | --- |
| plain | 1 | 481 (396–500) | 133 (133–133) | 83% |
| plain | 2 | 888 (785–960) | 268 (268–268) | 84% |
| plain | 4 | 1429 (1225–1597) | 520 (516–523) | 81% |
| declared limit, 200 customers | 4 | 836 (737–941) | 413 (407–435) | 65% |
| attempt history | 4 | 1112 (1094–1226) | 476 (458–494) | 74% |
| 100k dormant runs | 4 | 1504 (1033–1528) | 519 (512–534) | 81% |

The ceiling for a 50ms step is 8 slots × 20 steps a second = 160 per worker.

| work becoming due gradually | lateness p50 | p95 | p99 |
| --- | --- | --- | --- |
| plain, 2 workers | 27ms | 52ms | 55ms |
| declared limit, 2 workers | 29ms | 53ms | 60ms |

**Workers are bound by their own CPU.** With a no-op step each worker's CPU is
saturated while Postgres's are under half busy: the engine costs about 2ms of
Python per step, so one process tops out near 500 steps a second, and adding
processes adds throughput nearly linearly. With a 50ms step the workers are
mostly idle and reach 81–84% of the ceiling at every scale: a slot is held for
about 60ms per 50ms step, the difference being the round trips to load the row,
commit it, and claim the next.

**Dormant runs cost nothing measurable.** 100k runs sleeping in the table change
neither figure; the claim finds due rows through the index on `wake_at` in about
0.4ms either way.

**A declared limit costs the most**, 42% of throughput with a no-op step and 21%
with a 50ms one, because each group is claimed in a transaction of its own under
an advisory lock. **Attempt history** costs 22% and 9%, one insert per step.

**Timer lateness is about half the poll interval**, as it should be: a run due at
a given moment waits for the next poll, and `LISTEN`/`NOTIFY` does not shorten
that, since nothing is written when a timer comes due.

**Statistics matter.** After a bulk insert with no `ANALYZE`, the claim's pick
falls back to a sequential scan: 6.5ms against 0.3ms on 100k rows. Autovacuum
does this for a running system; the harness analyzes after every seed.

**The harness found a bug.** An earlier version reported a single worker doing
480 steps a second with a 100ms step, against a ceiling of 80. The claim was
`UPDATE … WHERE pk IN (SELECT … LIMIT n FOR UPDATE SKIP LOCKED)`, and when the
planner's statistics said little was due it ran the subquery once per candidate
row, each rescan locking rows the last one had skipped: one claim of 8 took all
800 due rows, and a customer limited to 2 was given 50. The pick is now a
materialized CTE, and the harness checks every trial's concurrency against the
rows so a figure like that cannot be printed again.
