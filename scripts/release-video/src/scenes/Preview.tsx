import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

import { Scene } from "../components/Scene";
import {
  Body,
  Chip,
  Cursor,
  Eyebrow,
  Headline,
  Reveal,
  Terminal,
  typed,
} from "../components/ui";
import { c, font } from "../theme";

const COMMAND = "reflex run --env preview";

const Out: React.FC<{ frame: number; delay: number; children: string }> = ({
  frame,
  delay,
  children,
}) => (
  <div
    style={{
      fontFamily: font.mono,
      fontSize: 27,
      color: c.slate11,
      marginTop: 14,
      opacity: interpolate(frame, [delay, delay + 8], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }),
    }}
  >
    <span style={{ color: c.jade8 }}>✓</span> {children}
  </div>
);

export const Preview: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  const typing = interpolate(frame, [26, 56], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <Scene durationInFrames={durationInFrames}>
      <div style={{ width: 1460 }}>
        <Reveal frame={frame} delay={0} y={14}>
          <Eyebrow color={c.violet11}>New run mode</Eyebrow>
        </Reveal>

        <Reveal frame={frame} delay={6} y={22} style={{ marginTop: 18 }}>
          <Headline size={76}>Hot reload, on a real build.</Headline>
        </Reveal>

        <Reveal frame={frame} delay={18} y={26} style={{ marginTop: 42 }}>
          <Terminal label="bash">
            <div
              style={{
                fontFamily: font.mono,
                fontSize: 30,
                color: c.slate12,
                letterSpacing: "-0.015em",
              }}
            >
              <span style={{ color: c.violet9, marginRight: 14 }}>$</span>
              {typed(COMMAND, typing)}
              {typing < 1 ? <Cursor frame={frame} /> : null}
            </div>

            <Out frame={frame} delay={62}>
              freshly built bundle, mounted into the backend
            </Out>
            <Out frame={frame} delay={72}>
              no Vite dev server &nbsp;·&nbsp; un-minified, readable output
            </Out>
          </Terminal>
        </Reveal>

        <div style={{ display: "flex", gap: 14, marginTop: 34 }}>
          {["VITE_MINIFY", "REFLEX_NO_AUTOPREFIXER", "VITE_SOURCEMAP"].map(
            (t, i) => (
              <Reveal key={t} frame={frame} delay={86 + i * 6} y={16}>
                <Chip variant="slate" size={23} mono>
                  {t}
                </Chip>
              </Reveal>
            ),
          )}
        </div>

        <Reveal frame={frame} delay={104} y={14} style={{ marginTop: 22 }}>
          <Body size={26} color={c.slate9}>
            Minification, autoprefixer and sourcemaps off by default — each
            overridable.
          </Body>
        </Reveal>
      </div>
    </Scene>
  );
};
