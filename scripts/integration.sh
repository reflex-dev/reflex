  GNU nano 4.8                                                                run_bash.sh                                                                          #!/bin/bash

cd "$1"
curl -fsSL https://bun.sh/install | bash -s -- bun-v0.5.5

set -e
if [ "$2" = "dev" ]; then
  timeout 2m poetry run pc run --env "$2" || exit 0 & sleep 50
else
  timeout 5m poetry run pc run --env "$2" || exit 0 & sleep 250
fi

# set the HOST to request
HOST="127.0.0.1"
FRONTEND_PORT="3000"
API_PORT="8000"

# make the curl request and save the response and HTTP status code
RESPONSE=$(curl -s -w "\n%{http_code}" "$HOST:$FRONTEND_PORT")

# extract the HTTP status code from the response
HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)


# check for errors based on the HTTP status code
if [[ $HTTP_STATUS -ge 400 ]]; then
  echo "Error: HTTP status code $HTTP_STATUS"
  exit 1
fi

# check for errors on API server
API_RESPONSE=$(curl --silent "$HOST:$API_PORT/ping")

if echo "$API_RESPONSE" | grep -q "pong"; then
  echo "success with HTTP STATUS: $HTTP_STATUS"
  exit 0
else
  echo "Error starting API server"
  exit 1
fi

