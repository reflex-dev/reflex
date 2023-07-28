"""Script to wait for ports to start listening.

Replaces logic previously implemented in a shell script that needed
tools that are not available on Windows.
"""
import argparse
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def _wait_for_port(port, server_pid, timeout):
    start = time.time()
    print(f"Waiting for up to {timeout} seconds for port {port} to start listening.")
    while True:
        # TODO fail early if server pid not there
        try:
            socket.create_connection(("localhost", port), timeout=0.5)
            print(f"OK! Port {port} is listening after {time.time() - start} seconds")
            return True
        except Exception:
            if time.time() - start > timeout:
                print(f"FAIL: Port {port} still not listening after {timeout} seconds.")
                return False
            time.sleep(5)


def main():
    """Wait for ports to start listening."""
    parser = argparse.ArgumentParser(description="Wait for ports to start listening.")
    parser.add_argument("port", type=int, nargs="+")
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--server-pid", type=int)
    args = parser.parse_args()
    executor = ThreadPoolExecutor(max_workers=len(args.port))
    futures = []
    for p in args.port:
        futures.append(
            executor.submit(_wait_for_port, p, args.server_pid, args.timeout)
        )
    for f in as_completed(futures):
        if not f.result():
            print("At least one port failed... exiting with failure.")
            exit(1)


if __name__ == "__main__":
    main()
