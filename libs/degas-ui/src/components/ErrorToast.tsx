import React from "react";

interface Props {
  message: string | null;
  onDismiss: () => void;
}

export function ErrorToast({ message, onDismiss }: Props): React.ReactElement | null {
  if (message === null) {
    return null;
  }

  const containerStyle: React.CSSProperties = {
    position: "fixed",
    bottom: 24,
    left: "50%",
    transform: "translateX(-50%)",
    zIndex: 200,
    background: "#1e1010",
    border: "1px solid #ec5f67",
    borderRadius: 8,
    padding: "10px 16px",
    display: "flex",
    alignItems: "center",
    gap: 12,
    maxWidth: 480,
    boxShadow: "0 4px 24px #0008",
  };

  const messageStyle: React.CSSProperties = {
    color: "#ec5f67",
    fontSize: 12,
    fontFamily: "inherit",
  };

  const dismissStyle: React.CSSProperties = {
    background: "none",
    border: "none",
    color: "#ec5f6799",
    fontSize: 16,
    cursor: "pointer",
    padding: 0,
    lineHeight: 1,
  };

  return (
    <div style={containerStyle}>
      <span style={messageStyle}>{message}</span>
      <button type="button" style={dismissStyle} onClick={onDismiss}>
        ×
      </button>
    </div>
  );
}
