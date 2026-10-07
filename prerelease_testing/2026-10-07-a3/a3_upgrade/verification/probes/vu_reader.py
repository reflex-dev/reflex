"""verify_upgrade (A3-07 / A3-08): launch `reflex run [--json]`, consume its stdout like a slow
JSON-lines reader, deliver a stop signal the way a process manager would, and analyze the stream.

Written independently of the explorer's json_drain.py. Runs under the driver venv (asserted);
the reflex under test is $SB/envs/<venv>/bin/reflex, checked by importing reflex in that venv
from the app dir (a neutral dir under $SB/apps, never the checkout).

Signal targets:
  pid   -> os.kill(top pid)             (kill -INT <pid>, proc.send_signal, supervisord stopasgroup=false,
                                         systemd KillMode=mixed/process, docker stop / tini to PID 1)
  group -> os.killpg(top pgid)          (terminal Ctrl-C, supervisord stopasgroup=true)
  tree  -> every pid in the tree at once (systemd KillMode=control-group)
  child -> the inner `python -m reflex run` only (diagnostic)
"""

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import threading
import time
import urllib.request

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable

SB = "/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad"
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ping(bp: int) -> bool:
    try:
        with _OPENER.open(f"http://127.0.0.1:{bp}/ping", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def proc_table() -> dict[int, tuple[int, int, str]]:
    """pid -> (ppid, sid, state)."""
    out = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                s = f.read()
        except OSError:
            continue
        rest = s[s.rfind(")") + 2 :].split()
        out[int(name)] = (int(rest[1]), int(rest[3]), rest[0])
    return out


def descendants(root: int, table=None) -> list[int]:
    table = table or proc_table()
    kids: dict[int, list[int]] = {}
    for pid, (ppid, _, _) in table.items():
        kids.setdefault(ppid, []).append(pid)
    out, stack = [], [root]
    while stack:
        p = stack.pop()
        for c in kids.get(p, []):
            out.append(c)
            stack.append(c)
    return out


def cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        return "?"


def alive(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat") as f:
            s = f.read()
    except OSError:
        return False
    return s[s.rfind(")") + 2] != "Z"


def listening(ports: set[int]) -> set[int]:
    found = set()
    for fn in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(fn) as f:
                next(f)
                for line in f:
                    parts = line.split()
                    if parts[3] == "0A":
                        port = int(parts[1].rsplit(":", 1)[1], 16)
                        if port in ports:
                            found.add(port)
        except OSError:
            pass
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", required=True)
    ap.add_argument("--app", required=True)
    ap.add_argument("--fp", type=int, required=True)
    ap.add_argument("--bp", type=int, required=True)
    ap.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--sig", default="INT")
    ap.add_argument("--target", default="pid", choices=["pid", "group", "tree", "child"])
    ap.add_argument("--chatty", type=float, default=0.0, help="VU_CHATTY_RATE lines/s")
    ap.add_argument("--warm", type=float, default=3.0, help="fast-read seconds after /ping ok")
    ap.add_argument("--pause", type=float, default=0.0, help="seconds of not reading before the signal")
    ap.add_argument(
        "--rate-bps",
        type=float,
        default=-1,
        help="read rate after the signal: -1 fast, 0 read nothing until the top process exits",
    )
    ap.add_argument("--sig2", type=float, default=None, help="send a second SIGINT (same target) N s after the first")
    ap.add_argument("--max-wait", type=float, default=60.0)
    ap.add_argument("--pidns", action="store_true", help="run as PID 1 of a new PID namespace (docker-like)")
    ap.add_argument("--freeze-after-inner-exit", action="store_true")
    ap.add_argument("--strace", default=None, help="strace output file for the top process")
    ap.add_argument("--linger", type=float, default=0.0, help="after consuming, wait N s and record survivors")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    vpy = f"{SB}/envs/{a.venv}/bin/python"
    where = subprocess.run(
        [vpy, "-I", "-c", "import reflex,importlib.metadata as m;print(reflex.__file__, m.version('reflex'))"],
        cwd=a.app, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert f"/scratchpad/envs/{a.venv}/" in where, where

    cmd = [f"{SB}/envs/{a.venv}/bin/reflex", "run", "--frontend-port", str(a.fp), "--backend-port", str(a.bp)]
    if a.json:
        cmd.insert(2, "--json")
    if a.pidns:
        cmd = ["unshare", "--pid", "--fork", "--mount-proc", *cmd]
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy",)}
    env["REFLEX_TELEMETRY_ENABLED"] = "false"
    seq_file = a.out + ".seq"
    if os.path.exists(seq_file):
        os.unlink(seq_file)
    env["VU_CHATTY_RATE"] = str(a.chatty)
    env["VU_SEQ_FILE"] = seq_file
    errf = open(a.out + ".stderr", "wb")
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=a.app, stdout=subprocess.PIPE, stderr=errf, env=env, start_new_session=True)
    fd = proc.stdout.fileno()
    buf = bytearray()
    ev = {"cmd": " ".join(cmd), "reflex": where}

    def read_some(timeout: float, n: int = 1 << 16) -> bool:
        r, _, _ = select.select([fd], [], [], timeout)
        if r:
            chunk = os.read(fd, n)
            if not chunk:
                return False
            buf.extend(chunk)
        return True

    # Phase 1: read fast until /ping answers (+ warm seconds).
    eof = False
    ready_at = None
    last_ping = 0.0
    while time.monotonic() - t0 < 420:
        if not read_some(0.1):
            eof = True
            break
        if time.monotonic() - last_ping > 0.5:
            last_ping = time.monotonic()
            if ping(a.bp):
                ready_at = time.monotonic()
                break
    ev["ready_s"] = None if ready_at is None else round(ready_at - t0, 2)
    if ready_at is None:
        ev["error"] = "never ready" if not eof else "EOF before ready"
    else:
        end = time.monotonic() + a.warm
        while time.monotonic() < end and read_some(0.05):
            pass
        # Phase 2: stop reading so every pipe fills.
        time.sleep(a.pause)

    table = proc_table()
    top = proc.pid
    if a.pidns:
        kids = [p for p, (pp, _, _) in table.items() if pp == proc.pid]
        top = kids[0] if kids else proc.pid
    tree_before = descendants(top, table)
    inner = [p for p, (pp, _, _) in table.items() if pp == top]
    inner_pid = inner[0] if inner else None
    ev["top_pid"] = top
    ev["inner_pid"] = inner_pid
    ev["tree_before"] = {p: cmdline(p)[:140] for p in [top, *tree_before]}
    ev["bytes_before_signal"] = len(buf)

    def sigmask(pid):
        # SIGINT is bit 1 (signal 2), SIGTERM bit 14 (signal 15) of the SigIgn/SigCgt masks.
        try:
            st = dict(l.split(":\t", 1) for l in open(f"/proc/{pid}/status").read().splitlines() if ":\t" in l)
        except OSError:
            return None
        ign, cgt = int(st["SigIgn"], 16), int(st["SigCgt"], 16)
        return {"INT": "ignored" if ign >> 1 & 1 else "caught" if cgt >> 1 & 1 else "default",
                "TERM": "ignored" if ign >> 14 & 1 else "caught" if cgt >> 14 & 1 else "default"}

    ev["sig_dispositions"] = {"reader": sigmask(os.getpid()), "top": sigmask(top), "inner": sigmask(inner_pid) if inner_pid else None}
    signum = getattr(signal, f"SIG{a.sig}")

    def deliver():
        if a.target == "pid":
            os.kill(top, signum)
        elif a.target == "group":
            os.killpg(os.getpgid(top), signum)
        elif a.target == "tree":
            for p in [top, *descendants(top)]:
                try:
                    os.kill(p, signum)
                except ProcessLookupError:
                    pass
        elif a.target == "child" and inner_pid:
            os.kill(inner_pid, signum)

    marks: dict[str, float | None] = {"inner_exit": None, "top_exit": None, "ping_down": None}
    stop_mon = threading.Event()

    def monitor():
        while not stop_mon.is_set():
            now = time.monotonic()
            if inner_pid and marks["inner_exit"] is None and not alive(inner_pid):
                marks["inner_exit"] = now
            if marks["top_exit"] is None and proc.poll() is not None:
                marks["top_exit"] = now
            if marks["ping_down"] is None and not ping(a.bp):
                marks["ping_down"] = time.monotonic()
            time.sleep(0.02)

    strace_proc = None
    if a.strace and ready_at is not None:
        # Trace the supervisor's writes (all threads) to see whether its last write to fd 1 is cut off at exit.
        strace_proc = subprocess.Popen(
            ["strace", "-f", "-tt", *os.environ.get("VU_STRACE_EXPR", "-e trace=write,exit_group -e signal=none").split(), "-s", "0", "-p", str(top), "-o", a.strace],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)
    t_sig = time.monotonic()
    if ready_at is not None:
        deliver()
    mon = threading.Thread(target=monitor, daemon=True)
    mon.start()
    sig2_sent = None

    # Phase 3: consume after the signal.
    deadline = t_sig + a.max_wait
    killed = False
    if not eof:
        if a.rate_bps == 0:
            while marks["top_exit"] is None and time.monotonic() < deadline:
                if a.sig2 is not None and sig2_sent is None and time.monotonic() - t_sig >= a.sig2:
                    deliver(); sig2_sent = time.monotonic() - t_sig
                time.sleep(0.05)
        else:
            chunk = 1 << 16 if a.rate_bps < 0 else 512
            delay = 0 if a.rate_bps < 0 else chunk / a.rate_bps
            while time.monotonic() < deadline:
                if a.sig2 is not None and sig2_sent is None and time.monotonic() - t_sig >= a.sig2:
                    deliver(); sig2_sent = time.monotonic() - t_sig
                if a.freeze_after_inner_exit and marks["inner_exit"] is not None:
                    # Stop reading entirely once the inner child is gone; read the rest only after the
                    # supervisor (the only writer of our pipe) has exited.
                    ev["froze_at_s"] = round(time.monotonic() - t_sig, 2)
                    ev["bytes_at_freeze"] = len(buf)
                    while marks["top_exit"] is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                    if marks["top_exit"] is not None:
                        ev["bytes_read_after_writer_exit_start"] = len(buf)
                    break
                if not read_some(0.1, chunk):
                    eof = True
                    break
                if delay:
                    time.sleep(delay)
        if not eof and marks["top_exit"] is None:
            killed = True
            ev["still_running_after_s"] = round(time.monotonic() - t_sig, 1)
            ev["ping_while_hung"] = ping(a.bp)
            ev["ports_bound_while_hung"] = sorted(listening({a.fp, a.bp}))
            ev["tree_while_hung"] = {p: cmdline(p)[:140] for p in [top, *descendants(top)]}

    def session_procs():
        return {p: (pp, cmdline(p)[:140]) for p, (pp, sid, st) in proc_table().items() if sid == proc.pid and st != "Z"}

    # Optionally linger after the top process is gone, then look for survivors (orphans keep the session id).
    if a.linger:
        time.sleep(a.linger)
        ev["after_linger"] = {
            "linger_s": a.linger,
            "top_alive": proc.poll() is None,
            "ping": ping(a.bp),
            "ports_bound": sorted(listening({a.fp, a.bp})),
            "session_procs": session_procs(),
        }
    # Kill whatever is left (hung tree or orphans), then drain to EOF.
    for p in [*session_procs(), proc.pid]:
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass
    while not eof:
        if not read_some(1.0):
            eof = True
    t_eof = time.monotonic()
    rc = proc.wait()
    if strace_proc is not None:
        try:
            strace_proc.wait(10)
        except subprocess.TimeoutExpired:
            strace_proc.kill()
    time.sleep(1.0)
    stop_mon.set()
    mon.join()
    ev["leftover_after"] = session_procs()
    ev["ports_bound_after"] = sorted(listening({a.fp, a.bp}))

    rel = lambda t: None if t is None else round(t - t_sig, 2)  # noqa: E731
    ev.update(
        rc=rc,
        killed_by_reader=killed,
        sig=a.sig,
        target=a.target,
        json_mode=a.json,
        rate_bps=a.rate_bps,
        pause=a.pause,
        sig2_at=sig2_sent,
        inner_exit_s=rel(marks["inner_exit"]),
        top_exit_s=rel(marks["top_exit"]),
        ping_down_s=rel(marks["ping_down"]),
        eof_s=rel(t_eof),
    )
    if marks["inner_exit"] and marks["top_exit"]:
        ev["top_exit_minus_inner_exit_s"] = round(marks["top_exit"] - marks["inner_exit"], 2)

    data = bytes(buf)
    lines = data.split(b"\n")
    tail = lines[-1]
    ev["bytes_total"] = len(data)
    ev["ends_with_newline"] = data.endswith(b"\n")
    ev["truncated_tail"] = tail[-200:].decode(errors="replace") if tail else ""
    ev["truncated_tail_len"] = len(tail)
    complete = lines[:-1]
    invalid, seqs, levels = [], [], {}
    for ln in complete:
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
            assert isinstance(rec, dict)
        except Exception:
            invalid.append(ln[:200].decode(errors="replace"))
            continue
        msg = str(rec.get("message", ""))
        levels[rec.get("level")] = levels.get(rec.get("level"), 0) + 1
        if msg.startswith("VUSEQ "):
            seqs.append(int(msg.split()[1]))
    ev["lines_complete"] = len(complete)
    ev["invalid_count"] = len(invalid)
    ev["invalid_sample"] = invalid[:5]
    ev["levels"] = levels
    if seqs:
        ev["seq_first"], ev["seq_max"] = seqs[0], max(seqs)
        ev["seq_gaps"] = sum(1 for x, y in zip(seqs, seqs[1:]) if y != x + 1)
    try:
        with open(seq_file) as f:
            ev["seq_printed_by_app"] = int(f.read().strip() or 0)
    except OSError:
        ev["seq_printed_by_app"] = None
    if seqs and ev["seq_printed_by_app"]:
        ev["seq_lost_at_end"] = ev["seq_printed_by_app"] - max(seqs)
    with open(a.out + ".stdout", "wb") as f:
        f.write(data)
    with open(a.out, "w") as f:
        json.dump(ev, f, indent=1)
    show = {k: v for k, v in ev.items() if k not in ("tree_before", "invalid_sample")}
    print(json.dumps(show, indent=1))


if __name__ == "__main__":
    main()
