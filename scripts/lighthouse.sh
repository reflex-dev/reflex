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
nextpy run --loglevel debug --env "$env_mode" "$@" & pid=$!

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

# Change to .web directory
project_dir=$1
shift
pushd "$project_dir" || exit 1
echo "Changed directory to $project_dir"
cd .web

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
      target: 'temporary-public-storage',
    },
  },
};
EOF

# Install and Run LHCI
npm install -g @lhci/cli
lhci autorun || echo "LHCI failed!"

#!/bin/bash

# Define the base URL where you want to send the POST requests
base_url="https://app.posthog.com/capture/"

# Directory containing JSON files
json_dir=".lighthouseci"

# API Key
api_key="$POSTHOG"

# Get the current timestamp
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Loop through each JSON file in the directory
for json_file in "$json_dir"/*.json; do
    if [ -f "$json_file" ]; then
        # Extract the file name without the extension
        file_name=$(basename "$json_file" .json)

        # Generate a random distinct_id (a random number)
        distinct_id=$((RANDOM))

        # Read the contents of the JSON file
        json_data=$(cat "$json_file")

        # Construct the event name with the JSON file name
        event="Lighthouse CI - $file_name"

        # Construct the JSON payload with the random distinct_id
        payload="{\"api_key\": \"$api_key\", \"event\": \"$event\", \"timestamp\": \"$timestamp\", \"distinct_id\": $distinct_id, \"properties\": $json_data}"

        # Create a temporary file for the payload
        tmpfile=$(mktemp)

        # Write the payload to the temporary file
        echo "$payload" > "$tmpfile"

        # Send the POST request with the constructed payload using curl
        response=$(curl -X POST -H "Content-Type: application/json" --data @"$tmpfile" "$base_url")

        # Clean up the temporary file
        rm "$tmpfile"

        # Print the response for each file
        echo "Response for $json_file:"
        echo "$response"
    fi
done