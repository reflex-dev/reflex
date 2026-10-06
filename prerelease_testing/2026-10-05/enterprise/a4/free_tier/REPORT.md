# Published a4 Free-tier validation

All eight public production/export cases pass with the exact 104-package alpha
graph and enterprise 0.9.7a4. The app/driver are unchanged copies of the a3
fixtures, executed from a neutral directory with isolated PyPI imports and
existing Bun 1.4.2. The [raw results](results.json), [summary](summary.json),
[driver](drive.py), and per-case logs retain the actual assertions and requests.

The matrix checks Free-tier production/export with badge requested on/off,
Free-tier development export, paid badge-off export and rejected credentials for
production/export. Real browser counters change 0→1 with a production backend;
browser/static HTML observations verify badge enforcement. The official hosting
SDK made ten loopback account requests using fictional credentials. All 33 guard
contexts have CI/harness flags absent and offline false; tier/auth functions are
unmodified. No real cloud entitlement was exercised.

Rejected credentials still prevent startup and archives while returning status
0. This is historical finding 11, a preexisting automation limitation rather
than a demonstrated security bypass or newly introduced failure. Proposed PR
#250 addresses that separately and was unmerged when reviewed. No new blocker
was found here. The frontend-only development export preview retains three
expected WebSocket refusals to its absent backend.

Previously reviewed driver limits remain: its browser assertions gate page
exceptions but not all console/network anomalies; the Python socket audit does
not cover Bun/browser network traffic; lexical path checking is weaker than
resolved containment (actual temporary paths were safe); rejected runs do not
independently probe for transient listeners. Current raw contexts/logs were
manually reviewed. No framework or retained driver fix was made.

For reuse, install [the frozen alpha graph](../requirements-alpha-lock.txt) into
a fresh UV environment, copy this directory's `app/` and `drive.py` to a neutral
temporary directory and run the driver there with published Playwright/Chromium:

```sh
env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers uv --no-config run --no-project --python /private/tmp/your-a4-env/bin/python python drive.py
```

The driver owns the local API and subprocesses. All completed cases were saved;
the API and production app listeners were stopped afterward. [Cookie provenance](../cookies/alpha-provenance.json)
records the same root environment's complete graph and isolated import origins.
