import { Sun, Moon } from "lucide-react";

type Props = { theme: "light" | "dark"; onToggle: () => void };

export function ThemeToggle({ theme, onToggle }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--btn-bg)",
        border: "1px solid var(--btn-border)",
        borderRadius: 8,
        padding: "6px 10px",
        cursor: "pointer",
        lineHeight: 1,
        color: "var(--text-primary)",
        transition: "background 0.15s",
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = "var(--btn-hover)")
      }
      onMouseLeave={(e) => (e.currentTarget.style.background = "var(--btn-bg)")}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
