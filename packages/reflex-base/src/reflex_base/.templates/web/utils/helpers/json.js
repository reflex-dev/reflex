// Sentinels for non-finite floats, emitted by reflex_base.utils.format and
// restored by the reviver below. Colliding user strings arrive escaped; the
// reviver strips one escape level. Keep in sync with that module.
const SENTINEL_PREFIX = "__reflex_";
const NAN_SENTINEL = "__reflex_nan__";
const INF_SENTINEL = "__reflex_inf__";
const NEG_INF_SENTINEL = "__reflex_neg_inf__";
const SENTINEL_ESCAPE_PREFIX = "__reflex_esc__";

const reviveNonFiniteFloats = (_k, v) => {
  if (typeof v !== "string" || !v.startsWith(SENTINEL_PREFIX)) return v;
  if (v === NAN_SENTINEL) return NaN;
  if (v === INF_SENTINEL) return Infinity;
  if (v === NEG_INF_SENTINEL) return -Infinity;
  if (v.startsWith(SENTINEL_ESCAPE_PREFIX))
    return v.slice(SENTINEL_ESCAPE_PREFIX.length);
  return v;
};

// The backend emits bare Infinity/-Infinity/NaN tokens (invalid JSON) wherever
// it serializes non-finite floats with stdlib json. Rewrite them to sentinels
// outside string literals. The alternation matches whole string literals first
// (passed through unchanged), guaranteeing bare-token matches only land in
// numeric positions. A token followed by ':' is a key no serializer produces,
// so it is left alone for JSON.parse to reject rather than turned into one.
const NON_FINITE_FLOAT_RE =
  /"(?:[^"\\]|\\.)*"|(?:-?\bInfinity\b|\bNaN\b)(?!\s*:)/g;
const NON_FINITE_REPLACEMENTS = {
  Infinity: `"${INF_SENTINEL}"`,
  "-Infinity": `"${NEG_INF_SENTINEL}"`,
  NaN: `"${NAN_SENTINEL}"`,
};
const rewriteBareNonFiniteFloats = (str) =>
  str.replace(NON_FINITE_FLOAT_RE, (match) =>
    match[0] === '"' ? match : NON_FINITE_REPLACEMENTS[match],
  );

/**
 * Parse a JSON payload that may encode non-finite floats.
 *
 * Passing a reviver disables the engine's fast JSON parser (~4-12x slower), so
 * only pay for it when a sentinel can actually appear in the payload. Bare
 * NaN/Infinity tokens make the first parse throw; they are rewritten to
 * sentinels and parsed again on retry.
 *
 * @param {string} str - the JSON payload to parse
 * @returns the parsed value
 * @throws {SyntaxError} if the payload is not valid JSON either way
 */
export const parseNonFiniteAwareJSON = (str) => {
  try {
    return str.includes(SENTINEL_PREFIX)
      ? JSON.parse(str, reviveNonFiniteFloats)
      : JSON.parse(str);
  } catch (e) {
    // Bare tokens are the only recoverable failure, so a payload the rewrite
    // leaves untouched is simply malformed -- report the original error rather
    // than paying for a second parse. Partial upload chunks hit this on every
    // progress event.
    const rewritten = rewriteBareNonFiniteFloats(str);
    if (rewritten === str) throw e;
    return JSON.parse(rewritten, reviveNonFiniteFloats);
  }
};
