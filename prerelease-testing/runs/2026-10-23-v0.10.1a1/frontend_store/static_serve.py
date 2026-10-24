"""Serve an exported reflex frontend (build/client) with SPA fallback, like the prod server does.

    $SB/envs/driver/bin/python static_serve.py <dir> <port>
"""

import http.server
import os
import sys
from functools import partial


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        full = super().translate_path(path)
        if os.path.isfile(full):
            return full
        rel = path.split("?")[0].strip("/")
        for cand in (f"{rel}.html", os.path.join(rel, "index.html")):
            p = os.path.join(self.directory, cand)
            if os.path.isfile(p):
                return p
        return os.path.join(self.directory, "__spa-fallback.html")

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    directory, port = sys.argv[1], int(sys.argv[2])
    http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=directory)).serve_forever()
