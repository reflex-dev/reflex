#!/usr/bin/env bash

set -euxo pipefail

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
export TELEMETRY_ENABLED=false

function do_export () {
    template=$1
    mkdir ~/"$template"
    cd ~/"$template"
    rm -rf ~/.local/share/reflex ~/"$template"/.web
    reflex init --template "$template"
    reflex export
    (
        cd "$SCRIPTPATH/../../.."
        scripts/integration.sh ~/"$template" dev
        pkill -9 -f 'next-server|python3' || true
        sleep 10
        REDIS_URL=redis://localhost scripts/integration.sh ~/"$template" prod
        pkill -9 -f 'next-server|python3' || true
        sleep 10
    )
}

echo "Preparing test project dir"
python3 -m venv ~/venv
source ~/venv/bin/activate
pip install -U pip

echo "Installing reflex from local repo code"
pip install /reflex-repo

redis-server &

echo "Running reflex init in test project dir"
do_export blank
