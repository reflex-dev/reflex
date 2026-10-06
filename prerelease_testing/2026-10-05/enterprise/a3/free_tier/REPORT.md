# Enterprise a3 Free-tier rerun

All eight public CLI cases pass with the published `reflex-enterprise==0.9.7a3`
and frozen Reflex `0.10.0a1` graph. Only the enterprise version changed from the
a2 graph. This rerun copied the app into a neutral temporary directory.

The matrix covers Free-tier production with badge enabled/disabled, Free-tier
production export with badge enabled/disabled, Free-tier development export,
a paid badge-disabled export control, and rejected credentials for production
and export. Real production-browser counter interactions and exported HTML
confirm badge enforcement. The official SDK made ten real HTTP account requests
to a disposable local API. All 33 recorded guard contexts have CI/harness flags
absent and offline mode false; production guards were active. Only fictional
credentials and account responses were used.

The frontend-only development export preview logs three expected WebSocket
connection failures to the absent backend. Production counters are checked
with a real backend. The inherited browser helper rejects page exceptions but
does not enforce console output or capture HTTP/request failures. The network
audit covers Python sockets, not Bun/browser traffic. Current raw contexts,
requests and CLI output were manually reviewed. The denied-run assertions check
denial text and absent ZIPs, but do not independently probe for a transient
production listener; actual denied logs show no startup. These reusable-driver
limits remain unchanged after review.

Rejected credentials still block startup/export but return exit status **0**.
This preserves historical finding 11; the matrix's pass means denial occurred,
not that its exit-status contract is correct. No real cloud entitlement or
deployment was exercised.

[Summary](summary.json), [raw matrix](results.json), [provenance](provenance.json),
[driver](drive.py), [fixture app](app/free_tier/free_tier.py) and per-case logs
retain the requests, contexts, CLI output and browser evidence. The fixture
contains the previously reviewed lexical-path helper limitation; actual paths
were safe `TemporaryDirectory` paths. No framework code was patched.

To repeat, install [the frozen graph](../requirements-alpha-lock.txt) into a
fresh UV environment from PyPI. Copy this directory's `app/` and `drive.py` into
a neutral temporary directory, excluding generated `.web` and state files.
Use an available Bun 1.4.2 path in `app/rxconfig.py`, then run:

```sh
env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers uv --no-config run --no-project --python /private/tmp/your-a3-venv/bin/python python /private/tmp/your-free-tier/drive.py
```

The driver owns its account API and public CLI subprocesses. It saves results
beside its copied source. All owned services were stopped after this run.
