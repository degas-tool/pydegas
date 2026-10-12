import { useEffect, useRef } from "react";

export type PlotlyTrace = Record<string, unknown>;
export type PlotlyLayout = Record<string, unknown>;

interface PlotlyGlobal {
  react: (
    root: HTMLElement,
    data: PlotlyTrace[],
    layout: PlotlyLayout,
    config: Record<string, unknown>,
  ) => Promise<unknown>;
  purge: (root: HTMLElement) => void;
  Plots: { resize: (root: HTMLElement) => Promise<unknown> };
}

declare global {
  interface Window {
    Plotly?: PlotlyGlobal;
  }
}

const CONFIG = { displayModeBar: false };

interface Props {
  data: PlotlyTrace[];
  layout: PlotlyLayout;
  visible: boolean;
}

export function PlotlyChart({ data, layout, visible }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    const plotly = window.Plotly;
    if (!visible || !el || !plotly) return;
    plotly
      .react(el, data, { ...layout, autosize: true }, CONFIG)
      .catch(console.error);
  }, [data, layout, visible]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width === 0 || height === 0) return;
      window.Plotly?.Plots.resize(el).catch(() => undefined);
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
      window.Plotly?.purge(el);
    };
  }, []);

  return (
    <div
      ref={ref}
      style={{
        width: "100%",
        height: "100%",
        display: visible ? "block" : "none",
      }}
    />
  );
}
