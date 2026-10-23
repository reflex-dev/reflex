"""Repro: after on_load tuple on '/', click clear then a tuple on_click; check whether an
on_load event (B.load_tuple_b) re-runs unexpectedly. Prints websocket frames on anomaly."""
import sys, time
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
SCREENSHOT = (sys.argv[3] if len(sys.argv) > 3 else "shot") == "shot"
anomalies = 0
for attempt in range(N):
    frames = []
    t0 = time.time()
    def logws(ws):
        ws.on("framesent", lambda f: frames.append(f"{time.time()-t0:6.2f} SENT {str(f)[:300]}"))
        ws.on("framereceived", lambda f: frames.append(f"{time.time()-t0:6.2f} RECV {str(f)[:300]}"))
    cap = Capture()
    with browser() as b:
        ctx, page = new_page(b, cap)
        page.on("websocket", logws)
        page.goto(BASE + "/", wait_until="networkidle"); page.wait_for_timeout(1500)
        first = (page.inner_text("#a-log"), page.inner_text("#b-log"))
        if SCREENSHOT:
            page.screenshot(path="../shots/repro_shot.png", full_page=True)
            frames.append(f"{time.time()-t0:6.2f} screenshot taken")
        page.click("#clear")
        wait_text(page, "#a-log", "A.log:")
        frames.append(f"{time.time()-t0:6.2f} a-log cleared, b={page.inner_text('#b-log')!r}")
        page.click("#btn-tuple"); page.wait_for_timeout(2500)
        after = (page.inner_text("#a-log"), page.inner_text("#b-log"))
        ok = after == ("A.log: A.h1", "B.log: B.h2") and first == ("A.log: A.load_tuple_a", "B.log: B.load_tuple_b")
        print(f"attempt {attempt}: first={first} after={after} -> {'ok' if ok else 'ANOMALY'}")
        if not ok:
            anomalies += 1
            print("\n".join(frames))
            print(cap.summary()["console_all"])
print("anomalies:", anomalies)
