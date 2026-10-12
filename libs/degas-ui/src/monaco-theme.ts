import type { BeforeMount } from "@monaco-editor/react";

type Monaco = Parameters<BeforeMount>[0];

export const EDITOR_THEME = {
  dark: "degas-dark",
  light: "degas-light",
} as const;

export function defineEditorThemes(monaco: Monaco): void {
  monaco.editor.defineTheme(EDITOR_THEME.dark, {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "444444", fontStyle: "italic" },
      { token: "keyword", foreground: "6699cc" },
      { token: "keyword.degas-loss", foreground: "6699cc", fontStyle: "bold" },
      { token: "type.soga", foreground: "99c794" },
      { token: "type.degas-loss", foreground: "c594c5" },
      { token: "builtin", foreground: "99c794" },
      { token: "accessor", foreground: "fac863" },
      { token: "number", foreground: "f99157" },
      { token: "operator", foreground: "c594c5" },
      { token: "parameter", foreground: "fac863", fontStyle: "bold" },
      { token: "identifier", foreground: "cdd3de" },
      { token: "delimiter", foreground: "3a3a3a" },
    ],
    colors: {
      "editor.background": "#111111",
      "editor.foreground": "#cdd3de",
      "editorLineNumber.foreground": "#2a2a2a",
      "editorLineNumber.activeForeground": "#555555",
      "editor.lineHighlightBackground": "#181818",
      "editorCursor.foreground": "#6699cc",
      "editor.selectionBackground": "#1e3a5f",
    },
  });

  monaco.editor.defineTheme(EDITOR_THEME.light, {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment", foreground: "aaaaaa", fontStyle: "italic" },
      { token: "keyword", foreground: "3a6fb5" },
      { token: "keyword.degas-loss", foreground: "3a6fb5", fontStyle: "bold" },
      { token: "type.soga", foreground: "3a8a60" },
      { token: "type.degas-loss", foreground: "8b4fa8" },
      { token: "builtin", foreground: "3a8a60" },
      { token: "accessor", foreground: "b07d00" },
      { token: "number", foreground: "c2621a" },
      { token: "operator", foreground: "8b4fa8" },
      { token: "parameter", foreground: "b07d00", fontStyle: "bold" },
      { token: "identifier", foreground: "2a2a2a" },
      { token: "delimiter", foreground: "bbbbbb" },
    ],
    colors: {
      "editor.background": "#ffffff",
      "editor.foreground": "#2a2a2a",
      "editorLineNumber.foreground": "#dddddd",
      "editorLineNumber.activeForeground": "#aaaaaa",
      "editor.lineHighlightBackground": "#f7f5f2",
      "editorCursor.foreground": "#3a6fb5",
      "editor.selectionBackground": "#d0e4f7",
    },
  });
}
