export interface Tree {
  [key: string]: Tree;
}

export type Nested = Nested[];

export function grow(tree: Tree, nested: Nested, depth: number): void {}
