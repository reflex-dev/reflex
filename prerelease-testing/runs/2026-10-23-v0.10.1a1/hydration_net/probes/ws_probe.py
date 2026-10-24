"""Raw Engine.IO v4 / Socket.IO websocket client for a reflex backend, with arbitrary RAW header bytes.

Hand-rolls the HTTP upgrade (so duplicate header lines, non-UTF-8 bytes, odd whitespace all go on the wire exactly
as given) and the websocket framing. Sends the socket.io CONNECT with reflex's hydrate event in `auth`, then one
`IPState.rec(tag)` event of the hnet app, collects deltas and prints the router snapshot the handler recorded.

Usage:
  ws_probe.py --port BP [--host 127.0.0.1] [--local-addr 127.0.0.3] [--hdr 'Name: value']... [--hdr-hex 'name:hex']...
              [--tag ws] [--path /ip] [--state-schema HASH] [--version 0.10.1a1] [--wait 2.5] [--out out.json]
  --hdr adds one raw header line (repeat for duplicates); --hdr-hex adds `name: <bytes from hex>`.
"""

import argparse
import asyncio
import base64
import json
import os
import struct
import sys
import time
import uuid

import playwright  # noqa: F401  venv guard

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__

STATE = "reflex___state____state"
# IPState.get_full_name() on both 0.10.0 and 0.10.1a1 (checked with an import of the app)
IPSTATE = f"{STATE}.hnet___hnet___ip_state"


def ws_frame(payload: bytes, opcode: int = 1) -> bytes:
    mask = os.urandom(4)
    n = len(payload)
    if n < 126:
        hdr = bytes([0x80 | opcode, 0x80 | n])
    elif n < 65536:
        hdr = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", n)
    else:
        hdr = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", n)
    return hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


async def read_frame(r):
    b1, b2 = await r.readexactly(2)
    opcode = b1 & 0x0F
    n = b2 & 0x7F
    if n == 126:
        n = struct.unpack(">H", await r.readexactly(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", await r.readexactly(8))[0]
    mask = await r.readexactly(4) if b2 & 0x80 else None
    data = await r.readexactly(n)
    if mask:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--local-addr", default=None)
    ap.add_argument("--hdr", action="append", default=[])
    ap.add_argument("--hdr-hex", action="append", default=[])
    ap.add_argument("--line-hex", action="append", default=[], help="a whole raw header line as hex (name bytes too)")
    ap.add_argument("--tag", default="ws")
    ap.add_argument("--path", default="/ip")
    ap.add_argument("--state-schema", default=None)
    ap.add_argument("--version", default="0.10.1a1")
    ap.add_argument("--wait", type=float, default=2.5)
    ap.add_argument("--token", default=None)
    ap.add_argument("--no-hydrate", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    out = {"args": sys.argv[1:], "frames_in": [], "seen": [], "errors": []}
    tok = a.token or str(uuid.uuid4())
    out["token"] = tok
    kw = {"local_addr": (a.local_addr, 0)} if a.local_addr else {}
    try:
        r, w = await asyncio.open_connection(a.host, a.port, **kw)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"connect: {e!r}")
        return finish(out, a)
    out["local"] = list(w.get_extra_info("sockname"))
    key = base64.b64encode(os.urandom(16)).decode()
    lines = [
        f"GET /_event/?EIO=4&transport=websocket&token={tok} HTTP/1.1".encode(),
        f"Host: {a.host}:{a.port}".encode(),
        b"Upgrade: websocket",
        b"Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}".encode(),
        b"Sec-WebSocket-Version: 13",
        f"Sec-WebSocket-Protocol: {a.version}".encode(),
        f"Origin: http://localhost:{a.port}".encode(),
        b"User-Agent: ws_probe/1",
    ]
    for h in a.hdr:
        lines.append(h.encode("utf-8"))
    for h in a.hdr_hex:
        name, _, hx = h.partition(":")
        lines.append(name.encode() + b": " + bytes.fromhex(hx))
    for hx in a.line_hex:
        lines.append(bytes.fromhex(hx))
    w.write(b"\r\n".join(lines) + b"\r\n\r\n")
    await w.drain()
    try:
        head = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), 10)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"upgrade read: {e!r}")
        return finish(out, a)
    status = head.split(b"\r\n", 1)[0].decode("latin-1")
    out["upgrade_status"] = status
    if " 101 " not in status:
        try:
            body = await asyncio.wait_for(r.read(4096), 2)
        except Exception:  # noqa: BLE001
            body = b""
        out["upgrade_head"] = head.decode("latin-1")[:1200]
        out["upgrade_body"] = body.decode("latin-1")[:800]
        return finish(out, a)

    async def recv_loop():
        try:
            while True:
                opcode, data = await read_frame(r)
                if opcode == 8:
                    out["frames_in"].append(f"CLOSE {data[:2].hex()} {data[2:].decode('latin-1')[:200]}")
                    return
                if opcode == 9:
                    w.write(ws_frame(data, 10))
                    continue
                txt = data.decode("utf-8", "replace")
                out["frames_in"].append(txt[:600])
                if txt == "2":
                    w.write(ws_frame(b"3"))
                    await w.drain()
                elif txt.startswith("0{"):
                    out["open"] = json.loads(txt[1:])
                elif txt.startswith("42/_event,"):
                    try:
                        ev = json.loads(txt[len("42/_event,") :])
                        delta = ev[1].get("delta", {}) if isinstance(ev[1], dict) else {}
                        for st, fields in delta.items():
                            if st == IPSTATE:
                                # delta keys carry the field marker suffix (e.g. "seen_rx_state_")
                                for k, v in fields.items():
                                    if k.split("_rx_state_")[0] == "seen":
                                        out["seen"] = v
                    except Exception as e:  # noqa: BLE001
                        out["errors"].append(f"parse: {e!r}")
        except (asyncio.IncompleteReadError, ConnectionResetError) as e:
            out["frames_in"].append(f"EOF {e!r}")
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"recv: {e!r}")

    task = asyncio.create_task(recv_loop())
    # wait for the engine.io OPEN packet
    t0 = time.time()
    while "open" not in out and time.time() - t0 < 5 and not task.done():
        await asyncio.sleep(0.05)
    if "open" not in out:
        out["errors"].append("no OPEN packet")
        return finish(out, a)
    rd = {"pathname": a.path, "asPath": a.path, "query": {}}
    auth = {}
    if not a.no_hydrate:
        auth["event"] = {"name": f"{STATE}.hydrate_and_load", "payload": {}, "router_data": rd}
    if a.state_schema:
        auth["state_schema"] = a.state_schema
    w.write(ws_frame(b"40/_event," + json.dumps(auth).encode()))
    await w.drain()
    await asyncio.sleep(0.8)
    ev = {"name": f"{IPSTATE}.rec", "payload": {"tag": a.tag}, "router_data": rd}
    w.write(ws_frame(b"42/_event," + json.dumps(["event", ev]).encode()))
    await w.drain()
    t0 = time.time()
    while time.time() - t0 < a.wait and not task.done():
        await asyncio.sleep(0.1)
    task.cancel()
    try:
        w.write(ws_frame(b"41/_event"))
        await w.drain()
    except Exception:  # noqa: BLE001
        pass
    w.close()
    return finish(out, a)


def finish(out, a):
    seen = [json.loads(s) for s in out.get("seen", [])]
    out["seen_parsed"] = seen
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
    summary = {
        "status": out.get("upgrade_status"),
        "maxPayload": (out.get("open") or {}).get("maxPayload"),
        "n_in": len(out["frames_in"]),
        "errors": out["errors"],
        "seen": [{k: v for k, v in s.items() if k != "pid"} for s in seen],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return out


asyncio.run(main())
