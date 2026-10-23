# hydration_net — reflex 0.10.1a1 pre-release pass (2026-10-23)

Item: HYD-01/02/08/09 re-verification, #7360 credential exposure, C21, and the hunt over #7614 (client_ip /
trusted_proxy_hops), #7588 / #7602 (repeated and non-UTF-8 headers), #7551 / #7605 (oversized hydrate, backoff),
#7545 / #7568 / #7603 / #7572 (storage sync / cached dependents / storage annotations / override dependents),
#7407 (global client_state late readers).

Everything ran from `$SB/apps/hydration_net/` with PUBLISHED packages only:
- `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`
- venvs: `new` = reflex 0.10.1a1 / reflex-base 0.10.1a1 (granian 2.8.5), `prev` = 0.10.0, `driver` = playwright 1.64.1 +
  websockets 17.3 + httpx; positive controls built here from PyPI: `hydration_net-0.10.0a1` (F-002/F-003),
  `hydration_net-0.10.0a3` (A3-11/A3-12 storms), `hydration_net-0.10.0a4` (#7360 leaks).
  `cd $SB && uv --no-config venv --python 3.12 $SB/envs/hydration_net-<v> && uv --no-config pip install --python
  $SB/envs/hydration_net-<v>/bin/python --prerelease=allow "reflex[db]==<v>" "reflex-base==<v>" 'pydantic<2.15'`
- fixture copy: `cp -r prerelease-testing/fixtures/hydration $SB/apps/hydration_net/src` (`F=$SB/apps/hydration_net/src`)
- my app + probes (copied here): `hnet/` (app), `probes/` (`hnet_drive.py`, `ws_probe.py`, `xff_proxy.py`,
  `close_proxy.py`), `run_hnet.sh` (how each leg was started).
- ports 3140-3159 / 8140-8159 only; one app server set at a time.

## 1. Re-verification with `run_area.sh quick` (positive controls first)

```
export SB=... WORK=$SB/apps/hydration_net NEW=new PREV=prev \
  CTRL_F002=hydration_net-0.10.0a1 CTRL_STORM=hydration_net-0.10.0a3 CTRL_RTR=hydration_net-0.10.0a4
$WORK/src/scripts/run_area.sh quick > $WORK/area_quick.txt 2>&1     # trimmed copy: area_quick.txt
```

| leg | control (must fail) | new (0.10.1a1) | verdict |
|---|---|---|---|
| probe `cs_storage_default_probe.py` | — | `assign_*` #7516 TypeError, `field_plain`/`field_none` ordinary, `field_storage` LocalStorage `box_pref_dark` | = 0.10.0 |
| HYD-01 / F-002 `run_f002.sh <v> prod ... 3140 3140` | 0.10.0a1: fresh profile's localStorage holds `cu_ls, wt_ls, wu_ls, wu_sync` (+ SS, cookies) after the first load; v2 returning visitor keeps `wu-light` (stale default) | fresh x2 and same-build returning: localStorage only `theme=system`; v2 returning + fresh show `*-dark-v2` / `wu-sync-v2`; sync tabs converge on `sync-from-tabA` | **fixed, unchanged vs 0.10.0** |
| HYD-02 / F-003 `run_cv.sh <v> dev ... 3142 8142 <vars> PYTHONHASHSEED=4` | 0.10.0a1 a/b/g: `reload [l='bad']` (browser keeps the bad token through reload/probe/noop) | `CVSTORE MATCHES cvstore_dev.summary.txt` (a–j, 0-byte diff vs the 0.10.0 expected file; b keeps N-016) | **fixed, unchanged** |
| HYD-08 / A3-11 `run_storm.sh <v> dev 3 3142 8142 S 6` | 0.10.0a3 Part S: **0/3 storms on this box** (README recorded 3/4 on a quieter machine — Part S is timing dependent; see the Part R control below) | 0/3 storms, 59–65 frames, 0 in the quiet window, all 7 tabs + localStorage `s5` | pass (control via Part R) |
| HYD-09 / A3-12 `run_stamp2.sh <v> dev 3142 8142 2 1 6` | 0.10.0a3: run 1 **storm** (1,108,630 frames, 306k/299k per 5 s window, tabs split `36382b-1`/`2a91e1-1`); run 2 quiet (timing) | 0/2 storms, 87 frames each, 0 per 5 s afterwards, all 6 tabs on one slug; `/same` quiet (48 frames); compiled `state.js` md5 `de8ccd2b` (0.10.0: `b7915eda` — the template changed: #7545/#7551/#7605/#7435/#7553) | **fixed** |
| #7360 / ENT-16 / DOC-14 `run_rtr.sh <v> dev <label> 3142 8142 8143` (hdr_proxy injects 8 credential headers + plain and HttpOnly cookie; scans every websocket frame, document, DOM, console) | 0.10.0a4: **all 10 secrets leak**: 20–21 inbound frames each, 1–2 outbound, present in the `/front` DOM (`front_html_has` all True), `recv_cookie` arg carries `rtr_plain=PLAINSECRET7a1; rtr_httponly=H…` | **0 secrets** in received / sent frames, documents, DOM, console (258 in / 111 out frames, 34 sockets, 18 proxied upgrades); `headers.cookie` renders `""`, `recv_cookie` arg `""`; backend handlers still see cookies + auth headers; `cmp_rtr.py ctrl-dev new-dev`: `steps A=37 B=37 log/url diffs=0`, reconnect identical; console only the favicon 404 | **holds** (= 0.10.0) |

`area_quick.txt` exit 0 (14.5 min). Area results: `results/area/*.txt`, `results/{f002,f003,sync,stamp,rtr}/`.

## 2. Hunt: the `hnet` app (`hnet/`), driver `probes/hnet_drive.py`, runner `legs.sh`

`hnet` pages: `/ip` (#7614 + headers), `/big` (#7551/#7605), `/shared` (#7545), `/cv` (#7568), `/typed` (#7603),
`/ovr` (#7572), `/cs` + `/gate` (#7407); `/whoami` is a plain Starlette route (`api_transformer`) returning
`request.client` and `X-Forwarded-For`. `rxconfig.py` maps `HNET_HOPS` to `trusted_proxy_hops`.
Rerun one leg: `export SB=... WORK=$SB/apps/hydration_net; cd $WORK && ./legs.sh <leg>` (legs listed in `legs.sh`;
outputs in `results/hnet/`, copied here under `hnet_results/`).

### 2.1 Leg `dev_h0` (new, dev 3142/8142, `trusted_proxy_hops` default 0, browser websocket via `xff_proxy.py` 8143)
`legs.sh dev_h0` -> `hnet_results/dev-h0.scen.txt`, `dev-h0.ip.txt`, `dev-h0.whoami.txt`, `dev-h0.server.log`.

| check | result |
|---|---|
| `/ip` in the browser through the proxy (the proxy connects from 127.0.0.2 and appends the browser's 127.0.0.1 to XFF) | frontend `router.session.client_ip` = **127.0.0.2** (the proxy, i.e. the connection peer); computed var, `on_load`, click and **upload** handlers all record `ip=127.0.0.2`, `x-forwarded-for=127.0.0.1`, `asgi-scope-client=127.0.0.2` — XFF ignored with hops=0, consistent on every path |
| `/whoami` (HTTP API route, user code) direct / via proxy with spoofed `X-Forwarded-For: 6.6.6.6` | `client=127.0.0.1, xff=null` / `client=127.0.0.2, xff="6.6.6.6, 127.0.0.1"`: reflex does not touch XFF on HTTP routes (user code decides) |
| #7551/#7605 `big`: 300k LocalStorage | roundtrip ok, reload hydrates in 0.42 s |
| #7551 `big`: 1.1 MB LocalStorage, reload, observe 12 s | **one** console error `Hydration payload (1100569 characters) exceeds the server limit (1000000 characters). Reduce browser storage data and reload.`; toast with that text at 0.4 s and still there at 12 s; **1 websocket open, 0 CONNECT frames sent**, `is_hydrated` stays false; after shrinking storage + reload: hydrates, 1 open, toast gone, click works (screenshot `hnet_results/big_oversize.png`). 0.10.0 (F-008): 600+ opens / 22 s, never hydrates, no error — **fixed** |
| #7545 `shared`: ComponentState `Pref` used twice + `Plain.shared`, all `sync=True` on storage name `hnet_shared`, two tabs | every write in tab A (button in instance a, button in the plain state, typed input in instance b) makes **all three** vars converge in tab B (`from-a`/`from-plain`/`typed-b`), localStorage holds the value, a third tab boots with all three equal, 0 frames in the 2 s quiet window (30 frames total), `hnet_other` unaffected. In the **writing** tab only the var that was written changes (no `storage` event fires in the writing tab) — see the prev comparison |
| #7568 `cv`: cached `Store.tok_len` (same state) and async cached `Sib.sib_len` (sibling, via `get_state`) over `LocalStorage`+`Cookie`; eval counters reset, reload, snapshot | `tok_len` evaluated **1**x per load, `sib_len` **1**x (uncached var 4x); values right (`tok_len:8`, `sib_len:6`); twice |
| #7603 `typed`: `ann_ls: rx.LocalStorage`, `ann_ck: rx.Cookie`, `ann_ss: rx.SessionStorage`, `ann_opt: rx.LocalStorage \| None`, `ann_fld: rx.Field[rx.LocalStorage]` | defaults shown, writes reach storage (`hnet_ann_ls=ls-w1`, cookie `hnet_ann_ck=ck-w1`, sessionStorage `hnet_ann_ss=ss-w1`), reload hydrates all five as plain `str` values; **no** `Expected field 'Typed.ann_*'` line in the server log, browser console clean; `ann_opt = None` writes the string `null` to localStorage and hydrates back as the string `"null"` (pre-existing shape, info) |
| `typed` non-str storage vars `n_int: int = rx.LocalStorage("3")`, `n_bool: bool = rx.Cookie("true")`, `j_dict: dict = rx.LocalStorage('{"a": 1}')` | server log: `Expected field 'Typed.n_int' to receive type int, but got '3' of type LocalStorage` (+ bool, dict) **41x each in one leg** (every state instantiation), plus `got '2' of type str` at every hydrate; after a write the dict is stored as `[object Object]`; after reload all three hydrate as **strings** (`"2"`, `"true"`, `"[object Object]"`). Compared with 0.10.0 below |
| #7572 `ovr`: `get_delta` override (`@rx.state._override_base_method`) that assigns `self.tok = ""` + `self.plain = "sanitised"` for a non-`good-` token before `super().get_delta()` | stored `bad-x` + reload: `tok_ok` (cached dependent) = `ok:False:`, `plain_dep` = `plain:sanitised`, `tok` = `[]`, localStorage corrected to `""`; same after another reload and through an event |
| #7407 `cs` / `gate`: global `rx._x.client_state` readers behind `rx.cond` / behind `is_hydrated`; `on_load` pushes before any reader mounts | no `_client_state_set... is not a function` error; late reader shows `pushed-on-load` and `count=5`; set `clicked` -> hide -> show -> set default: reader shows `initial`; `push(None)` -> `[]`; backend push -> `from-backend`; gate page reader gets the on_load push |

### 2.2 #7614 / #7588 / #7602 — raw websocket header matrix (`xff_matrix.sh` over `probes/ws_probe.py`)
`ws_probe.py` hand-rolls the HTTP upgrade (raw header bytes, duplicates, non-UTF-8) and the socket.io CONNECT with
reflex's hydrate event, then sends `IPState.rec(tag)` and reads back the handler's `router_snap` (client_ip, raw
headers). "direct" = probe -> backend (peer 127.0.0.1); "via proxy" = probe bound to 127.0.0.3 -> `xff_proxy.py`
(appends the peer to XFF like nginx `$proxy_add_x_forwarded_for`, connects out from 127.0.0.2) -> backend.
Full tables: `hnet_results/<leg>.matrix.txt`; per-case JSON (every frame) in `$WORK/results/xff/<leg>/`.

**hops = 0 (default), leg `dev_h0m`** — every case resolves to the connection peer: direct `ip=127.0.0.1`, via proxy
`ip=127.0.0.2` (the proxy), regardless of `X-Forwarded-For: 6.6.6.6`, chains, two XFF lines, whitespace/garbage,
IPv6, `[v6]:port`, `X-Real-IP`, `Forwarded:`; `asgi-scope-client` always = the peer.
- #7588: two `Cookie` lines (`a=1` / `b=2; c=3`) -> `router.headers.cookie` = `a=1; b=2; c=3` (both `.cookie` and
  `raw_headers["cookie"]`); two `X-Dup` lines -> `one, two`; two XFF lines -> `6.6.6.6, 7.7.7.7`.
- #7602: `X-Bad: \xff\xfe\x80` -> `ÿþ` (latin-1), `Cookie: a=\xe9` + `Cookie: z=9` -> `z=9; a=é`, non-UTF-8 XFF
  line -> `7.7.7.7, éè`: connection accepted, handler runs, nothing in the server log. A non-UTF-8 header **name**
  (`X-N\xe9me`, and the UTF-8 `X-Néme`) is refused by granian with **HTTP 400** before reflex sees it (not a reflex
  path; same on 0.10.0).
- `X-Forwarded-For:` with an empty value is dropped by the server (header absent in `raw_headers`).
- d12: three cookie secrets + `Authorization` reach the backend handler (`cookie_attr` has all three) — the frontend
  side of this is the #7360 rtr run above (0 secrets in frames/DOM).

**hops = 1 (`HNET_HOPS=1`), leg `dev_h1`** — via the proxy every spoof resolves to the real client **127.0.0.3**
(`6.6.6.6, 127.0.0.3`, `6.6.6.6, 7.7.7.7, 127.0.0.3`, two spoofed lines + the proxy's line, IPv6 spoof, `X-Real-IP`
ignored); the browser through the proxy shows `client_ip=127.0.0.1` (its real address at the proxy) on the
frontend, in the computed var and in on_load / click / upload handlers. **Direct** connections with hops=1 are the
documented footgun: `X-Forwarded-For: 6.6.6.6` -> `ip=6.6.6.6`, chain -> rightmost `7.7.7.7`, and
`X-Forwarded-For: not an ip!! <script>` -> `client_ip="not an ip!! <script>"` (no syntactic validation of the
entry; 0.10.0 took the leftmost entry with the same lack of validation).
**hops = 2 behind ONE proxy, leg `dev_h2`** (over-configured) — `6.6.6.6, 127.0.0.3` -> `ip=6.6.6.6`: the client
controls the result (as the docs warn: set hops to the real number of proxies); a chain shorter than hops
(`127.0.0.3` alone) falls back to the connection peer `127.0.0.2` (the proxy), never to the forwarded entry.
**Separate XFF lines (`xff_proxy.py --mode line`), hops=1, leg `dev_line`** — the proxy adds its own
`X-Forwarded-For: 127.0.0.3` line after the client's spoofed line(s); #7588 joins them in order and hops=1 takes the
rightmost -> `127.0.0.3` in every case.

