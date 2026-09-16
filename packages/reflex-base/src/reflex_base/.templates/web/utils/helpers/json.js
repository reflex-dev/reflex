// Python's json.dumps emits bare Infinity/-Infinity/NaN tokens (invalid JSON).
// Rewrite them so JSON.parse accepts the payload: 1e999 / -1e999 overflow to
// ±Infinity, while NaN, which has no JSON literal, becomes a sentinel string
// revived back to NaN after parsing.
// The alternation consumes whole string literals first, so tokens inside them
// are left alone, and a bare token is only rewritten where JSON permits a value
// (document start, or after ':', ',' or '['). A token anywhere else leaves the
// payload malformed for JSON.parse to reject, which the streaming upload parser
// relies on to tell a partial chunk from a complete one.
const NAN_SENTINEL = "__reflex_nan__";
const NON_FINITE_FLOAT_RE =
  /"(?:[^"\\]|\\.)*"|(^\s*|[:,[]\s*)(-?Infinity|NaN)\b/g;

// Reviving by string value would also convert a genuine string equal to the
// sentinel, so lengthen it until the payload no longer contains it. Only the
// placeholder can then survive parsing as that exact value.
const uniqueNanSentinel = (str) => {
  let sentinel = NAN_SENTINEL;
  while (str.includes(sentinel)) {
    sentinel += "_";
  }
  return sentinel;
};

const parseNonFiniteFloats = (str) => {
  const sentinel = uniqueNanSentinel(str);
  const replacements = {
    Infinity: "1e999",
    "-Infinity": "-1e999",
    NaN: `"${sentinel}"`,
  };
  return JSON.parse(
    // A string literal match leaves both groups undefined; note that `prefix`
    // is legitimately empty at the start of the document.
    str.replace(NON_FINITE_FLOAT_RE, (match, prefix, token) =>
      prefix === undefined ? match : prefix + replacements[token],
    ),
    (_k, v) => (v === sentinel ? NaN : v),
  );
};

/**
 * Parse a JSON payload, tolerating the bare non-finite float tokens that
 * python's json.dumps emits.
 *
 * The rewrite only runs when plain parsing fails, so well-formed payloads take
 * the native fast path.
 *
 * @param str The payload to parse.
 * @returns The parsed value.
 * @throws {SyntaxError} If the payload is not parseable either way.
 */
export const parseJson = (str) => {
  try {
    return JSON.parse(str);
  } catch {
    return parseNonFiniteFloats(str);
  }
};
