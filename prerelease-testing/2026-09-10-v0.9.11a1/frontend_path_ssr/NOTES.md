# Cluster: frontend_path_ssr — #7044 (`frontend_path` + `REFLEX_SSR=false`) end to end

The 0.9.11a1 changelog says:

> `reflex run --env prod` and `reflex export` no longer fail with `FileNotFoundError` when
> `frontend_path` is set and route prerendering is disabled (`REFLEX_SSR=false`) […]

Nothing in the campaign had exercised that combination, so this cluster builds it for real and
then serves the result and drives it in a browser.

`fpapp/` is a two-page app (`/` and `/about`) with `frontend_path="/myapp"`, a counter state and a
computed var — enough to tell "the build succeeded" apart from "the deployment works".

## The claim holds

| | reflex 0.9.10.post2 | reflex 0.9.11a1 |
| --- | --- | --- |
| `reflex export --frontend-only --no-zip --no-ssr` | **fails**: `FileNotFoundError: [Errno 2] No such file or directory: '.web/build/client/myapp/index.html.gz'` | succeeds; `.web/build/client/myapp/{index,404}.html{,.gz}`, `assets/`, `sitemap.xml` |
| `REFLEX_SSR=false reflex run --env prod` | **fails**, same `FileNotFoundError` | serves the app at `/myapp/` |

Logs: `logs/export_0910_nossr.tail.log`, `logs/export_a1_nossr.tail.log`, `logs/prod_0910.tail.log`.
The failure reproduces the changelog text exactly, which is the strongest evidence the fix is real.

Driving the 0.9.11a1 prod deployment in Chromium (`drive_fp.py`, evidence `logs/fp_a1.json`):
the page loads under the sub-path, two clicks on the counter give `count=2 doubled=4` (so the
websocket and state round-trip work under `frontend_path`), the in-app link to `/about` routes
client-side, going back preserves `count=2`, a reload keeps `count=2`, and a deep link straight to
`/myapp/about` renders the about page. No page errors, no failed requests.

Reproduce (a prod build takes 2-4 minutes):

```
cd fpapp && REFLEX_SSR=false reflex run --env prod --frontend-port 5471 --backend-port 5471
python drive_fp.py 5471 logs/fp_a1.json
./probe_routes.sh 5471 /myapp
```

Note prod mode still requires frontend and backend on the **same** port (pre-existing since 0.9.8).

## One thing the browser hides: FINDING-037

The deep link works in a browser but the server answers it with **HTTP 404**. `probe_routes.sh`
across four prod configurations (`logs/route_status_matrix.txt`):

| config | `/` | real route | unknown route |
| --- | --- | --- | --- |
| A `frontend_path=/myapp`, `REFLEX_SSR=false`, 0.9.11a1 | 200 | **404** | 404 |
| B `frontend_path=/myapp`, SSR on, 0.9.11a1 | 200 | 307 → 200 | 404 |
| C no `frontend_path`, `REFLEX_SSR=false`, 0.9.11a1 | 200 | **404** | 404 |
| D no `frontend_path`, `REFLEX_SSR=false`, 0.9.10.post2 | 200 | **404** | 404 |

So it is `REFLEX_SSR=false`, not `frontend_path`, and it is pre-existing (D). Detail in
FINDING-037.

## Findings raised

* FINDING-037 — with `REFLEX_SSR=false`, the prod server answers every route but `/` with 404 while
  serving the correct SPA document (LOW, pre-existing).
