/// <reference path="./greetings.d.ts" />
/// <reference path="./missing.d.ts" />
import type { ReactNode } from "react";
import type { Nowhere } from "./nowhere";
import { pick } from "./typed";

export function greet(greeting: Greeting): void {
  pick("a", greeting);
}

type Imported = [ReactNode, Nowhere];
