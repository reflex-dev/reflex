#!/usr/bin/env bash
# Item 2: install / upgrade paths to reflex 0.10.0a3 (PyPI only, uv --no-config, cwd=$SB).
# Usage: install_paths.sh   (writes $W/freeze/ip-*.txt, $W/logs/ip-*.log, summary in $W/logs/ip-summary.txt)
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_upgrade; F=$W/freeze; L=$W/logs; E=$SB/envs
cd $SB
uvx() { uv --no-config "$@" 2>&1 | grep -v UV_NATIVE_TLS; }
mk() { rm -rf $E/$1; uv --no-config venv -q --seed --python ${2:-3.12} $E/$1 2>&1 | grep -v UV_NATIVE_TLS; }
frz() { $E/$1/bin/python -m pip freeze --all 2>/dev/null | grep -v -E '^(pip|setuptools|wheel)==' | sort -f > $F/$2.txt; }
chk() { echo "--- pip check $1:"; $E/$1/bin/python -m pip check 2>&1 | tail -3; }
ver() { (cd /tmp && $E/$1/bin/python -I -c "import importlib.metadata as m
for p in ['reflex','reflex-base','reflex-components-core','reflex-hosting-cli','sqlalchemy','sqlmodel','greenlet','pydantic']:
    try: print(f'{p}={m.version(p)}', end=' ')
    except Exception: print(f'{p}=-', end=' ')
print()"); }
dif() { diff $F/$1.txt $F/$2.txt > $F/$3.diff; echo "--- diff $1 -> $2:"; grep -E '^[<>]' $F/$3.diff | tr '\n' ' '; echo; }
imp() { (cd /tmp && $E/$1/bin/python -I -c "import reflex, reflex.model; print('import reflex.model OK', reflex.__file__)" 2>&1 | tail -1); }

echo "=== A. pip: a2 -> a3 (pip install -U --pre reflex==0.10.0a3)"
mk a3_upgrade-pipa2
$E/a3_upgrade-pipa2/bin/python -m pip install -q 'reflex==0.10.0a2' > $L/ip-pipa2-base.log 2>&1; echo "base rc=$?"
frz a3_upgrade-pipa2 ip-pipa2-base; ver a3_upgrade-pipa2
$E/a3_upgrade-pipa2/bin/python -m pip install --dry-run --report $L/ip-pipa2-dryrun-nopre.json -U 'reflex==0.10.0a3' > $L/ip-pipa2-dryrun-nopre.log 2>&1; echo "dry-run without --pre rc=$?: $(grep -E '^Would install' $L/ip-pipa2-dryrun-nopre.log)"
$E/a3_upgrade-pipa2/bin/python -m pip install -U --pre 'reflex==0.10.0a3' > $L/ip-pipa2-up.log 2>&1; echo "upgrade rc=$?"
frz a3_upgrade-pipa2 ip-pipa2-up; ver a3_upgrade-pipa2; dif ip-pipa2-base ip-pipa2-up ip-pipa2; chk a3_upgrade-pipa2

echo "=== B. uv: a2 -> a3 (uv pip install -U --prerelease=allow reflex==0.10.0a3)"
mk a3_upgrade-uva2
uvx pip install -q --python $E/a3_upgrade-uva2/bin/python --prerelease=allow 'reflex==0.10.0a2' > $L/ip-uva2-base.log; echo "base done"
frz a3_upgrade-uva2 ip-uva2-base; ver a3_upgrade-uva2
uvx pip install --dry-run --python $E/a3_upgrade-uva2/bin/python 'reflex==0.10.0a3' > $L/ip-uva2-dryrun-noprerelease.log; echo "uv dry-run without --prerelease: $(grep -iE 'error|hint|pre-release|Would' $L/ip-uva2-dryrun-noprerelease.log | head -3 | cut -c1-220)"
uvx pip install --dry-run --python $E/a3_upgrade-uva2/bin/python --prerelease=allow 'reflex==0.10.0a3' > $L/ip-uva2-dryrun-noU.log; echo "uv dry-run --prerelease=allow without -U:"; grep -E '^ [-+]' $L/ip-uva2-dryrun-noU.log | tr '\n' ' '; echo
uvx pip install -U --python $E/a3_upgrade-uva2/bin/python --prerelease=allow 'reflex==0.10.0a3' > $L/ip-uva2-up.log; echo "upgrade done"
frz a3_upgrade-uva2 ip-uva2-up; ver a3_upgrade-uva2; dif ip-uva2-base ip-uva2-up ip-uva2; chk a3_upgrade-uva2

echo "=== C. a2[db] without greenlet (N-001 broken) -> a3 with and without the extra (pip)"
mk a3_upgrade-pipa2db
$E/a3_upgrade-pipa2db/bin/python -m pip install -q 'reflex[db]==0.10.0a2' 'pydantic<2.14' > $L/ip-pipa2db-base.log 2>&1; echo "base rc=$?"
frz a3_upgrade-pipa2db ip-pipa2db-base; ver a3_upgrade-pipa2db; imp a3_upgrade-pipa2db
$E/a3_upgrade-pipa2db/bin/python -m pip install -U --pre 'reflex==0.10.0a3' > $L/ip-pipa2db-up-noextra.log 2>&1; echo "upgrade without [db] rc=$?"
frz a3_upgrade-pipa2db ip-pipa2db-up-noextra; ver a3_upgrade-pipa2db; imp a3_upgrade-pipa2db; dif ip-pipa2db-base ip-pipa2db-up-noextra ip-pipa2db-noextra
$E/a3_upgrade-pipa2db/bin/python -m pip install -U --pre 'reflex[db]==0.10.0a3' > $L/ip-pipa2db-up-db.log 2>&1; echo "upgrade with [db] rc=$?"
frz a3_upgrade-pipa2db ip-pipa2db-up-db; ver a3_upgrade-pipa2db; imp a3_upgrade-pipa2db; dif ip-pipa2db-up-noextra ip-pipa2db-up-db ip-pipa2db-db; chk a3_upgrade-pipa2db

echo "=== D. fresh pip install --pre reflex==0.10.0a3"
mk a3_upgrade-pipfresh
$E/a3_upgrade-pipfresh/bin/python -m pip install --pre 'reflex==0.10.0a3' > $L/ip-pipfresh.log 2>&1; echo "rc=$?"
frz a3_upgrade-pipfresh ip-pipfresh; ver a3_upgrade-pipfresh; chk a3_upgrade-pipfresh
echo "pre-release dists in the --pre graph:"; grep -E '(a|b|rc|\.dev)[0-9]+$' $F/ip-pipfresh.txt | tr '\n' ' '; echo
mk a3_upgrade-pipfresh-nopre
$E/a3_upgrade-pipfresh-nopre/bin/python -m pip install 'reflex==0.10.0a3' > $L/ip-pipfresh-nopre.log 2>&1; echo "exact pin without --pre rc=$?"
frz a3_upgrade-pipfresh-nopre ip-pipfresh-nopre; ver a3_upgrade-pipfresh-nopre; dif ip-pipfresh ip-pipfresh-nopre ip-pipfresh-pre-vs-nopre; chk a3_upgrade-pipfresh-nopre

echo "=== E. stock installs without --pre (what a new user gets today)"
mk a3_upgrade-stock
$E/a3_upgrade-stock/bin/python -m pip install 'reflex' > $L/ip-stock.log 2>&1; echo "pip install reflex rc=$?"
frz a3_upgrade-stock ip-stock; ver a3_upgrade-stock
mk a3_upgrade-stockdb
$E/a3_upgrade-stockdb/bin/python -m pip install 'reflex[db]' > $L/ip-stockdb.log 2>&1; echo "pip install reflex[db] rc=$?"
frz a3_upgrade-stockdb ip-stockdb; ver a3_upgrade-stockdb; imp a3_upgrade-stockdb
uvx pip install --dry-run --python $E/a3_upgrade-stock/bin/python 'reflex[db]' > $L/ip-stock-uv-dryrun-db.log; echo "uv (no prerelease) reflex[db] dry-run: $(grep -E 'reflex==|sqlalchemy|greenlet' $L/ip-stock-uv-dryrun-db.log | tr '\n' ' ')"
echo "=== done $(date +%T)"
