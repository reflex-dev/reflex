# benchmark-data

Append-only history of the reflex-bench CI results of `reflex-dev/reflex`
(see `packages/reflex-bench/README.md`, section "CI", on `main`). Nothing here
is edited by hand; the `benchmarks-daily` and `macro-benchmarks` workflows add
files through `.github/actions/bench_history`.

```
README.md                                              this file
runs/<profile_id>/<YYYY-MM-DDTHH-MM>_<kind>_<short sha>_<run id>_<stem>.json
backfill/<profile_id>/<reflex version>.json            release backfills
```

- `runs/`: one `reflex-bench/1` result document per benchmark job of a
  scheduled or manually dispatched run on `main`. `kind` is the result's
  `invocation.kind` (`daily` for the schedule, `ci` for a manual run), the time
  its `invocation.started_at` (UTC), `stem` the result file's name in the job
  (`macro`, or the shard of the daily run). Pull request runs never land here.
- `backfill/`: results of released reflex versions, measured later on the same
  runner type, so their series continue the daily ones.

The noise table of one profile:

```console
$ git fetch origin benchmark-data
$ git worktree add ../bench-data benchmark-data
$ uv run reflex-bench noise ../bench-data/runs/<profile_id> --kind daily --format md
```
