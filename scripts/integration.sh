#!/bin/bash

# Change directory to the first argument passed to the script
pushd "$1" || exit 1
echo "Changed directory to $1"

# So we get stdout / stderr from Python ASAP. Without this, delays can be very long (e.g. on Windows, Github Actions)
export PYTHONUNBUFFERED=1

# Start the server in the background
reflex run --loglevel debug --env "$2" & pid=$!

# TODO does this even work on windows? Not clear, possibly not impactful though.
trap "kill -INT $pid ||:" EXIT

echo "Started server with PID $pid"

# Assume we run from the root of the repo
popd
python scripts/wait_for_listening_port.py 3000 8000 --timeout=600 --server-pid "$pid"