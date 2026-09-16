// Python's json.dumps emits bare Infinity/-Infinity/NaN tokens (invalid JSON).
// Rewrite them outside string literals so JSON.parse accepts the payload.
// 1e999 / -1e999 overflow to ±Infinity; NaN has no JSON literal, so it is
// swapped for a sentinel string and revived back to NaN after parsing.
// The alternation matches whole string literals first (passed through unchanged),
// guaranteeing bare-token matches only land in numeric positions.
const NAN_SENTINEL = "__reflex_nan__";
const NON_FINITE_FLOAT_RE = /"(?:[^"\\]|\\.)*"|-?\bInfinity\b|\bNaN\b/g;

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
    str.replace(NON_FINITE_FLOAT_RE, (match) =>
      match[0] === '"' ? match : replacements[match],
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
