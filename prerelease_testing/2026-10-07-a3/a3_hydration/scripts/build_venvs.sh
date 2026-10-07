#!/bin/bash
# Build the third-party venvs (PyPI only). cwd=$SB, uv --no-config.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
cd $SB
TP="reflex-local-auth==0.5.0 reflex-google-auth==0.2.0 google-api-python-client>=2.184.0 pydantic<2.14"
mk() { # name reflex-spec...
  local n=$1; shift
  uv --no-config venv --python 3.12 $SB/envs/$n && \
  uv --no-config pip install --python $SB/envs/$n/bin/python --prerelease=allow "$@" $TP
  $SB/envs/$n/bin/python -I -c "import importlib.metadata as m; print('$n', *[(p, m.version(p)) for p in ('reflex','reflex-base','reflex-local-auth','reflex-google-auth','sqlmodel','sqlalchemy','greenlet','pydantic')])" 2>&1
}
mk a3_hydration-tp-a3 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3'
mk a3_hydration-tp-a2 'reflex[db]==0.10.0a2' 'reflex-base==0.10.0a2' 'greenlet>=3.3'
mk a3_hydration-tp-s912 'reflex[db]==0.9.12' 'greenlet>=3.3'
