/**
 * The Reflex wordmark as a pixel grid.
 *
 * Decoded from docs/images/reflex.svg, whose single path is drawn on a 2.24-unit
 * lattice (viewBox 0 0 56 12 => 25 columns x 5 rows). Keeping the mark as cells
 * rather than a path lets each block be animated independently.
 */

type Glyph = {
  /** Column the glyph starts at, in grid cells. */
  col: number;
  /** Row-major bitmap, 1 = filled cell. */
  rows: number[][];
};

const R: number[][] = [
  [1, 1, 1, 1],
  [1, 0, 0, 1],
  [1, 1, 1, 0],
  [1, 0, 0, 1],
  [1, 0, 0, 1],
];

const E: number[][] = [
  [1, 1, 1],
  [1, 0, 0],
  [1, 1, 1],
  [1, 0, 0],
  [1, 1, 1],
];

const F: number[][] = [
  [1, 1, 1],
  [1, 0, 0],
  [1, 1, 1],
  [1, 0, 0],
  [1, 0, 0],
];

const L: number[][] = [
  [1, 0, 0],
  [1, 0, 0],
  [1, 0, 0],
  [1, 0, 0],
  [1, 1, 1],
];

const X: number[][] = [
  [1, 0, 0, 1],
  [1, 0, 0, 1],
  [0, 1, 1, 0],
  [1, 0, 0, 1],
  [1, 0, 0, 1],
];

const GLYPHS: Glyph[] = [
  { col: 0, rows: R },
  { col: 5, rows: E },
  { col: 9, rows: F },
  { col: 13, rows: L },
  { col: 17, rows: E },
  { col: 21, rows: X },
];

export const LOGO_COLS = 25;
export const LOGO_ROWS = 5;

export type Cell = { x: number; y: number };

/** Every filled cell of the wordmark, in reading order. */
export const LOGO_CELLS: Cell[] = GLYPHS.flatMap(({ col, rows }) =>
  rows.flatMap((cells, y) =>
    cells.flatMap((on, i) => (on ? [{ x: col + i, y }] : [])),
  ),
);
