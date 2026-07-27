/** Compare ISO datetime values without losing sub-millisecond precision. */
export default function compareDatetime(lhs, rhs) {
  const toMicroseconds = (value) => {
    const stringValue = String(value).replace(" ", "T");
    const fraction = stringValue.match(/\.(\d+)/)?.[1] ?? "";
    const microseconds = BigInt(fraction.padEnd(6, "0").slice(3, 6) || "0");
    return BigInt(new Date(stringValue).getTime()) * 1000n + microseconds;
  };

  const lhsMicroseconds = toMicroseconds(lhs);
  const rhsMicroseconds = toMicroseconds(rhs);
  return lhsMicroseconds < rhsMicroseconds
    ? -1
    : lhsMicroseconds > rhsMicroseconds
      ? 1
      : 0;
}
