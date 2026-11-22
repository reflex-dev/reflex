import { describe } from "./helpers";

export const Counter = <T,>({ value }: { value: T }) => (
  <span title="a / b">{describe(String(value))}</span>
);
