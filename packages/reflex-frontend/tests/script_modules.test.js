// @vitest-environment node
/**
 * `script-modules.js` reads the JavaScript modules an app imports from Python
 * for the compiler. It is a command run in an app's .web, so this sets its
 * arguments, imports it and reads what it prints.
 */
import {
  mkdirSync,
  mkdtempSync,
  realpathSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, onTestFinished, test, vi } from "vitest";

const fixtures = realpathSync(
  fileURLToPath(new URL("./fixtures/script_modules/", import.meta.url)),
);

/**
 * Run the script on modules.
 * @param {string} directory The modules' directory.
 * @param {string[]} names The modules' paths in it.
 * @returns {Promise<any>} Its output, with paths relative to the directory.
 */
const readModules = async (directory, names) => {
  const argv = process.argv;
  process.argv = [
    argv[0],
    "script-modules.js",
    ...names.map((name) => join(directory, name)),
  ];
  const write = vi
    .spyOn(process.stdout, "write")
    .mockImplementation(() => true);
  try {
    vi.resetModules();
    await import("$/script-modules.js");
    expect(write).toHaveBeenCalledTimes(1);
    return JSON.parse(
      String(write.mock.calls[0][0]).replaceAll(`${directory}/`, ""),
    );
  } finally {
    write.mockRestore();
    process.argv = argv;
  }
};

test("lists each module's files, its exports, and what each script imports", async () => {
  expect(await readModules(fixtures, ["party.ts", "counter.tsx"])).toEqual({
    format: 1,
    modules: {
      "party.ts": {
        // Followed: relative imports, also dynamic and re-exported, resolved
        // as the bundler does (`./lib/format.js` is format.ts), and the
        // `@import`, `url()` and `image-set()` of stylesheets, quoted paths
        // with spaces included.
        files: [
          "party.ts",
          "helpers.ts",
          "party.css",
          "message.txt",
          "widgets/index.jsx",
          "lazy.mjs",
          "lib/format.ts",
          "theme.css",
          "img/bg.png",
          "img/my bg.png",
          "img/hi.png",
        ],
        // `made` and `later` may hold a function, and `reexported` comes from
        // another file: none is rejected. Types and the default are left out.
        functions: [
          "celebrate",
          "load",
          "arrow",
          "made",
          "later",
          "local",
          "reexported",
        ],
        values: [
          "limit",
          "label",
          "options",
          "list",
          "Shaper",
          "wrapped",
          "Widget",
          "Mode",
          "renamedValue",
          "namespace",
        ],
        // `export * from "star-pkg"` exports names only the package knows.
        exportsAll: true,
      },
      "counter.tsx": {
        files: ["counter.tsx", "helpers.ts", "lib/format.ts"],
        functions: ["Counter"],
        values: [],
        exportsAll: false,
      },
    },
    // Without type-only imports, and with only a dynamic import of a string.
    // A stylesheet's are those of its `@import`s that name a package.
    imports: {
      "party.ts": ["canvas-confetti", "$/utils/reflex", "star-pkg", "dayjs"],
      "helpers.ts": ["dayjs"],
      "party.css": [],
      "widgets/index.jsx": [],
      "lazy.mjs": [],
      "lib/format.ts": [],
      "theme.css": [],
      "counter.tsx": [],
    },
    errors: [],
  });
});

/**
 * Make a directory of files that is removed after the test.
 * @param {Record<string, string>} contents Each file's text, by its path in it.
 * @returns {string} The directory's real path.
 */
const writeFiles = (contents) => {
  const directory = realpathSync(
    mkdtempSync(join(tmpdir(), "script-modules-")),
  );
  onTestFinished(() => rmSync(directory, { recursive: true }));
  for (const [path, text] of Object.entries(contents)) {
    mkdirSync(dirname(join(directory, path)), { recursive: true });
    writeFileSync(join(directory, path), text);
  }
  return directory;
};

test("lists a linked file where its import names it, and its imports from there", async () => {
  // Vite does not follow links (`resolve.preserveSymlinks`), so it reads a
  // link where the import names it, and finds the files it imports beside it.
  const directory = writeFiles({
    "party.js":
      'import { shout } from "./linked.js";\nexport function go() {}\n',
    "shared/linked.js": 'export { near as shout } from "./near.js";\n',
    "near.js": "export const near = (s) => s;\n",
  });
  symlinkSync(
    join(directory, "shared", "linked.js"),
    join(directory, "linked.js"),
  );
  const { modules, imports } = await readModules(directory, ["party.js"]);
  expect(modules["party.js"].files).toEqual([
    "party.js",
    "linked.js",
    "near.js",
  ]);
  expect(imports).toEqual({ "party.js": [], "linked.js": [], "near.js": [] });
});

test("lists a file that Vite loads as its text or URL without reading it", async () => {
  // `?raw` loads the text and `?url` the URL of a script, so their imports
  // never run. A stylesheet or a worker loaded by URL is still bundled.
  const directory = writeFiles({
    "party.js": [
      'import text from "./example.js?raw";',
      'import worklet from "./worklet.js?url";',
      'import theme from "./theme.css?url";',
      'import worker from "./worker.js?worker&url";',
      "export function go() {}",
    ].join("\n"),
    "example.js": 'import fs from "node:fs";\n',
    "worklet.js": 'import "worklet-pkg";\n',
    "theme.css": '@import "./more.css";\n',
    "more.css": "",
    "worker.js": 'import "worker-pkg";\n',
  });
  const { modules, imports } = await readModules(directory, ["party.js"]);
  expect(modules["party.js"].files).toEqual([
    "party.js",
    "example.js",
    "worklet.js",
    "theme.css",
    "worker.js",
    "more.css",
  ]);
  expect(imports).toEqual({
    "party.js": [],
    "theme.css": [],
    "worker.js": ["worker-pkg"],
    "more.css": [],
  });
});

test("lists a file a script names by URL, and reads a worker's imports", async () => {
  // Vite bundles a worker started from `new URL(path, import.meta.url)` and
  // loads any other file named so as it is, as it does a `?url` import. A URL
  // relative to anything else, or to no file, is not the module's.
  const directory = writeFiles({
    "party.js": [
      "import './first.js';",
      'new Worker(new URL("./worker.js", import.meta.url), { type: "module" });',
      "new SharedWorker(new URL(`./shared.js`, import.meta.url));",
      'const logo = new URL("./logo.png?v=2", import.meta.url);',
      'const script = new URL("./script.js", import.meta.url);',
      'const page = new URL("./page.js", location.href);',
      'const remote = new URL("https://example.com/x.js", import.meta.url);',
      'const missing = new URL("./missing.png", import.meta.url);',
      "export function go() {}",
    ].join("\n"),
    "first.js": "",
    "worker.js": 'import "./helper.js";\nimport "worker-pkg";\n',
    "helper.js": "",
    "shared.js": "",
    "logo.png": "",
    "script.js": 'import "script-pkg";\n',
    "page.js": "",
  });
  const { modules, imports } = await readModules(directory, ["party.js"]);
  expect(modules["party.js"].files).toEqual([
    "party.js",
    "first.js",
    "worker.js",
    "shared.js",
    "logo.png",
    "script.js",
    "helper.js",
  ]);
  expect(imports).toEqual({
    "party.js": [],
    "first.js": [],
    "worker.js": ["worker-pkg"],
    "shared.js": [],
    "helper.js": [],
  });
});

test("finds an import without an extension as Vite does, JSON included", async () => {
  // Vite tries .mjs, .js, .mts, .ts, .jsx, .tsx and .json, in that order.
  const directory = writeFiles({
    "party.js": [
      'import settings from "./settings";',
      'import { help } from "./helpers";',
      'import { shared } from "./shared";',
      "export function go() {}",
    ].join("\n"),
    "settings.json": "{}",
    "helpers.js": "export const help = 1;\n",
    "helpers.ts": "export const help = 2;\n",
    "shared.mts": 'import "shared-pkg";\nexport const shared = 3;\n',
  });
  const { modules, imports } = await readModules(directory, ["party.js"]);
  expect(modules["party.js"].files).toEqual([
    "party.js",
    "settings.json",
    "helpers.js",
    "shared.mts",
  ]);
  expect(imports).toEqual({
    "party.js": [],
    "helpers.js": [],
    "shared.mts": ["shared-pkg"],
  });
});

test("finds the TypeScript file an import names by the JavaScript it compiles to", async () => {
  // As TypeScript and Vite do: `.js` names `.ts` or else `.tsx`, `.jsx` names
  // `.tsx`, and `.mjs` names `.mts`.
  const directory = writeFiles({
    "party.ts": [
      'import { plain } from "./plain.js";',
      'import { Widget } from "./widget.js";',
      'import { View } from "./view.jsx";',
      'import { esm } from "./esm.mjs";',
      "export function go() {}",
    ].join("\n"),
    "plain.ts": "export const plain = 1;\n",
    "widget.tsx": 'import "widget-pkg";\nexport const Widget = () => null;\n',
    "view.tsx": "export const View = () => null;\n",
    "esm.mts": "export const esm = 1;\n",
  });
  const { modules, imports } = await readModules(directory, ["party.ts"]);
  expect(modules["party.ts"].files).toEqual([
    "party.ts",
    "plain.ts",
    "widget.tsx",
    "view.tsx",
    "esm.mts",
  ]);
  expect(imports).toEqual({
    "party.ts": [],
    "plain.ts": [],
    "widget.tsx": ["widget-pkg"],
    "view.tsx": [],
    "esm.mts": [],
  });
});

test("lists the packages a stylesheet imports", async () => {
  // Vite resolves a bare `@import` from the stylesheet first, then from the
  // installed packages, so a name with no file beside it is a package.
  const directory = writeFiles({
    "party.js": 'import "./theme.css";\nexport function go() {}\n',
    "theme.css": [
      '@import "normalize.css";',
      "@import url(bootstrap/dist/css/bootstrap.css);",
      '@import "local.css";',
      '@import "./missing.css";',
      ".logo { background: url(logo.png); }",
    ].join("\n"),
    "local.css": "",
  });
  const { modules, imports } = await readModules(directory, ["party.js"]);
  expect(modules["party.js"].files).toEqual([
    "party.js",
    "theme.css",
    "local.css",
  ]);
  expect(imports).toEqual({
    "party.js": [],
    "theme.css": ["normalize.css", "bootstrap/dist/css/bootstrap.css"],
    "local.css": [],
  });
});

test("reports the position of a file's first syntax error", async () => {
  // Written here: the repository's formatter cannot read a fixture that does
  // not parse.
  const directory = writeFiles({});
  writeFileSync(
    join(directory, "broken.mjs"),
    '// é😀\nconst s = "é😀"; export const = 1;\n',
  );
  const { modules, errors } = await readModules(directory, ["broken.mjs"]);
  expect(modules["broken.mjs"].files).toEqual(["broken.mjs"]);
  // The column counts UTF-16 code units, as editors do: 😀 is two.
  expect(errors).toEqual([
    { file: "broken.mjs", line: 2, column: 31, message: "Unexpected token" },
  ]);
});
