#!/bin/bash

# Change directory to the first argument passed to the script
cd "$1" || exit 1
echo "Changed directory to $1"

# Start the server in the background
poetry run pc run --env "$2" & pid=$!
echo "Started server with PID $pid"

# Wait for ports 3000 and 8000 to become available
wait_time=0
while ! nc -z localhost 3000 || ! lsof -i :8000 >/dev/null; do
  if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "Error: Server process with PID $pid exited early"
      break
  fi
  if ((wait_time >= 500)); then
    echo "Error: Timeout waiting for ports 3000 and 8000 to become available"
    exit 1
  fi
  sleep 5
  ((wait_time += 5))
  echo "Waiting for ports 3000 and 8000 to become available (waited $wait_time seconds)..."
done

# Check if the server is still running
if kill -0 "$pid" >/dev/null 2>&1; then
  echo "Integration test passed"
  kill -TERM $(pgrep -P "$pid")
  exit 0
else
  echo "Integration test failed"
  exit 1
fi