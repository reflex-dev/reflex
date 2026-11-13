import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");
const { pyStrAt, pyStrChars, pyStrLength, pyStrSlice } =
  await createQueueRuntime(source);

// Expected values are Python's len(), list(), s[i] and s[a:b].
const cases = [
  { s: "", chars: [] },
  { s: "hello", chars: ["h", "e", "l", "l", "o"] },
  { s: "中文é", chars: ["中", "文", "é"] },
  { s: "a\u{1f600}b", chars: ["a", "\u{1f600}", "b"] },
  { s: "\u{1f600}\u{1f600}", chars: ["\u{1f600}", "\u{1f600}"] },
  { s: "x\ud83dy", chars: ["x", "\ud83d", "y"] },
];

test("string helpers count code points", () => {
  for (const { s, chars } of cases) {
    assert.deepEqual(pyStrChars(s), chars, s);
    assert.equal(pyStrLength(s), chars.length, s);
    for (const i of [0, 1, -1, -2, chars.length]) {
      assert.equal(pyStrAt(s, i), chars.at(i), `${s}[${i}]`);
    }
    for (const [start, stop] of [
      [1, null],
      [null, 1],
      [1, -1],
      [-2, undefined],
      [null, null],
      [5, 1],
    ]) {
      assert.equal(
        pyStrSlice(s, start, stop),
        chars.slice(start ?? 0, stop ?? chars.length).join(""),
        `${s}[${start}:${stop}]`,
      );
    }
  }
});

test("string helpers treat null as the empty string", () => {
  for (const s of [null, undefined]) {
    assert.equal(pyStrLength(s), 0);
    assert.equal(pyStrAt(s, 0), undefined);
    assert.equal(pyStrSlice(s, 1, null), "");
    assert.deepEqual(pyStrChars(s), []);
  }
});
