#!/bin/bash
# Build a third-party auth venv (PyPI only, cwd=$SB, uv --no-config, Python ${PYV:-3.12}) for run_la.sh / run_gauth.sh:
#   build_venvs.sh <venv-name> <reflex spec...>
#   e.g. build_venvs.sh hydration-tp-new 'reflex[db]==0.10.1' 'reflex-base==0.10.1'
#        build_venvs.sh hydration-tp-prev 'reflex[db]==0.10.0'
# Pins: reflex-local-auth 0.5.0, reflex-google-auth 0.2.0, google-api-python-client>=2.184.0, pydantic<2.14 (as in every
# campaign; bump when newer auth releases ship). Add 'greenlet>=3.3' for reflex < 0.10.0a3 (N-001).
. "$(dirname "$0")/env.sh"
cd "$SB" || exit 1
n=$1; shift
TP="reflex-local-auth==0.5.0 reflex-google-auth==0.2.0 google-api-python-client>=2.184.0 pydantic<2.14"
uv --no-config venv --python "${PYV:-3.12}" "$SB/envs/$n" && \
uv --no-config pip install --python "$SB/envs/$n/bin/python" --prerelease=allow "$@" $TP
"$SB/envs/$n/bin/python" -I -c "import importlib.metadata as m; print('$n', *[(p, m.version(p)) for p in ('reflex','reflex-base','reflex-local-auth','reflex-google-auth','sqlmodel','sqlalchemy','greenlet','pydantic')])" 2>&1
