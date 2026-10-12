import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label?: string;
}

interface State {
  error: Error | null;
}

export class PanelErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[PanelErrorBoundary]", this.props.label ?? "panel", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (error) {
      return (
        <div
          style={{
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
            gap: 8,
            padding: 16,
            textAlign: "center",
          }}
        >
          <span style={{ fontSize: 11, fontWeight: 600, color: "#ec5f67" }}>
            {this.props.label ?? "Panel"} crashed
          </span>
          <span
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              maxWidth: 300,
              wordBreak: "break-word",
              fontFamily: "Menlo, Consolas, 'Courier New', monospace",
            }}
          >
            {error.message}
          </span>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            style={{
              marginTop: 4,
              padding: "3px 10px",
              borderRadius: 6,
              border: "1px solid #ec5f6766",
              background: "#ec5f6711",
              color: "#ec5f67",
              fontSize: 11,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
