import type { Shape } from "./shapes";

export enum Color {
  Red = "red",
  Green = "green",
}

export enum Level {
  Low,
  High,
}

export interface Options {
  size: number;
}

export type Count = number;

export class Widget {}

export * from "./reexported.js";

export function literals(
  color: Color,
  level: Level,
  mode: "b" | "a" | 2 | true,
  ratio: 1.5 | 2.5,
  flag: true,
  shape: Shape,
): void {}

export function containers(
  names: string[],
  pair: [number, string],
  empty: [],
  counts: Record<string, number>,
  options: Options,
  inline: { a: number },
  partial: Partial<Options>,
  keyed: Record<"x" | "y", number>,
  nested: Array<string | null>,
): void {}

export function noJsonForm(
  tags: Set<string>,
  lookup: Map<string, number>,
  big: bigint,
  later: Promise<number>,
  make: () => string[],
  element: HTMLElement,
  widget: Widget,
  anything: object,
  both: Options & { b: number },
  either: string | HTMLElement,
): void {}

export function maybe(value?: string | null, ...rest: [number, string]): void {}
