"""#7428 probe: `reflex run --json` stopped by a signal while a slow consumer reads its stdout.

Usage: json_drain.py <venv> <appdir> <fp> <bp> <signal: INT-group|INT-pid|TERM-pid> <slow_rate_lines_per_s> <out.json>
         [--pause S] [--warm S]
Starts `<venv>/bin/reflex run --json` (own session) with QA_CHATTY=1, reads stdout fast until the backend answers
/ping and the chatty thread runs for --warm seconds, stops reading for --pause seconds (pipes fill), sends the
signal, then reads at <slow_rate> lines/s until EOF. Records signal->EOF / exit times, exit code, JSON validity of
every line (esp. the last), QA-SEQ gaps and the tail lost against the worker's own seq file.
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable
venv, appdir, fp, bp, sig, rate, out = sys.argv[1:8]
opts = dict(zip(sys.argv[8::2], sys.argv[9::2]))
pause, warm = float(opts.get("--pause", "4")), float(opts.get("--warm", "3"))
rate = float(rate)
seq_file = os.path.join(appdir, "chatty.seq")
if os.path.exists(seq_file):
    os.remove(seq_file)
env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy",)}
CHATTY = os.environ.get("QA_CHATTY_OFF") != "1"
env.update(REFLEX_TELEMETRY_ENABLED="false", QA_CHATTY="1" if CHATTY else "0", QA_CHATTY_SEQ_FILE=seq_file)
env.pop("QA_CHATTY_OFF", None)
err = open(out + ".stderr", "wb")
t0 = time.monotonic()
cmd = [f"{venv}/bin/reflex", "run", "--json", "--frontend-port", fp, "--backend-port", bp]
if os.environ.get("QA_NOJSON") == "1":
    cmd.remove("--json")
proc = subprocess.Popen(cmd,
                        cwd=appdir, stdout=subprocess.PIPE, stderr=err, stdin=subprocess.DEVNULL, env=env,
                        start_new_session=True)
lines, marks = [], {}


def ping():
    try:
        h = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return h.open(f"http://127.0.0.1:{bp}/ping", timeout=2).status == 200
    except Exception:
        return False


os.set_blocking(proc.stdout.fileno(), False)
buf = b""


def read_some(max_lines=None):
    """Read what is available (non-blocking); return number of complete lines taken."""
    global buf
    got = 0
    while max_lines is None or got < max_lines:
        nl = buf.find(b"\n")
        if nl >= 0:
            lines.append((time.monotonic() - t0, buf[: nl + 1]))
            buf = buf[nl + 1:]
            got += 1
            continue
        try:
            chunk = os.read(proc.stdout.fileno(), 4096 if max_lines else 65536)
        except BlockingIOError:
            return got
        if not chunk:
            marks.setdefault("eof", time.monotonic() - t0)
            return got
        buf += chunk
    return got


# 1) fast reading until up + chatty
deadline = time.monotonic() + 420
while time.monotonic() < deadline:
    read_some()
    if "up" not in marks and ping():
        marks["up"] = time.monotonic() - t0
    if "up" in marks and (os.path.exists(seq_file) or not CHATTY) and time.monotonic() - t0 - marks["up"] > warm:
        break
    if proc.poll() is not None:
        break
    time.sleep(0.02)
# 2) stop reading: pipes fill
marks["pause_start"] = time.monotonic() - t0
time.sleep(pause)
# 3) signal
pgid = os.getpgid(proc.pid)
s = signal.SIGINT if sig.startswith("INT") else signal.SIGTERM
if sig.endswith("group"):
    os.killpg(pgid, s)
else:
    os.kill(proc.pid, s)
marks["signal"] = time.monotonic() - t0
marks["signal_wall"] = time.time()
seq_at_signal = open(seq_file).read() if os.path.exists(seq_file) else None
# 4) slow reading until EOF (cap QA_EOF_CAP s)
while "eof" not in marks and time.monotonic() - t0 - marks["signal"] < float(os.environ.get("QA_EOF_CAP", "150")):
    got = read_some(max_lines=1)
    if proc.poll() is not None:
        marks.setdefault("exit", time.monotonic() - t0)
    time.sleep(1.0 / rate if got else 0.02)
if buf:
    lines.append((time.monotonic() - t0, buf + b"<NO-NEWLINE-AT-EOF>"))
try:
    rc = proc.wait(timeout=float(os.environ.get("QA_WAIT_CAP", "60")))
except subprocess.TimeoutExpired:
    rc = "TIMEOUT"
marks.setdefault("exit", time.monotonic() - t0)
time.sleep(1)
seq_final = open(seq_file).read() if os.path.exists(seq_file) else None
# leftovers in the session
left = subprocess.run(["bash", "-c", f"ps -o pid=,stat=,cmd= -s {pgid} 2>/dev/null; lsof -nP -iTCP:{fp} -sTCP:LISTEN -t; lsof -nP -iTCP:{bp} -sTCP:LISTEN -t"],
                      capture_output=True, text=True).stdout.strip()
if left:
    os.killpg(pgid, signal.SIGKILL)
bad, seqs, after_sig = [], [], 0
for ts, raw in lines:
    txt = raw.decode("utf-8", "replace").rstrip("\n")
    if ts >= marks["signal"]:
        after_sig += 1
    try:
        rec = json.loads(txt)
    except Exception as e:  # noqa: BLE001
        bad.append({"t": round(ts, 2), "err": str(e)[:80], "line": txt[:160] + ("..." if len(txt) > 160 else "") + f" [len {len(txt)}]"})
        continue
    msg = rec.get("message", "") if isinstance(rec, dict) else ""
    if isinstance(msg, str) and msg.startswith("QA-SEQ "):
        seqs.append(int(msg.split()[1]))
gaps = [(a, b) for a, b in zip(seqs, seqs[1:]) if b != a + 1]
last_txt = lines[-1][1].decode("utf-8", "replace")[:300] if lines else None
non_seq_tail = [l.decode("utf-8", "replace")[:220] for _, l in lines[-12:] if b"QA-SEQ" not in l]
res = {
    "cmd": " ".join(cmd[1:]),
    "venv": venv, "chatty": CHATTY, "signal": sig, "slow_rate": rate, "pause": pause, "marks": {k: (round(v, 2) if k != "signal_wall" else time.strftime("%H:%M:%S", time.gmtime(v)) + f".{int(v % 1 * 1000):03d}Z") for k, v in marks.items()},
    "signal_to_eof_s": round(marks.get("eof", float("nan")) - marks["signal"], 2),
    "signal_to_exit_s": round(marks["exit"] - marks["signal"], 2), "returncode": rc,
    "lines_total": len(lines), "lines_after_signal": after_sig, "invalid_json": len(bad), "invalid_samples": bad[-3:],
    "last_line_valid_json": not bad or bad[-1]["t"] != round(lines[-1][0], 2),
    "seq_first": seqs[0] if seqs else None, "seq_max_received": max(seqs) if seqs else None,
    "seq_written_at_signal": seq_at_signal, "seq_written_final": seq_final,
    "lost_tail": (int(seq_final) - max(seqs)) if seqs and seq_final else None, "seq_gaps": gaps[:5],
    "last_line": last_txt, "last_non_seq_lines": non_seq_tail, "leftover_after_exit": left,
}
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: res[k] for k in ("signal", "slow_rate", "signal_to_eof_s", "signal_to_exit_s", "returncode", "lines_total", "lines_after_signal", "invalid_json", "seq_max_received", "seq_written_final", "lost_tail", "seq_gaps", "leftover_after_exit")}))
