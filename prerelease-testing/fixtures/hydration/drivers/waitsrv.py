"""Poll URLs until all return HTTP 200 or timeout. Usage: waitsrv.py TIMEOUT_S URL [URL...]"""
import sys
import time
import urllib.request

deadline = time.time() + float(sys.argv[1])
urls = sys.argv[2:]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
pending = set(urls)
t0 = time.time()
while pending and time.time() < deadline:
    for u in list(pending):
        try:
            with opener.open(u, timeout=3) as r:
                if r.status == 200:
                    pending.discard(u)
                    print(f"UP {u} after {time.time()-t0:.1f}s", flush=True)
        except Exception:
            pass
    if pending:
        time.sleep(1)
if pending:
    print(f"TIMEOUT waiting for {sorted(pending)}")
    sys.exit(1)
