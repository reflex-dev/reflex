"""Script to wait for ports to start listening.

Replaces logic previously implemented in a shell script that needed
tools that are not available on Windows.
"""

import argparse
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

import httpx

# psutil is already a dependency of Reflex itself - so it's OK to use
import psutil


def _pid_exists(pid):
    # os.kill(pid, 0) doesn't work on Windows (actually kills the PID)
    # psutil.pid_exists() doesn't work on Windows (does os.kill underneath)
    # psutil.pids() seems to return the right thing. Inefficient but doesn't matter - keeps things simple.
    #
    # Note: For windows, the pid here is really the "winpid".
    return pid in psutil.pids()


# Not really used anymore now that we actually check the HTTP response.
def _wait_for_port(port, server_pid, timeout) -> Tuple[bool, str]:
    start = time.time()
    print(f"Waiting for up to {timeout} seconds for port {port} to start listening.")  # noqa: T201
    while True:
        if not _pid_exists(server_pid):
            return False, f"Server PID {server_pid} is not running."
        try:
            socket.create_connection(("localhost", port), timeout=0.5)
            return True, f"Port {port} is listening after {time.time() - start} seconds"
        except Exception:
            if time.time() - start > timeout:
                return (
                    False,
                    f"Port {port} still not listening after {timeout} seconds.",
                )
            time.sleep(5)


def _wait_for_http_response(port, server_pid, timeout, path) -> Tuple[bool, str, str]:
    start = time.time()
    if path[0] != "/":
        # This is a hack for passing the path on windows without a leading slash
        # which mangles it https://stackoverflow.com/a/49013604
        path = "/" + path
    url = f"http://localhost:{port}{path}"
    print(f"Waiting for up to {timeout} seconds for {url} to return HTTP response.")  # noqa: T201
    while True:
        try:
            if not _pid_exists(server_pid):
                return False, f"Server PID {server_pid} is not running.", ""
            response = httpx.get(url, timeout=0.5)
            response.raise_for_status()
            return (
                True,
                f"{url} returned response after {time.time() - start} seconds",
                response.text,
            )
        except Exception as exc:  # noqa: PERF203
            if time.time() - start > timeout:
                return (
                    False,
                    f"{url} still returning errors after {timeout} seconds: {exc!r}.",
                    "",
                )
            time.sleep(5)


def main():
    """Wait for ports to start listening."""
    parser = argparse.ArgumentParser(description="Wait for ports to start listening.")
    parser.add_argument("port", type=int, nargs="+")
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--server-pid", type=int)
    parser.add_argument("--path", type=str, default="/")
    args = parser.parse_args()
    start = time.time()
    executor = ThreadPoolExecutor(max_workers=len(args.port))
    futures = [
        executor.submit(
            _wait_for_http_response,
            p,
            args.server_pid,
            args.timeout,
            args.path,
        )
        for p in args.port
    ]
    base_content = None
    for f in as_completed(futures):
        ok, msg, content = f.result()
        if ok:
            print(f"OK: {msg}")  # noqa: T201
            if base_content is None:
                base_content = content
            else:
                assert (
                    content == base_content
                ), f"HTTP responses are not equal {content!r} != {base_content!r}."
        else:
            print(f"FAIL: {msg}")  # noqa: T201
            exit(1)
    print(f"OK: All HTTP responses are equal after {time.time() - start} sec.")  # noqa: T201


if __name__ == "__main__":
    main()
