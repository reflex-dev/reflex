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
export REFLEX_TELEMETRY_ENABLED=false
reflex run --loglevel debug --env "$env_mode" "$@" & pid=$!

# Within the context of this bash, $pid_in_bash is what we need to pass to "kill" on exit
# This is true on all platforms.
pid_in_bash=$pid
cleanup() {
  kill -INT $pid_in_bash ||:
  # Wait for the process to exit so it releases file locks (important on Windows)
  for i in $(seq 1 10); do
    kill -0 $pid_in_bash 2>/dev/null || return 0
    sleep 1
  done
  # Force kill if still alive
  kill -9 $pid_in_bash 2>/dev/null ||:
  sleep 1
}
trap cleanup EXIT

echo "Started server with PID $pid"

# Assume we run from the root of the repo
popd

# In Windows, our Python script below needs to work with the WINPID
if [ -f /proc/$pid/winpid ]; then
  pid=$(cat /proc/$pid/winpid)
  echo "Windows detected, passing winpid $pid to port waiter"
fi

python scripts/wait_for_listening_port.py $check_ports --timeout=900 --server-pid "$pid"
