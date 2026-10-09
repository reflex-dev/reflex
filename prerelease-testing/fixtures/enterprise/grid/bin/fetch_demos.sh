#!/usr/bin/env bash
# Copy the reflex-enterprise demo apps into $WORK/grid/demos/ (never into the repo) and apply our QA overlays:
#   ag_grid + demo_overlay/ag_grid/qa_extras.py (/qa-grid-memo, /qa-grid-props, /qa-model-workaround)
#   mantine + demo_overlay/mantine/qa_mantine.py (/qa-mantine), highcharts + demo_overlay/highcharts/qa_highcharts.py (/qa)
#   dnd, flow, map, tickets unchanged.
# The demos are NOT in the published wheel: they live in the private repo github.com/reflex-dev/reflex-enterprise under demos/
# (check out the tag of the enterprise release under test). Usage: fetch_demos.sh [<enterprise checkout>, default $ENT_REPO or /home/user/reflex-enterprise] [demo...]
. "$(dirname "$0")/../../lib.sh"; W=$WORK/grid
R=${ENT_REPO:-/home/user/reflex-enterprise}; [ -d "${1:-}" ] && { R=$1; shift; }
[ -d "$R/demos" ] || { echo "no reflex-enterprise checkout at $R (gh repo clone reflex-dev/reflex-enterprise)"; exit 1; }
DEMOS=${*:-ag_grid dnd flow mantine map highcharts tickets}
overlay() {  # <demo> <qa module> <import line>
  cp "$FX/grid/demo_overlay/$1/$2.py" "$W/demos/$1/$1/$2.py"
  # insert after the module's last top-level relative import (the demo registry is iterated later in the module)
  python3 -I -c 'import sys,re; p,line=sys.argv[1],sys.argv[2]; L=open(p).read().split("\n")
if not any(l.startswith(line.split(" import")[0]+" import") for l in L):
    i=max([n for n,l in enumerate(L) if re.match(r"from \.\w* import", l)] or [len(L)-1]); L.insert(i+1, line+"  # noqa: F401  QA overlay (fixtures/enterprise/grid/demo_overlay)"); open(p,"w").write("\n".join(L))' \
    "$W/demos/$1/$1/$1.py" "$3"
}
for d in $DEMOS; do
  rm -rf "$W/demos/$d"; mkdir -p "$W/demos/$d"
  (cd "$R/demos/$d" && tar --exclude=.web --exclude=__pycache__ --exclude='*.db' -cf - .) | (cd "$W/demos/$d" && tar -xf -)
  case $d in
    ag_grid) overlay ag_grid qa_extras "from .qa_extras import qa_grid_memo_page, qa_grid_props_page, qa_model_workaround_page";;
    mantine) overlay mantine qa_mantine "from .qa_mantine import qa_mantine_page";;
    highcharts) overlay highcharts qa_highcharts "from .qa_highcharts import qa_page";;
  esac
  echo "fetched $d"
done
echo "enterprise demos rev: $(git -C "$R" log -1 --format='%h %cd %D' 2>/dev/null)"
