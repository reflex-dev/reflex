const DATETIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(?:(Z)|([+-])(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?)?$/;

/** Parse a serialized Python date or datetime without using local browser time. */
function parseDatetime(value) {
  const match = DATETIME_PATTERN.exec(String(value));
  if (match === null) {
    return null;
  }

  const [, year, month, day, hour, minute, second, fraction, zulu, sign] =
    match;
  const date = new Date(0);
  date.setUTCFullYear(Number(year), Number(month) - 1, Number(day));
  date.setUTCHours(Number(hour ?? 0), Number(minute ?? 0), Number(second ?? 0));

  let microseconds =
    BigInt(date.getTime()) * 1000n +
    BigInt((fraction ?? "").padEnd(6, "0") || "0");
  const kind = hour === undefined ? "date" : zulu || sign ? "aware" : "naive";

  if (kind === "aware" && sign !== undefined) {
    const offsetSeconds =
      Number(match[10]) * 3600 +
      Number(match[11]) * 60 +
      Number(match[12] ?? 0);
    const offsetMicroseconds =
      BigInt(offsetSeconds) * 1000000n +
      BigInt((match[13] ?? "").padEnd(6, "0") || "0");
    microseconds -= sign === "+" ? offsetMicroseconds : -offsetMicroseconds;
  }

  return { kind, microseconds };
}

/** Compare serialized Python date or datetime values.
 *
 * Returns NaN for incomparable operands (mismatched kinds, null, or
 * unparsable values), so equality is false and ordering is false.
 */
export default function compareDatetime(lhs, rhs) {
  const lhsDatetime = parseDatetime(lhs);
  const rhsDatetime = parseDatetime(rhs);
  if (lhsDatetime === null || rhsDatetime === null) {
    return lhs === rhs ? 0 : Number.NaN;
  }
  if (lhsDatetime.kind !== rhsDatetime.kind) {
    return Number.NaN;
  }
  return lhsDatetime.microseconds < rhsDatetime.microseconds
    ? -1
    : lhsDatetime.microseconds > rhsDatetime.microseconds
      ? 1
      : 0;
}
