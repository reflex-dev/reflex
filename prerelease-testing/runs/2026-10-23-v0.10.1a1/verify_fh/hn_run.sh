#!/usr/bin/env bash
# verify_fh / HN-3: hnet app (copied from the hydration_net item) on ports 3701/8701 with xff_proxy.py on 8702.
#   hn_run.sh server <venv> <hops> <label>      start `reflex run` (dev) with trusted_proxy_hops=<hops>, REFLEX_API_URL -> proxy 8702
#   hn_run.sh proxy <mode> [--add 'Name: v']...  (re)start xff_proxy.py 8702 -> 8701 (binds 127.0.0.2) in mode append|line|none
#   hn_run.sh matrix <label> <ver>               ws_probe.py matrix: direct -> 8701 (peer 127.0.0.1) and via proxy from 127.0.0.3
#   hn_run.sh stop                               stop server + proxy
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
V=$SB/apps/verify_fh; DRV=$SB/envs/driver/bin/python; FP=3701; BP=8701; PP=8702
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"
cmd=$1; shift
case $cmd in
  server)
    venv=$1; hops=$2; label=$3
    RUN=$V/hnet_run_$venv; mkdir -p "$RUN/hnet"; cp "$V/hnet/rxconfig.py" "$RUN/"; cp "$V/hnet/hnet/"*.py "$RUN/hnet/"
    cd "$RUN" || exit 1
    # hops="" leaves HNET_HOPS unset (the 0.10.0 baseline has no trusted_proxy_hops option)
    nohup env REFLEX_TELEMETRY_ENABLED=false RVH_VENV=$venv ${hops:+HNET_HOPS=$hops} REFLEX_API_URL=http://localhost:$PP \
      "$SB/envs/$venv/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug > "$V/logs/$label.log" 2>&1 &
    echo $! > "$V/logs/hn_server.pid"; echo "server $label pid=$(cat "$V/logs/hn_server.pid") venv=$venv hops=$hops"
    for i in $(seq 1 420); do grep -q "App running at" "$V/logs/$label.log" 2>/dev/null && { echo "up after ${i}s"; break; }; sleep 1; done
    for i in $(seq 1 60); do curl --noproxy '*' -s -o /dev/null "http://localhost:$BP/ping" && break; sleep 1; done; sleep 2;;
  proxy)
    [ -f "$V/logs/hn_proxy.pid" ] && { kill "$(cat "$V/logs/hn_proxy.pid")" 2>/dev/null; sleep 0.5; rm -f "$V/logs/hn_proxy.pid"; }
    mode=$1; shift
    nohup $DRV "$V/probes/xff_proxy.py" $PP $BP --mode "$mode" "$@" > "$V/logs/hn_proxy_$mode.log" 2>&1 &
    echo $! > "$V/logs/hn_proxy.pid"; sleep 1; echo "proxy mode=$mode args=[$*] pid=$(cat "$V/logs/hn_proxy.pid")";;
  matrix)
    label=$1; ver=$2; O=$V/results/xff_$label; mkdir -p "$O"
    run() { local name=$1 port=$2; shift 2
      local out; out=$($NP "$DRV" "$V/probes/ws_probe.py" --port "$port" --version "$ver" --tag "$name" --out "$O/$name.json" "$@" 2>&1 | tail -1)
      "$DRV" -I -c '
import json,sys
name,raw=sys.argv[1],sys.argv[2]
try: d=json.loads(raw)
except Exception: print(f"{name:26} RAW {raw[:200]}"); sys.exit()
s=d["seen"][-1] if d["seen"] else {}
print(f"{name:26} {str(d.get(chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115)))[:12]:12} client_ip={s.get(chr(105)+chr(112))!r:30} xff={s.get(chr(120)+chr(45)+chr(102)+chr(111)+chr(114)+chr(119)+chr(97)+chr(114)+chr(100)+chr(101)+chr(100)+chr(45)+chr(102)+chr(111)+chr(114))!r:40} peer={s.get(chr(97)+chr(115)+chr(103)+chr(105)+chr(45)+chr(115)+chr(99)+chr(111)+chr(112)+chr(101)+chr(45)+chr(99)+chr(108)+chr(105)+chr(101)+chr(110)+chr(116))} err={d[chr(101)+chr(114)+chr(114)+chr(111)+chr(114)+chr(115)][:1]}")
' "$name" "$out"; }
    echo "## [$label] direct -> $BP (peer 127.0.0.1)"
    run d0_none           $BP
    run d1_xff_one        $BP --hdr "X-Forwarded-For: 6.6.6.6"
    run d2_xff_chain      $BP --hdr "X-Forwarded-For: 6.6.6.6, 7.7.7.7"
    run d4b_junk          $BP --hdr "X-Forwarded-For: not an ip!! <script>"
    run d5b_ipv6_port     $BP --hdr "X-Forwarded-For: [2001:db8::1]:443, 1.2.3.4:5678"
    run d5c_port_only     $BP --hdr "X-Forwarded-For: 1.2.3.4:5678"
    run d7_latin1         $BP --hdr-hex "X-Forwarded-For:e9e8" --hdr "X-Forwarded-For: 7.7.7.7"
    run d7b_latin1_last   $BP --hdr "X-Forwarded-For: 7.7.7.7" --hdr-hex "X-Forwarded-For:e9e8"
    echo "## [$label] via proxy $PP -> $BP (proxy peer 127.0.0.2, client 127.0.0.3)"
    run p0_none           $PP --local-addr 127.0.0.3
    run p1_spoof_one      $PP --local-addr 127.0.0.3 --hdr "X-Forwarded-For: 6.6.6.6"
    run p4b_junk          $PP --local-addr 127.0.0.3 --hdr "X-Forwarded-For: not an ip!! <script>"
    run p5c_port          $PP --local-addr 127.0.0.3 --hdr "X-Forwarded-For: 1.2.3.4:5678"
    run p7_latin1         $PP --local-addr 127.0.0.3 --hdr-hex "X-Forwarded-For:e9e8";;
  stop)
    [ -f "$V/logs/hn_proxy.pid" ] && { kill "$(cat "$V/logs/hn_proxy.pid")" 2>/dev/null; rm -f "$V/logs/hn_proxy.pid"; echo "proxy stopped"; }
    if [ -f "$V/logs/hn_server.pid" ]; then pid=$(cat "$V/logs/hn_server.pid")
      pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null
      for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
      kill -0 "$pid" 2>/dev/null && { pkill -KILL -P "$pid" 2>/dev/null; kill -KILL "$pid" 2>/dev/null; }
      rm -f "$V/logs/hn_server.pid"; echo "server stopped ($pid)"; fi
    for p in $(pgrep -f "bun run dev"); do case "$(readlink /proc/$p/cwd 2>/dev/null)" in $V/*) kill -TERM $p 2>/dev/null; echo "killed stray bun $p";; esac; done
    lsof -nP -iTCP:$FP -iTCP:$BP -iTCP:$PP -sTCP:LISTEN 2>/dev/null || echo "ports $FP/$BP/$PP free";;
esac
