import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

/**
 * Scene container. Cross-fades at the seams and adds a touch of scale so cuts
 * read as a push rather than a hard swap.
 */
export const Scene: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
  /** Frames of fade at each edge. */
  fadeIn?: number;
  fadeOut?: number;
  style?: React.CSSProperties;
}> = ({ durationInFrames, children, fadeIn = 9, fadeOut = 11, style }) => {
  const frame = useCurrentFrame();

  const clamp = {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  } as const;

  // The final scene holds instead of fading, so the tail keyframes are optional.
  const outAt = durationInFrames - fadeOut;
  const hasFadeOut = fadeOut > 0 && outAt > fadeIn;

  const range = hasFadeOut
    ? [0, fadeIn, outAt, durationInFrames]
    : [0, fadeIn];

  const opacity = interpolate(
    frame,
    range,
    hasFadeOut ? [0, 1, 1, 0] : [0, 1],
    clamp,
  );

  const scale = interpolate(
    frame,
    range,
    hasFadeOut ? [0.985, 1, 1, 1.012] : [0.985, 1],
    clamp,
  );

  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `scale(${scale})`,
        justifyContent: "center",
        alignItems: "center",
        ...style,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
