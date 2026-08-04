import React from "react";
import { useCurrentFrame } from "remotion";

import { Scene } from "../components/Scene";
import { Body, Eyebrow, Headline, Reveal } from "../components/ui";
import { c, font } from "../theme";

const BUMPS: [name: string, from: string, to: string, note?: string][] = [
  ["react", "19.2.6", "19.2.8"],
  ["react-router", "7.15.0", "7.18.2"],
  ["vite", "8.0.16", "8.2.0"],
  ["lucide-react", "1.14.0", "1.26.0", "+46 icons"],
  ["react-plotly.js", "2.6.0", "4.0.0"],
  ["shiki", "3.3.0", "4.3.1"],
  ["universal-cookie", "7.2.2", "8.1.2"],
  ["bun", "1.3.13", "1.3.14"],
];

export const Deps: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  return (
    <Scene durationInFrames={durationInFrames}>
      <div style={{ width: 1460 }}>
        <Reveal frame={frame} delay={0} y={14}>
          <Eyebrow color={c.violet11}>Under the hood</Eyebrow>
        </Reveal>

        <Reveal frame={frame} delay={5} y={20} style={{ marginTop: 16 }}>
          <Headline size={70}>Everything, up to date.</Headline>
        </Reveal>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            columnGap: 64,
            marginTop: 44,
          }}
        >
          {BUMPS.map(([name, from, to, note], i) => (
            <Reveal key={name} frame={frame} delay={14 + i * 5} y={16}>
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "space-between",
                  gap: 20,
                  padding: "17px 0",
                  borderBottom: `1px solid ${c.slate4}`,
                  fontFamily: font.mono,
                  fontSize: 27,
                  letterSpacing: "-0.02em",
                }}
              >
                <span style={{ color: c.slate12, fontWeight: 500 }}>
                  {name}
                  {note ? (
                    <span
                      style={{
                        fontFamily: font.sans,
                        fontSize: 21,
                        color: c.violet11,
                        marginLeft: 12,
                        fontWeight: 550,
                      }}
                    >
                      {note}
                    </span>
                  ) : null}
                </span>
                <span style={{ color: c.slate9, whiteSpace: "nowrap" }}>
                  {from}
                  <span style={{ margin: "0 12px", color: c.slate8 }}>→</span>
                  <span style={{ color: c.violet9, fontWeight: 550 }}>
                    {to}
                  </span>
                </span>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal frame={frame} delay={62} y={14} style={{ marginTop: 28 }}>
          <Body size={25} color={c.slate9}>
            Radix primitives bumped · postcss pinned to a patched release · CVEs
            cleared in aiohttp, cryptography and Pillow.
          </Body>
        </Reveal>
      </div>
    </Scene>
  );
};
