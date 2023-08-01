#!/bin/bash

# Change directory to the first argument passed to the script
pushd "$1" || exit 1
echo "Changed directory to $1"

# So we get stdout / stderr from Python ASAP. Without this, delays can be very long (e.g. on Windows, Github Actions)
export PYTHONUNBUFFERED=1

# Start the server in the background
reflex run --loglevel debug --env "$2" & pid=$!

# Within the context of this bash, $pid_in_bash is what we need to pass to "kill" on exit
# This is true on all platforms.
pid_in_bash=$pid
trap "kill -INT $pid_in_bash ||:" EXIT

echo "Started server with PID $pid"

# Assume we run from the root of the repo
popd

# In Windows, our Python script below needs to work with the WINPID
if [ -f /proc/$pid/winpid ]; then
  pid=$(cat /proc/$pid/winpid)
  echo "Windows detected, passing winpid $pid to port waiter"
fi

python scripts/wait_for_listening_port.py 3000 8000 --timeout=600 --server-pid "$pid"