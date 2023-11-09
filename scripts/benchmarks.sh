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
export TELEMETRY_ENABLED=false
reflex run --env "$env_mode" "$@" & pid=$!

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

python scripts/wait_for_listening_port.py $check_ports --timeout=600 --server-pid "$pid"


# Check if something is running on port 3000
if curl --output /dev/null --silent --head --fail "http://localhost:3000"; then
  echo "URL exists: http://localhost:3000"
else
  echo "URL does not exist: https://localhost:3000"
fi

mkdir -p ./tests/benchmarks/.lighthouseci

# Create a lighthouserc.js file
cat << EOF > lighthouserc.js
module.exports = {
  ci: {
    collect: {
     isSinglePageApplication: true,
     numberOfRuns: 1,
     url: ['http://localhost:3000', "http://localhost:3000/docs/getting-started/introduction/", "http://localhost:3000/blog/2023-08-02-seed-annoucement/"]
    },
    upload: {
      target: 'filesystem',
      "outputDir": "./integration/benchmarks/.lighthouseci"
    },
  },
};
EOF

# Install and Run LHCI
npm install -g @lhci/cli
lhci autorun

# Check to see if the LHCI report is generated
if [ -d "./integration/benchmarks/.lighthouseci" ] && [ "$(ls -A ./integration/benchmarks/.lighthouseci)" ]; then
  echo "LHCI report generated"
else
  echo "LHCI report not generated"
  exit 1 # Exits the script with a status of 1, which will cause the GitHub Action to stop
fi