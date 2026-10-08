"""Tiny forwarding proxy that injects credential headers into every HTTP request head (incl. the websocket upgrade).

Usage: hdr_proxy.py LISTEN_PORT TARGET_PORT
Simulates an auth proxy (Cloudflare Access / oauth2-proxy / AWS ALB / Google IAP / Basic auth) in front of a Reflex
backend: the browser connects to LISTEN_PORT, the proxy adds the headers below and forwards to TARGET_PORT.
"""

import asyncio
import sys

import playwright  # noqa: F401  (guard: run with the driver venv)

assert "/envs/driver/" in playwright.__file__, playwright.__file__

INJECT = {
    "Authorization": "Bearer AUTHSECRET41c",
    "Proxy-Authorization": "Basic PROXYAUTHSECRET5d",
    "Cf-Access-Jwt-Assertion": "CFJWTSECRET88b",
    "X-Forwarded-Access-Token": "XFATSECRET2e0",
    "X-Auth-Request-Access-Token": "XARATSECRET6b2",
    "X-Amzn-Oidc-Accesstoken": "AMZNSECRET3c9",
    "X-Amzn-Oidc-Data": "AMZNDATASECRET1f",
    "X-Goog-Iap-Jwt-Assertion": "IAPSECRET77e",
}
LISTEN, TARGET = int(sys.argv[1]), int(sys.argv[2])
STATS = {"conns": 0, "heads": 0, "upgrades": 0}


async def pipe(r, w):
    try:
        while chunk := await r.read(65536):
            w.write(chunk)
            await w.drain()
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            w.close()
        except Exception:  # noqa: BLE001
            pass


async def c2s(r, w):
    buf = b""
    try:
        while True:
            while b"\r\n\r\n" not in buf:
                chunk = await r.read(65536)
                if not chunk:
                    w.close()
                    return
                buf += chunk
            head, buf = buf.split(b"\r\n\r\n", 1)
            lines = head.split(b"\r\n")
            hdrs = {}
            for ln in lines[1:]:
                k, _, v = ln.partition(b":")
                hdrs[k.strip().lower()] = v.strip()
            lines += [f"{k}: {v}".encode() for k, v in INJECT.items()]
            w.write(b"\r\n".join(lines) + b"\r\n\r\n")
            STATS["heads"] += 1
            if hdrs.get(b"upgrade", b"").lower() == b"websocket":
                STATS["upgrades"] += 1
                w.write(buf)
                await w.drain()
                await pipe(r, w)
                return
            cl = int(hdrs.get(b"content-length", b"0") or 0)
            while len(buf) < cl:
                chunk = await r.read(65536)
                if not chunk:
                    break
                buf += chunk
            w.write(buf[:cl])
            buf = buf[cl:]
            await w.drain()
    except Exception:  # noqa: BLE001
        try:
            w.close()
        except Exception:  # noqa: BLE001
            pass


async def handle(cr, cw):
    STATS["conns"] += 1
    try:
        sr, sw = await asyncio.open_connection("127.0.0.1", TARGET)
    except Exception:  # noqa: BLE001
        cw.close()
        return
    await asyncio.gather(c2s(cr, sw), pipe(sr, cw))


async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    print(f"hdr_proxy {LISTEN} -> {TARGET}", flush=True)
    async with srv:
        while True:
            await asyncio.sleep(10)
            print("stats", STATS, flush=True)


asyncio.run(main())
