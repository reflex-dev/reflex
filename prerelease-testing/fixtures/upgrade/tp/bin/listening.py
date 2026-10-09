"""List listening TCP ports (from /proc/net/tcp*), optionally filtered to a range."""
import sys
lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, 65535)
ports = set()
for f in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        for line in open(f).readlines()[1:]:
            parts = line.split()
            if parts[3] == "0A":  # LISTEN
                port = int(parts[1].split(":")[1], 16)
                if lo <= port <= hi:
                    ports.add(port)
    except FileNotFoundError:
        pass
print(sorted(ports))
