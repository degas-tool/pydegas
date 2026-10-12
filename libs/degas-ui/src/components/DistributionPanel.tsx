import { useMemo } from "react";
import type { StepOut } from "../types";
import {
  PlotlyChart,
  type PlotlyLayout,
  type PlotlyTrace,
} from "./PlotlyChart";

const COLORS = [
  "#6699cc",
  "#99c794",
  "#c594c5",
  "#fac863",
  "#ec5f67",
  "#5fb3b3",
];

interface Props {
  steps: StepOut[];
  theme: "light" | "dark";
}

export function DistributionPanel({ steps, theme }: Props) {
  const dark = theme === "dark";
  const bg = dark ? "#0a0a0a" : "#fafaf9";
  const fg = dark ? "#e8e6e0" : "#1a1a1a";
  const grid = dark ? "#1e1e1e" : "#e2ddd8";

  const isEmpty = steps.length === 0;

  const data = useMemo<PlotlyTrace[]>(() => {
    const paramNames = steps.length > 0 ? Object.keys(steps[0].params) : [];
    const xs = steps.map((s) => s.step);
    const safeNum = (v: number) => (Number.isFinite(v) ? v : null);

    return paramNames.map((name, i) => ({
      x: xs,
      y: steps.map((s) => safeNum(s.params[name] ?? NaN)),
      name: `_${name}`,
      type: "scatter",
      mode: "lines",
      line: { color: COLORS[i % COLORS.length], width: 2 },
    }));
  }, [steps]);

  const layout = useMemo<PlotlyLayout>(
    () => ({
      paper_bgcolor: bg,
      plot_bgcolor: bg,
      font: {
        color: fg,
        family: "Menlo, Consolas, 'Courier New', monospace",
        size: 11,
      },
      margin: { t: 16, r: 60, b: 48, l: 60 },
      xaxis: {
        title: { text: "step", font: { size: 11 } },
        gridcolor: grid,
        zerolinecolor: grid,
        tickfont: { size: 10 },
      },
      yaxis: {
        side: "right",
        gridcolor: grid,
        zerolinecolor: grid,
        tickfont: { size: 10 },
      },
      yaxis2: {
        overlaying: "y",
        side: "left",
        matches: "y",
        showgrid: false,
        zeroline: false,
        tickfont: { size: 10 },
      },
      legend: {
        bgcolor: "transparent",
        font: { size: 10 },
        x: 0.01,
        y: 0.99,
        xanchor: "left",
        yanchor: "top",
      },
      showlegend: true,
    }),
    [bg, fg, grid],
  );

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          padding: "8px 14px 0",
          fontSize: 11,
          color: "var(--text-muted)",
        }}
      >
        parameter trajectory
      </div>
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: isEmpty ? "flex" : "none",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-muted)",
            fontSize: 12,
            letterSpacing: "0.08em",
          }}
        >
          run optimization to see parameter trajectory
        </div>
        <PlotlyChart data={data} layout={layout} visible={!isEmpty} />
      </div>
    </div>
  );
}
