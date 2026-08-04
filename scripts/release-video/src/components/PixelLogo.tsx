import React from "react";
import { interpolate, random, spring, useVideoConfig } from "remotion";

import { LOGO_CELLS, LOGO_COLS, LOGO_ROWS } from "../logo";
import { c } from "../theme";

/**
 * The Reflex wordmark, drawn block by block.
 *
 * At `progress` 0 the blocks are scattered and transparent; at 1 they have
 * settled into the mark. Each block springs on its own stagger so the word
 * resolves left to right.
 */
export const PixelLogo: React.FC<{
  /** Size of one grid cell in px. */
  cell: number;
  /** Drives the assemble animation; pass the scene-local frame. */
  frame: number;
  color?: string;
  /** How many frames the whole assembly takes. */
  duration?: number;
  gap?: number;
}> = ({ cell, frame, color = c.ink, duration = 40, gap = 0 }) => {
  const { fps } = useVideoConfig();
  const size = cell - gap;

  return (
    <div
      style={{
        position: "relative",
        width: LOGO_COLS * cell,
        height: LOGO_ROWS * cell,
      }}
    >
      {LOGO_CELLS.map(({ x, y }, i) => {
        // Left-to-right stagger, softened by a per-block jitter.
        const stagger =
          (x / LOGO_COLS) * duration * 0.62 + random(`d${i}`) * duration * 0.22;

        const p = spring({
          frame: frame - stagger,
          fps,
          config: { damping: 14, mass: 0.5, stiffness: 110 },
          durationInFrames: duration,
        });

        // Scatter origin: blocks converge from a ring around the mark.
        const angle = random(`a${i}`) * Math.PI * 2;
        const dist = 120 + random(`r${i}`) * 260;
        const dx = interpolate(p, [0, 1], [Math.cos(angle) * dist, 0]);
        const dy = interpolate(p, [0, 1], [Math.sin(angle) * dist, 0]);
        const scale = interpolate(p, [0, 1], [0.3, 1]);
        const rot = interpolate(p, [0, 1], [random(`t${i}`) * 90 - 45, 0]);

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x * cell,
              top: y * cell,
              width: size,
              height: size,
              backgroundColor: color,
              opacity: interpolate(p, [0, 0.35, 1], [0, 0.9, 1]),
              transform: `translate(${dx}px, ${dy}px) scale(${scale}) rotate(${rot}deg)`,
              borderRadius: Math.max(1, cell * 0.06),
            }}
          />
        );
      })}
    </div>
  );
};
