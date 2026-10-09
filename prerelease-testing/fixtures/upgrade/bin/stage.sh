#!/usr/bin/env bash
# Stage the `upgrade` area into the work dir $W and fetch the upstream app sources at their pinned commits.
#   - copies this fixture tree to $W (apps get .web/, dbs, logs there, never inside the repo checkout)
#   - reflex-examples apps   -> $W/up/apps/<app>   (git archive of $EXAMPLES_COMMIT, QA patches applied, rxconfig venv guard)
#   - third-party demo apps  -> $W/tp/apps/<demo>  (git archive of the pinned commit, tp/patches applied)
# Sources: an existing clone ($EXAMPLES_SRC, $TP_SRC/<repo>) or `git clone` from GitHub into $SB/downloads.
# Usage: bin/stage.sh [--no-fetch]      (re-running refreshes the fixtures; app dirs are re-extracted, so .web/ etc. are lost)
set -eu
. "$(dirname "$0")/env.sh"
EXAMPLES_COMMIT=${EXAMPLES_COMMIT:-ebe19ff00dfee36f9d67a9a584840c6745950b05}
EXAMPLES_SRC=${EXAMPLES_SRC:-$SB/downloads/reflex-examples}
EXAMPLES=${EXAMPLES:-form-designer github-stats twitter clock counter todo traversal json-tree reflexle lorem-stream local-component nba quiz snakegame upload}
TP_SRC=${TP_SRC:-$SB/downloads}
# demo app : repo : commit  (the PyPI packages they exercise are pinned in tp/packages.txt)
TP_DEMOS=${TP_DEMOS:-"local_auth_demo:reflex-local-auth:a61d50d813b4a83e4f67d61641a48babed53dab2 magic_link_auth_demo:reflex-magic-link-auth:352c675b2feb34ba56c897b2041e68adf359f218 google_auth_demo:reflex-google-auth:753a029830c5a4ba5afc3676e2a18e2c2c96f9ef"}

mkdir -p "$W"
(cd "$UPG_ROOT" && tar --exclude=README.md --exclude=__pycache__ -cf - .) | tar -xf - -C "$W"
echo "staged fixtures: $UPG_ROOT -> $W"
[ "${1:-}" = --no-fetch ] && exit 0

ensure_clone() { # ensure_clone <dir> <url> <commit>
  [ -d "$1/.git" ] || git clone -q "$2" "$1"
  git -C "$1" cat-file -e "$3^{commit}" 2>/dev/null || git -C "$1" fetch -q origin
}
guard_rxconfig() { # venv guard: QA_EXPECT_VENV=<venv name> makes the app refuse to run from another venv
  grep -q QA_EXPECT_VENV "$1" && return 0
  "$DPY" -I - "$1" <<'EOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
g = ('import os as _qa_os\n\n_qa_ev = _qa_os.environ.get("QA_EXPECT_VENV")\n'
     'if _qa_ev:  # QA venv guard\n    assert f"/envs/{_qa_ev}/" in rx.__file__, rx.__file__\n')
s = s.replace("import reflex as rx\n", "import reflex as rx\n" + g, 1)
p.write_text(s)
EOF
}

ensure_clone "$EXAMPLES_SRC" https://github.com/reflex-dev/reflex-examples "$EXAMPLES_COMMIT"
mkdir -p "$W/up/apps"
for app in $EXAMPLES; do
  rm -rf "${W:?}/up/apps/$app"
  git -C "$EXAMPLES_SRC" archive "$EXAMPLES_COMMIT" "$app" | tar -x -C "$W/up/apps"
  guard_rxconfig "$W/up/apps/$app/rxconfig.py"
done
for p in "$W"/examples/patches/*.diff; do
  app=$(sed -n 's#^+++ b/\([^/]*\)/.*#\1#p' "$p" | head -1)
  [ -d "$W/up/apps/$app" ] && { patch -s -d "$W/up/apps" -p1 < "$p" && echo "patched $app <- $(basename "$p")"; }
done
# twitter prod + Redis runs on its own copy so the dev (disk state) run keeps its own db
if [ -d "$W/up/apps/twitter" ]; then rm -rf "$W/up/apps/twitter-redis"; cp -r "$W/up/apps/twitter" "$W/up/apps/twitter-redis"; fi
echo "reflex-examples @ $EXAMPLES_COMMIT -> $W/up/apps: $EXAMPLES"

mkdir -p "$W/tp/apps"
for spec in $TP_DEMOS; do
  IFS=: read -r demo repo commit <<< "$spec"
  ensure_clone "$TP_SRC/$repo" "https://github.com/masenf/$repo" "$commit"
  rm -rf "${W:?}/tp/apps/$demo"
  git -C "$TP_SRC/$repo" archive "$commit" "$demo" | tar -x -C "$W/tp/apps"
  patch -s -d "$W/tp/apps" -p1 < "$W/tp/patches/$demo.diff"
  echo "tp demo $demo <- $repo @ ${commit:0:9} (+ tp/patches/$demo.diff)"
done
