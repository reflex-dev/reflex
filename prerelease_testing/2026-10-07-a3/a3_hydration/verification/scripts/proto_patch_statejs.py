"""EXPERIMENT ONLY (validates where a fix belongs; not a proposed patch): rewrite the COMPILED .web/utils/state.js of a
scratch app run dir (never the package or the checkout) with two guards for sync=True LocalStorage keys:
  (A3-11) a boot echo whose value equals what this tab read for its hydrate payload is not written back (one-shot);
  (A3-12) the storage handler syncs the CURRENT localStorage value, and the backend's answer to that sync is not
          written back to localStorage.
Usage: proto_patch_statejs.py <path to .web/utils/state.js> [boot-only]   (boot-only: just the A3-11 guard)"""
import sys

p = sys.argv[1]
s = open(p).read()
assert "__vhProto" not in s, "already patched"


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:60], s.count(old))
    s = s.replace(old, new)


rep("export const hydrateClientStorage = (client_storage) => {\n  const client_storage_values = {};",
    "let __vhProtoBootSent = null;\nconst __vhProtoFromStorage = {};\n"
    "export const hydrateClientStorage = (client_storage) => {\n  const client_storage_values = {};\n"
    "  __vhProtoBootSent = client_storage_values;")
rep("""        const options = client_storage.local_storage[state_key];
        localStorage.setItem(options.name || state_key, delta[substate][key]);""",
    """        const options = client_storage.local_storage[state_key];
        const __name = options.name || state_key;
        const __v = delta[substate][key];
        if (options.sync && boot && boot[state_key] === __v) continue;  // A3-11: unchanged boot echo
        const __pend = __vhProtoFromStorage[__name];
        const __i = options.sync && __pend ? __pend.indexOf(__v) : -1;
        if (__i >= 0) {
          __pend.splice(__i, 1);  // A3-12: answer to one of this tab's storage syncs
          continue;
        }
        localStorage.setItem(__name, __v);""")
rep("""  // Save known client storage values to cookies and localStorage.
  for (const substate in delta) {""", """  // Save known client storage values to cookies and localStorage.
  const boot = __vhProtoBootSent;
  __vhProtoBootSent = null;
  for (const substate in delta) {""")
rep("""        const vars = {};
        vars[storage_to_state_map[e.key]] = e.newValue;""", """        const vars = {};
        const __cur = localStorage.getItem(e.key);
        (__vhProtoFromStorage[e.key] ??= []).push(__cur);
        vars[storage_to_state_map[e.key]] = __cur;""")
if len(sys.argv) > 2 and sys.argv[2] == "boot-only":
    s = s.replace("(__vhProtoFromStorage[e.key] ??= []).push(__cur);", "")
    s = s.replace("vars[storage_to_state_map[e.key]] = __cur;", "vars[storage_to_state_map[e.key]] = e.newValue;")
open(p, "w").write(s)
print("patched", p, sys.argv[2:] or "both guards")
