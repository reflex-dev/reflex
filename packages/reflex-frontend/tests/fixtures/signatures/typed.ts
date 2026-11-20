export function pick(mode: "a" | "b", maybe: string | null): void {}

export function overloaded(n: number): void;
export function overloaded(): void;
export function overloaded(n?: number): void {}
