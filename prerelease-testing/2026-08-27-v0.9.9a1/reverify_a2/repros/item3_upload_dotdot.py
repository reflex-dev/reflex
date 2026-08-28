"""Item 3 (FINDING-007): raw multipart upload of all-dots/traversal filenames.
Expect: HTTP 200 (not 500), saved name 'upload', no dir escape."""
import asyncio, json, sys, uuid, socketio, httpx

BACKEND = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8140"
HANDLER = "reflex___state____state.pep695app___pep695app____alias_state.upload_probe"
CASES = ["..", "./../.", "..\\", "/..", "...", "../x.txt"]

async def main():
    token = str(uuid.uuid4())
    c = socketio.AsyncClient(reconnection=False)
    await c.connect(f"{BACKEND}?token={token}", socketio_path="_event", namespaces=["/_event"], transports=["websocket"], wait_timeout=10)
    await asyncio.sleep(0.4)
    print("TOKEN linked:", token)
    results = []
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        for raw in CASES:
            r = await client.post(
                f"{BACKEND}/_upload",
                headers={"Reflex-Client-Token": token, "Reflex-Event-Handler": HANDLER},
                files={"files": (raw, b"probe-bytes", "application/octet-stream")},
            )
            saved = None
            for line in r.text.splitlines():
                line = line.strip()
                if not line: continue
                try: obj = json.loads(line)
                except json.JSONDecodeError: continue
                for _s, fields in obj.get("delta", {}).items():
                    if "saved_rx_state_" in fields:  # not used
                        pass
                    if "saved_names" in fields and fields["saved_names"]:
                        saved = fields["saved_names"][-1]
            results.append((raw, r.status_code, saved))
            print(f"raw={raw!r:10} status={r.status_code} saved={saved!r}")
    await c.disconnect()
    bad = [x for x in results if x[1] >= 500]
    print("ANY 500:", bool(bad))

asyncio.run(main())
