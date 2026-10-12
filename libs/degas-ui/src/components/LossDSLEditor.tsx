import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";
import { validateLossSource } from "../api";
import { defineEditorThemes, EDITOR_THEME } from "../monaco-theme";
import type { LossParamInfo } from "../types";

const LANG = "degas-loss";

const registerLanguage: BeforeMount = (monaco) => {
  defineEditorThemes(monaco);
  if (
    monaco.languages.getLanguages().find((l: { id: string }) => l.id === LANG)
  )
    return;

  monaco.languages.register({ id: LANG });

  monaco.languages.setMonarchTokensProvider(LANG, {
    keywords: ["loss"],
    types: ["dist", "traj_set", "index_list", "scalar", "int"],
    builtins: [
      "sum",
      "mean_agg",
      "max",
      "min",
      "log",
      "exp",
      "abs",
      "sqrt",
      "range",
      "ones",
    ],
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
};

type Props = {
  theme: "light" | "dark";
  value: string;
  onChange: (value: string) => void;
  onValidate: (params: LossParamInfo[], errors: string[]) => void;
  readOnly?: boolean;
};

export function LossDSLEditor({
  theme,
  value,
  onChange,
  onValidate,
  readOnly = false,
}: Props) {
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const [editorReady, setEditorReady] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onValidateRef = useRef(onValidate);
  useEffect(() => {
    onValidateRef.current = onValidate;
  });

  useEffect(() => {
    const monaco = monacoRef.current;
    if (readOnly) {
      if (editorRef.current && monaco) {
        const model = editorRef.current.getModel();
        if (model) monaco.editor.setModelMarkers(model, "degas-loss", []);
      }
      return;
    }
    let cancelled = false;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const result = await validateLossSource(value);
        if (cancelled) return;
        onValidateRef.current(result.params, result.errors);

        if (editorRef.current && monaco) {
          const model = editorRef.current.getModel();
          if (model) {
            const markers = result.errors.flatMap((msg) => {
              const m = msg.match(/line (\d+):(\d+) (.+)/);
              if (!m) return [];
              const line = parseInt(m[1], 10);
              const col = parseInt(m[2], 10) + 1;
              return [
                {
                  severity: monaco.MarkerSeverity.Error,
                  startLineNumber: line,
                  startColumn: col,
                  endLineNumber: line,
                  endColumn: col + 10,
                  message: m[3],
                  source: "degas-loss",
                },
              ];
            });
            monaco.editor.setModelMarkers(model, "degas-loss", markers);
          }
        }
      } catch {
        // network error - leave markers as-is
      }
    }, 400);
    return () => {
      cancelled = true;
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [value, readOnly, editorReady]);

  function handleChange(val: string | undefined) {
    if (readOnly) return;
    onChange(val ?? "");
  }

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    setEditorReady(true);
  };

  return (
    <Editor
      height="100%"
      language={LANG}
      theme={EDITOR_THEME[theme]}
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
