import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

import { PixelLogo } from "../components/PixelLogo";
import { Scene } from "../components/Scene";
import { Body, Reveal } from "../components/ui";
import { c, font } from "../theme";

export const Intro: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // The rule between wordmark and version draws itself once the mark lands.
  const rule = spring({
    frame: frame - 46,
    fps,
    config: { damping: 200, mass: 0.6, stiffness: 80 },
  });

  const version = spring({
    frame: frame - 52,
    fps,
    config: { damping: 13, mass: 0.7, stiffness: 120 },
  });

  return (
    <Scene durationInFrames={durationInFrames} fadeIn={5}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 54,
          marginBottom: 46,
        }}
      >
        <PixelLogo cell={30} frame={frame} duration={34} gap={2.5} />

        <div
          style={{
            width: 2,
            height: 128,
            background: c.slate6,
            transform: `scaleY(${interpolate(rule, [0, 1], [0, 1])})`,
            opacity: rule,
          }}
        />

        <div
          style={{
            fontFamily: font.sans,
            fontSize: 104,
            fontWeight: 600,
            letterSpacing: "-0.05em",
            color: c.violet9,
            opacity: interpolate(version, [0, 0.5], [0, 1], {
              extrapolateRight: "clamp",
            }),
            transform: `translateY(${interpolate(
              version,
              [0, 1],
              [26, 0],
            )}px) scale(${interpolate(version, [0, 1], [0.86, 1])})`,
          }}
        >
          0.9.8
        </div>
      </div>

      <Reveal frame={frame} delay={64} y={18}>
        <Body size={34} color={c.slate11}>
          Performant, customizable web apps in pure Python.
        </Body>
      </Reveal>
    </Scene>
  );
};
