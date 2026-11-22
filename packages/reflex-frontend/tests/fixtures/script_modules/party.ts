import confetti from "canvas-confetti";
import { reflex } from "$/utils/reflex";
import { describe } from "./helpers";
import type { Options } from "options-types";
import { type Shape } from "shape-types";
import "./party.css";
import message from "./message.txt?raw";
import "./missing";

export function celebrate(count: number) {
  confetti({ particleCount: count });
}
export async function load() {
  return import("./lazy.mjs");
}
export const arrow = () => describe(message);
export const made = make();
export let later = 1;
// biome-ignore format: the parentheses are what `wrapped` tests.
export const limit = 5,
  label = `x`,
  options = { a: 1 } satisfies Options,
  list = [1] as const,
  Shaper = class {},
  wrapped = (null);
export class Widget {}
export enum Mode {
  A,
}
export interface Ignored {}
export type Alias = Shape;
export declare const declared: number;
const local = () => reflex;
const localValue = "v";
export { local, localValue as renamedValue };
export { helper as reexported } from "./helpers";
export * as namespace from "./widgets";
export * from "star-pkg";
export type * from "types-pkg";
export default function () {}
import(`dayjs`);
import(`./${limit}`);
import(String(limit));
