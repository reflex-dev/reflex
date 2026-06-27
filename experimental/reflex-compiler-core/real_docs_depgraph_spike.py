"""Fine-grained dependency graph vs coarse epoch, on the real docs app.

Two measurements:

1. DEPENDENCY GRAPH vs EPOCH. Each page's compiled output references the state
   contexts it actually uses (`reflex___state...` identifiers). That's the page's
   real state-dependency set. When ONE state class changes:
     - coarse epoch  -> invalidate ALL pages
     - fine-grained  -> invalidate only pages that reference that state
   We measure, per state class, how many pages actually depend on it.

2. COMPONENT REUSE: static vs dynamic. Walk each render dict, hash every
   subtree, and split by context: a subtree under a cond/iterable/match's
   variable part is "dynamic" (can't be cheaply identified across pages -> just
   re-render it); everything else is "static" (cacheable). Compare the reuse you
   can actually capture (cache static, re-render dynamic) to the 72.7% ceiling.

Run from docs/app (see real_docs_salsa.py header for setup).
"""

import re
import sys
import time
import types
from collections import Counter

import reflex as rx

_rxe = types.ModuleType("reflex_enterprise"); _rxe.App = rx.App
sys.modules["reflex_enterprise"] = _rxe
_pp = types.ModuleType("reflex_pyplot")
class _PyplotStub(rx.Component):
    library = "@stub/pyplot"; tag = "Pyplot"
_pp.pyplot = _PyplotStub.create
sys.modules["reflex_pyplot"] = _pp

from reflex.compiler import compiler  # noqa: E402
import hashlib  # noqa: E402

app = __import__("reflex_docs.reflex_docs", fromlist=["app"]).app
app = getattr(app, "_app", app)
routes = list(app._unevaluated_pages)

STATE_RE = re.compile(r"reflex___state[A-Za-z0-9_]+")


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def subtree_hashes(node, dynamic, static_acc, dyn_acc):
    """Hash subtrees; route each to static or dynamic bucket by context."""
    acc = dyn_acc if dynamic else static_acc
    if isinstance(node, str):
        h = sha(node); acc.append(h); return h
    if not isinstance(node, dict):
        h = sha(repr(node)); acc.append(h); return h
    parts = [str(node.get("name")), "|".join(map(str, node.get("props", [])))]
    for k in ("contents", "cond_state", "iterable_state", "cond"):
        if k in node:
            parts.append(f"{k}={node[k]}")
    # children of an iterable/match, and cond branches, are dynamic context
    is_dyn_container = ("iterable" in node) or ("match_cases" in node) or ("cond_state" in node)
    child_dynamic = dynamic or is_dyn_container
    for child in node.get("children", []):
        parts.append(subtree_hashes(child, child_dynamic, static_acc, dyn_acc))
    for tv in ("true_value", "false_value", "default"):
        if tv in node:
            parts.append(subtree_hashes(node[tv], child_dynamic, static_acc, dyn_acc))
    h = sha("\x1f".join(parts)); acc.append(h); return h


def reuse(hashes):
    total, unique = len(hashes), len(set(hashes))
    return total, unique, (100 * (total - unique) / total if total else 0.0)


def main():
    page_states: dict[str, set] = {}
    static_h, dyn_h = [], []
    ok = 0
    t0 = time.perf_counter()
    for r in routes:
        try:
            ev = app._unevaluated_pages[r]
            comp = ev.component
            tree = comp() if callable(comp) else comp
            out = compiler._compile_page(tree)
            page_states[r] = set(STATE_RE.findall(out))
            subtree_hashes(tree.render(), False, static_h, dyn_h)
            ok += 1
        except Exception:
            pass
    print(f"compiled {ok} pages in {time.perf_counter()-t0:.1f}s\n")

    # --- 1. dependency graph vs coarse epoch ---
    state_to_pages = Counter()
    for states in page_states.values():
        for s in states:
            state_to_pages[s] += 1
    n = ok
    print("DEPENDENCY GRAPH vs COARSE EPOCH (invalidation on a single state change):")
    print(f"  pages: {n}   distinct state contexts: {len(state_to_pages)}")
    if state_to_pages:
        deps = sorted(state_to_pages.values(), reverse=True)
        import statistics
        print(f"  pages invalidated by changing ONE state class:")
        print(f"    coarse epoch : {n} (always all)")
        print(f"    fine-grained : max={deps[0]}  median={int(statistics.median(deps))}  min={deps[-1]}")
        # total rebuilds if each state class changed once
        coarse_total = len(state_to_pages) * n
        fine_total = sum(deps)
        print(f"    if each of the {len(state_to_pages)} state classes changed once:")
        print(f"      coarse = {coarse_total} page-rebuilds;  fine = {fine_total}  ({coarse_total/max(fine_total,1):.1f}x fewer)")
    # how many pages use NO state (pure static -> never invalidated by state)
    stateless = sum(1 for s in page_states.values() if not s)
    print(f"  stateless pages (a state change never touches them): {stateless}/{n}\n")

    # --- 2. component reuse: static vs dynamic ---
    st, su, sp = reuse(static_h)
    dt, du, dp = reuse(dyn_h)
    allt, allu, allp = reuse(static_h + dyn_h)
    print("COMPONENT REUSE (cache static subtrees, re-render cond/foreach/match):")
    print(f"  all subtrees     : {allt:7d} total, {allp:4.1f}% redundant (ceiling)")
    print(f"  static (cacheable): {st:7d} total, {sp:4.1f}% redundant  <- reuse we can capture")
    print(f"  dynamic (re-render): {dt:7d} total, {dp:4.1f}% redundant  <- left on the table")
    captured = (st - su)
    ceiling = (allt - allu)
    print(f"  redundant compiles removed: {captured}/{ceiling} = {100*captured/max(ceiling,1):.0f}% of the ceiling")


if __name__ == "__main__":
    main()
