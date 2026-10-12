import { useEffect, useRef, useState } from "react";
import { deleteSession, getSessions, patchSession } from "../api";
import { getOwnerToken, removeOwnerToken } from "../session-storage";
import type { SessionSummary } from "../types";

function asUTC(iso: string): Date {
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
}

function timeAgo(iso: string): string {
  const secs = Math.floor((Date.now() - asUTC(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function StatusDot({ status, outcome }: { status: string; outcome: string | null }) {
  let color = "#888";
  if (status === "running") color = "#6699cc";
  else if (status === "done" && outcome === "converged") color = "#99c794";
  else if (status === "done") color = "#fac863";
  else if (status === "error") color = "#ec5f67";

  return (
    <span
      style={{
        display: "inline-block",
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
        marginTop: 1,
      }}
    />
  );
}

interface Props {
  open: boolean;
  currentSessionId: string | null;
  onClose: () => void;
  onSelectSession: (id: string) => void;
}

export function HistoryPanel({
  open,
  currentSessionId,
  onClose,
  onSelectSession,
}: Props) {
  const [summaries, setSummaries] = useState<SessionSummary[] | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    getSessions()
      .then(setSummaries)
      .catch(() => setSummaries([]));
  }, [open]);

  useEffect(() => {
    if (editingId && inputRef.current) inputRef.current.focus();
  }, [editingId]);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open, onClose]);

  async function handleRename(id: string) {
    const trimmed = editValue.trim();
    setEditingId(null);
    if (!trimmed) return;
    const token = getOwnerToken(id);
    if (!token) return;
    try {
      await patchSession(id, { name: trimmed }, token);
      setSummaries((prev) => prev?.map((s) => s.id === id ? { ...s, name: trimmed } : s) ?? null);
    } catch { /* empty */ }
  }

  async function handleDelete(id: string) {
    const token = getOwnerToken(id);
    if (!token) return;
    try {
      await deleteSession(id, token);
    } catch { /* empty */ }
    removeOwnerToken(id);
    setSummaries((prev) => prev?.filter((s) => s.id !== id) ?? null);
    if (id === currentSessionId) {
      const url = new URL(window.location.href);
      url.searchParams.delete("s");
      window.history.pushState({}, "", url);
    }
  }

  const iconBtn: React.CSSProperties = {
    background: "transparent",
    border: "none",
    cursor: "pointer",
    color: "var(--text-muted)",
    fontSize: 12,
    lineHeight: 1,
    padding: "2px 4px",
    borderRadius: 4,
    flexShrink: 0,
  };

  return (
    <>
      {open && <div style={{ position: "fixed", inset: 0, zIndex: 199 }} />}

      <div
        ref={panelRef}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          bottom: 0,
          width: 280,
          zIndex: 200,
          background: "var(--bg-surface)",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          transform: open ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 0.2s ease",
          boxShadow: open ? "4px 0 24px #0004" : "none",
        }}
      >
        {/* header */}
        <div
          style={{
            padding: "14px 16px 10px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
            history
          </span>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
              fontSize: 16,
              lineHeight: 1,
              padding: "0 2px",
            }}
          >
            ×
          </button>
        </div>

        {/* session list */}
        <div style={{ flex: 1, overflowY: "auto", padding: "6px 0" }}>
          {summaries === null && (
            <div style={{ padding: "16px", fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
              loading…
            </div>
          )}
          {summaries !== null && summaries.length === 0 && (
            <div style={{ padding: "16px", fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
              no sessions yet
            </div>
          )}
          {summaries !== null && summaries.map((s) => {
            const active = s.id === currentSessionId;
            const owned = !!getOwnerToken(s.id);
            const hovered = hoveredId === s.id;
            const displayName = s.name ?? s.loss_name;

            return (
              <div
                key={s.id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  padding: "8px 14px",
                  background: active ? "var(--btn-hover)" : hovered ? "var(--btn-bg)" : "transparent",
                  borderLeft: active ? "2px solid #6699cc" : "2px solid transparent",
                  transition: "background 0.1s",
                  cursor: editingId === s.id ? "default" : "pointer",
                }}
                onMouseEnter={() => setHoveredId(s.id)}
                onMouseLeave={() => setHoveredId(null)}
                onClick={() => {
                  if (editingId === s.id) return;
                  onSelectSession(s.id);
                  onClose();
                }}
              >
                <StatusDot status={s.status} outcome={s.outcome} />

                <div style={{ flex: 1, minWidth: 0 }}>
                  {editingId === s.id ? (
                    <input
                      ref={inputRef}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRename(s.id);
                        if (e.key === "Escape") setEditingId(null);
                        e.stopPropagation();
                      }}
                      onBlur={() => handleRename(s.id)}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        width: "100%",
                        fontSize: 12,
                        background: "var(--bg-page)",
                        border: "1px solid var(--btn-border)",
                        borderRadius: 4,
                        color: "var(--text-primary)",
                        padding: "2px 4px",
                        fontFamily: "inherit",
                        outline: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  ) : (
                    <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: active ? 600 : 400 }}>
                      {displayName}
                      {s.loss_mode === "custom" && (
                        <span style={{ marginLeft: 5, fontSize: 10, color: "#6699cc" }}>custom</span>
                      )}
                      {s.name && (
                        <span style={{ marginLeft: 5, fontSize: 10, color: "var(--text-muted)" }}>{s.loss_name}</span>
                      )}
                    </div>
                  )}
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2, display: "flex", gap: 6 }}>
                    <span style={{ fontFamily: "monospace" }}>{s.id}</span>
                    <span>{timeAgo(s.created_at)}</span>
                  </div>
                </div>

                {owned && hovered && editingId !== s.id && (
                  <div style={{ display: "flex", gap: 2, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      title="Rename"
                      style={iconBtn}
                      onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                      onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditValue(s.name ?? s.loss_name);
                        setEditingId(s.id);
                      }}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      title="Delete"
                      style={iconBtn}
                      onMouseEnter={(e) => (e.currentTarget.style.color = "#ec5f67")}
                      onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(s.id);
                      }}
                    >
                      ✕
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
