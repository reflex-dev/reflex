#!/usr/bin/env bash
# In-place install / upgrade paths BASE_VERSION -> NEW_VERSION (no app; PyPI only). Venvs $SB/envs/$VENV_PREFIX-ip-<key>, py ${PY:-3.12}.
#   A pip  : 'reflex==BASE' -> pip install -U [--pre] 'reflex==NEW'   (+ a dry-run without --pre)
#   B uv   : 'reflex==BASE' -> uv pip install -U [--prerelease=allow] 'reflex==NEW' (+ dry-runs without the flag / without -U)
#   C pip  : 'reflex[db]==BASE' -> -U 'reflex==NEW' (extra NOT re-requested: pip does not remember extras) -> -U 'reflex[db]==NEW'
#   D fresh: pip install 'reflex==NEW' with and without --pre (identical graphs expected = F-006)
# Expected (a3 pass, a2 -> a3; 0.10.0 final behaves the same way): only the train packages that changed move, pip check clean;
# C without the extra keeps the old db deps (greenlet is only added when [db] is re-requested). Freeze files -> inst/freeze/ip-*.txt
set -u; . "$(dirname "$0")/../../bin/env.sh"; I=$(cd "$(dirname "$0")/.." && pwd); F=$I/freeze; L=$I/logs; mkdir -p "$F" "$L"; cd "$SB"
B=$BASE_VERSION; N=$NEW_VERSION; PRE=$(case $N in *a*|*b*|*rc*|*dev*) echo --pre;; esac)
E() { echo "$SB/envs/$VENV_PREFIX-ip-$1"; }
mk() { rm -rf "$(E $1)"; uvq venv -q --seed --python "${PY:-3.12}" "$(E $1)"; }
pip_() { local k=$1; shift; "$(E $k)/bin/python" -m pip --disable-pip-version-check "$@"; }
frz() { pip_ $1 freeze --all 2>/dev/null | grep -v -E '^(pip|setuptools|wheel)==' | sort -f > "$F/$2.txt"; }
dif() { diff "$F/$1.txt" "$F/$2.txt" > "$F/$3.diff"; echo "  diff $1 -> $2: $(grep -E '^[<>]' "$F/$3.diff" | tr '\n' ' ')"; }
imp() { "$(E $1)/bin/python" -I -c "import reflex.model; print('  import reflex.model OK')" 2>&1 | tail -1; }
chk() { echo "  pip check: $(pip_ $1 check 2>&1 | tail -1)"; }
echo "=== A. pip: $B -> $N"; mk pip
pip_ pip install -q "reflex==$B" > "$L/ip-pip-base.log" 2>&1; echo "  base rc=$?"; frz pip ip-pip-base
pip_ pip install --dry-run -U "reflex==$N" > "$L/ip-pip-dryrun-nopre.log" 2>&1; echo "  dry-run without --pre: $(grep -E '^Would install' "$L/ip-pip-dryrun-nopre.log" | cut -c1-300)"
pip_ pip install -U $PRE "reflex==$N" > "$L/ip-pip-up.log" 2>&1; echo "  upgrade rc=$?"; frz pip ip-pip-up; dif ip-pip-base ip-pip-up ip-pip; chk pip
echo "=== B. uv: $B -> $N"; mk uv; UVP=$(E uv)/bin/python
uvq pip install -q --python "$UVP" $(pre_flag "$B") "reflex==$B" > "$L/ip-uv-base.log"; frz uv ip-uv-base
echo "  uv dry-run without a prerelease flag: $(uvq pip install --dry-run --python "$UVP" "reflex==$N" | grep -iE 'error|hint|pre-release|Would' | head -2 | tr '\n' ' ' | cut -c1-240)"
echo "  uv dry-run without -U: $(uvq pip install --dry-run --python "$UVP" $(pre_flag "$N") "reflex==$N" | grep -E '^ [-+]' | tr '\n' ' ')"
uvq pip install -U --python "$UVP" $(pre_flag "$N") "reflex==$N" > "$L/ip-uv-up.log"; frz uv ip-uv-up; dif ip-uv-base ip-uv-up ip-uv; chk uv
echo "=== C. pip: reflex[db]==$B -> reflex==$N (no extra) -> reflex[db]==$N"; mk pipdb
pip_ pipdb install -q "reflex[db]==$B" ${BASE_EXTRA:-} > "$L/ip-pipdb-base.log" 2>&1; frz pipdb ip-pipdb-base; imp pipdb
pip_ pipdb install -U $PRE "reflex==$N" > "$L/ip-pipdb-noextra.log" 2>&1; frz pipdb ip-pipdb-noextra; imp pipdb; dif ip-pipdb-base ip-pipdb-noextra ip-pipdb-noextra
pip_ pipdb install -U $PRE "reflex[db]==$N" > "$L/ip-pipdb-db.log" 2>&1; frz pipdb ip-pipdb-db; imp pipdb; dif ip-pipdb-noextra ip-pipdb-db ip-pipdb-db; chk pipdb
echo "=== D. fresh pip install reflex==$N, with and without --pre"; mk fresh; mk freshnopre
pip_ fresh install -q --pre "reflex==$N" > "$L/ip-fresh.log" 2>&1; frz fresh ip-fresh
pip_ freshnopre install -q "reflex==$N" > "$L/ip-freshnopre.log" 2>&1; frz freshnopre ip-freshnopre; dif ip-fresh ip-freshnopre ip-fresh-pre-vs-nopre
echo "  pre-releases in the graph: $(grep -E '(a|b|rc|\.dev)[0-9]+$' "$F/ip-freshnopre.txt" | tr '\n' ' ')"; chk freshnopre
