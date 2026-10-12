import Editor, { useMonaco, type BeforeMount, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";
import { validateLossSource } from "../api";
import type { LossParamInfo } from "../types";

const LANG = "degas-loss";

const registerLanguage: BeforeMount = (monaco) => {
  if (monaco.languages.getLanguages().find((l: { id: string }) => l.id === LANG))
    return;

  monaco.languages.register({ id: LANG });

  monaco.languages.setMonarchTokensProvider(LANG, {
    keywords: ["loss"],
    types: ["dist", "traj_set", "index_list", "scalar", "int"],
    builtins: ["sum", "mean_agg", "max", "min", "log", "exp", "abs", "sqrt", "range", "ones"],
    accessors: ["mean", "marg_pdf", "pdf", "var"],
    tokenizer: {
      root: [
        [/\/\/.*$/, "comment"],
        [/\/\*/, "comment", "@blockComment"],
        [
          /[a-zA-Z_]\w*/,
          {
            cases: {
              "@keywords": "keyword",
              "@types": "type",
              "@builtins": "builtin",
              "@accessors": "accessor",
              "@default": "identifier",
            },
          },
        ],
        [/\d+\.?\d*([eE][+-]?\d+)?/, "number"],
        [/[+\-*/<>=!^]/, "operator"],
        [/[{}()[\]]/, "delimiter"],
        [/[,;:.]/, "delimiter"],
      ],
      blockComment: [
        [/[^/*]+/, "comment"],
        [/\*\//, "comment", "@pop"],
        [/[/*]/, "comment"],
      ],
    },
  });

  monaco.editor.defineTheme("degas-loss-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "comment", foreground: "444444", fontStyle: "italic" },
      { token: "keyword", foreground: "6699cc", fontStyle: "bold" },
      { token: "type", foreground: "c594c5" },
      { token: "builtin", foreground: "99c794" },
      { token: "accessor", foreground: "fac863" },
      { token: "number", foreground: "f99157" },
      { token: "operator", foreground: "c594c5" },
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

  monaco.editor.defineTheme("degas-loss-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment", foreground: "aaaaaa", fontStyle: "italic" },
      { token: "keyword", foreground: "3a6fb5", fontStyle: "bold" },
      { token: "type", foreground: "8b4fa8" },
      { token: "builtin", foreground: "3a8a60" },
      { token: "accessor", foreground: "b07d00" },
      { token: "number", foreground: "c2621a" },
      { token: "operator", foreground: "8b4fa8" },
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
};

type Props = {
  theme: "light" | "dark";
  value: string;
  onChange: (value: string) => void;
  onValidate: (params: LossParamInfo[], errors: string[]) => void;
  readOnly?: boolean;
};

export function LossDSLEditor({ theme, value, onChange, onValidate, readOnly = false }: Props) {
  const monaco = useMonaco();
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!monaco) return;
    monaco.editor.setTheme(theme === "dark" ? "degas-loss-dark" : "degas-loss-light");
  }, [monaco, theme]);

  const onValidateRef = useRef(onValidate);
  useEffect(() => {
    onValidateRef.current = onValidate;
  });

  useEffect(() => {
    if (readOnly) {
      if (editorRef.current && monaco) {
        const model = editorRef.current.getModel();
        if (model) monaco.editor.setModelMarkers(model, "degas-loss", []);
      }
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const result = await validateLossSource(value);
        onValidateRef.current(result.params, result.errors);

        if (editorRef.current && monaco) {
          const model = editorRef.current.getModel();
          if (model) {
            const markers = result.errors.flatMap((msg) => {
              const m = msg.match(/line (\d+):(\d+) (.+)/);
              if (!m) return [];
              const line = parseInt(m[1], 10);
              const col = parseInt(m[2], 10) + 1;
              return [{
                severity: monaco.MarkerSeverity.Error,
                startLineNumber: line,
                startColumn: col,
                endLineNumber: line,
                endColumn: col + 10,
                message: m[3],
                source: "degas-loss",
              }];
            });
            monaco.editor.setModelMarkers(model, "degas-loss", markers);
          }
        }
      } catch {
        // network error - leave markers as-is
      }
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [value, readOnly, monaco]);

  function handleChange(val: string | undefined) {
    if (readOnly) return;
    onChange(val ?? "");
  }

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  return (
    <Editor
      height="100%"
      language={LANG}
      theme={theme === "dark" ? "degas-loss-dark" : "degas-loss-light"}
      value={value}
      onChange={handleChange}
      onMount={handleMount}
      beforeMount={registerLanguage}
      options={{
        readOnly,
        fontSize: 13,
        lineHeight: 22,
        fontFamily: "Menlo, Consolas, 'Courier New', monospace",
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderLineHighlight: "line",
        padding: { top: 12, bottom: 12 },
        tabSize: 4,
        wordWrap: "on",
        smoothScrolling: true,
        glyphMargin: false,
        folding: false,
        lineDecorationsWidth: 4,
      }}
    />
  );
}
