// React Compiler coverage audit over a generated .web tree (verify_fh / FS-2).
// Usage (run with cwd = the app's .web so the installed @babel/core + plugin resolve):
//   node /path/rc_audit.mjs <webdir> [--verbose]
// Runs babel-plugin-react-compiler with the SAME options as reflex's
// vite-plugin-react-compiler.js over every app/, app_components/, utils/components/
// *.js[x] file, using the plugin's `logger` option to record one event per function
// (CompileSuccess / CompileError / CompileSkip ...). Prints a per-file summary and a
// reason histogram; --verbose prints every bail-out with the function name and the
// first offending line.
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const web = path.resolve(process.argv[2]);
const verbose = process.argv.includes("--verbose");
const req = createRequire(path.join(web, "package.json"));
const { transformAsync } = req("@babel/core");
const reactCompiler = req("babel-plugin-react-compiler").default ?? req("babel-plugin-react-compiler");

const SCOPE = /^(?:app|app_components|utils\/components)\/.*\.[cm]?jsx?$/;
function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (name === "node_modules") continue;
    if (statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}
const files = walk(web)
  .map((f) => path.relative(web, f).split(path.sep).join("/"))
  .filter((rel) => SCOPE.test(rel))
  .sort();

const hist = {};
const rows = [];
let totalFns = 0, totalOk = 0, totalBail = 0;
for (const rel of files) {
  const source = readFileSync(path.join(web, rel), "utf8");
  const events = [];
  let code = "";
  try {
    const r = await transformAsync(source, {
      filename: path.join(web, rel),
      configFile: false,
      babelrc: false,
      sourceMaps: false,
      parserOpts: { plugins: ["jsx"] },
      plugins: [[reactCompiler, {
        target: "19", compilationMode: "infer", panicThreshold: "none",
        logger: { logEvent: (_f, e) => events.push(e) },
      }]],
    });
    code = r?.code ?? "";
  } catch (e) {
    rows.push({ rel, fatal: String(e.message).slice(0, 200) });
    continue;
  }
  const ok = events.filter((e) => e.kind === "CompileSuccess");
  // one function can log several CompileError events (one per offending statement): keep one per function
  const seenFn = new Set();
  const bails = events.filter((e) => {
    if (e.kind !== "CompileError") return false;
    const k = e.fnLoc?.start?.line ?? Math.random();
    if (seenFn.has(k)) return false;
    seenFn.add(k);
    return true;
  });
  const skips = events.filter((e) => e.kind === "CompileSkip");
  const cCalls = (code.match(/\b_c\(/g) || []).length;
  totalFns += ok.length + bails.length + skips.length;
  totalOk += ok.length;
  totalBail += bails.length;
  const lines = source.split("\n");
  const fnNameAt = (ev) => {
    const l = ev.fnLoc?.start?.line;
    if (!l) return ev.fnName ?? "?";
    const m = (lines[l - 1] || "").match(/(?:function|const|let)\s+([A-Za-z_$][\w$]*)/);
    return (m ? m[1] : ev.fnName ?? "?") + `@L${l}`;
  };
  const bailNames = [];
  for (const b of bails) {
    const d = b.detail || {};
    const reason = (d.reason || d.description || d.category || "?").toString().split("\n")[0].slice(0, 90);
    const key = `${d.category ?? d.severity ?? ""}: ${reason}`;
    hist[key] = (hist[key] || 0) + 1;
    const name = fnNameAt(b);
    bailNames.push(name);
    if (verbose) {
      const loc = d.loc || (d.primaryLocation && d.primaryLocation()) || {};
      const line = loc?.start?.line ?? d.details?.[0]?.loc?.start?.line;
      const srcLine = line ? lines[line - 1]?.trim().slice(0, 120) : "";
      console.log(`  BAIL ${rel} fn=${name} line=${line ?? "?"} :: ${key}\n       ${srcLine}`);
    }
  }
  if (verbose) for (const o of ok) console.log(`  ok   ${rel} fn=${fnNameAt(o)}`);
  rows.push({ rel, fns: ok.length + bails.length + skips.length, ok: ok.length, bail: bails.length, skip: skips.length, c: cCalls,
    hasId: /\bid:\s*"/.test(source) || /\bid=\{?"/.test(source), hasRefs: /\brefs\[/.test(source),
    fnNames: [...new Set(bailNames)].slice(0, 6).join(",") });
}
console.log(`\n## ${path.basename(path.dirname(web))}/.web : ${files.length} files in scope`);
console.log("file | functions | compiled | bailed | skipped | _c( calls | has id: | has refs[ | bailed fns");
for (const r of rows) {
  if (r.fatal) { console.log(`${r.rel} | FATAL ${r.fatal}`); continue; }
  console.log(`${r.rel} | ${r.fns} | ${r.ok} | ${r.bail} | ${r.skip} | ${r.c} | ${r.hasId} | ${r.hasRefs} | ${r.fnNames}`);
}
console.log(`\nTOTAL functions=${totalFns} compiled=${totalOk} bailed=${totalBail}`);
console.log("bail-out reasons:");
for (const [k, v] of Object.entries(hist).sort((a, b) => b[1] - a[1])) console.log(`  ${v}  ${k}`);
