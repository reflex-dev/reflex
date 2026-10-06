# Confirmed rolling-upgrade persistence regression

**Release classification: newly introduced rolling-upgrade blocker under the user's stated gate.** A backend list append persists with published Reflex 0.9.12 alone and 0.10.0a1 alone, but is silently lost when a 0.9.12 worker handles state serialized by 0.10.0a1. The documented exception in [PR #7312](https://github.com/reflex-dev/reflex/pull/7312) does not waive that demonstrated regression. This corrects the earlier campaign's classification of this behavior as only an expected limitation.

| Seed writer → append worker → fresh reader | Fresh backend list | Computed checksum | Outcome |
| --- | --- | --- | --- |
| 0.9.12 → 0.9.12 → 0.9.12 | `["saved", "inplace"]` | 23 | Control persisted |
| 0.10.0a1 → 0.9.12 → 0.10.0a1 | `["saved"]` | 22 | Append lost |
| 0.10.0a1 → 0.10.0a1 → 0.10.0a1 | `["saved", "inplace"]` | 23 | Control persisted |

All nine workers ran in fresh processes using the same unchanged [app](rolling_app.py) and [worker](worker.py) sources from the earlier compatibility test. Every append worker saw the appended value in memory. Both controls marked `_items` and `checksum` dirty and wrote changed Redis payloads. The mixed-version worker marked nothing dirty, left its computed checksum stale, and left the Redis payload hash unchanged. A fresh reader then confirmed the lost update. [Raw comparison](evidence/results.json) records the explicit persistence booleans; individual worker `status: passed` values mean execution completed, not that persistence succeeded.

This can lose ordinary backend mutable-state updates during a mixed-version rolling deployment. The release fix should preserve backward-compatible wrapping and dirty tracking of mutable backend values when the new serialized state is loaded by the existing stable runtime. Add a regression test that writes with the new worker, appends with a fresh old worker, and reads with another fresh worker, alongside old/old and new/new controls. Changing the published stable package is not a fix available to deployments already running it. Temporary operational mitigation is to avoid overlapping old/new workers for these sessions; explicit reassignment rather than in-place mutation is a separate application workaround, not the framework repair. Reassignment was covered in the prior campaign, not repeated here.

The stable environment contained 91 published distributions and the alpha environment 104; both used Python 3.12.1 and published `reflex-enterprise==0.9.7a4`. Enterprise APIs were not used by this app. Exact graphs are [stable](requirements-stable-lock.txt) and [alpha](requirements-alpha-lock.txt), with full per-worker distribution lists and [verified import origins](evidence/finalization.json). No packages were installed during this comparison. Framework imports came only from the two existing isolated site-packages trees; workers asserted no checkout path, `PYTHONPATH`, editable or direct-URL installation. Execution used `uv --no-config run --no-project --python` from a neutral directory.

This was a bounded, sequential real-Redis manager comparison, one independent UUID session per case. It did not add browser traffic, concurrent event races, other mutation forms, or new security testing. The original worker clears prior dirty/touched bookkeeping before the isolated mutation, identically in every case. The operation lock was disabled in every worker. The full dependency graphs differ, so this is a measured published-version compatibility boundary rather than a dependency-minimized source bisect.

Redis 8.10.2 was started only after a no-listener check on port 9141. Persistence was disabled; only database 5 was accessed. Exactly the three owned UUID state keys were deleted, database size returned from 0 to 0, Redis shut down without saving, and a final port check found no listener. [Server log](evidence/redis.log) and [cleanup/source/syntax checks](evidence/finalization.json) are retained. No framework code, external issue, comment, or commit was changed.

To repeat with the same two published environments, copy this folder to `/private/tmp/reflex-enterprise-a4-20261005-rolling`, prove port 9141 is free, and start an owned disposable Redis with `--bind 127.0.0.1 --port 9141 --save '' --appendonly no --protected-mode yes`. From that neutral directory run:

```sh
env -u PYTHONPATH UV_CACHE_DIR=/private/tmp/reflex-enterprise-a4-20261005-rolling/uv-cache \
  /Users/masenf/.local/bin/uv --no-config run --no-project \
  --python /private/tmp/reflex-enterprise-a4-20261005-root-stable-venv/bin/python compare.py
```

The [driver](compare.py) uses the existing root stable and alpha environment paths and removes only its own tokens in `finally`. Preserve its output, then stop only the owned Redis. [Finalization](finalize.py) is the campaign's source/graph/cleanup collector; its original-source path is specific to this workspace. Exact executed driver bytes are retained in [executed-drivers](evidence/executed-drivers/compare.py). The reusable top-level copies received formatting only after execution, with AST equality verified; they were not rerun against Redis. The saved pickle files contain only this synthetic app's test state and should be treated as diagnostic data, never unpickled from an untrusted source.
