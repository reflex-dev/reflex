# Shared settings for the class_state fixtures. Source it: `. "<area>/env.sh"` (the bin/ scripts do it themselves).
# Every value can be overridden from the environment.
CS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"            # this fixture area (read-only source)
: "${SB:?export SB=<scratch root holding envs/ apps/ downloads/; see prerelease-testing/scripts/bootstrap_envs.sh>}"  # scratch root ($SB/envs, $SB/downloads)
: "${NEW:=class_state-new}"          # venv name (under $SB/envs) of the version under test; needs pytest (build_venvs.sh)
: "${PREV:=class_state-prev}"            # venv name of the previous release (N-004 interchange, baselines)
: "${CTRL:=}"                         # optional positive-control venv (a version a finding was broken on)
: "${DRIVER:=driver}"                 # playwright venv for the browser drivers
: "${FP:=3300}"                       # frontend port (dev); the area owns 3300-3339 / 8300-8339
: "${BP:=8300}"                       # backend port (dev)
: "${REDIS_PORT:=8309}"               # redis for prod + Redis runs and the N-004 chains
: "${W:=$SB/apps/class_state}"        # work dir: app copies, pids, logs, out
export CS SB NEW PREV CTRL DRIVER FP BP REDIS_PORT W
export REFLEX_TELEMETRY_ENABLED=false
mkdir -p "$W/pids" "$W/logs" "$W/out" "$W/run"
CLIENT_ENV="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"   # prefix for browser drivers only, never for servers
