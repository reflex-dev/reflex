/**
 * Round a number using Python's round-half-even semantics.
 * Decompose the IEEE 754 value into a rational so ties are compared exactly.
 *
 * @param {number} value The value to round.
 * @param {number} ndigits The decimal precision.
 * @returns {number} The rounded value.
 */
export default function pyRound(value, ndigits) {
  if (!Number.isFinite(value) || ndigits > 323) return value;
  if (ndigits < -308) return value * 0;

  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, Math.abs(value));
  const bits = view.getBigUint64(0);
  const exponent = Number((bits >> 52n) & 0x7ffn);
  const fraction = bits & 0xfffffffffffffn;
  const significand = exponent === 0 ? fraction : fraction | 0x10000000000000n;
  const binaryExponent = exponent === 0 ? -1074 : exponent - 1075;
  const fivePower = 5n ** BigInt(Math.abs(ndigits));

  let numerator = significand * (ndigits >= 0 ? fivePower : 1n);
  let denominator = ndigits < 0 ? fivePower : 1n;
  const shift = binaryExponent + ndigits;
  if (shift >= 0) {
    numerator <<= BigInt(shift);
  } else {
    denominator <<= BigInt(-shift);
  }

  let rounded = numerator / denominator;
  const doubledRemainder = (numerator % denominator) * 2n;
  if (
    doubledRemainder > denominator ||
    (doubledRemainder === denominator && rounded % 2n === 1n)
  ) {
    rounded += 1n;
  }

  const sign = value < 0 || Object.is(value, -0) ? "-" : "";
  const result = Number(`${sign}${rounded}e${-ndigits}`);
  return result === 0 && sign ? -0 : result;
}
