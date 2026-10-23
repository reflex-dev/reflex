#!/bin/bash
# Usage: xff_matrix.sh <label> <BP> [PP]   (server already running; PP = xff_proxy listening port, optional)
# Runs probes/ws_probe.py with a matrix of raw header sets directly against BP and (if PP) through the proxy from
# 127.0.0.3, prints one line per case: case | status | client_ip seen by the handler | raw x-forwarded-for | extras.
SB=${SB:?}; export WORK=${WORK:-$SB/apps/hydration_net}
. "$WORK/src/scripts/env.sh"
L=$1; BP=$2; PP=${3:-}
O=$W/results/xff/$L; mkdir -p "$O"
VER=${VER:-0.10.1a1}
run() {  # name port [probe args...]
  local name=$1 port=$2; shift 2
  local out; out=$($NP "$DRV" "$WORK/probes/ws_probe.py" --port "$port" --version "$VER" --tag "$name" --out "$O/$name.json" "$@" 2>&1 | tail -1)
  "$DRV" -I -c '
import json,sys
name=sys.argv[1]; raw=sys.argv[2]
try:
    d=json.loads(raw)
except Exception:
    print(f"{name:34} RAW {raw[:300]}"); sys.exit()
s=d["seen"][-1] if d["seen"] else {}
extras={k:v for k,v in s.items() if k in ("x-real-ip","forwarded","x-dup","x-bad","x-name","cookie","cookie_attr","raw_n") and v not in (None,"")}
print(f"{name:34} {str(d['"'"'status'"'"'])[:12]:12} ip={s.get('"'"'ip'"'"')!s:14} xff={s.get('"'"'x-forwarded-for'"'"')!r:38} asc={s.get('"'"'asgi-scope-client'"'"')} err={d['"'"'errors'"'"'][:1]} {json.dumps(extras, ensure_ascii=False)[:200]}")
' "$name" "$out"
}
echo "## direct -> $BP (peer 127.0.0.1)"
run d0_none            "$BP"
run d1_xff_one         "$BP" --hdr "X-Forwarded-For: 6.6.6.6"
run d2_xff_chain       "$BP" --hdr "X-Forwarded-For: 6.6.6.6, 7.7.7.7"
run d3_xff_two_lines   "$BP" --hdr "X-Forwarded-For: 6.6.6.6" --hdr "X-Forwarded-For: 7.7.7.7"
run d4_xff_ws_garbage  "$BP" --hdr "X-Forwarded-For:   6.6.6.6 ,, ,  7.7.7.7  "
run d4b_xff_junk       "$BP" --hdr "X-Forwarded-For: not an ip!! <script>"
run d4c_xff_empty      "$BP" --hdr "X-Forwarded-For: "
run d5_xff_ipv6        "$BP" --hdr "X-Forwarded-For: 2001:db8::1"
run d5b_xff_ipv6_port  "$BP" --hdr "X-Forwarded-For: [2001:db8::1]:443, 1.2.3.4:5678"
run d6_xrealip_fwd     "$BP" --hdr "X-Real-IP: 9.9.9.9" --hdr "Forwarded: for=8.8.8.8;proto=https"
run d7_xff_latin1      "$BP" --hdr-hex "X-Forwarded-For:e9e8" --hdr "X-Forwarded-For: 7.7.7.7"
run d8_dup_cookie      "$BP" --hdr "Cookie: a=1" --hdr "Cookie: b=2; c=3" --hdr "X-Dup: one" --hdr "X-Dup: two"
run d9_bad_utf8_value  "$BP" --hdr-hex "X-Bad:fffe80" --hdr-hex "Cookie:613de9" --hdr "Cookie: z=9"
run d10_bad_utf8_name  "$BP" --hdr-hex "X-Nam$(printf 'e9'):41"
run d11_name_latin1    "$BP" --hdr-hex "$(printf 'X-N\xe9me'):41"
run d12_cookie_secret  "$BP" --hdr "Cookie: sid=COOKIESECRET1; other=COOKIESECRET2" --hdr "Cookie: third=COOKIESECRET3" --hdr "Authorization: Bearer AUTHSECRET9"
if [ -n "$PP" ]; then
  echo "## via xff_proxy $PP -> $BP (proxy binds 127.0.0.2, client from 127.0.0.3)"
  run p0_none            "$PP" --local-addr 127.0.0.3
  run p1_spoof_one       "$PP" --local-addr 127.0.0.3 --hdr "X-Forwarded-For: 6.6.6.6"
  run p2_spoof_chain     "$PP" --local-addr 127.0.0.3 --hdr "X-Forwarded-For: 6.6.6.6, 7.7.7.7"
  run p3_spoof_two_lines "$PP" --local-addr 127.0.0.3 --hdr "X-Forwarded-For: 6.6.6.6" --hdr "X-Forwarded-For: 7.7.7.7"
  run p4_spoof_ipv6      "$PP" --local-addr 127.0.0.3 --hdr "X-Forwarded-For: 2001:db8::1"
  run p5_xrealip         "$PP" --local-addr 127.0.0.3 --hdr "X-Real-IP: 9.9.9.9"
fi
