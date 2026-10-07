"""List LISTEN sockets on this cluster's reserved ports (3100-3119, 8100-8119) from /proc/net/tcp{,6}."""
mine = set(range(3100, 3120)) | set(range(8100, 8120))
found = set()
for f in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        for line in open(f).readlines()[1:]:
            parts = line.split()
            port = int(parts[1].rsplit(":", 1)[1], 16)
            if parts[3] == "0A" and port in mine:
                found.add(port)
    except FileNotFoundError:
        pass
print("listening on reserved ports:", sorted(found) or "none")
