// @vitest-environment node
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, beforeEach, expect, test } from "vitest";

import { generate } from "../scripts/generate.js";

const GENERATED = [
  { path: "tokens/space.stylex.js", render: () => "export const space = 1;\n" },
  { path: "style/_css_props.py", render: async () => "PROPS = ()\n" },
];

/** @type {string} */
let root;

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "reflex-ui-generate-"));
});

afterEach(async () => {
  await rm(root, { recursive: true });
});

test("writes every file, creating its directory", async () => {
  expect(await generate(GENERATED, root, false)).toEqual([
    "tokens/space.stylex.js",
    "style/_css_props.py",
  ]);
  expect(await readFile(join(root, "tokens/space.stylex.js"), "utf8")).toBe(
    "export const space = 1;\n",
  );
  expect(await readFile(join(root, "style/_css_props.py"), "utf8")).toBe(
    "PROPS = ()\n",
  );
});

test("check reports nothing for files that match their generator", async () => {
  await generate(GENERATED, root, false);
  expect(await generate(GENERATED, root, true)).toEqual([]);
});

test("check reports an edited file and a missing one, and writes neither", async () => {
  await generate(GENERATED, root, false);
  await writeFile(join(root, "tokens/space.stylex.js"), "edited by hand\n");
  await rm(join(root, "style/_css_props.py"));
  expect(await generate(GENERATED, root, true)).toEqual([
    "tokens/space.stylex.js",
    "style/_css_props.py",
  ]);
  expect(await readFile(join(root, "tokens/space.stylex.js"), "utf8")).toBe(
    "edited by hand\n",
  );
  await expect(readFile(join(root, "style/_css_props.py"))).rejects.toThrow(
    "ENOENT",
  );
});
