import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

import { PixelLogo } from "./PixelLogo";
import { c, font } from "../theme";

/**
 * Persistent overlay for the body scenes: a small wordmark lock-up and a
 * progress rule along the bottom edge. Hidden over the intro and outro, which
 * already carry the mark full size.
 */
export const Chrome: React.FC<{
  totalFrames: number;
  /** Frame the watermark starts fading in / out on. */
  showFrom: number;
  showUntil: number;
}> = ({ totalFrames, showFrom, showUntil }) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(
    frame,
    [showFrom, showFrom + 14, showUntil - 14, showUntil],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const progress = interpolate(frame, [0, totalFrames - 1], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: 96,
          bottom: 86,
          display: "flex",
          alignItems: "center",
          gap: 18,
          opacity: opacity * 0.5,
        }}
      >
        {/* Frame past the assembly window: this is a mark, not an animation. */}
        <PixelLogo cell={8} frame={999} gap={1} color={c.slate9} />
        <span
          style={{
            fontFamily: font.mono,
            fontSize: 19,
            fontWeight: 500,
            color: c.slate9,
            letterSpacing: "-0.01em",
          }}
        >
          0.9.8
        </span>
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 3,
          background: c.slate4,
        }}
      >
        <div
          style={{
            width: `${progress * 100}%`,
            height: "100%",
            background: c.violet9,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
