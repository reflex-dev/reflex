#!/bin/bash

# Change directory to the first argument passed to the script
project_dir=$1
shift
pushd "$project_dir" || exit 1
echo "Changed directory to $project_dir"

# So we get stdout / stderr from Python ASAP. Without this, delays can be very long (e.g. on Windows, Github Actions)
export PYTHONUNBUFFERED=1

env_mode=$1
shift
check_ports=${1:-3000 8000}
shift

# Start the server in the background
reflex run --loglevel debug --env "$env_mode" "$@" & pid=$!

# TODO does this even work on windows? Not clear, possibly not impactful though.
trap "kill -INT $pid ||:" EXIT

echo "Started server with PID $pid"

# Assume we run from the root of the repo
popd
python scripts/wait_for_listening_port.py $check_ports --timeout=600 --server-pid "$pid"