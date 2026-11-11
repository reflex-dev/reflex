"""Header-profile reverse proxy emulating what a front door sends upstream.

usage: hproxy.py <listen_port> <upstream_port> <profile> [cert key]
One request per upstream connection (Connection: close is forced on non-upgrade
requests), so every request head is rewritten. With cert/key it terminates TLS.
"""
import asyncio, ssl, sys

LP, UP, PROFILE = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
CERT = sys.argv[4:6]
UPSTREAM_HOST = f"127.0.0.1:{UP}"

# name -> function(host) -> (new_host, extra_headers); every profile first strips
# client-sent X-Forwarded-*/Forwarded/X-Original-Host (as overwriting proxies do).
def prof(host, upgrade):
    p = PROFILE
    if p == "passthrough":           # L4 TLS (stunnel, NLB/ELB TLS listener, HAProxy mode tcp)
        return host, []
    if p == "nginx-default":         # proxy_pass, no proxy_set_header: Host $proxy_host
        return UPSTREAM_HOST, []
    if p == "nginx-host":            # proxy_set_header Host $http_host; no XFP
        return host, []
    if p == "nginx-host-xfp":        # + proxy_set_header X-Forwarded-Proto $scheme
        return host, [("X-Forwarded-Proto", "https")]
    if p == "xfp-https":             # ALB, GCP LB, Heroku, Fly, Cloudflare (full/strict), DO, Render (http)
        return host, [("X-Forwarded-Proto", "https")]
    if p == "xfp-xfh":               # Caddy/Traefik/ingress-nginx at the edge, Railway
        return host, [("X-Forwarded-Proto", "https"), ("X-Forwarded-Host", host)]
    if p == "render-wss":            # XFP wss on websocket upgrades (Render staff, community.render.com)
        return host, [("X-Forwarded-Proto", "wss" if upgrade else "https")]
    if p == "caddy-behind-edge":     # docker-example/production behind a TLS edge: Caddy replaces untrusted XFP
        return host, [("X-Forwarded-Proto", "http"), ("X-Forwarded-Host", host)]
    if p == "appgw-override":        # Azure App Gateway host override to backend name
        return "backend.azurewebsites.test", [("X-Forwarded-Proto", "https"), ("X-Original-Host", host)]
    if p == "afd":                   # Azure Front Door: origin host header = origin name, XFH = original
        return "origin.azurewebsites.test", [("X-Forwarded-Proto", "https"), ("X-Forwarded-Host", host)]
    raise SystemExit(f"unknown profile {p}")

STRIP = {b"x-forwarded-proto", b"x-forwarded-host", b"forwarded", b"x-original-host", b"connection", b"host"}

async def pipe(r, w):
    try:
        while data := await r.read(65536):
            w.write(data); await w.drain()
    except Exception:
        pass
    finally:
        try: w.close()
        except Exception: pass

async def handle(cr, cw):
    try:
        head = await cr.readuntil(b"\r\n\r\n")
    except Exception:
        cw.close(); return
    lines = head[:-4].split(b"\r\n")
    reqline, hdrs = lines[0], [l.split(b":", 1) for l in lines[1:] if b":" in l]
    get = lambda n: next((v.strip() for k, v in hdrs if k.strip().lower() == n), b"")
    host = get(b"host").decode()
    conn = get(b"connection")
    upgrade = b"upgrade" in conn.lower()
    new_host, extra = prof(host, upgrade)
    out = [reqline, b"Host: " + new_host.encode()]
    out += [k + b":" + v for k, v in hdrs if k.strip().lower() not in STRIP]
    out += [f"{k}: {v}".encode() for k, v in extra]
    out.append(b"Connection: " + (conn if upgrade else b"close"))
    ur, uw = await asyncio.open_connection("127.0.0.1", UP)
    uw.write(b"\r\n".join(out) + b"\r\n\r\n"); await uw.drain()
    await asyncio.gather(pipe(cr, uw), pipe(ur, cw))

async def main():
    ctx = None
    if CERT:
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH); ctx.load_cert_chain(*CERT)
    srv = await asyncio.start_server(handle, "127.0.0.1", LP, ssl=ctx)
    print("hproxy", PROFILE, LP, "->", UP, flush=True)
    async with srv:
        await srv.serve_forever()

asyncio.run(main())
