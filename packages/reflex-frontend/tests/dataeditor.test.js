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
  test("display the cell value as text without replacing the raw value", () => {
    expect(formatCell(125, { type: "currency" })).toEqual({
      kind: "text",
      data: 125,
      displayData: "125",
    });
  });

  test("display object values as JSON", () => {
    const value = { amount: 125 };
    expect(formatCell(value, { type: "currency" })).toEqual({
      kind: "text",
      data: value,
      displayData: '{"amount":125}',
    });
  });

  test.each([null, undefined])("display %s as an empty cell", (value) => {
    expect(formatCell(value, { type: "currency" })).toEqual({
      kind: "text",
      data: value,
      displayData: "",
    });
  });
});
