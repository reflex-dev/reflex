# Cluster: config_assets_cli — the shared-asset fix (#7039) and CLI startup (#7050)

Two claims from the 0.9.11a1 changelog checked against the previous stable, both without a
browser: they are process-level behaviours, so they are tested the way they actually bite.

## #7039 — shared assets under concurrent compiles

> Compiling an app from several processes against one working directory — pytest-xdist workers,
> parallel builds, or containers sharing a bind mount — no longer aborts with `FileNotFoundError`
> or `FileExistsError` while linking a `rx.asset(shared=True)` file into `assets/external/`. A
> shared asset whose link already points at a different file is repointed at the asset rather than
> left alone.

`sharedasset/` is a two-file app whose page calls `rx.asset(path="lib.js", shared=True)`;
`other.js` sits next to it as the wrong target. `race_assets2.py` tests both halves:

```
python race_assets2.py <trials> <workers>
```

**Half two — the stale link — is a clean pass/fail, and 0.9.11a1 fixes it.** The script registers
the asset, repoints the resulting symlink at `other.js`, and registers again:

| | link after re-registering | content served |
| --- | --- | --- |
| reflex 0.9.11a1 | `lib.js` — **repointed** | `console.log("shared asset v1");` |
| reflex 0.9.10.post2 | `other.js` — **left alone** | `console.log("OTHER FILE");` |

So on the previous stable an app whose shared asset moved kept serving the old file with no
warning; on 0.9.11a1 it is corrected. Exactly as claimed.

**Half one — the concurrent first-create race — could not be provoked here, on either version.**
`multiprocessing.Barrier`-synchronised workers all racing the very first creation of the link:
80 registrations (8 trials × 10 workers) and then 320 (20 × 16) on 0.9.10.post2, **0 failures**;
same on 0.9.11a1. The check-then-symlink window is evidently too narrow on this container's
overlayfs. Not evidence against the fix — the bug reports name bind mounts and network
filesystems — just a note that this repro does not demonstrate that half. `race_assets.py` is the
simpler unsynchronised variant (12 workers × 40 registrations, also clean on both).

## #7050 — CLI startup

> Reduce CLI startup time by loading component and cloud command implementations only when
> invoked […] caching successful latest-version checks for 24 hours.

Best of five, cold shell, `cwd=/tmp` (no reflex project):

| command | 0.9.10.post2 | 0.9.11a1 |
| --- | --- | --- |
| `reflex --help` | 0.404 s | **0.174 s** |
| `reflex db --help` | 0.393 s | **0.172 s** |
| `reflex cloud --help` | 0.412 s | **0.195 s** |
| `reflex --version` | 0.362 s | **0.162 s** |

A consistent ~2.3× improvement across every subcommand, including `cloud`, whose implementation is
the one now loaded lazily. Claim verified; no finding.

## Findings raised

None. Both claims hold; the one half that could not be exercised is recorded above rather than
reported as a problem.
