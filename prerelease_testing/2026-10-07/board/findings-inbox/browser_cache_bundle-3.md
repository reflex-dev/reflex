ITEM: browser_cache_bundle
KIND: verify
REF: N-016
TITLE: Pure read-only external inventory control does not reproduce the reported uncached hydration staleness
SEVERITY: low
STATUS: changed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Follow browser_cache_bundle/deploy_cache/NOTES.md; uncached_probe.py reads an external warehouse quantity from a file outside the watched app directory using a pure @rx.var(cache=False). Refresh at10, externally set0, reload→0, externally set10, ordinary Refresh→10, reload→10. No computed-var state writes or private framework calls. Run alpha2 dev/prod, stable dev/prod and alpha1 dev, each Chromium+WebKit.
EVIDENCE: browser_cache_bundle/deploy_cache/evidence/uncached-stock/*/result.json, *-trace.json.gz, screenshots and complete server.log.gz; all40 comparisons pass. Per-event frames and backend READ_STOCK logs are retained.
ROOT_CAUSE_GUESS: Not established by this passing control.
SCOPE: Does not refute the coordinator's original side-effectful N-016 repro. It limits the evidence: a comparable read-only external-value workflow does not become stuck. Do not promote that report to a general high-severity polling/data-freshness regression without a realistic failing example. No framework fix applied.
