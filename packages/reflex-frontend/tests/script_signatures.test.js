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
 * @returns {Promise<Record<string, unknown>>} Its output, by file name.
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
    const output = JSON.parse(String(write.mock.calls[0][0]));
    return Object.fromEntries(
      Object.entries(output).map(([file, exports]) => [
        basename(file),
        exports,
      ]),
    );
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
