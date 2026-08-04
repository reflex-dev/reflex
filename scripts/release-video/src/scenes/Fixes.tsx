import React from "react";
import { useCurrentFrame } from "remotion";

import { Scene } from "../components/Scene";
import { Check, Eyebrow, Headline, Reveal } from "../components/ui";
import { c, font } from "../theme";

// Two independent columns: a wrap on one side must not punch a gap in the other.
const COLUMNS = [
  [
    "Nested stylesheets load on Windows",
    "No more frozen-lockfile failures on upgrade",
    "Timezone-aware datetime Vars compare by instant",
    "reflex component build works on Python 3.10 & 3.11",
  ],
  [
    "Production hydration fixed on Windows",
    "reflex rename survives non-UTF-8 locales",
    "Hot reload survives edits to unloaded routes",
    "Clean event-processor shutdown on Python 3.13+",
  ],
];

export const Fixes: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  return (
    <Scene durationInFrames={durationInFrames}>
      <div style={{ width: 1460 }}>
        <Reveal frame={frame} delay={0} y={14}>
          <Eyebrow color={c.violet11}>Fixed</Eyebrow>
        </Reveal>

        <Reveal frame={frame} delay={5} y={20} style={{ marginTop: 16 }}>
          <Headline size={70}>Rough edges, sanded.</Headline>
        </Reveal>

        <div style={{ display: "flex", gap: 56, marginTop: 46 }}>
          {COLUMNS.map((column, col) => (
            <div
              key={col}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                gap: 24,
              }}
            >
              {column.map((fix, row) => (
                <Reveal
                  key={fix}
                  frame={frame}
                  // Interleave the stagger so the columns fill together.
                  delay={14 + (row * 2 + col) * 5}
                  y={16}
                  x={-10}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 16,
                      fontFamily: font.sans,
                      fontSize: 27,
                      lineHeight: 1.3,
                      color: c.slate12,
                      letterSpacing: "-0.014em",
                    }}
                  >
                    <Check size={30} />
                    <span>{fix}</span>
                  </div>
                </Reveal>
              ))}
            </div>
          ))}
        </div>
      </div>
    </Scene>
  );
};
