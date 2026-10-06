# Bounded State-scale release reassessment

No newly introduced blocker is demonstrated by this comparison. Fresh published
alpha and stable graphs with enterprise a4 installed but unused by the core app
show that this rendering-limit class already exists in stable. This does not
prove identical failure thresholds for every browser or State topology.

Both graphs use identical fixture/config source, Bun 1.4.2, production CLI on
3146, disk State and fresh Chromium 140 contexts. The fixture defines dormant
one-field States plus a normal counter and memoized dynamic article. No generated
JS or framework code was changed. Full frozen graphs and isolated origins are
in [alpha provenance](alpha-provenance.json) and [stable provenance](stable-provenance.json).

| Dormant States | Alpha 0.10.0a1 | Stable 0.9.12 |
| --- | --- | --- |
| 1,200 | Direct Article 7 HTTP 200, memoized navigation and counter 0→1 pass; no browser errors | Builds/starts, but browser displays React stack-overflow error |
| 1,300 | Builds/HTTP 200; dynamic page fails with maximum-call-stack error | Builds/starts, but React stack-overflow error on both dynamic and ordinary root pages |
| 1,500 | Builds/HTTP 200; dynamic page fails with maximum-call-stack error | Not rerun at this size; original Bun/Node control could not start |

The alpha's fallback root shows static Runtime QA text at 1,300/1,500, but its
counter does not update and another page exception occurs. That is a failing
interactive app, not a recovery. Stable's 1,300
[root-route control](root-route-control/stable-1300/browser.json) explicitly
fails to render Runtime QA, retaining the React error. Its direct dynamic URL
also has the known preexisting HTTP 404 fixed by this alpha; the separate root
observation prevents confusing that routing status with the scale failure.

The original 500/1,000 stable/alpha passes remain valid prior coverage. This
bounded follow-up finds a working alpha at 1,200 where stable fails, and a
shared failing size at 1,300; it does not establish a working stable application
broken by the alpha. Historical finding 4 therefore remains a noncritical
scale limitation, without a demonstrated new regression, and does not satisfy
the user's release-blocker criteria on the available evidence.

[alpha-1200](alpha-1200/result.json), [alpha-1300](alpha-1300/result.json),
[alpha-1500](alpha-1500/result.json), [stable-1200](stable-1200/result.json),
[stable-1300](stable-1300/result.json), source hashes, screenshots and full
startup/shutdown logs are retained. Stable logs the old lifespan-cancellation
traceback; alpha shutdown is clean. The first observer required HTTP 200 before
heading checks; its stable observations are supplemented by the root control.
The exact [initial observer](initial-observer.py) and
[later executed observer](executed-observer.py) retain that distinction.

For reuse, install either [alpha](../requirements-alpha-lock.txt) or
[stable](../requirements-stable-lock.txt) graph into a fresh PyPI-only UV
environment. Copy [root_runs.py](../root_runs.py) to a neutral directory, then:

```sh
env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers uv --no-config run --no-project --python /private/tmp/your-a4-env/bin/python python root_runs.py scale --graph alpha --counts 1200 1300 --campaign /absolute/path/to/prerelease_testing/2026-10-05 --output /private/tmp/scale-results
```

Close each browser and stop the owned server before switching graphs on the
same port. The controller does this automatically. Its exit status is
observation-only; inspect per-case `passed`, browser diagnostics and startup
fields. Different drivers may overwrite a graph summary when appending runs;
the authoritative per-case JSON remains separate. Screenshots are taken after
fallback navigation, so use JSON for the initial dynamic-page failure. This is
an exploratory comparison, not a performance benchmark or precise threshold.
