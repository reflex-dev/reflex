"""Tiny stand-in for https://api.github.com/graphql used by the github-stats example.

POST /graphql with {"variables": {"login": X}} -> canned userInfo payload (deterministic
per login), unknown logins ("ghost*") -> {"data": {"user": null}}. GET /count returns
per-login request counts so drivers can assert whether a fetch happened.
Usage: python github_stub.py <port>
"""
import hashlib
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COUNTS: dict[str, int] = {}


def stats(login: str) -> dict:
    h = int(hashlib.sha256(login.lower().encode()).hexdigest(), 16)
    n = lambda k, m: (h >> k) % m + 1  # noqa: E731
    return {
        "name": login.title(), "login": login,
        "contributionsCollection": {"totalCommitContributions": n(3, 900), "totalPullRequestReviewContributions": n(7, 90)},
        "repositoriesContributedTo": {"totalCount": n(11, 60)},
        "pullRequests": {"totalCount": n(13, 400)},
        "mergedPullRequests": {"totalCount": n(17, 300)},
        "openIssues": {"totalCount": n(19, 40)},
        "closedIssues": {"totalCount": n(23, 200)},
        "followers": {"totalCount": n(29, 1000)},
        "repositoryDiscussions": {"totalCount": n(31, 20)},
        "repositoryDiscussionComments": {"totalCount": n(37, 20)},
    }


class H(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        login = body.get("variables", {}).get("login", "")
        COUNTS[login] = COUNTS.get(login, 0) + 1
        user = None if login.startswith("ghost") else stats(login)
        out = json.dumps({"data": {"user": user}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):  # noqa: N802
        out = json.dumps(COUNTS).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, fmt, *args):
        sys.stderr.write("stub: " + fmt % args + "\n")


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
