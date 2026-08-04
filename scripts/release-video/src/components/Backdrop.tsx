import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import { c } from "../theme";

const GRID = 48;

/**
 * The page canvas: near-white, a hairline grid on the same 48px rhythm the
 * pixel blocks use, and a violet glow that drifts with the scene.
 */
export const Backdrop: React.FC<{
  /** Horizontal position of the glow, 0-1 across the frame. */
  glowX?: number;
  glowY?: number;
  /** Glow strength, 0-1. */
  intensity?: number;
}> = ({ glowX = 0.5, glowY = 0.45, intensity = 1 }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // A slow drift keeps the grid from reading as a static texture: exactly one
  // cell over the whole video, so it never reads as scrolling.
  const drift = interpolate(frame, [0, durationInFrames], [0, GRID]);

  return (
    <AbsoluteFill style={{ backgroundColor: c.slate1 }}>
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${c.slate4} 1px, transparent 1px),
             linear-gradient(90deg, ${c.slate4} 1px, transparent 1px)`,
          backgroundSize: `${GRID}px ${GRID}px`,
          backgroundPosition: `${drift}px ${drift}px`,
          opacity: 0.55,
          maskImage:
            "radial-gradient(ellipse 78% 68% at 50% 46%, #000 32%, transparent 100%)",
        }}
      />

      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 46% 52% at ${glowX * 100}% ${
            glowY * 100
          }%, ${c.glow} 0%, rgba(235, 228, 255, 0) 68%)`,
          opacity: 0.9 * intensity,
        }}
      />

      {/* Vignette: keeps the eye centred and hides the grid's hard edge. */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 70% 70% at 50% 50%, transparent 55%, ${c.slate1} 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};
