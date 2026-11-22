/// <reference path="./greetings.d.ts" />
/// <reference path="./missing.d.ts" />
import { pick } from "./typed";

export function greet(greeting: Greeting): void {
  pick("a", greeting);
}
