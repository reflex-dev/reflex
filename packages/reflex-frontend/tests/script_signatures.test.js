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
 * @returns {Promise<{format: number, modules: Record<string, unknown>, files: string[]}>} Its
 * output, with file names in place of paths.
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
      files: files.map((file) => basename(file)),
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

test("lists the files the types were read from, without libraries", async () => {
  // jsdoc.js reads a type of shapes.d.ts in a JSDoc `import("./shapes")`, which
  // the bundler never loads.
  expect((await signatures(["jsdoc.js"])).files).toEqual([
    "shapes.d.ts",
    "jsdoc.js",
  ]);
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
    files: ["recursive.ts"],
  });
});
