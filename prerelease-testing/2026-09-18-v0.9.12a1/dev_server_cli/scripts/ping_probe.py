"""Probe http://localhost:PORT/ping every 50ms for N seconds; classify outcomes."""

import socket
import sys
import time

PORT = int(sys.argv[1])
DUR = float(sys.argv[2])
OUT = sys.argv[3]

res = []
t0 = time.time()
while time.time() - t0 < DUR:
    s = time.time()
    try:
        c = socket.create_connection(("127.0.0.1", PORT), timeout=10)
        c.sendall(b"GET /ping HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        data = c.recv(200)
        c.close()
        code = data.split(b" ")[1].decode() if data.startswith(b"HTTP") else "noresp"
        res.append((round(s - t0, 3), round(time.time() - s, 3), code))
    except ConnectionRefusedError:
        res.append((round(s - t0, 3), round(time.time() - s, 3), "REFUSED"))
    except Exception as e:
        res.append((round(s - t0, 3), round(time.time() - s, 3), f"ERR:{type(e).__name__}"))
    time.sleep(0.05)

refused = [r for r in res if r[2] == "REFUSED"]
errs = [r for r in res if r[2].startswith("ERR") or r[2] == "noresp"]
slow = sorted(res, key=lambda r: -r[1])[:8]
with open(OUT, "w") as f:
    for r in res:
        f.write(f"{r[0]}\t{r[1]}\t{r[2]}\n")
print(f"total={len(res)} refused={len(refused)} errors={len(errs)} ok={len(res) - len(refused) - len(errs)}")
print("refused windows:", [r[0] for r in refused][:30])
print("errors:", errs[:10])
print("slowest (t_offset, latency, code):", slow)
