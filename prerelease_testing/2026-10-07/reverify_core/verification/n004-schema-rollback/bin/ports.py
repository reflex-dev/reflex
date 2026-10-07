"""List LISTEN sockets on this cluster's reserved ports (3600-3603, 8600-8603) from /proc/net/tcp{,6}."""
mine = set(range(3600, 3604)) | set(range(8600, 8604))
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
