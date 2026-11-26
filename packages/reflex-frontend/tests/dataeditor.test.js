import { readFileSync } from "node:fs";

import { beforeAll, describe, expect, test } from "vitest";

let formatCell;

beforeAll(async () => {
  const sourcePath = `${__WEB_ROOT__}/utils/helpers/dataeditor.js`;
  const source = readFileSync(sourcePath, "utf8");
  const glideImport =
    'import { GridCellKind } from "@glideapps/glide-data-grid";';
  expect(source).toContain(glideImport);

  const testSource = source.replace(
    glideImport,
    `const GridCellKind = ${JSON.stringify({
      Image: "image",
      Loading: "loading",
      Number: "number",
      Text: "text",
      Boolean: "boolean",
      Custom: "custom",
    })};`,
  );
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(testSource).toString("base64")}`;
  ({ formatCell } = await import(moduleUrl));
});

describe("unsupported DataEditor column types", () => {
  test.each([
    [125, "125"],
    [0, "0"],
    [false, "false"],
    [true, "true"],
    ["", ""],
    ["text", "text"],
    [null, ""],
    [undefined, ""],
    [{ amount: 125 }, '{"amount":125}'],
    [[], "[]"],
    [[1, "a", null], '[1,"a",null]'],
  ])("display %j as text without replacing the raw value", (value, displayData) => {
    const cell = formatCell(value, { type: "currency" });
    expect(cell).toStrictEqual({ kind: "text", data: value, displayData });
    expect(cell.data).toBe(value);
  });
});
