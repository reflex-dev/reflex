import { test } from "node:test";
import assert from "node:assert/strict";
import {
  communityColumns,
  validateRowIds,
} from "../../packages/reflex-components-internal/src/reflex_components_internal/components/base/CommunityGrid.js";

test("rejects missing, duplicate and mixed-type-colliding row ids", () => {
  assert.throws(() => validateRowIds([{ name: "A" }], "id"), /stable/);
  assert.throws(
    () => validateRowIds([{ id: 1 }, { id: "1" }], "id"),
    /Duplicate/,
  );
  assert.throws(() => validateRowIds([{ id: NaN }], "id"), /stable/);
  const rows = [{ key: "a" }, { key: "b" }];
  assert.equal(validateRowIds(rows, "key"), rows);
});
test("rejects unsupported features rather than silently removing them", () => {
  assert.throws(
    () => communityColumns([{ field: "x", rowGroup: true }]),
    /Unsupported Community column options/,
  );
  assert.throws(
    () => communityColumns([{ field: "x", filter: "agSetColumnFilter" }]),
    /Unsupported Community filter/,
  );
  assert.deepEqual(
    communityColumns([
      { field: "x", filter: "agNumberColumnFilter", pinned: "left" },
    ]),
    [{ field: "x", filter: "agNumberColumnFilter", pinned: "left" }],
  );
});
