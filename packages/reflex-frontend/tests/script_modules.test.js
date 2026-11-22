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
    imports: {
      "party.ts": ["canvas-confetti", "$/utils/reflex", "star-pkg", "dayjs"],
      "helpers.ts": ["dayjs"],
      "widgets/index.jsx": [],
      "lazy.mjs": [],
      "lib/format.ts": [],
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
  // The compiler copies each file at its path, so the copy of a link must be
  // where the import looks for it, and the files that copy imports beside it.
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
