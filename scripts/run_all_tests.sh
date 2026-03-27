#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

show_help() {
  cat <<'EOF'
Usage: bash scripts/run_all_tests.sh [act args]

Run selected Reflex GitHub Actions jobs locally with `act`.

Examples:
  bash scripts/run_all_tests.sh
  bash scripts/run_all_tests.sh -l

Environment:
  ACT_BIN=/path/to/act                      Override the `act` binary.
  REFLEX_ACT_EVENT=pull_request            Override the event passed to `act`.
  REFLEX_ACT_UNIT_TESTS_PYTHON_VERSION=3.13
  REFLEX_ACT_INTEGRATION_PYTHON_VERSION=3.13
  REFLEX_ACT_INTEGRATION_STATE_MANAGER=memory
  REFLEX_ACT_PLATFORM_LATEST=...
  REFLEX_ACT_PLATFORM_22_04=...
  REFLEX_ACT_ALLOW_SELF_HOSTED=1           Run on the host when Docker is unavailable.
  REFLEX_ACT_SELF_HOSTED_PRESERVE_HOST_ENV=1
                                            Keep host-only env vars in self-hosted mode.
  REFLEX_ACT_SKIP_BENCHMARKS=1             Skip the benchmark workflow.
EOF
}

has_arg() {
  local needle="$1"
  shift
  local arg

  for arg in "$@"; do
    if [[ "$arg" == "$needle" ]]; then
      return 0
    fi
  done

  return 1
}

is_list_mode() {
  local arg

  for arg in "$@"; do
    case "$arg" in
      -l|--list|--list-options)
        return 0
        ;;
    esac
  done

  return 1
}

ensure_act() {
  local resolved_act_bin=""

  if [[ -n "$ACT_BIN" ]]; then
    # Resolve bare command names through PATH before validating executability.
    resolved_act_bin="$(command -v "$ACT_BIN" 2>/dev/null || true)"

    if [[ -n "$resolved_act_bin" && -x "$resolved_act_bin" ]]; then
      ACT_BIN="$resolved_act_bin"
      return 0
    fi
  fi

  cat >&2 <<'EOF'
Error: act is required to run the local CI workflow script.

Install it from https://nektosact.com/installation/ or set ACT_BIN to an existing binary.
EOF
  exit 1
}

docker_daemon_available() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

self_hosted_mode_enabled() {
  [[ "${REFLEX_ACT_ALLOW_SELF_HOSTED:-0}" == "1" ]]
}

require_runner_support() {
  if is_list_mode "${extra_act_args[@]+"${extra_act_args[@]}"}"; then
    return 0
  fi

  if docker_daemon_available || self_hosted_mode_enabled; then
    return 0
  fi

  cat >&2 <<'EOF'
Error: Docker is required to run Reflex GitHub Actions locally with act.

Use `bash scripts/run_all_tests.sh -l` to list the selected jobs without running them,
or set REFLEX_ACT_ALLOW_SELF_HOSTED=1 to execute directly on the host with lower CI parity.
EOF
  exit 1
}

configure_platform_args() {
  local latest_platform
  local ubuntu_2204_platform

  if self_hosted_mode_enabled; then
    latest_platform="${REFLEX_ACT_PLATFORM_LATEST:--self-hosted}"
    ubuntu_2204_platform="${REFLEX_ACT_PLATFORM_22_04:--self-hosted}"
    echo "Warning: Docker unavailable or bypassed; using self-hosted act platform mapping." >&2
  else
    latest_platform="${REFLEX_ACT_PLATFORM_LATEST:-catthehacker/ubuntu:full-latest}"
    ubuntu_2204_platform="${REFLEX_ACT_PLATFORM_22_04:-catthehacker/ubuntu:full-22.04}"
  fi

  platform_args=(
    -P "ubuntu-latest=${latest_platform}"
    -P "ubuntu-22.04=${ubuntu_2204_platform}"
  )
}

configure_self_hosted_env() {
  if ! self_hosted_mode_enabled; then
    return 0
  fi

  if [[ "${REFLEX_ACT_SELF_HOSTED_PRESERVE_HOST_ENV:-0}" == "1" ]]; then
    echo "Warning: preserving host environment in self-hosted mode." >&2
    return 0
  fi

  # Keep host-specific shell state from leaking into workflow behavior.
  act_env_prefix=(
    env
    -u CODESPACE_NAME
    -u GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN
    -u GITHUB_CODESPACE_TOKEN
    -u PYTHONSAFEPATH
  )

  echo "Warning: self-hosted mode scrubs Codespaces and PYTHONSAFEPATH env vars for better CI parity." >&2

  if [[ "$(id -u)" == "0" ]]; then
    cat >&2 <<'EOF'
Warning: browser-based workflows may still fail as root.
Use a non-root environment for best parity. If you stay on root, try APP_HARNESS_DRIVER_ARGS=--no-sandbox as a local-only fallback.
EOF
  fi
}

run_job() {
  local workflow="$1"
  local job="$2"
  local label="$3"
  shift 3

  echo "==> ${label}"
  "${act_env_prefix[@]+"${act_env_prefix[@]}"}" "${ACT_BIN}" \
    "${ACT_EVENT}" \
    "${platform_args[@]}" \
    -W ".github/workflows/${workflow}" \
    -j "${job}" \
    "$@" \
    "${extra_act_args[@]+"${extra_act_args[@]}"}"
}

if has_arg "-h" "$@" || has_arg "--help" "$@"; then
  show_help
  exit 0
fi

ACT_BIN="${ACT_BIN:-$(command -v act || true)}"
ACT_EVENT="${REFLEX_ACT_EVENT:-pull_request}"
extra_act_args=("$@")
act_env_prefix=()
platform_args=()

ensure_act
require_runner_support
configure_platform_args
configure_self_hosted_env

cd "$repo_root"

run_job \
  "unit_tests.yml" \
  "unit-tests" \
  "unit-tests (ubuntu-latest, python ${REFLEX_ACT_UNIT_TESTS_PYTHON_VERSION:-3.13})" \
  --matrix "os:ubuntu-latest" \
  --matrix "python-version:${REFLEX_ACT_UNIT_TESTS_PYTHON_VERSION:-3.13}"

for split_index in 1 2; do
  run_job \
    "integration_app_harness.yml" \
    "integration-app-harness" \
    "integration-app-harness (python ${REFLEX_ACT_INTEGRATION_PYTHON_VERSION:-3.13}, ${REFLEX_ACT_INTEGRATION_STATE_MANAGER:-memory}, split ${split_index})" \
    --matrix "python-version:${REFLEX_ACT_INTEGRATION_PYTHON_VERSION:-3.13}" \
    --matrix "state_manager:${REFLEX_ACT_INTEGRATION_STATE_MANAGER:-memory}" \
    --matrix "split_index:${split_index}"
done

if [[ "${REFLEX_ACT_SKIP_BENCHMARKS:-0}" != "1" ]]; then
  run_job \
    "performance.yml" \
    "benchmarks" \
    "benchmarks"
fi

for split_index in 1 2; do
  run_job \
    "check_node_latest.yml" \
    "check_latest_node" \
    "check-node-latest (split ${split_index})" \
    --matrix "split_index:${split_index}"
done
