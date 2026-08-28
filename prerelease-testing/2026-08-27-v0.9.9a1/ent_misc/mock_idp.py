"""Tiny mock OIDC identity provider for exercising the oidc demo without a real IdP.

Serves the OIDC discovery document, an empty JWKS, and an /authorize endpoint
that just echoes the query parameters back as HTML so a browser test can assert
the authorization redirect was formed correctly. Never issues tokens.

Usage: python mock_idp.py <port>
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlsplit

PORT = int(sys.argv[1])
BASE = f"http://localhost:{PORT}"


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/.well-known/openid-configuration":
            self._json(
                {
                    "issuer": BASE,
                    "authorization_endpoint": f"{BASE}/authorize",
                    "token_endpoint": f"{BASE}/token",
                    "userinfo_endpoint": f"{BASE}/userinfo",
                    "jwks_uri": f"{BASE}/jwks",
                    "end_session_endpoint": f"{BASE}/logout",
                    "response_types_supported": ["code"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "code_challenge_methods_supported": ["S256"],
                    "scopes_supported": ["openid", "email", "profile"],
                }
            )
        elif url.path == "/jwks":
            self._json({"keys": []})
        elif url.path == "/authorize":
            params = dict(parse_qsl(url.query))
            body = (
                "<html><head><title>MOCK IDP AUTHORIZE</title></head><body>"
                "<h1>MOCK IDP AUTHORIZE</h1><pre id='params'>"
                + json.dumps(params, indent=2)
                + "</pre></body></html>"
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "text/html")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/logout":
            params = dict(parse_qsl(url.query))
            body = (
                "<html><head><title>MOCK IDP LOGOUT</title></head><body>"
                "<h1>MOCK IDP LOGOUT</h1><pre>" + json.dumps(params, indent=2)
                + "</pre></body></html>"
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "text/html")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": "not found", "path": self.path}, status=404)

    def do_POST(self):
        # token endpoint: always refuse, we never mint tokens
        self._json({"error": "invalid_grant", "error_description": "mock idp"}, 400)

    def log_message(self, fmt, *args):
        sys.stderr.write("MOCKIDP %s - %s\n" % (self.address_string(), fmt % args))


HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
