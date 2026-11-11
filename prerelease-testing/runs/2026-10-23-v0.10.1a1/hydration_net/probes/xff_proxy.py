"""Forwarding proxy that behaves like a real reverse proxy for X-Forwarded-For.

Usage: xff_proxy.py LISTEN_PORT TARGET_PORT [--bind 127.0.0.2] [--mode append|line|none] [--add 'Name: value']...

For every request head (incl. the websocket upgrade) it appends the connecting peer's address to X-Forwarded-For:
  append (nginx $proxy_add_x_forwarded_for): all incoming XFF lines joined with ", " + ", <peer>" in ONE line
  line:  keeps the incoming XFF lines as they are and ADDS a new `X-Forwarded-For: <peer>` line
  none:  passes headers through untouched (a proxy that does not set XFF at all)
It connects to the backend from --bind (default 127.0.0.2) so the backend's peer address is the proxy's, not the
client's. --add injects extra raw header lines. Prints stats every 10 s.
"""

import argparse
import asyncio
import os

import playwright  # noqa: F401  venv guard

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__

ap = argparse.ArgumentParser()
ap.add_argument("listen", type=int)
ap.add_argument("target", type=int)
ap.add_argument("--bind", default="127.0.0.2")
ap.add_argument("--mode", default="append", choices=["append", "line", "none"])
ap.add_argument("--add", action="append", default=[])
A = ap.parse_args()
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


def rewrite(head: bytes, peer: str) -> tuple[bytes, bool]:
    lines = head.split(b"\r\n")
    out = [lines[0]]
    xff = []
    upgrade = False
    cl = 0
    for ln in lines[1:]:
        k, _, v = ln.partition(b":")
        kl = k.strip().lower()
        if kl == b"upgrade" and v.strip().lower() == b"websocket":
            upgrade = True
        if kl == b"content-length":
            cl = int(v.strip() or 0)
        if kl == b"x-forwarded-for" and A.mode == "append":
            xff.append(v.strip())
            continue
        out.append(ln)
    if A.mode == "append":
        out.append(b"X-Forwarded-For: " + b", ".join([*xff, peer.encode()]))
    elif A.mode == "line":
        out.append(b"X-Forwarded-For: " + peer.encode())
    for h in A.add:
        out.append(h.encode())
    return b"\r\n".join(out) + b"\r\n\r\n", upgrade, cl


async def c2s(r, w, peer):
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
            new_head, upgrade, cl = rewrite(head, peer)
            w.write(new_head)
            STATS["heads"] += 1
            if upgrade:
                STATS["upgrades"] += 1
                w.write(buf)
                await w.drain()
                await pipe(r, w)
                return
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
    peer = cw.get_extra_info("peername")[0]
    try:
        sr, sw = await asyncio.open_connection("127.0.0.1", A.target, local_addr=(A.bind, 0))
    except Exception as e:  # noqa: BLE001
        print("backend connect failed", repr(e), flush=True)
        cw.close()
        return
    await asyncio.gather(c2s(cr, sw, peer), pipe(sr, cw))


async def main():
    srv = await asyncio.start_server(handle, "127.0.0.1", A.listen)
    print(f"xff_proxy {A.listen} -> {A.target} from {A.bind} mode={A.mode} add={A.add}", flush=True)
    async with srv:
        while True:
            await asyncio.sleep(10)
            print("stats", STATS, flush=True)


asyncio.run(main())
