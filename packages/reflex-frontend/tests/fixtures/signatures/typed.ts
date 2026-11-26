export function pick(mode: "a" | "b", maybe: string | null): void {}

export function overloaded(n: number): void;
export function overloaded(): void;
export function overloaded(n?: number): void {}

export function tupleRest(...args: [number, string]): void {}

export function defaultFirst(prefix = "", count: number): void {}

export function optionalItems(
  pair: [string, string?],
  picks: ["b", ("c" | "a")?],
): void {}
