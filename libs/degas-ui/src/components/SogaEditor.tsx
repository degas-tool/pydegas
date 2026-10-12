import Editor, {
  useMonaco,
  type BeforeMount,
  type OnChange,
} from "@monaco-editor/react";
import { useEffect } from "react";

const LANG = "soga";

function registerLanguage(monaco: Parameters<BeforeMount>[0]) {
  if (
    monaco.languages.getLanguages().find((l: { id: string }) => l.id === LANG)
  )
    return;

  monaco.languages.register({ id: LANG });

  monaco.languages.setMonarchTokensProvider(LANG, {
    keywords: [
      "for",
      "in",
      "range",
      "end",
      "if",
      "else",
      "observe",
      "skip",
      "prune",
      "array",
      "data",
    ],
    builtins: ["gauss", "gm", "uniform", "beta", "bern"],
    tokenizer: {
      root: [
        [/\/\*/, "comment", "@blockComment"],
        [/_[a-zA-Z]\w*/, "parameter"],
        [
          /[a-zA-Z_]\w*/,
          {
            cases: {
              "@keywords": "keyword",
              "@builtins": "type",
              "@default": "identifier",
            },
          },
        ],
        [/\d+\.?\d*/, "number"],
        [/[+\-*/<>=!]/, "operator"],
        [/[{}()[\]]/, "delimiter"],
        [/[,;]/, "delimiter"],
      ],
      blockComment: [
        [/[^/*]+/, "comment"],
        [/\*\//, "comment", "@pop"],
        [/[/*]/, "comment"],
      ],
    },
  });

  monaco.editor.defineTheme("soga-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "444444", fontStyle: "italic" },
      { token: "keyword", foreground: "6699cc" },
      { token: "type", foreground: "99c794" },
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

  monaco.editor.defineTheme("soga-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment", foreground: "aaaaaa", fontStyle: "italic" },
      { token: "keyword", foreground: "3a6fb5" },
      { token: "type", foreground: "3a8a60" },
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

type Props = {
  theme: "light" | "dark";
  value: string;
  onChange: OnChange;
};

export function SogaEditor({ theme, value, onChange }: Props) {
  const monaco = useMonaco();

  useEffect(() => {
    if (!monaco) return;
    monaco.editor.setTheme(theme === "dark" ? "soga-dark" : "soga-light");
  }, [monaco, theme]);

  return (
    <Editor
      height="100%"
      language={LANG}
      theme={theme === "dark" ? "soga-dark" : "soga-light"}
      value={value}
      onChange={onChange}
      beforeMount={registerLanguage}
      options={{
        fontSize: 13,
        lineHeight: 22,
        fontFamily: "Menlo, Consolas, 'Courier New', monospace",
        fontLigatures: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderLineHighlight: "line",
        padding: { top: 16, bottom: 16 },
        tabSize: 4,
        wordWrap: "on",
        smoothScrolling: true,
      }}
    />
  );
}
