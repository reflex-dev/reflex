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
if [ "$env_mode" = "prod" ]; then
  check_ports=${1:-3000}
else
  check_ports=${1:-3000 8000}
fi
shift

# Start the server in the background
export REFLEX_TELEMETRY_ENABLED=false
reflex run --loglevel debug --env "$env_mode" "$@" & pid=$!

# Within the context of this bash, $pid_in_bash is what we need to pass to "kill" on exit
# This is true on all platforms.
pid_in_bash=$pid

echo "Started server with PID $pid"

# Assume we run from the root of the repo
popd

# In Windows, our Python script below needs to work with the WINPID
is_windows=false
if [ -f /proc/$pid/winpid ]; then
  winpid=$(cat /proc/$pid/winpid)
  is_windows=true
  echo "Windows detected, passing winpid $winpid to port waiter"
  pid=$winpid
fi

cleanup() {
  if [ "$is_windows" = true ]; then
    # Use taskkill to kill the entire process tree on Windows,
    # so that reflex.exe and child processes release their file locks.
    taskkill //F //T //PID $winpid 2>/dev/null ||:
  else
    kill -INT $pid_in_bash ||:
  fi
}
trap cleanup EXIT

python scripts/wait_for_listening_port.py $check_ports --timeout=900 --server-pid "$pid"
