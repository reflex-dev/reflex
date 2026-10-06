# Enterprise a3 HTTP-only cookies

The same small app passes six production-browser scenarios with published
enterprise **0.9.7a3** on both Reflex **0.10.0a1** and **0.9.12**. Framework
imports resolve exclusively inside isolated PyPI environments. The app runs
from neutral temporary directories via the public production CLI.

The browser verifies initial values; paired HTTP-only cookie writes hidden from
`document.cookie`; inherited cached computed values rendered through `rx.memo`;
five rapid paired updates ending at generation six; persistence after reload;
browser-cookie changes pulled through `HTTPCookie.sync` with dependency
invalidation; and explicit deletion from the browser jar. These form six
recorded scenario groups. No framework workaround was applied.

Both runs recorded **15 successful cookie-sync HTTP 200 responses and 15
`net::ERR_ABORTED` request-failure notifications**, with no HTTP errors, page
exceptions or error-level console messages. Cookie headers, values and the
visible UI assertions pass. The driver records request failures but does not
reject them; these notifications must remain visible during acceptance review.
Both servers emit a published-cookie `rx.event.fix_events` deprecation warning,
without a traceback. Stable additionally logs twelve field-type warnings for
assigning strings to the `HTTPCookie`-annotated fields; alpha does not. The
cookie descriptors still synchronize and invalidate correctly in both runs.
Read-only review found a serialized cookie promise chain, no explicit fetch
abort signal, and an empty HTTP 200 response in published a3 code. That source
inspection does not establish the cause of the aborted notifications; do not
attribute all fifteen to navigation, since the driver has only one reload.
The five Playwright clicks are sequential; this tests final-value consistency
under repeated updates without proving request overlap or every race condition.

Evidence: [alpha browser](logs/alpha-prod/browser.json),
[stable browser](logs/stable-prod/browser.json),
[alpha provenance](logs/alpha-provenance.json),
[stable provenance](logs/stable-provenance.json), and both production server
logs. Screenshots show the final deleted-cookie state.

Fixture authoring attempts are preserved: positional `rx.memo` props were
replaced with keyword props, `State.reset` was wrapped in a registered event,
and the deletion assertion was corrected to expect no cookie entry. They are
test authoring corrections, not framework defects. The visible Reset State
button is not exercised by this six-scenario driver. Partitioned cookies,
secure HTTPS, ComponentState and multi-worker persistence remain untested.

To repeat, install [the alpha graph](../requirements-alpha-lock.txt) or the
the [stable frozen graph](../auth-stable/requirements-resolved.txt) into a fresh
PyPI-only environment. Copy `app/`
and `browser.py` to neutral temporary directories. Set `bun_path` in the copied
config to an available Bun 1.4.2 binary. From the copied app directory:

```sh
env -u PYTHONPATH uv --no-config run --no-project --python /private/tmp/your-a3-venv/bin/python reflex run --env prod
```

Then run the driver from another shell with published Playwright and Chromium:

```sh
env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers uv --no-config run --no-project --python /private/tmp/your-a3-venv/bin/python python /private/tmp/your-cookie-driver/browser.py --output /private/tmp/your-cookie-results
```

Ports are 3145/8145. Both owned production servers were stopped at completion.
