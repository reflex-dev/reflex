"""Hit /api/whoami N times; summarise distinct (pid, token-manager instance_id). Usage: whoami_probe.py <base_url> [n]"""
import json
import sys
import urllib.request

url, n = sys.argv[1].rstrip("/"), int(sys.argv[2]) if len(sys.argv) > 2 else 40
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
rows = [json.loads(opener.open(f"{url}/api/whoami", timeout=10).read()) for _ in range(n)]
pids = sorted({r["pid"] for r in rows})
ids = sorted({r["instance_id"] for r in rows})
print(f"requests={len(rows)} distinct_pids={len(pids)} distinct_instance_ids={len(ids)} token_manager={rows[0]['token_manager']}")
print("pids:", pids)
print("instance_ids:", ids)
print("local_tokens per pid:", {r["pid"]: r["local_tokens"] for r in rows})
