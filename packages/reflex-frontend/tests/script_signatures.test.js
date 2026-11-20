// @vitest-environment node
/**
 * `script-signatures.js` prints the call signatures of the functions modules
 * export, which Reflex turns into Python type stubs. It runs in an app's .web
 * with node, so this runs it the same way, as a child process.
 */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

const root = fileURLToPath(new URL("..", import.meta.url));
const fixture = (name) =>
  fileURLToPath(new URL(`./fixtures/signatures/${name}`, import.meta.url));

const signatures = (...files) =>
  JSON.parse(
    execFileSync(process.execPath, ["src/script-signatures.js", ...files], {
      cwd: root,
      encoding: "utf-8",
    }),
  );

const param = (name, type, optional = false, rest = false) => ({
  name,
  type,
  optional,
  rest,
});

test("reads JSDoc types, optional and rest parameters", () => {
  const file = fixture("jsdoc.js");
  expect(signatures(file)).toEqual({
    [file]: [
      {
        name: "celebrate",
        signatures: [
          {
            parameters: [
              param("count", "number"),
              param("elementId", "string"),
              param("loud", "boolean | undefined", true),
            ],
          },
        ],
      },
      {
        name: "many",
        signatures: [{ parameters: [param("names", "string", false, true)] }],
      },
      {
        name: "untyped",
        signatures: [{ parameters: [param("a", "any"), param("b", "any")] }],
      },
      { name: "notAFunction", signatures: [] },
    ],
  });
});

test("reads TypeScript types and overloads, several files at once", () => {
  const typed = fixture("typed.ts");
  const result = signatures(typed, fixture("jsdoc.js"));
  expect(Object.keys(result)).toEqual([typed, fixture("jsdoc.js")]);
  expect(result[typed]).toEqual([
    {
      name: "pick",
      signatures: [
        {
          parameters: [
            param("mode", '"a" | "b"'),
            param("maybe", "string | null"),
          ],
        },
      ],
    },
    {
      name: "overloaded",
      signatures: [{ parameters: [param("n", "number")] }, { parameters: [] }],
    },
  ]);
});
