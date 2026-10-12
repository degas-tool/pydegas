import { useEffect, useMemo, useRef, useState } from "react";
import type { RunOutcome, RunStatus, StepOut } from "../types";

// Badge label + color per terminal outcome.
const OUTCOME_BADGE: Record<RunOutcome, { label: string; color: string }> = {
  converged: { label: "converged", color: "#99c794" },
  not_converged: { label: "not converged", color: "#ec5f67" },
  stopped: { label: "stopped", color: "#fac863" },
  run_timeout: { label: "timed out", color: "#fac863" },
};

const COLORS = [
  "#6699cc",
  "#99c794",
  "#c594c5",
  "#fac863",
  "#ec5f67",
  "#5fb3b3",
];

function traceColor(index: number) {
  return COLORS[index % COLORS.length];
}

interface Props {
  steps: StepOut[];
  status: RunStatus;
  error: string | null;
  outcome: RunOutcome | null;
  slowStep: boolean;
  theme: "light" | "dark";
  canDownload: boolean;
  onDownload: () => void;
}

export function ResultsPanel({ steps, status, error, outcome, slowStep, theme, canDownload, onDownload }: Props) {
  const dark = theme === "dark";
  const bg = dark ? "#0a0a0a" : "#fafaf9";
  const fg = dark ? "#e8e6e0" : "#1a1a1a";
  const grid = dark ? "#1e1e1e" : "#e2ddd8";

  const paramNames = useMemo(
    () => (steps.length > 0 ? Object.keys(steps[0].params) : []),
    [steps],
  );
  const paramKey = paramNames.join(",");

  // 'hidden' is the inverse of visible — everything is shown by default.
  // Reset on new run (new paramKey) using conditional setState during render.
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [lastParamKey, setLastParamKey] = useState("");
  if (paramKey !== lastParamKey) {
    setLastParamKey(paramKey);
    setHidden(new Set());
  }

  function toggle(key: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const isVisible = (key: string) => !hidden.has(key);

  const isEmpty = steps.length === 0;
  const finalParams = steps.length > 0 ? steps[steps.length - 1].params : null;
  const plotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isEmpty || !plotRef.current) return;

    const xs = steps.map((s) => s.step);

    const safeNum = (v: number) => (Number.isFinite(v) ? v : null);

    const lossTrace = {
      x: xs,
      y: steps.map((s) => safeNum(s.loss)),
      name: "Loss",
      type: "scatter",
      mode: "lines",
      yaxis: "y",
      line: { color: "#f99157", width: 2 },
      visible: isVisible("loss") ? true : "legendonly",
    };

    const paramTraces = paramNames.map((name, i) => ({
      x: xs,
      y: steps.map((s) => safeNum(s.params[name] ?? NaN)),
      name,
      type: "scatter",
      mode: "lines",
      yaxis: "y2",
      line: { color: traceColor(i), width: 2 },
      visible: isVisible(name) ? true : "legendonly",
    }));

    const layout = {
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
        title: { text: "loss", font: { size: 11 } },
        gridcolor: grid,
        zerolinecolor: grid,
        tickfont: { size: 10 },
        side: "left",
      },
      yaxis2: {
        title: { text: "params", font: { size: 11 } },
        gridcolor: "transparent",
        zerolinecolor: "transparent",
        tickfont: { size: 10 },
        overlaying: "y",
        side: "right",
      },
      legend: {
        bgcolor: "transparent",
        font: { size: 10 },
        x: 0.01,
        y: 0.99,
        xanchor: "left",
        yanchor: "top",
      },
      showlegend: false,
    };

    const config = { displayModeBar: false, responsive: true };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Plotly = (window as any).Plotly;
    if (Plotly && plotRef.current) {
      Plotly.react(
        plotRef.current,
        [lossTrace, ...paramTraces],
        layout,
        config,
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [steps, hidden, theme]);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "10px 14px 0",
          flexWrap: "wrap",
        }}
      >
        <TogglePill
          label="Loss"
          color="#f99157"
          active={isVisible("loss")}
          onClick={() => toggle("loss")}
        />
        {paramNames.map((name, i) => (
          <TogglePill
            key={name}
            label={`_${name}`}
            color={traceColor(i)}
            active={isVisible(name)}
            onClick={() => toggle(name)}
          />
        ))}

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          {status === "running" && (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              step {steps.length > 0 ? steps[steps.length - 1].step + 1 : "…"}
            </span>
          )}
          {status === "done" && steps.length > 0 && (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {steps.length} steps
            </span>
          )}
          {outcome !== null && status === "done" && (
            <span
              style={{
                fontSize: 10,
                padding: "2px 7px",
                borderRadius: 20,
                background: `${OUTCOME_BADGE[outcome].color}22`,
                border: `1px solid ${OUTCOME_BADGE[outcome].color}`,
                color: OUTCOME_BADGE[outcome].color,
              }}
            >
              {OUTCOME_BADGE[outcome].label}
            </span>
          )}
          {status === "error" && (
            <span
              style={{
                fontSize: 10,
                padding: "2px 7px",
                borderRadius: 20,
                background: "#ec5f6722",
                border: "1px solid #ec5f67",
                color: "#ec5f67",
              }}
            >
              failed
            </span>
          )}
          <button
            type="button"
            onClick={onDownload}
            disabled={!canDownload}
            title="Download run data (JSON)"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              padding: "3px 8px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "transparent",
              color: canDownload ? "var(--text-primary)" : "var(--text-muted)",
              fontSize: 11,
              cursor: canDownload ? "pointer" : "not-allowed",
              opacity: canDownload ? 1 : 0.5,
              fontFamily: "inherit",
            }}
          >
            {/* Inline download glyph — no icon-library dependency. */}
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            data
          </button>
        </div>
      </div>

      {status === "done" && finalParams && Object.keys(finalParams).length > 0 && (
        <div
          style={{
            display: "flex",
            gap: 16,
            padding: "6px 14px",
            borderTop: "1px solid var(--border)",
            flexWrap: "wrap",
          }}
        >
          {Object.entries(finalParams).map(([name, val]) => (
            <span key={name} style={{ fontSize: 11, fontFamily: "inherit" }}>
              <span style={{ color: "var(--text-muted)" }}>_{name} = </span>
              <span style={{ color: "#f99157" }}>{val.toFixed(4)}</span>
            </span>
          ))}
        </div>
      )}

      {slowStep && status === "running" && (
        <div
          style={{
            padding: "6px 14px",
            background: "#fac86312",
            borderTop: "1px solid #fac86344",
            borderBottom: "1px solid #fac86344",
            color: "#fac863",
            fontSize: 11,
            flexShrink: 0,
          }}
        >
          This step is taking longer than usual; consider checking your loss arguments and learning rate, or stop the optimization manually.
        </div>
      )}

      {error !== null && (
        <div
          style={{
            padding: "5px 14px",
            background: "#ec5f6712",
            borderTop: "1px solid #ec5f6744",
            borderBottom: "1px solid #ec5f6744",
            color: "#ec5f67",
            fontSize: 11,
            fontFamily: "Menlo, Consolas, 'Courier New', monospace",
            flexShrink: 0,
            wordBreak: "break-word",
          }}
        >
          {error}
        </div>
      )}

      {/* Plotly div stays mounted to keep the ref alive */}
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
          run optimization to see results
        </div>
        <div
          ref={plotRef}
          style={{
            width: "100%",
            height: "100%",
            display: isEmpty ? "none" : "block",
          }}
        />
      </div>
    </div>
  );
}

function TogglePill({
  label,
  color,
  active,
  onClick,
}: {
  label: string;
  color: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 8px",
        borderRadius: 20,
        border: `1px solid ${active ? color : "var(--border)"}`,
        background: active ? `${color}22` : "transparent",
        color: active ? color : "var(--text-muted)",
        fontSize: 11,
        cursor: "pointer",
        fontFamily: "inherit",
        transition: "all 0.15s",
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: active ? color : "var(--text-muted)",
          flexShrink: 0,
        }}
      />
      {label}
    </button>
  );
}
