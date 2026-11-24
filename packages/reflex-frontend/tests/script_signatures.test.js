// @vitest-environment node
/**
 * `script-signatures.js` prints the call signatures of the functions modules
 * export, which Reflex renders as Python type stubs. It is a command run in an
 * app's .web, so this sets its arguments, imports it and reads what it prints.
 * `fixtures/signatures/signatures.json` is that output, which the Python tests
 * render, so both sides are held to the same contract.
 */
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, vi } from "vitest";

const fixtures = fileURLToPath(
  new URL("./fixtures/signatures/", import.meta.url),
);

/**
 * Run the script on fixture files.
 * @param {string[]} names The fixtures' file names.
 * @returns {Promise<{format: number, modules: Record<string, unknown>, files: Record<string, string[]>}>}
 * Its output, with file names in place of paths, and an installed package's
 * files by their path from node_modules.
 */
const signatures = async (names) => {
  const argv = process.argv;
  process.argv = [
    argv[0],
    "script-signatures.js",
    ...names.map((name) => fixtures + name),
  ];
  const write = vi
    .spyOn(process.stdout, "write")
    .mockImplementation(() => true);
  try {
    vi.resetModules();
    await import("$/script-signatures.js");
    expect(write).toHaveBeenCalledTimes(1);
    const { format, modules, files } = JSON.parse(
      String(write.mock.calls[0][0]),
    );
    return {
      format,
      modules: Object.fromEntries(
        Object.entries(modules).map(([file, exports]) => [
          basename(file),
          exports,
        ]),
      ),
      files: Object.fromEntries(
        Object.entries(files).map(([file, read]) => [
          basename(file),
          read.map((name) =>
            name.includes("/node_modules/")
              ? name.slice(name.lastIndexOf("node_modules/"))
              : basename(name),
          ),
        ]),
      ),
    };
  } finally {
    write.mockRestore();
    process.argv = argv;
  }
};

test("classifies each parameter's type into the JSON value Python sends", async () => {
  // types.ts declares `mode: "b" | "a" | 2 | true`; the union comes out sorted.
  expect(
    await signatures(["jsdoc.js", "typed.ts", "types.ts", "script.js"]),
  ).toEqual(JSON.parse(readFileSync(`${fixtures}signatures.json`, "utf-8")));
});

test("lists the files each module's types are read from", async () => {
  // jsdoc.js reads a type of shapes.d.ts in a JSDoc `import("./shapes")`, which
  // the bundler never loads; types.ts, from shapes.d.ts and reexported.js.
  // referencing.ts reads a global type of a `/// <reference>`d file, and a
  // missing one is listed too, so that adding it rewrites the stub; the import
  // that resolves to no file is not. Its npm package, and the package that
  // package's declarations import, are listed by their package.json, whose
  // version changes with them. No module lists another's files, nor
  // TypeScript's libraries.
  const { modules, files } = await signatures([
    "jsdoc.js",
    "types.ts",
    "referencing.ts",
  ]);
  expect(files).toEqual({
    "jsdoc.js": ["jsdoc.js", "shapes.d.ts"],
    "types.ts": ["types.ts", "shapes.d.ts", "reexported.js"],
    "referencing.ts": [
      "referencing.ts",
      "node_modules/@types/react/package.json",
      "typed.ts",
      "greetings.d.ts",
      "missing.d.ts",
      "node_modules/csstype/package.json",
    ],
  });
  expect(modules["referencing.ts"]).toEqual({
    greet: [
      {
        parameters: [
          {
            name: "greeting",
            type: {
              kind: "union",
              members: [
                { kind: "literal", value: "hey" },
                { kind: "literal", value: "hi" },
              ],
            },
            optional: false,
            rest: false,
          },
        ],
      },
    ],
  });
});

test("a type that contains itself stops at its first repeat", async () => {
  // The repeat has no finite JSON shape, so it accepts any value.
  expect(await signatures(["recursive.ts"])).toEqual({
    format: 1,
    modules: {
      "recursive.ts": {
        Tree: [],
        Nested: [],
        grow: [
          {
            parameters: [
              {
                name: "tree",
                type: { kind: "mapping", value: "any" },
                optional: false,
                rest: false,
              },
              {
                name: "nested",
                type: { kind: "list", item: "any" },
                optional: false,
                rest: false,
              },
              { name: "depth", type: "float", optional: false, rest: false },
            ],
          },
        ],
      },
    },
    files: { "recursive.ts": ["recursive.ts"] },
  });
});
