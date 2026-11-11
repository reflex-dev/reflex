# FINDING-022: true impact of the prod CORS default, and the fix

Engagement: fix022 (2026-11-11). Fix branch `fix/same-origin-behind-tls-proxy` in worktree `/home/user/reflex-fix-022`, commit
`894437913f27f2b9f6be9ed48b8ccc2fc59fb0f5`, based on origin/main `2d71015b7`.

Venvs (PyPI, built in `$SB=/tmp/claude-0/-home-user/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/fix022`):
`envs/a1` = `reflex==0.11.0a1`, `envs/v101` = `reflex==0.10.1`. Both resolve python-engineio 4.15.1, python-socketio 5.18.1,
granian 2.8.7 and starlette 1.10.0. `envs/fix` = editable install of the fix worktree. Browser: Playwright Chromium (shared driver venv).
Scripts are in `bin/`, the probe app is in `src/fapp` (a counter; a run passes when two clicks give `count=2`), and raw outputs are in `evidence/`.

## 1. How the decision is made (code facts)

- **engine.io's origin check** (python-engineio 4.15.1, `engineio/base_server.py:284-300`, enforced in `async_server.py:222-236`).
  It runs only when the request has an `Origin` header. With `cors_allowed_origins=None` (the 0.11.0a1 prod default without `deploy_url`),
  the allowed list is `{wsgi.url_scheme}://{Host}`, plus `{X-Forwarded-Proto}://{X-Forwarded-Host or Host}` when either forwarded
  header is present (first comma-separated value). The comparison is an exact string match.
- **The ASGI driver never reads the scope's scheme.** `engineio/async_drivers/asgi.py:217`:
  `environ['wsgi.url_scheme'] = environ.get('HTTP_X_FORWARDED_PROTO', 'http')`. Without X-Forwarded-Proto, engine.io treats every
  request as `http`, whatever granian put in `scope["scheme"]`. Granian's proxy-header support (`granian/utils/proxies.py`,
  `wrap_asgi_with_proxy_headers`) is an opt-in wrapper. Reflex does not use it: `reflex/utils/exec.py:run_granian_backend_prod` passes only
  target/address/port/interface/log/workers. Even if it did, it would not change engine.io's decision. `Forwarded` (RFC 7239) is
  not read by engine.io or by Reflex.
- **Callable form.** `cors_allowed_origins` may be a callable. engine.io 4.11.0 calls it as `f(origin)`; since **4.12.0** it calls
  `f(origin, environ)`. reflex declared `python-socketio >=5.12.0`, which allows engine.io 4.11. The fix adds `python-engineio >=4.12.0,<5.0`.
  `scripts/check_min_deps.py reflex` passes, and the callable was exercised under engine.io 4.12.0 (`bin/floor_check.py`).
- **HTTP CORS layer** (`reflex/app.py:_cors_options/_add_cors`, and the `CORSMiddleware` wrapped around the root ASGI app).
  When the prod default has no deploy_url, no middleware is installed. That is correct for a same-origin app behind any proxy:
  the browser decides "same origin" from its own URL bar, so a same-origin `fetch`/upload needs no CORS headers. A cross-origin
  `/_upload` sends custom headers, so it is preflighted, and the preflight fails (no middleware, POST-only route). With
  `deploy_url` set, only that origin gets ACAO. So the HTTP layer was never the problem; only the websocket, where the *server* must
  guess its public origin, was. The fix leaves the HTTP layer unchanged (see 5c).
- **Frontend URL selection** (`.templates/web/utils/state.js:getBackendURL`). When `api_url`'s host is localhost/0.0.0.0/::, the
  browser swaps in `window.location.hostname`, and on https it also drops the port. So a page loaded from `127.0.0.1` connects to
  `127.0.0.1`, never to `localhost`. A "localhost vs 127.0.0.1" mismatch therefore happens only when `api_url` explicitly names the
  other loopback name. That is genuinely cross-origin.

## 2. Front doors: what the upstream (Reflex) receives

Fetching vendor pages directly was blocked in this sandbox (WebFetch: nginx.org, caddyserver.com, docs.aws.amazon.com,
doc.traefik.io and developers.cloudflare.com are outside the allowed domains). Running downloaded proxy binaries (Caddy, Traefik)
was also denied by the sandbox policy, and nginx/haproxy are not installed. So:
(a) the header profiles below come from vendor documentation, found with WebSearch (URLs cited; "secondary" marks forum/community
or third-party sources and "unverified" marks my own knowledge not confirmed here);
(b) every profile was emulated end to end by `bin/hproxy.py`: a TLS-terminating reverse proxy that strips client `X-Forwarded-*`
headers and sends exactly the profile's `Host`/`X-Forwarded-*`. Behind it ran a real `reflex run --env prod` single-port app, with Chromium
in front. Raw handshakes with the same headers were also sent directly to the app (`bin/hsmatrix.sh`).

| Profile (emulated) | Upstream sees | Real front doors with this profile by default | Source |
|---|---|---|---|
| `passthrough` | Host kept, no XFP/XFH | L4 TLS terminators: stunnel, AWS NLB TLS listener / Classic ELB SSL listener (no HTTP parsing), HAProxy `mode tcp`; HAProxy `mode http` without `http-request set-header X-Forwarded-Proto https if { ssl_fc }`; nginx with `proxy_set_header Host $http_host` but no XFP line | HAProxy: XFP is a manual rule [OPNsense forum](https://forum.opnsense.org/English_Forums/General_Discussion/Re:_HAProxy_Questions), [serversforhackers](https://serversforhackers.com/using-ssl-certificates-with-haproxy) (secondary); NLB: L4 adds no headers [gist](https://gist.github.com/richdougherty/ff00424178b9e1dba9bca65db9997146) (secondary). The verifier's `tls_term.py` is this profile |
| `nginx-default` | `Host: 127.0.0.1:<port>` ($proxy_host), no XFP/XFH | nginx `proxy_pass` with no `proxy_set_header` (nginx rewrites Host to `$proxy_host` and sets `Connection: close`) | [NGINX admin guide](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/) |
| `nginx-host-xfp` = `xfp-https` | Host kept, `XFP: https` | nginx with `Host $http_host` + `X-Forwarded-Proto $scheme`; AWS ALB; GCP external ALB; Heroku router; Fly.io; Cloudflare proxy (XFP = visitor protocol, including Flexible SSL); DigitalOcean App Platform; Render (plain https) | ALB XFP [AWS docs](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/x-forwarded-headers.html) (ALB Host preservation: unverified); GCP "preserves the Host header", adds XFP [GCP docs](https://docs.cloud.google.com/load-balancing/docs/https); Heroku overwrites XFP [Heroku help](https://help.heroku.com/J2R1S4T8/can-heroku-force-an-application-to-use-ssl-tls); Fly sets X-Forwarded-* [Fly docs](https://fly.io/docs/networking/request-headers/); Cloudflare XFP [CF docs](https://developers.cloudflare.com/fundamentals/reference/http-headers/); DO [DO community](https://www.digitalocean.com/community/questions/app-platform-django-secure_proxy_ssl_header-use) (secondary); Render [community.render.com](https://community.render.com/t/proxy-https-settings/19249) (secondary) |
| `xfp-xfh` | Host kept, `XFP: https`, `XFH: host` | Caddy terminating TLS itself (docker-example/production-compose); Traefik at the edge; Kubernetes ingress-nginx at the edge; Railway | Caddy sets XFH/XFF/XFP and replaces untrusted values [caddy.community](https://caddy.community/t/caddy-v2-5-0-rc-1-and-x-forwarded-headers/15694) (secondary; docs page not fetchable); Traefik [forum](https://community.traefik.io/t/use-x-forwarded-in-traefik-v2/5206) (secondary); ingress-nginx `use-forwarded-headers` default false [configmap.md](https://github.com/kubernetes/ingress-nginx/blob/main/docs/user-guide/nginx-configuration/configmap.md); Railway "X-Forwarded-Proto always indicates https", XFH [Railway docs](https://docs.railway.com/networking/public-networking/specs-and-limits) |
| `render-wss` | Host kept, `XFP: wss` on websocket upgrades | Render, per a Render staff forum answer | [community.render.com](https://community.render.com/t/rails-actioncable-and-websockets/1153) (secondary, unverified on a live Render service) |
| `caddy-behind-edge` | Host kept, `XFP: http`, `XFH: host` | **docker-example/production** (Caddy on `:$PORT`, no `trusted_proxies`) behind Render/Heroku/Railway/Fly/ALB TLS. Caddy replaces the edge's untrusted `XFP: https` with its own `http`. Likewise Traefik/ingress-nginx behind an outer TLS LB with no trust configured | Caddy replacement behaviour as above; ingress-nginx behind TLS NLB [Camunda forum](https://forum.camunda.io/t/camunda-on-kubernetes-helm-ignores-x-forwarded-headers-behind-aws-nlb-with-ssl/57382) (secondary) |
| `appgw-override` | `Host: backend.azurewebsites...`, `XFP: https`, `X-Original-Host: host` | Azure Application Gateway with "override host name" (the usual App Service setup) | [Microsoft: App Gateway + App Service](https://learn.microsoft.com/en-us/azure/app-service/overview-app-gateway-integration), [host-name preservation](https://learn.microsoft.com/azure/architecture/best-practices/host-name-preservation) |
| `afd` | `Host: origin...` (rewritten), `XFP: https`, `XFH: host` | Azure Front Door with the default origin host header | Host rewrite by default [host-name preservation](https://learn.microsoft.com/azure/architecture/best-practices/host-name-preservation); XFH: unverified |
| not emulated | | Cloudflare Tunnel (cloudflared): Host stays the public hostname unless `httpHostHeader` is set ([CF origin parameters](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/origin-configuration), secondary snippet). With the default it behaves like `passthrough`/`xfp-https`; with `httpHostHeader: localhost:8000` it behaves like `nginx-default`. Reflex Cloud: managed, sets its own URLs; not testable here | |

## 3. Matrix: results (B = Chromium through the emulated front door, R = raw handshake with the same headers)

`a1` = 0.11.0a1; `a1+D` = 0.11.0a1 with `REFLEX_DEPLOY_URL=https://<public host>`; `fix` / `fix+D` = this branch. 101/count=2 = works,
403/count=0 = never connects. Public host `app.test:39xx` (non-default port; every profile keeps the port in Host the way `$http_host` does).
Evidence: `evidence/hs_before.txt`, `hs_after.txt`, `br_*.txt` and the per-run `*.json` files.

| Profile / scenario | 0.10.1 | 0.11.0a1 | a1+D | **fix** | fix+D |
|---|---|---|---|---|---|
| `passthrough` (L4 TLS, HAProxy/nginx without XFP) | B ok, R 101 | **B fail, R 403** | ok | **B ok, R 101** | ok |
| `nginx-default` (Host rewritten) | ok | **fail** | ok | **fail** (needs Host or deploy_url) | ok |
| `nginx-host-xfp` / ALB / GCP / Heroku / Fly / Cloudflare / DO | ok | ok | ok | ok | ok |
| `xfp-xfh` (Caddy/Traefik/ingress-nginx at the edge, Railway) | ok | ok | ok | ok | ok |
| `render-wss` (XFP `wss`) | ok | **fail** | ok | **ok** | ok |
| `caddy-behind-edge` (docker-example/production on Render/Heroku) | ok | **fail** | ok | **ok** | ok |
| `appgw-override` (Azure App Gateway host override) | ok | **fail** | ok | **fail** (needs deploy_url) | ok |
| `afd` (Azure Front Door) | ok | ok (via XFH) | ok | ok | ok |
| plain http behind a proxy that keeps Host | R 101 | R 101 | **R 403** | R 101 | **R 101** |
| split `--frontend-only` + `--backend-only` (docs recipe, B) | ok | fail | ok | **fail + actionable warning** | ok (B, `fix_split_dep`) |
| static export / CDN frontend + backend (R: `Host api`, `Origin https://app`) | 101 | 403 | 101 | 403 + warning | 101 |
| same host, other port (page :443, backend :8000) | 101 | 403 | 101 | 403 + warning | 101 |
| local `reflex run --env prod`, http://localhost:P and http://127.0.0.1:P (B) | ok | ok | **R 403** (deploy_url locks out direct access) | ok | **R 101** |
| `Origin http://127.0.0.1:P` to `Host localhost:P` (api_url names the other loopback) | 101 | 403 | 403 | 403 | 403 |
| attacker: cross-site `Origin https://evil.example` (+XFP https) | **101** | 403 | 403 | 403 | 403 |
| attacker: `Origin http://host` while XFP says https (downgraded page) | 101 | 403 | 403 | 403 | 403 |
| `Origin: null` | 101 | 403 | 403 | 403 | 403 |
| no Origin (non-browser client) | 101 | 101 | 101 | 101 | 101 |
| non-browser client forging `XFH: evil.example` + `XFP: https` + `Origin https://evil.example` | 101 | 101 | 403 | 101 | 101 |

The last row is not a browser attack: a page cannot set `X-Forwarded-Host` on a websocket handshake, and a non-browser client can
forge `Origin` anyway and carries no victim cookies. engine.io's own 0.11.0a1 default already accepts it. The fix keeps that parity
and, under fix+D, extends it to the deploy_url case.

## 4. True impact of 0.11.0a1 (without the fix)

**Breaks (regression vs 0.10.1, the websocket never connects, and the toast says "Cannot connect to server ... check if server is reachable"):**
1. Any same-origin prod app behind a TLS terminator that sends no `X-Forwarded-Proto`: L4/TLS-passthrough load balancers (AWS NLB TLS
   listener, ELB SSL listener, stunnel), HAProxy without an explicit XFP rule, and nginx configs that set Host but not XFP. The self-hosting
   guide promised "no api_url configuration at all" for this setup.
2. **The docs' "start here" container, `docker-example/production`, deployed on Render, Heroku, Railway, Fly or behind any TLS LB.**
   Caddy replaces the platform's `XFP: https` with `http`. This is reproduced with the emulated header profile, not with a real Caddy binary (the sandbox
   denied running it); Caddy's replace-untrusted behaviour is documented. The same applies to Traefik or ingress-nginx behind an outer TLS LB without trust configured.
3. Render, if its edge sends `XFP: wss` on upgrades as its staff stated (secondary source).
4. Any proxy that rewrites `Host` without sending `X-Forwarded-Host`: nginx `proxy_pass` without `proxy_set_header Host`, and Azure Application
   Gateway with host override. Plain http breaks too, not only TLS.
5. Every documented cross-origin layout: split `--frontend-only`/`--backend-only`, static export or CDN plus backend (self-hosting.md,
   scaling.md, app-platform-backend README), and a backend on another port of the same host.

**Unaffected:** front doors that keep Host and send `XFP: https`, which is the default on ALB, GCP LB, Heroku, Fly, Cloudflare proxy, DO,
Railway, Caddy/Traefik/ingress-nginx at the edge, and docker-example/production-compose. Also unaffected: Azure Front Door (XFH), local `reflex run --env prod`, and plain http
behind a proxy that keeps Host.

**Gotcha in 0.11.0a1's own workaround:** setting `REFLEX_DEPLOY_URL` makes the websocket accept *only* that origin, so direct access
(`http://localhost:3000`, an internal IP, a second hostname) stops working (`a1+D` rows above).

**reflex-enterprise (FINDING-002):** rxe's MCP `resolve_server_url()` reads `config.deploy_url`. No zero-config origin rule can help it:
the OAuth issuer must be a configured public URL. It still needs `REFLEX_DEPLOY_URL` (or `MCPPlugin(issuer_url=...)` / the rxe
fix). With this branch, setting `REFLEX_DEPLOY_URL` is safe for those users, because it no longer locks out the backend's own origin.

## 5. Design chosen

**a. Reflex's own origin check for engine.io** (`reflex/app.py: _SocketOriginCheck`, `_origin_matches_request`, `_host_authority`,
`_socket_cors_allowed_origins`). It is used for the websocket transport whenever the resolved origins are not `*`:
- Prod default (no explicit `cors_allowed_origins`): accept `deploy_url`'s origin (if set) **plus** the request's own origin.
  The request's own origin is an `Origin` of the form `scheme://host[:port]` (http/https only, no userinfo or path) whose lowercase host and
  port (the scheme's default port when omitted) equal those of `Host` or of `X-Forwarded-Host` (first value). This applies **except** when the
  Origin is `http` and `X-Forwarded-Proto` says `https`/`wss`.
- Explicit list: used exactly. `*` (dev default or explicit): passed through unchanged.
- First rejection per worker: one WARNING naming the rejected origin, the `Host`/`X-Forwarded-Host` the backend saw and
  `REFLEX_DEPLOY_URL=<origin>` (or, for explicit lists, `cors_allowed_origins`). See `evidence/fix_split_backend_warning.txt`.

**Security argument (CSWSH / credentialed cross-origin reads).** In this threat model the attacker is a page in the victim's browser.
- `Origin` is set by the browser and cannot be forged by the page. `Host` is the host the browser actually connects to. A page cannot
  add headers to a WebSocket handshake, so it cannot set `X-Forwarded-Host` or `X-Forwarded-Proto` either. A polling or `fetch` request with such
  a custom header is preflighted, and the preflight carries no such header.
- Compared with engine.io's own default (0.11.0a1), the only origin added is **`https://<the host the browser connected to>`** on requests the
  proxy did not mark as https. Only the holder of that host's certificate can serve a page at that origin, which in practice is the site
  itself. `http://host` was already accepted by engine.io on such requests. The fix keeps it (local prod, plain-http proxies) and
  *removes* it where a proxy reports https (a downgraded or MITM'd http page). So the fix accepts nothing an attacker can control that
  0.11.0a1 rejects, and `X-Forwarded-Proto` can only narrow the decision.
- Host/port equality is exact, so `https://h:8443` is not `h`, sibling subdomains are not accepted, and `Origin: null` (sandboxed
  iframes, file:) and non-http schemes (extensions) are rejected. Malformed hosts/ports are rejected without raising (a `TypeError` would
  make engine.io retry the one-argument form).
- Same-origin checks do not stop DNS rebinding (an attacker's page whose own name resolves to the server). That was also true of
  engine.io's default and of 0.10.1, and it involves the attacker's own cookies, not the victim's. A `Host` allowlist would be the remedy;
  that is out of scope here.
- Adding the backend's own origin when `deploy_url` is set is safe for the same reason: same-origin is the case CORS never restricts.

**b. Rejected options**
- *Revert to `["*"]`*: defeats #7641 (any site could drive a victim's session with their cookies).
- *Ignore the scheme entirely*: would also accept `http://host` when the proxy says https. That is a needless widening beyond engine.io
  for an active-network attacker; the asymmetric rule costs one line.
- *Honour `X-Forwarded-Host`/`Forwarded` only from configured trusted proxies* (e.g. tie it to `trusted_proxy_hops`): not needed for
  the browser threat model (see above). It would also regress the Azure Front Door case, which works on 0.11.0a1 through engine.io's unconditional XFH.
  `Forwarded` and `X-Original-Host` are not read: no common default needs them; App Gateway users set deploy_url.
- *Trust `scope["scheme"]` / granian proxy headers*: engine.io ignores the scope scheme, and granian's wrapper is opt-in. The rule
  does not need the scheme anyway.
- *Same-site acceptance* (`app.example.com` accepting `cdn.example.com`): would accept every sibling subdomain, including user content.
  A split deployment cannot be identified safely without configuration, so it still needs `REFLEX_DEPLOY_URL`.
- *Startup WARNING for `--backend-only` without deploy_url/cors*: both docker examples (production and production-compose) run
  `--backend-only` *same-origin* behind Caddy, so the warning would fire on the recommended correct setups. The rejection-time warning
  fires exactly when a wrong origin shows up.

**c. HTTP CORS layer left as is**: browsers do not apply CORS to same-origin requests, so the backend never has to identify its own
origin for HTTP. With deploy_url set, `CORSMiddleware` already allows that origin. Websocket and HTTP now agree on "browser-same-origin
+ deploy_url", with one exception: behind a Host-rewriting proxy, HTTP works but the websocket cannot recognise the host, and the
warning says so. Uploads were not driven end to end in this engagement; that part rests on the reasoning above.

## 6. Before / after (fix branch, same scripts)

- Chromium through every profile: see `evidence/br_fix.txt`, `br_fixdep.txt`. The fix turns `passthrough`, `render-wss` and
  `caddy-behind-edge` from count=0 into count=2 with zero config. `nginx-default` and `appgw-override` still need Host forwarding or deploy_url,
  and with `REFLEX_DEPLOY_URL` every profile works.
- Local prod (`fix_local_localhost`, `fix_local_127.0.0.1`, and `a1_local_*` for comparison): ok.
- Split docs recipe without deploy_url: still 403 by design, now with the warning; with backend `REFLEX_DEPLOY_URL=http://localhost:3909`: count=2.
- Unit tests: 9 regression cases fail on the unfixed `reflex/app.py` (`evidence/tests_before.txt`) and pass after (`tests_after.txt`).

## 7. What still needs configuration (documented by the branch)

`REFLEX_DEPLOY_URL=<frontend public URL, scheme included>` on the **backend** is required for: split frontend/backend, static
export/CDN, a backend on a different port or host, a proxy that rewrites `Host` (nginx without `proxy_set_header Host $http_host;`, Azure
App Gateway host override), and reflex-enterprise MCP. Several origins: `REFLEX_CORS_ALLOWED_ORIGINS`. Docs updated:
`docs/hosting/self-hosting.md` (split commands, reverse-proxy note, API URL, static export), `docs/hosting/scaling.md`,
`docs/advanced_onboarding/configuration.md`, `docker-example/app-platform-backend/README.md`, `docker-example/production/README.md`,
and the unreleased `news/+cors-prod-default.breaking.md` (now carries the upgrade note).

Not changed: the frontend toast text (FINDING-023's optional "reachable but refused" ping); engine.io still prints its own terse ERROR
line next to the Reflex warning; and the debug Config dump still shows the configured `('*',)`, although the warning now states the effective rule
when it matters.
